"""Main logging part"""

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
import contextlib
import git
import inspect
import io
import linecache
import logging
import re
import sys
import traceback
import typing
import os
import functools
from collections.abc import Coroutine

import herokutl
from herokutl.errors import PersistentTimestampOutdatedError, TimeoutError
from herokutl.errors.rpcbaseerrors import ServerError, RPCError
from herokutl.errors.rpcerrorlist import FloodWaitError

from . import utils
from ._internal import (
    PrivateRotatingFileHandler,
    RedactingFormatter,
    redact,
    get_branch_name,
    get_client_id,
    check_commit_ancestor,
    reset_to_master,
    restore_worktree,
    restart,
)
from .tl_cache import CustomTelegramClient
from .types import BotInlineCall, Module, CoreOverwriteError

INTERNET_ERRORS = (
    TimeoutError,
    asyncio.exceptions.TimeoutError,
    ServerError,
    PersistentTimestampOutdatedError,
)
COMMON_ERRORS = (
    "InputPeerEmpty() does not have any entity type",
    "https://docs.telethon.dev/en/stable/concepts/entities.html",
)
old = linecache.getlines


def getlines(filename: str, module_globals=None) -> str:
    """
    Get the lines for a Python source file from the cache.
    Update the cache if it doesn't contain an entry for this file already.

    Modified version of original `linecache.getlines`, which returns the
    source code of Heroku modules properly.
    """

    try:
        if filename.startswith("<") and filename.endswith(">"):
            module = filename[1:-1].split(maxsplit=1)[-1]
            if (module.startswith("heroku.modules")) and module in sys.modules:
                return list(
                    map(
                        lambda x: f"{x}\n",
                        sys.modules[module].__loader__.get_source().splitlines(),
                    )
                )
    except Exception:
        logging.debug("Can't get lines for %s", filename, exc_info=True)

    return old(filename, module_globals)


linecache.getlines = getlines


def override_text(exception: Exception) -> str | None:
    """Returns error-specific description if available, else `None`"""

    match exception:
        case TimeoutError() | asyncio.exceptions.TimeoutError():
            return (
                "✈️ <b>You have problems with internet connection on your server.</b>"
            )

        case PersistentTimestampOutdatedError():
            return "✈️ <b>Telegram has problems with their datacenters.</b>"

        case CoreOverwriteError():
            return f"⚠️ {str(exception)}"

        case ServerError():
            return "📡 <b>Telegram servers are currently experiencing issues. Please try again later.</b>"

        case RPCError() if "TRANSLATION_TIMEOUT" in str(exception):
            return "🕓 <b>Telegram translation service timed out. Please try again later.</b>"

        case ModuleNotFoundError():
            return f"📦 {traceback.format_exception_only(type(exception), exception)[0].split(':')[1].strip()}"

        case FloodWaitError():
            return f"✋ <b>Bot is hitting limits and got {exception.seconds} seconds floodwait</b>"

        case _:
            return None


