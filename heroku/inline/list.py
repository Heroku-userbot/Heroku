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
import functools
import logging
import time
import traceback
import typing

from herokutl.errors.rpcerrorlist import FloodWaitError
from herokutl.errors.rpcerrorlist import ChatSendInlineForbiddenError
from herokutl.tl.types import Message

from .. import main, utils
from .._internal import tag_client_id
from ..types import HerokuReplyMarkup
from .types import InlineMessage, InlineUnit

if typing.TYPE_CHECKING:
    from ..inline.core import InlineManager

logger = logging.getLogger(__name__)


class List(InlineUnit):
    @tag_client_id("_client.tg_id")
    async def list(
        self: "InlineManager",
        message: Message | int,
        strings: list[str],
        *,
        force_me: bool = False,
        always_allow: list[int] | None = None,
        manual_security: bool = False,
        disable_security: bool = False,
        ttl: int | bool = False,
        on_unload: typing.Callable[[], typing.Any] | None = None,
        silent: bool = False,
        custom_buttons: HerokuReplyMarkup | None = None,
    ) -> bool | InlineMessage:
        """
        Send inline list to chat
        :param message: Where to send list. Can be either `Message` or `int`
        :param strings: List of strings, which should become inline list
        :param force_me: Either this list buttons must be pressed only by owner scope or no
        :param always_allow: Users, that are allowed to press buttons in addition to previous rules
        :param ttl: Time, when the list is going to be unloaded. Unload means, that the list
                    will become unusable. Pay attention, that ttl can't
                    be bigger, than default one (1 day) and must be either `int` or `False`
        :param on_unload: Callback, called when list is unloaded and/or closed. You can clean up trash
                          or perform another needed action
        :param manual_security: By default, Heroku will try to inherit inline buttons security from the caller (command)
                                If you want to avoid this, pass `manual_security=True`
        :param disable_security: By default, Heroku will try to inherit inline buttons security from the caller (command)
                                 If you want to disable all security checks on this list in particular, pass `disable_security=True`
        :param silent: Whether the list must be sent silently (w/o "Opening list..." message)
        :param custom_buttons: Custom buttons to add above native ones
        :return: If list is sent, returns :obj:`InlineMessage`, otherwise returns `False`
        """
        custom_buttons = self._validate_markup(custom_buttons)

        if not isinstance(manual_security, bool):
            logger.error(
                "Invalid type for `manual_security`. Expected `bool`, got `%s`",
                type(manual_security),
            )
            return False

        if not isinstance(silent, bool):
            logger.error(
                "Invalid type for `silent`. Expected `bool`, got `%s`",
                type(silent),
            )
            return False

        if not isinstance(disable_security, bool):
            logger.error(
                "Invalid type for `disable_security`. Expected `bool`, got `%s`",
                type(disable_security),
            )
            return False

        if not isinstance(message, (Message, int)):
            logger.error(
                "Invalid type for `message`. Expected `Message` or `int`, got `%s`",
                type(message),
            )
            return False

        if not isinstance(force_me, bool):
            logger.error(
                "Invalid type for `force_me`. Expected `bool`, got `%s`",
                type(force_me),
            )
            return False

        if not isinstance(strings, list) or not strings:
            logger.error(
                (
                    "Invalid type for `strings`. Expected `list` with at least one"
                    " element, got `%s`"
                ),
                type(strings),
            )
            return False

        if len(strings) > 50:
            logger.error("Too much pages for `strings` (%s)", len(strings))
            return False

        if always_allow and not isinstance(always_allow, list):
            logger.error(
                "Invalid type for `always_allow`. Expected `list`, got `%s`",
                type(always_allow),
            )
            return False

        if not always_allow:
            always_allow = []

        if not isinstance(ttl, int) and ttl:
            logger.error(
                "Invalid type for `ttl`. Expected `int` or `False`, got `%s`",
                type(ttl),
            )
            return False

        first_page_needs_premium_emoji_pre_edit = self._needs_premium_emoji_pre_edit(
            self.sanitise_text(strings[0])
        )
        unit_id = utils.rand(16)

        perms_map = None if manual_security else self._find_caller_sec_map()

        self._units[unit_id] = {
            "type": "list",
            "caller": message,
            "chat": None,
            "message_id": None,
            "top_msg_id": utils.get_topic(message),
            "uid": unit_id,
            "current_index": 0,
            "strings": strings,
            "premium_emoji_pre_edit": first_page_needs_premium_emoji_pre_edit,
            "future": asyncio.Event(),
            **({"ttl": round(time.time()) + ttl} if ttl else {}),
            **({"force_me": force_me} if force_me else {}),
            **({"disable_security": disable_security} if disable_security else {}),
            **({"on_unload": on_unload} if callable(on_unload) else {}),
            **({"always_allow": always_allow} if always_allow else {}),
            **({"perms_map": perms_map} if perms_map else {}),
            **({"message": message} if isinstance(message, Message) else {}),
            **({"custom_buttons": custom_buttons} if custom_buttons else {}),
        }

        btn_call_data = utils.rand(10)

        self._custom_map[btn_call_data] = {
            "handler": functools.partial(
                self._list_page,
                unit_id=unit_id,
            ),
            **(
                {"ttl": self._units[unit_id]["ttl"]}
                if "ttl" in self._units[unit_id]
                else {}
            ),
            **({"always_allow": always_allow} if always_allow else {}),
            **({"force_me": force_me} if force_me else {}),
            **({"disable_security": disable_security} if disable_security else {}),
            **({"perms_map": perms_map} if perms_map else {}),
            **({"message": message} if isinstance(message, Message) else {}),
        }

        if isinstance(message, Message) and not silent:
            try:
                status_message = await (
                    message.edit if message.out else message.respond
                )(
                    (
                        utils.get_platform_emoji()
                        if self._client.heroku_me.premium
                        else "🪐"
                    )
                    + self.translator.getkey("inline.opening_list"),
                    **({"reply_to": utils.get_topic(message)} if message.out else {}),
                )
            except Exception:
                status_message = None
        else:
            status_message = None

        async def answer(msg: str):
            nonlocal message
            if isinstance(message, Message):
                await (message.edit if message.out else message.respond)(
                    msg,
                    **({} if message.out else {"reply_to": utils.get_topic(message)}),
                )
            else:
                await self._client.send_message(message, msg)

        try:
            m = await self._invoke_unit(unit_id, message)
        except ChatSendInlineForbiddenError:
            await answer(self.translator.getkey("inline.inline403"))
            del self._units[unit_id]
            return False
        except Exception:
            logger.exception("Can't send list")

            del self._units[unit_id]
            await answer(
                self.translator.getkey("inline.invoke_failed_logs").format(
                    utils.escape_html(
                        "\n".join(traceback.format_exc().splitlines()[1:])
                    )
                )
                if self._db.get(main.__name__, "inlinelogs", True)
                else self.translator.getkey("inline.invoke_failed")
            )

            return False

        await self._units[unit_id]["future"].wait()
        del self._units[unit_id]["future"]

        self._units[unit_id]["chat"] = utils.get_chat_id(m)
        self._units[unit_id]["message_id"] = m.id

        if isinstance(message, Message) and message.out:
            with contextlib.suppress(Exception):
                await message.delete()

        if status_message and not message.out:
            with contextlib.suppress(Exception):
                await status_message.delete()

        if first_page_needs_premium_emoji_pre_edit:
            try:
                await self._bot_client.edit_message(
                    self._units[unit_id]["inline_message_id"],
                    self.sanitise_text(self._units[unit_id]["strings"][0]),
                    parse_mode="HTML",
                    buttons=self._list_markup(unit_id),
                )
            except Exception:
                logger.exception("Can't apply premium emoji pre-edit for list")
                await self._delete_unit_message(unit_id=unit_id)
                await self._unload_unit(unit_id)
                return False

        return InlineMessage(self, unit_id, self._units[unit_id]["inline_message_id"])

    async def _list_page(
        self: "InlineManager",
        call,
        page: int | str,
        unit_id: str = None,
    ):
        match True:
            case _ if page == "close":
                deleted = await self._delete_unit_message(call, unit_id=unit_id)
                try:
                    await call.answer(
                        "" if deleted else "Error occurred", show_alert=not deleted
                    )
                except Exception:
                    pass
                return
            case _ if self._units[unit_id]["current_index"] < 0 or page >= len(
                self._units[unit_id]["strings"]
            ):
                await call.answer("Can't go to this page", show_alert=True)
                return

        self._units[unit_id]["current_index"] = page

        try:
            await self._bot_client.edit_message(
                call.inline_message_id,
                self.sanitise_text(
                    self._units[unit_id]["strings"][
                        self._units[unit_id]["current_index"]
                    ]
                ),
                parse_mode="HTML",
                buttons=self._list_markup(unit_id),
            )
            await call.answer()
        except FloodWaitError as e:
            await call.answer(
                f"Got FloodWait. Wait for {e.seconds} seconds",
                show_alert=True,
            )
        except Exception:
            logger.exception("Exception while trying to edit list")
            await call.answer("Error occurred", show_alert=True)
            return

    def _list_markup(self: "InlineManager", unit_id: str):
        """Generates Telethon markup for `list`"""
        callback = functools.partial(self._list_page, unit_id=unit_id)
        return self.generate_markup(
            self._units[unit_id].get("custom_buttons", [])
            + self.build_pagination(
                callback=callback,
                total_pages=len(self._units[unit_id]["strings"]),
                unit_id=unit_id,
            )
            + [[{"text": "🔻 Close", "callback": callback, "args": ("close",)}]],
        )

    async def _list_inline_handler(self: "InlineManager", inline_query):
        for unit in self._units.copy().values():
            if (
                inline_query.from_user.id == self._me
                and inline_query.query == unit["uid"]
                and unit["type"] == "list"
            ):
                try:
                    await inline_query.answer(
                        [
                            await inline_query.builder.article(
                                title="Heroku",
                                text=(
                                    "🪐"
                                    if unit.get("premium_emoji_pre_edit")
                                    else self.sanitise_text(unit["strings"][0])
                                ),
                                parse_mode="HTML",
                                link_preview=False,
                                buttons=self._list_markup(inline_query.query),
                                id=utils.rand(20),
                            )
                        ],
                        cache_time=60,
                    )
                except Exception as e:
                    if unit["uid"] in self._error_events:
                        self._error_events[unit["uid"]].set()
                        self._error_events[unit["uid"]] = e
