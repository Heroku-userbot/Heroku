"""Processes incoming events and dispatches them to appropriate handlers"""

# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import collections
import contextlib
import html
import inspect
import logging
from collections.abc import Callable
import re
import sys
import traceback

from herokutl import events
from herokutl.errors import FloodWaitError, RPCError
from herokutl.tl.types import Message

from . import main, security, utils
from ._event_filters import ALL_TAGS, find_failed_tag
from ._internal import tag_client_id, redact
from .database import Database
from .loader import Modules
from .tl_cache import CustomTelegramClient

logger = logging.getLogger(__name__)

MESSAGE_STATES_LIMIT = 1000

# Keys for layout switch
_LAYOUT_TRANSLATION = str.maketrans(
    'ёйцукенгшщзхъфывапролджэячсмитьбю.Ё"№;%:?ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭ/ЯЧСМИТЬБЮ,'
    + "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}ASDFGHJKL:\"|ZXCVBNM<>?",
    "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}ASDFGHJKL:\"|ZXCVBNM<>?"
    + 'ёйцукенгшщзхъфывапролджэячсмитьбю.Ё"№;%:?ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭ/ЯЧСМИТЬБЮ,',
)


def _decrement_ratelimit(delay, data, key, severity):
    def inner():
        data[key] = max(0, data[key] - severity)

    asyncio.get_event_loop().call_later(delay, inner)