class HerokuException:
    def __init__(
        self,
        message: str,
        full_stack: str,
        sysinfo: None | (tuple[object, Exception, traceback.TracebackException]) = None,
    ):
        self.message = redact(message)
        self.full_stack = redact(full_stack)
        self.sysinfo = sysinfo
        self.debug_url = None

    @classmethod
    def from_exc_info(
        cls,
        exc_type: object,
        exc_value: Exception,
        tb: traceback.TracebackException,
        stack: list[inspect.FrameInfo] | None = None,
        comment: typing.Any | None = None,
    ) -> "HerokuException":
        def to_hashable(dictionary: dict) -> dict:
            dictionary = dictionary.copy()
            for key, value in dictionary.items():
                match value:
                    case dict():
                        dictionary[key] = to_hashable(value)
                    case _ if (
                        getattr(getattr(value, "__class__", None), "__name__", None)
                        == "Database"
                    ):
                        dictionary[key] = "<Database>"
                    case herokutl.TelegramClient() | CustomTelegramClient():
                        dictionary[key] = f"<{value.__class__.__name__}>"
                    case _:
                        try:
                            if len(str(value)) > 512:
                                dictionary[key] = f"{str(value)[:512]}..."
                            else:
                                dictionary[key] = str(value)
                        except Exception:
                            dictionary[key] = f"<{value.__class__.__name__}>"

            return dictionary

        full_traceback = redact(traceback.format_exc()).replace(
            "Traceback (most recent call last):\n",
            "",
        )

        line_regex = re.compile(r'  File "(.*?)", line ([0-9]+), in (.+)')

        def format_line(line: str) -> str:
            filename_, lineno_, name_ = line_regex.search(line).groups()

            return (
                f"👉 <code>{utils.escape_html(filename_)}:{lineno_}</code> <b>in</b>"
                f" <code>{utils.escape_html(name_)}</code>"
            )

        filename, lineno, name = next(
            (
                line_regex.search(line).groups()
                for line in reversed(full_traceback.splitlines())
                if line_regex.search(line)
            ),
            (None, None, None),
        )

        full_traceback = "\n".join(
            [
                (
                    format_line(line)
                    if line_regex.search(line)
                    else f"<code>{utils.escape_html(line)}</code>"
                )
                for line in full_traceback.splitlines()
            ]
        )

        caller = utils.find_caller(stack or inspect.stack())

        return cls(
            message=override_text(exc_value)
            or (
                "{}<b>🎯 Source:</b> <code>{}:{}</code><b> in"
                ' </b><code>{}</code>\n<b>❓ Error:</b> <pre><code class="language-python">{}</code></pre>{}'
            ).format(
                (
                    (
                        "🔮 <b>Cause: method </b><code>{}</code><b> of"
                        " </b><code>{}</code>\n\n"
                    ).format(
                        utils.escape_html(caller.__name__),
                        utils.escape_html(caller.__self__.__class__.__name__),
                    )
                    if (
                        caller
                        and hasattr(caller, "__self__")
                        and hasattr(caller, "__name__")
                    )
                    else ""
                ),
                utils.escape_html(filename),
                lineno,
                utils.escape_html(name),
                utils.escape_html(
                    redact("".join(
                        traceback.format_exception_only(exc_type, exc_value)
                    ).strip())
                ),
                (
                    "\n💭 <b>Message:</b>"
                    f" <code>{utils.escape_html(redact(comment))}</code>"
                    if comment
                    else ""
                ),
            ),
            full_stack=full_traceback,
            sysinfo=(exc_type, exc_value, tb),
        )


class TelegramLogsHandler(logging.Handler):
    """
    Keeps 2 buffers.
    One for dispatched messages.
    One for unused messages.
    When the length of the 2 together is 100
    truncate to make them 100 together,
    first trimming handled then unused.
    """

    def __init__(self, targets: list, capacity: int):
        super().__init__(0)
        self.buffer = []
        self.handledbuffer = []
        self._queue = []
        self._mods = {}
        self.tg_buff = []
        self.force_send_all = False
        self.tg_level = 20
        self.ignore_common = False
        self._client_options: dict[int, dict] = {}
        self.targets = targets
        self.capacity = capacity
        self.lvl = logging.NOTSET
        self._send_lock = asyncio.Lock()

    def install_tg_log(self, mod: Module):
        if getattr(self, "_task", False):
            self._task.cancel()

        self._mods[mod.tg_id] = mod

        self._task = asyncio.ensure_future(self.queue_poller())

    async def queue_poller(self):
        while True:
            with contextlib.suppress(Exception):
                await self.sender()
            await asyncio.sleep(3)

    def setLevel(self, level: int):
        self.lvl = level

    def set_client_options(
        self,
        client_id: int,
        *,
        force_send_all: bool | None = None,
        tg_level: int | None = None,
        ignore_common: bool | None = None,
    ):
        """Override logging options for a single client"""
        options = self._client_options.setdefault(client_id, {})

        for name, value in {
            "force_send_all": force_send_all,
            "tg_level": tg_level,
            "ignore_common": ignore_common,
        }.items():
            if value is not None:
                options[name] = value

    def _option(self, client_id: int, name: str):
        return self._client_options.get(client_id, {}).get(name, getattr(self, name))

    def _min_tg_level(self) -> int:
        return min(
            (self._option(client_id, "tg_level") for client_id in self._mods),
            default=self.tg_level,
        )

    def _common_ignored(self) -> bool:
        if not self._mods:
            return self.ignore_common

        return all(
            self._option(client_id, "ignore_common") for client_id in self._mods
        )

    def _receives(self, client_id: int, item: tuple) -> bool:
        _, caller, levelno, common = item

        if levelno < self._option(client_id, "tg_level"):
            return False

        if common and self._option(client_id, "ignore_common"):
            return False

        return (
            caller is None and len(self._mods) == 1
            or caller == client_id
            or self._option(client_id, "force_send_all")
        )

    def dump(self):
        """Return a list of logging entries"""
        return self.handledbuffer + self.buffer

    def dumps(
        self,
        lvl: int = 0,
        client_id: int | None = None,
        mods: list[str] | None = None,
    ) -> list[str]:
        """Return all entries of minimum level as list of strings,
        optionally filtered to only those whose logger name belongs to
        one of the given `mods` namespaces. `mods` must already be
        resolved to real logger name prefixes (e.g. module's
        `__module__`), not raw user input — this only does an exact
        namespace match (equal or a sub-logger of it)."""
        prefixes = [m for m in (mods or []) if m]

        def _matches(name: str) -> bool:
            return any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes)

        return [
            self.targets[0].format(record)
            for record in (self.buffer + self.handledbuffer)
            if record.levelno >= lvl
            and (
                client_id is None
                or client_id == record.heroku_caller
                or record.heroku_caller is None and len(self._mods) <= 1
            )
            and (not prefixes or _matches(record.name or ""))
        ]

    async def _show_full_trace(
        self,
        call: BotInlineCall,
        bot,
        item: HerokuException,
    ):
        chunks = (
            item.message
            + "\n\n<b>🪐 Full traceback:</b>\n"
            + f'<pre><code class="language-python">{item.full_stack}</code></pre>'
        )

        chunks = list(utils.smart_split(*herokutl.extensions.html.parse(chunks), 4096))

        await call.edit(chunks[0])

        thread_id = call.message.message_thread_id

        for chunk in chunks[1:]:
            await bot.send_message(
                chat_id=call.chat_id, text=chunk, message_thread_id=thread_id
            )

    def get_logid_by_client(self, client_id: int) -> int:
        return self._mods[client_id].logchat

    async def get_logs_topic_id_by_client(self, client_id: int) -> int | None:
        """Get logs topic ID from database"""
        allmods = self._mods[client_id]
        topic_id = await utils.get_topic_id(allmods.db, "Logs")
        if not topic_id:
            logging.debug(
                f"No logs topic found for client {client_id}. Creating new one."
            )
            topic = await utils.asset_forum_topic(
                allmods.client,
                allmods.db,
                allmods.logchat,
                "Logs",
                "📊 Inline logs and error reports will be stored here",
                5877307202888273539,
            )
            topic_id = topic.id
        return topic_id

    async def sender(self):
        async with self._send_lock:
            if not self.tg_buff:
                return
            destinations = [
                client_id for client_id, mod in self._mods.items()
                if await utils.is_private_asset_channel(
                    mod.client, mod.logchat, allow_participants=True
                )
            ]
            self._queue = {
                client_id: utils.chunks(
                    utils.escape_html(
                        "".join(
                            [
                                item[0]
                                for item in self.tg_buff
                                if isinstance(item[0], str)
                                and self._receives(client_id, item)
                            ]
                        )
                    ),
                    4096,
                )
                for client_id in destinations
            }

            self._exc_queue = {}
            for client_id in destinations:
                topic_id = await self.get_logs_topic_id_by_client(client_id)

                funcs = []
                for item in self.tg_buff:
                    if not isinstance(item[0], HerokuException):
                        continue
                    if not self._receives(client_id, item):
                        continue
                    if isinstance(item[0].sysinfo[1], INTERNET_ERRORS) and getattr(
                        self._mods[client_id].lookup("tester"), "config", {}
                    ).get("disable_internet_warn", False):
                        continue

                    funcs.append(
                        functools.partial(
                            self._mods[client_id].inline.bot.send_message,
                            self._mods[client_id].logchat,
                            item[0].message,
                            reply_markup=self._mods[client_id].inline.generate_markup(
                                [
                                    {
                                        "text": "🪐 Full traceback",
                                        "callback": self._show_full_trace,
                                        "args": (
                                            self._mods[client_id].inline.bot,
                                            item[0],
                                        ),
                                        "force_me": True,
                                    },
                                ],
                            ),
                            message_thread_id=topic_id,
                        )
                    )

                self._exc_queue[client_id] = funcs

            await asyncio.gather(
                *(
                    self._exc_sender(*exceptions)
                    for exceptions in self._exc_queue.values()
                )
            )

            self.tg_buff = []

            for client_id in destinations:
                if client_id not in self._queue:
                    continue

                if len(self._queue[client_id]) > 5:
                    logfile = io.BytesIO(
                        "".join(self._queue[client_id]).encode("utf-8")
                    )
                    logfile.name = "heroku-logs.txt"
                    logfile.seek(0)
                    await self._mods[client_id].inline.bot.send_document(
                        self._mods[client_id].logchat,
                        logfile,
                        caption=(
                            "<b>🧳 Journals are too big to be sent as separate"
                            " messages</b>"
                        ),
                        message_thread_id=await self.get_logs_topic_id_by_client(
                            client_id
                        ),
                    )

                    self._queue[client_id] = []
                    continue

                while self._queue[client_id]:
                    if chunk := self._queue[client_id].pop(0):
                        asyncio.ensure_future(
                            self._mods[client_id].inline.bot.send_message(
                                self._mods[client_id].logchat,
                                f"<code>{chunk}</code>",
                                disable_notification=True,
                                message_thread_id=await self.get_logs_topic_id_by_client(
                                    client_id
                                ),
                            )
                        )

    async def _exc_sender(self, *funcs: typing.Callable[..., Coroutine]):
        for func in funcs:
            attempt = 0
            while attempt < 2:
                try:
                    await func()
                    break
                except FloodWaitError as e:
                    attempt += 1
                    await asyncio.sleep(e.seconds)
                except RuntimeError:
                    logging.debug(
                        "RuntimeError in sender, probably event loop is closed, skipping",
                        exc_info=True,
                    )
                    break
                except Exception:
                    logging.debug("Failed to send log message", exc_info=True)
                    break
            if attempt > 2:
                logging.debug(
                    "Failed to send log message after retries, skipping",
                    exc_info=True,
                )

    @staticmethod
    def _legacy_caller() -> int | None:
        frame = sys._getframe(1)

        while frame:
            tag = frame.f_locals.get("_heroku_client_id_logging_tag")
            if isinstance(tag, int):
                return tag

            frame = frame.f_back

        return None

    def emit(self, record: logging.LogRecord):
        try:
            caller = get_client_id()

            if caller is None:
                caller = self._legacy_caller()
        except Exception:
            caller = None

        record.heroku_caller = caller

        if record.levelno >= self._min_tg_level():
            if record.exc_info:
                try:
                    if record.args:
                        comment = record.msg % record.args
                    else:
                        comment = str(record.msg)
                except Exception:
                    comment = f"{record.msg} {record.args}"

                exc = HerokuException.from_exc_info(
                    *record.exc_info,
                    stack=record.__dict__.get("stack", None),
                    comment=comment,
                )

                common = any(field in exc.message for field in COMMON_ERRORS)

                if not common or not self._common_ignored():
                    self.tg_buff += [(exc, caller, record.levelno, common)]
            else:
                self.tg_buff += [
                    (
                        _tg_formatter.format(record),
                        caller,
                        record.levelno,
                        False,
                    )
                ]

        if len(self.buffer) + len(self.handledbuffer) >= self.capacity:
            if self.handledbuffer:
                del self.handledbuffer[0]
            else:
                del self.buffer[0]

        self.buffer.append(record)

        if record.levelno >= self.lvl >= 0:
            self.acquire()
            try:
                for precord in self.buffer:
                    for target in self.targets:
                        if record.levelno >= target.level:
                            target.handle(precord)

                self.handledbuffer = (
                    self.handledbuffer[-(self.capacity - len(self.buffer)) :]
                    + self.buffer
                )
                self.buffer = []
            finally:
                self.release()