class CommandDispatcher:
    def __init__(
        self,
        modules: Modules,
        client: CustomTelegramClient,
        db: Database,
    ):
        self._modules = modules
        self._client = client
        self.client = client
        self._db = db

        self._message_states: collections.OrderedDict[tuple[int, int], int] = (
            collections.OrderedDict()
        )

        self._ratelimit_storage_user = collections.defaultdict(int)
        self._ratelimit_storage_chat = collections.defaultdict(int)
        self._ratelimit_max_user = db.get(__name__, "ratelimit_max_user", 30)
        self._ratelimit_max_chat = db.get(__name__, "ratelimit_max_chat", 100)

        self.security = security.SecurityManager(client, db)

        self.check_security = self.security.check
        self._me = self._client.heroku_me.id
        self._cached_usernames = set()

        if self._client.heroku_me.username:
            self._cached_usernames.add(self._client.heroku_me.username.lower())

        if self._client.heroku_me.usernames:
            self._cached_usernames.update(
                u.username.lower()
                for u in getattr(self._client.heroku_me, "usernames", [])
            )

        self._cached_usernames.add(str(self._client.heroku_me.id))

        self.raw_handlers = []

    async def _handle_ratelimit(self, message: Message, func: Callable) -> bool:
        if await self.security.check(message, security.OWNER):
            return True

        func = getattr(func, "__func__", func)
        ret = True
        chat = self._ratelimit_storage_chat[message.chat_id]

        if message.sender_id:
            user = self._ratelimit_storage_user[message.sender_id]
            severity = (5 if getattr(func, "ratelimit", False) else 2) * (
                (user + chat) // 30 + 1
            )
            user += severity
            self._ratelimit_storage_user[message.sender_id] = user
            if user > self._ratelimit_max_user:
                ret = False
            else:
                self._ratelimit_storage_chat[message.chat_id] = chat

            _decrement_ratelimit(
                self._ratelimit_max_user * severity,
                self._ratelimit_storage_user,
                message.sender_id,
                severity,
            )
        else:
            severity = (5 if getattr(func, "ratelimit", False) else 2) * (
                chat // 15 + 1
            )

        chat += severity

        if chat > self._ratelimit_max_chat:
            ret = False

        _decrement_ratelimit(
            self._ratelimit_max_chat * severity,
            self._ratelimit_storage_chat,
            message.chat_id,
            severity,
        )

        return ret

    def _handle_grep(self, message: Message) -> Message:
        # Allow escaping grep with double stick
        if "||grep" in message.text or "|| grep" in message.text:
            message.raw_text = re.sub(r"\|\| ?grep", "| grep", message.raw_text)
            message.text = re.sub(r"\|\| ?grep", "| grep", message.text)
            message.message = re.sub(r"\|\| ?grep", "| grep", message.message)
            return message

        grep = False
        if not re.search(r".+\| ?grep (.+)", message.raw_text):
            return message

        grep = re.search(r".+\| ?grep (.+)", message.raw_text).group(1)
        message.text = re.sub(r"\| ?grep.+", "", message.text)
        message.raw_text = re.sub(r"\| ?grep.+", "", message.raw_text)
        message.message = re.sub(r"\| ?grep.+", "", message.message)

        ungrep = False

        if grep.startswith("-v "):
            ungrep = grep[3:]
            grep = False
        elif re.search(r"-v (.+)", grep):
            ungrep = re.search(r"-v (.+)", grep).group(1)
            grep = re.sub(r"(.+) -v .+", r"\g<1>", grep)

        grep = utils.escape_html(grep).strip() if grep else False
        ungrep = utils.escape_html(ungrep).strip() if ungrep else False

        old_edit = message.edit
        old_reply = message.reply
        old_respond = message.respond

        def process_text(text: str, *, rich: bool = False) -> str:
            nonlocal grep, ungrep
            res = []
            if rich:
                from .utils.grep import filter_rich_lines

                res = filter_rich_lines(
                    text,
                    html.unescape(grep) if grep else "",
                    html.unescape(ungrep) if ungrep else "",
                )

            for line in ([] if rich else text.split("\n")):
                if (
                    grep
                    and grep in utils.remove_html(line)
                    and (not ungrep or ungrep not in utils.remove_html(line))
                ):
                    res.append(
                        utils.remove_html(
                            line, escape=True, keep_emojis=True
                        ).replace(grep, f"<u>{grep}</u>")
                    )

                if not grep and ungrep and ungrep not in utils.remove_html(line):
                    res.append(
                        utils.remove_html(line, escape=True, keep_emojis=True)
                    )

            cont = (
                (f"contain <b>{grep}</b>" if grep else "")
                + (" and" if grep and ungrep else "")
                + ((" do not contain <b>" + ungrep + "</b>") if ungrep else "")
            )

            if res:
                text = f"<i>💬 Lines that {cont}:</i>\n" + "\n".join(res)
            else:
                text = f"💬 <i>No lines that {cont}</i>"

            return text

        async def my_edit(text, *args, **kwargs):
            text = process_text(text)
            kwargs["parse_mode"] = "HTML"
            return await old_edit(text, *args, **kwargs)

        async def my_reply(text, *args, **kwargs):
            text = process_text(text)
            kwargs["parse_mode"] = "HTML"
            return await old_reply(text, *args, **kwargs)

        async def my_respond(text, *args, **kwargs):
            text = process_text(text)
            kwargs["parse_mode"] = "HTML"
            kwargs.setdefault("reply_to", utils.get_topic(message))
            return await old_respond(text, *args, **kwargs)

        def process_rich(text: str) -> str:
            return "".join(
                f"<p>{line}</p>" for line in process_text(text, rich=True).split("\n")
            )

        message.edit = my_edit
        message.reply = my_reply
        message.respond = my_respond
        message._heroku_grep_rich = process_rich
        message.heroku_grepped = True

        return message

    def _keep_message_state(self) -> bool:
        settings = self._modules.lookup("settings")
        try:
            return bool(settings.config["keep_message_state"]) if settings else True
        except Exception:
            return True

    def _remember_state(self, message: Message) -> None:
        if not self._keep_message_state():
            self._message_states.clear()
            return

        key = (utils.get_chat_id(message), message.id)
        self._message_states[key] = hash(message.message)
        self._message_states.move_to_end(key)
        while len(self._message_states) > MESSAGE_STATES_LIMIT:
            self._message_states.popitem(last=False)

    def _is_reaction_update(
        self, event: events.NewMessage | events.MessageEdited
    ) -> bool:
        if not getattr(event, "reactions", False):
            return False

        if not self._keep_message_state():
            return True

        message = event.message
        state = self._message_states.get((utils.get_chat_id(message), message.id))
        if state is None:
            return True

        return state == hash(message.message)

    async def _handle_command(
        self,
        event: events.NewMessage | events.MessageDeleted,
        watcher: bool = False,
        selected: Callable | None = None,
    ) -> bool | tuple[Message, str, str, callable]:
        if not hasattr(event, "message") or not hasattr(event.message, "message"):
            return False

        initiator = getattr(event, "sender_id", 0)

        prefixes = utils.user_prefixes(
            self._db, main.__name__, initiator, self._client.tg_id
        )

        message = utils.censor(event.message)

        if not event.message.message:
            return False

        prefix, _switch_layout = utils.match_prefix(
            event.message.message, prefixes, _LAYOUT_TRANSLATION
        )
        if prefix is None:
            return False

        if (
            message.out
            and len(message.message) > len(prefix) * 2
            and message.message.startswith(prefix * 2)
            and any(s != prefix for s in message.message)
        ):
            possible_cmd_str = message.message[len(prefix) * 2 :]
            possible_cmd = (
                possible_cmd_str.strip().split(maxsplit=1)[0].split("@", maxsplit=1)[0]
            )

            _, func = self._modules.dispatch(possible_cmd)

            if func:
                if not watcher:
                    await message.edit(
                        message.message[len(prefix) :],
                        parse_mode=lambda s: (
                            s,
                            utils.relocate_entities(message.entities, -len(prefix))
                            or (),
                        ),
                    )
                return False

        _msg = (
            str.translate(message.message, _LAYOUT_TRANSLATION)
            if _switch_layout
            else message.message
        )

        reaction_update = selected is None and self._is_reaction_update(event)
        if not watcher:
            self._remember_state(event.message)

        if (
            event.sticker
            or event.dice
            or event.audio
            or event.via_bot_id
            or reaction_update
        ):
            return False

        blacklist_chats = self._db.get(main.__name__, "blacklist_chats", [])
        whitelist_chats = self._db.get(main.__name__, "whitelist_chats", [])
        whitelist_modules = self._db.get(main.__name__, "whitelist_modules", [])

        if (chat_id := utils.get_chat_id(message)) in blacklist_chats or (
            whitelist_chats and chat_id not in whitelist_chats
        ):
            return False

        if not _msg or len(_msg.strip()) == len(prefix):
            return False  # Message is just the prefix

        _cmd = _msg[len(prefix) :]
        command = _cmd.strip().split(maxsplit=1)[0]
        tag = command.split("@", maxsplit=1)

        if len(tag) == 2:
            if tag[1] == "me":
                if not message.out:
                    return False
            elif tag[1].lower() not in self._cached_usernames:
                return False
        elif (
            event.out
            or event.mentioned
            and event.message is not None
            and event.message.message is not None
            and not any(
                f"@{username}" in command.lower() for username in self._cached_usernames
            )
        ):
            pass
        elif (
            not event.is_private
            and not self._db.get(main.__name__, "no_nickname", False)
            and command not in self._db.get(main.__name__, "nonickcmds", [])
            and initiator not in self._db.get(main.__name__, "nonickusers", [])
            and not self.security.check_tsec(initiator, command)
            and utils.get_chat_id(event)
            not in self._db.get(main.__name__, "nonickchats", [])
        ):
            return False

        txt, handlers = self._modules.dispatch_candidates(tag[0])
        if selected is not None:
            handlers = [handler for handler in handlers if handler == selected]
        if not handlers:
            return False

        if message.is_channel and message.edit_date and not message.is_group:
            async for event in self._client.iter_admin_log(
                chat_id,
                limit=10,
                edit=True,
            ):
                if event.action.prev_message.id == message.id:
                    if event.user_id != self._client.tg_id:
                        logger.debug("Ignoring edit in channel")
                        return False

                    break

            return False

        _cmd_offset = len(prefix) + len(_cmd) - len(_cmd.strip())
        filter_event = type(event).__new__(type(event))
        filter_event.__dict__.update(event.__dict__)
        message = type(message).__new__(type(message))
        message.__dict__.update(event.message.__dict__)
        filter_event.__dict__["message"] = message
        if not watcher:
            new_text = prefix + txt + _msg[_cmd_offset + len(command) :]
            if new_text != message.message:
                offset = len(new_text) - len(message.message)
                if offset and message.entities:
                    entities = []
                    for entity in message.entities:
                        cloned = type(entity).__new__(type(entity))
                        cloned.__dict__.update(entity.__dict__)
                        entities.append(cloned)
                    message.entities = entities
                    utils.relocate_entities(message.entities, offset)
                message._text = None
                message.message = new_text

        available = []
        for handler in handlers:
            module_key = f"{chat_id}.{handler.__self__.__module__}"
            if module_key in blacklist_chats or (
                whitelist_modules and module_key not in whitelist_modules
            ):
                continue
            if not await self.security.check(
                message, handler, usernames=self._cached_usernames
            ):
                continue
            if await self._handle_tags(filter_event, handler):
                continue
            available.append(handler)
        if not available:
            return False
        if len(available) > 1 and not watcher:
            await self._choose_command(event, txt, available)
            return False
        func = available[-1]
        if not await self._handle_ratelimit(message, func):
            return False

        if (
            self._db.get(main.__name__, "grep", False)
            and not watcher
            and getattr(func.__self__.__class__, "__name__", "") != "TerminalMod"
        ):
            message = self._handle_grep(message)

        return message, prefix, txt, func

    def _conflict_text(self, key):
        return self._modules.translator.getkey(f"heroku.modules.command_conflicts.{key}")

    async def _choose_command(self, event, text, handlers):
        state = {"author": event.sender_id, "used": False}
        buttons = []
        for handler in handlers:
            module = handler.__self__
            name = module.strings["name"]
            buttons.append([{
                "text": name,
                "emoji_id": "5872695159631647090",
                "callback": self._run_chosen_command,
                "args": (event, handler, state),
            }])
        try:
            form = await self._modules.inline.form(
                text=self._conflict_text("choose").format(utils.escape_html(text)),
                message=utils.get_chat_id(event),
                reply_to=event.message.id,
                reply_markup=buttons,
                force_me=True,
                always_allow=[state["author"]],
                ttl=120,
            )
        except Exception:
            logger.exception("Unable to show command selection")
            form = False
        if not form:
            await utils.answer(event.message, self._conflict_text("failed"))

    async def _run_chosen_command(self, call, event, handler, state):
        if call.from_user.id != state["author"]:
            await call.answer(self._conflict_text("denied"), show_alert=True)
            return
        if state["used"]:
            await call.answer(self._conflict_text("used"), show_alert=True)
            return
        state["used"] = True
        result = await self._handle_command(event, selected=handler)
        if not result:
            await call.edit(self._conflict_text("unavailable"), reply_markup=[])
            return
        message, _, _, func = result
        try:
            await call.delete()
        except Exception:
            logger.exception("Unable to delete command selection")
        asyncio.ensure_future(self.future_dispatcher(func, message, self.command_exc))

    async def handle_raw(self, event: events.Raw):
        """Handle raw events."""
        for handler in self.raw_handlers:
            if isinstance(event, tuple(handler.updates)):
                try:
                    await handler(event)
                except Exception as e:
                    logger.exception("Error in raw handler %s: %s", handler.id, e)

    async def handle_command(
        self,
        event: events.NewMessage | events.MessageDeleted,
    ):
        """Handle all commands"""
        message = await self._handle_command(event)
        if not message:
            return

        message, _, _, func = message

        asyncio.ensure_future(
            self.future_dispatcher(
                func,
                message,
                self.command_exc,
            )
        )

    async def command_exc(self, _, message: Message):
        """Handle command exceptions."""
        exc = sys.exc_info()[1]
        logger.exception("Command failed", extra={"stack": inspect.stack()})
        if isinstance(exc, RPCError):
            if isinstance(exc, FloodWaitError):
                hours = exc.seconds // 3600
                minutes = (exc.seconds % 3600) // 60
                seconds = exc.seconds % 60
                hours = f"{hours} hours, " if hours else ""
                minutes = f"{minutes} minutes, " if minutes else ""
                seconds = f"{seconds} seconds" if seconds else ""
                fw_time = f"{hours}{minutes}{seconds}"
                txt = (
                    self._client.loader.lookup("translations")
                    .strings("fw_error")
                    .format(
                        utils.escape_html(message.message),
                        fw_time,
                        type(exc.request).__name__,
                    )
                )
            else:
                txt = (
                    "<tg-emoji emoji-id=5877477244938489129>🚫</tg-emoji> <b>Call"
                    f" </b><code>{utils.escape_html(message.message)}</code><b> failed"
                    " due to RPC (Telegram) error:</b>"
                    f" <code>{utils.escape_html(str(exc))}</code>"
                )
                txt = (
                    self._client.loader.lookup("translations")
                    .strings("rpc_error")
                    .format(
                        utils.escape_html(message.message),
                        utils.escape_html(str(exc)),
                    )
                )
        else:
            if not self._db.get(main.__name__, "inlinelogs", True):
                txt = (
                    "<tg-emoji emoji-id=5877477244938489129>🚫</tg-emoji><b> Call</b>"
                    f" <code>{utils.escape_html(message.message)}</code><b>"
                    " failed!</b>"
                )
            else:
                exc = "\n".join(traceback.format_exc().splitlines()[1:])
                txt = (
                    "<tg-emoji emoji-id=5877477244938489129>🚫</tg-emoji><b> Call</b>"
                    f" <code>{utils.escape_html(message.message)}</code><b>"
                    " failed!</b>\n\n<b>🧾 Logs:</b>\n<pre><code"
                    f' class="language-logs">{utils.escape_html(exc)}</code></pre>'
                )

        with contextlib.suppress(Exception):
            await (message.edit if message.out else message.reply)(redact(txt))

    async def watcher_exc(self, *_):
        logger.exception("Error running watcher", extra={"stack": inspect.stack()})

    async def _handle_tags(
        self,
        event: events.NewMessage | events.MessageDeleted,
        func: Callable,
    ) -> bool:
        return bool(await self._handle_tags_ext(event, func))

    async def _handle_tags_ext(
        self,
        event: events.NewMessage | events.MessageDeleted,
        func: Callable,
    ) -> str:
        """
        Handle tags.
        :param event: The event to handle.
        :param func: The function to handle.
        :return: The reason for the tag to fail.
        """
        m = event if isinstance(event, Message) else getattr(event, "message", event)

        if getattr(func, "no_commands", False) and await self._handle_command(
            event, watcher=True
        ):
            return "no_commands"
        if getattr(func, "only_commands", False) and not await self._handle_command(
            event, watcher=True
        ):
            return "only_commands"
        return find_failed_tag(
            m, func, mime_type=utils.mime_type, get_chat_id=utils.get_chat_id
        )

    async def handle_incoming(
        self,
        event: events.NewMessage | events.MessageDeleted,
    ):
        """Handle all incoming messages"""
        message = utils.censor(getattr(event, "message", event))

        blacklist_chats = self._db.get(main.__name__, "blacklist_chats", [])
        whitelist_chats = self._db.get(main.__name__, "whitelist_chats", [])
        whitelist_modules = self._db.get(main.__name__, "whitelist_modules", [])

        if (chat_id := utils.get_chat_id(message)) in blacklist_chats or (
            whitelist_chats and chat_id not in whitelist_chats
        ):
            logger.debug("Message is blocklisted")

        for func in self._modules.watchers:
            bl = self._db.get(main.__name__, "disabled_watchers", {})
            modname = str(func.__self__.__class__.strings["name"])

            if (
                modname in bl
                and isinstance(message, Message)
                and (
                    "*" in bl[modname]
                    or chat_id in bl[modname]
                    or "only_chats" in bl[modname]
                    and message.is_private
                    or "only_pm" in bl[modname]
                    and not message.is_private
                    or "out" in bl[modname]
                    and not message.out
                    or "in" in bl[modname]
                    and message.out
                )
                or f"{str(chat_id)}.{func.__self__.__module__}" in blacklist_chats
                or whitelist_modules
                and f"{str(chat_id)}.{func.__self__.__module__}"
                not in whitelist_modules
                or await self._handle_tags(event, func)
            ):
                continue

            # Avoid weird AttributeErrors in weird dochub modules by settings placeholder
            # of attributes
            for placeholder in {"text", "raw_text", "out"}:
                try:
                    if not hasattr(message, placeholder):
                        setattr(message, placeholder, "")
                except UnicodeDecodeError:
                    pass

            # Run watcher via ensure_future so in case user has a lot
            # of watchers with long actions, they can run simultaneously
            asyncio.ensure_future(
                self.future_dispatcher(
                    func,
                    message,
                    self.watcher_exc,
                )
            )

    @tag_client_id("client.tg_id")
    async def future_dispatcher(
        self,
        func: Callable,
        message: Message,
        exception_handler: Callable,
        *args,
    ):
        module = getattr(func, "__self__", None)
        if module is not None:
            if getattr(module, "_unloading", False):
                return
            if "_managed_tasks" not in module.__dict__:
                module._managed_tasks = set()
            module._managed_tasks.add(asyncio.current_task())
        try:
            await func(message)
        except Exception as e:
            await exception_handler(e, message, *args)
        finally:
            if module is not None:
                module._managed_tasks.discard(asyncio.current_task())