async def check_branch(me_id: int, allowed_ids: list, self):
    if os.environ.get("HEROKU_NO_GIT") == "1":
        return
    repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    try:
        with git.Repo(path=repo_path) as repo:
            if me_id in allowed_ids:
                return

            branch_name = get_branch_name(repo_path)
            is_ancestor = check_commit_ancestor(repo, branch_name)
            if is_ancestor:
                return
    except Exception:
        return

    try:
        reset_to_master(repo_path)
        restore_worktree(repo_path)
        self.client.log_out()
    except Exception:
        pass

    restart()


_main_formatter = RedactingFormatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    style="%",
)
_tg_formatter = RedactingFormatter(
    fmt="[%(levelname)s] %(name)s: %(message)s\n",
    datefmt=None,
    style="%",
)

rotating_handler = PrivateRotatingFileHandler(
    filename="heroku.log",
    mode="a",
    maxBytes=10 * 1024 * 1024,
    backupCount=1,
    encoding="utf-8",
    delay=0,
)

rotating_handler.setFormatter(_main_formatter)


def init():
    class NoFetchUpdatesFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            msg = record.getMessage()
            return "Failed to fetch updates" not in msg and "Sleep" not in msg

    logging.getLogger("herokutl.network").addFilter(NoFetchUpdatesFilter())
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(_main_formatter)
    logging.getLogger().handlers = []
    logging.getLogger().addHandler(
        TelegramLogsHandler((handler, rotating_handler), 7000)
    )
    logging.getLogger().setLevel(logging.NOTSET)
    logging.getLogger("herokutl").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.captureWarnings(True)
