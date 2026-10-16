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
import io
import itertools
import logging
import os
import re
import typing
from collections.abc import Callable
from copy import deepcopy
from urllib.parse import urlparse

from herokutl.errors.rpcbaseerrors import RPCError
from herokutl.errors.rpcerrorlist import (
    FloodWaitError,
    MediaPrevInvalidError,
    MessageNotModifiedError,
)

from .. import utils
from ..types import HerokuReplyMarkup
from .tl import make_button
from .types import InlineCall, InlineUnit

if typing.TYPE_CHECKING:
    from ..inline.core import InlineManager

logger = logging.getLogger(__name__)

VALID_BUTTON_STYLES = {"danger", "primary", "success"}
TG_EMOJI_RE = re.compile(
    r"<tg-emoji\b[^>]*\bemoji-id\s*=\s*['\"]?\d+['\"]?[^>]*>(.*?)</tg-emoji>",
    flags=re.IGNORECASE | re.DOTALL,
)


class Utils(InlineUnit):
    def _has_premium_emoji(self, text: typing.Any) -> bool:
        return isinstance(text, str) and bool(TG_EMOJI_RE.search(text))

    def _needs_premium_emoji_pre_edit(self, text: typing.Any) -> bool:
        return self._has_premium_emoji(text) and bool(
            getattr(getattr(self._client, "heroku_me", None), "premium", False)
        )

    def _get_button_style(self, button: dict) -> str | None:
        """Extract and validate button style from button dict"""
        style = button.get("style")
        if style and style in VALID_BUTTON_STYLES:
            return style
        return None

    def _get_button_emoji_id(self, button: dict) -> str | None:
        """Extract button custom emoji ID (for premium emoji support)"""

        emoji_id = button.get("emoji_id")

        if emoji_id:
            return str(emoji_id).strip()
        return None

    def _generate_markup(
        self: "InlineManager",
        markup_obj: HerokuReplyMarkup | str | None,
    ) -> list[list[typing.Any]] | None:
        """Generate markup for form or list of `dict`s"""
        if not markup_obj:
            return None

        if hasattr(markup_obj, "SUBCLASS_OF_ID"):
            return markup_obj

        markup = []

        map_ = (
            self._units[markup_obj]["buttons"]
            if isinstance(markup_obj, str)
            else markup_obj
        )

        map_ = self._normalize_markup(map_)

        setup_callbacks = False

        for row in map_:
            for button in row:
                if not isinstance(button, dict):
                    logger.error(
                        "Button %s is not a `dict`, but `%s` in %s",
                        button,
                        type(button),
                        map_,
                    )
                    return None

                if "callback" not in button:
                    if button.get("action") == "close":
                        button["callback"] = self._close_unit_handler

                    if button.get("action") == "unload":
                        button["callback"] = self._unload_unit_handler

                    if button.get("action") == "answer":
                        if not button.get("message"):
                            logger.error(
                                "Button %s has no `message` to answer with", button
                            )
                            return None

                        button["callback"] = functools.partial(
                            self._answer_unit_handler,
                            show_alert=button.get("show_alert", False),
                            text=button["message"],
                        )

                if "callback" in button and "_callback_data" not in button:
                    button["_callback_data"] = utils.rand(30)
                    setup_callbacks = True

                if "input" in button and "_switch_query" not in button:
                    button["_switch_query"] = utils.rand(10)

        for row in map_:
            line = []
            for button in row:
                try:
                    btn_kwargs = {"text": str(button["text"])}

                    if style := self._get_button_style(button):
                        btn_kwargs["style"] = style

                    if emoji_id := self._get_button_emoji_id(button):
                        btn_kwargs["icon"] = int(emoji_id)

                    match True:
                        case _ if "url" in button:
                            if not utils.check_url(button["url"]):
                                logger.warning(
                                    "Button have not been added to form, "
                                    "because its url is invalid"
                                )
                                continue
                            btn_kwargs["url"] = button["url"]

                        case _ if "callback" in button:
                            btn_kwargs["data"] = button["_callback_data"]

                            if setup_callbacks:
                                self._custom_map[button["_callback_data"]] = {
                                    "handler": button["callback"],
                                    "always_allow": button.get("always_allow", [])
                                    or [],
                                    "args": button.get("args", {}),
                                    "kwargs": button.get("kwargs", {}),
                                    "force_me": button.get("force_me", False),
                                    "disable_security": button.get(
                                        "disable_security", False
                                    ),
                                }

                        case _ if "input" in button:
                            btn_kwargs["switch_inline_query_current_chat"] = (
                                button["_switch_query"] + " "
                            )

                        case _ if "data" in button:
                            btn_kwargs["data"] = button["data"]

                        case _ if "web_app" in button:
                            btn_kwargs["web_app"] = button["web_app"]

                        case _ if "copy" in button:
                            btn_kwargs["copy_text"] = button["copy"]

                        case _ if "switch_inline_query_current_chat" in button:
                            btn_kwargs["switch_inline_query_current_chat"] = button[
                                "switch_inline_query_current_chat"
                            ]

                        case _ if "switch_inline_query" in button:
                            btn_kwargs["switch_inline_query"] = button[
                                "switch_inline_query"
                            ]

                        case _:
                            logger.warning(
                                (
                                    "Button have not been added to "
                                    "form, because it is not structured "
                                    "properly. %s"
                                ),
                                button,
                            )
                            continue

                    line.append(make_button(**btn_kwargs))

                except KeyError:
                    logger.exception(
                        "Error while forming markup! Probably, you "
                        "passed wrong type combination for button. "
                        "Contact developer of module."
                    )
                    return None
                except Exception as e:
                    logger.exception(f"Unexpected error creating button: {e}")
                    return None

            markup.append(line)

        return markup

    generate_markup = _generate_markup

    async def _close_unit_handler(self: "InlineManager", call: InlineCall):
        deleted = await self._delete_unit_message(call, unit_id=call.unit_id)
        try:
            await call.answer(
                "" if deleted else "Error occurred", show_alert=not deleted
            )
        except Exception:
            pass
        return deleted

    async def _unload_unit_handler(self: "InlineManager", call: InlineCall):
        await call.unload()

    async def _answer_unit_handler(
        self: "InlineManager", call: InlineCall, text: str, show_alert: bool
    ):
        await call.answer(text, show_alert=show_alert)

    def _reverse_method_lookup(
        self: "InlineManager", needle: Callable, /
    ) -> str | None:
        return next(
            (
                name
                for name, method in itertools.chain(
                    self._allmodules.inline_handlers.items(),
                    self._allmodules.callback_handlers.items(),
                )
                if method == needle
            ),
            None,
        )

    async def check_inline_security(
        self: "InlineManager", *, func: typing.Callable, user: int
    ) -> bool:
        """Checks if user with id `user` is allowed to run function `func`"""
        return await self._client.dispatcher.security.check(
            message=None,
            func=func,
            user_id=user,
            inline_cmd=self._reverse_method_lookup(func),
        )

    def _find_caller_sec_map(
        self: "InlineManager",
    ) -> typing.Callable[[], int] | None:
        try:
            caller = utils.find_caller()
            if not caller:
                return None

            logger.debug("Found caller: %s", caller)

            return lambda: self._client.dispatcher.security.get_flags(
                getattr(caller, "__self__", caller),
            )
        except Exception:
            logger.debug("Can't parse security mask in form", exc_info=True)

        return None

    def _normalize_markup(
        self: "InlineManager", reply_markup: HerokuReplyMarkup
    ) -> list[list[dict[str, typing.Any]]]:
        if isinstance(reply_markup, dict):
            return [[reply_markup]]

        if isinstance(reply_markup, list) and any(
            isinstance(i, dict) for i in reply_markup
        ):
            return [reply_markup]

        return reply_markup

    def sanitise_text(self: "InlineManager", text: str) -> str:
        return re.sub(r"</?emoji.*?>", "", text)

    async def _edit_unit(
        self: "InlineManager",
        text: str | None = None,
        reply_markup: HerokuReplyMarkup | None = None,
        *,
        photo: str | None = None,
        file: str | None = None,
        video: str | None = None,
        audio: dict | str | None = None,
        gif: str | None = None,
        mime_type: str | None = None,
        force_me: bool | None = None,
        disable_security: bool | None = None,
        always_allow: list[int] | None = None,
        disable_web_page_preview: bool = True,
        query: typing.Any | None = None,
        unit_id: str | None = None,
        inline_message_id: str | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> bool:
        """
        Edits unit message
        :param text: Text of message
        :param reply_markup: Inline keyboard
        :param photo: Url to a valid photo to attach to message
        :param file: Url to a valid file to attach to message
        :param video: Url to a valid video to attach to message
        :param audio: Url to a valid audio to attach to message
        :param gif: Url to a valid gif to attach to message
        :param mime_type: Mime type of file
        :param force_me: Allow only userbot owner to interact with buttons
        :param disable_security: Disable security check for buttons
        :param always_allow: List of user ids, which will always be allowed
        :param disable_web_page_preview: Disable web page preview
        :param query: Callback query
        :return: Status of edit
        """
        reply_markup = self._validate_markup(reply_markup) or []

        if text is not None and not isinstance(text, str):
            logger.error(
                "Invalid type for `text`. Expected `str`, got `%s`", type(text)
            )
            return False

        if file and not mime_type:
            logger.error(
                "You must pass `mime_type` along with `file` field\n"
                "It may be either 'application/zip' or 'application/pdf'"
            )
            return False

        if isinstance(audio, str):
            audio = {"url": audio}

        if isinstance(text, str):
            text = self.sanitise_text(text)

        media_params = [
            photo is None,
            gif is None,
            file is None,
            video is None,
            audio is None,
        ]

        if media_params.count(False) > 1:
            logger.error("You passed two or more exclusive parameters simultaneously")
            return False

        pending_unit_update = {}

        if unit_id is not None and unit_id in self._units:
            unit = self._units[unit_id]

            pending_unit_update["buttons"] = reply_markup
            if text is not None:
                pending_unit_update["text"] = text

            if isinstance(force_me, bool):
                pending_unit_update["force_me"] = force_me

            if isinstance(disable_security, bool):
                pending_unit_update["disable_security"] = disable_security

            if isinstance(always_allow, list):
                pending_unit_update["always_allow"] = always_allow
        else:
            unit = {}

        def commit_unit_update():
            if unit_id is not None and unit_id in self._units:
                self._units[unit_id].update(pending_unit_update)

        if unit:
            chat_id = chat_id or unit.get("chat")
            message_id = message_id or unit.get("message_id")

        inline_message_id = (
            inline_message_id
            or unit.get("inline_message_id", False)
            or getattr(query, "inline_message_id", None)
        )

        if not chat_id and not message_id and not inline_message_id:
            logger.warning(
                "Attempted to edit message with no `inline_message_id`. "
                "Possible reasons:\n"
                "- Form was sent without buttons and due to "
                "the limits of Telegram API can't be edited\n"
                "- There is an in-userbot error, which you should report"
            )
            return False

        try:
            path = urlparse(photo).path
            ext = os.path.splitext(path)[1]
        except Exception:
            ext = None

        if photo is not None and ext in {".gif", ".mp4"}:
            gif = deepcopy(photo)
            photo = None

        media = next(
            (media for media in [photo, file, video, audio, gif] if media), None
        )
        if isinstance(media, dict):
            media = media["url"]

        if isinstance(media, bytes):
            media = io.BytesIO(media)
            media.name = "upload.mp4"

        if isinstance(media, io.BytesIO):
            media.name = getattr(media, "name", "upload.mp4")

        kind = (
            "file"
            if file
            else (
                "photo"
                if photo
                else "audio" if audio else "video" if video else "gif" if gif else None
            )
        )

        if media is None and text is None and reply_markup:
            try:
                await self._bot_client.edit_message(
                    inline_message_id or chat_id,
                    (unit.get("text") or "") if inline_message_id else message_id,
                    buttons=self.generate_markup(reply_markup),
                )
            except Exception:
                return False

            commit_unit_update()
            return True

        if media is None and text is None:
            logger.error("You must pass either `text` or `media` or `reply_markup`")
            return False

        if media is None:
            try:
                await self._bot_client.edit_message(
                    inline_message_id or chat_id,
                    None if inline_message_id else message_id,
                    text,
                    parse_mode="HTML",
                    link_preview=not disable_web_page_preview,
                    buttons=self.generate_markup(
                        reply_markup
                        if isinstance(reply_markup, list)
                        else unit.get("buttons", [])
                    ),
                )
            except MessageNotModifiedError:
                commit_unit_update()
                return True
            except FloodWaitError as e:
                logger.info("Sleeping %ss on Telethon FloodWait...", e.seconds)
                await asyncio.sleep(e.seconds)
                return await self._edit_unit(**utils.get_kwargs())
            except RPCError as e:
                logger.warning(
                    "RPCError while editing inline message via inline_message_id: %s. "
                    "Attempting fallback via chat_id + message_id...",
                    e,
                )
                if inline_message_id and chat_id and message_id:
                    with contextlib.suppress(Exception):
                        await self._bot_client.edit_message(
                            chat_id,
                            message_id,
                            text,
                            parse_mode="HTML",
                            link_preview=not disable_web_page_preview,
                            buttons=self.generate_markup(
                                reply_markup
                                if isinstance(reply_markup, list)
                                else unit.get("buttons", [])
                            ),
                        )
                        commit_unit_update()
                        return True
                if query:
                    with contextlib.suppress(Exception):
                        await query.answer()
                return False
            else:
                commit_unit_update()
                return True

        try:
            await self._bot_client.edit_message(
                inline_message_id or chat_id,
                None if inline_message_id else message_id,
                text,
                parse_mode="HTML",
                file=media,
                force_document=kind == "file",
                buttons=self.generate_markup(
                    reply_markup
                    if isinstance(reply_markup, list)
                    else unit.get("buttons", [])
                ),
            )
        except FloodWaitError as e:
            logger.info("Sleeping %ss on Telethon FloodWait...", e.seconds)
            await asyncio.sleep(e.seconds)
            return await self._edit_unit(**utils.get_kwargs())
        except (RPCError, MediaPrevInvalidError):
            with contextlib.suppress(Exception):
                await query.answer(
                    "I should have edited some message, but it is deleted :("
                )
            return False
        else:
            commit_unit_update()
            return True

    async def _delete_unit_message(
        self: "InlineManager",
        call: typing.Any | None = None,
        unit_id: str | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> bool:
        """Params `self`, `unit_id` are for internal use only, do not try to pass them"""
        if not isinstance(call, InlineCall):
            chat_id = chat_id or getattr(
                getattr(getattr(call, "message", None), "chat", None), "id", None
            )
            message_id = message_id or getattr(
                getattr(call, "message", None), "id", None
            )
            if chat_id and message_id:
                try:
                    await self.bot.delete_message(chat_id, message_id)
                except Exception:
                    logger.debug(
                        "Failed to delete bot message %s", unit_id, exc_info=True
                    )
                    return False

                return True

        if not unit_id and getattr(call, "unit_id", None):
            unit_id = call.unit_id

        unit = self._units.get(unit_id) or {}
        if not (unit.get("chat") and unit.get("message_id")):
            return False

        try:
            await self._client.delete_messages(unit["chat"], unit["message_id"])
        except Exception:
            logger.debug("Failed to delete unit message %s", unit_id, exc_info=True)
            return False

        return True

    async def _unload_unit(self: "InlineManager", unit_id: str) -> bool:
        """Params `self`, `unit_id` are for internal use only, do not try to pass them"""
        try:
            if "on_unload" in self._units[unit_id] and callable(
                self._units[unit_id]["on_unload"]
            ):
                self._units[unit_id]["on_unload"]()

            if unit_id in self._units:
                del self._units[unit_id]
            else:
                return False
        except Exception:
            return False

        return True

    def build_pagination(
        self: "InlineManager",
        callback: typing.Callable[[int], typing.Awaitable[typing.Any]],
        total_pages: int,
        unit_id: str | None = None,
        current_page: int | None = None,
    ) -> list[list[dict[str, typing.Any]]]:
        # Based on https://github.com/pystorage/pykeyboard/blob/master/pykeyboard/inline_pagination_keyboard.py#L4
        if current_page is None:
            current_page = self._units[unit_id]["current_index"] + 1

        if total_pages <= 5:
            return [
                [
                    (
                        {"text": number, "args": (number - 1,), "callback": callback}
                        if number != current_page
                        else {
                            "text": f"· {number} ·",
                            "args": (number - 1,),
                            "callback": callback,
                        }
                    )
                    for number in range(1, total_pages + 1)
                ]
            ]

        if current_page <= 3:
            return [
                [
                    (
                        {
                            "text": f"· {number} ·",
                            "args": (number - 1,),
                            "callback": callback,
                        }
                        if number == current_page
                        else (
                            {
                                "text": f"{number} ›",
                                "args": (number - 1,),
                                "callback": callback,
                            }
                            if number == 4
                            else (
                                {
                                    "text": f"{total_pages} »",
                                    "args": (total_pages - 1,),
                                    "callback": callback,
                                }
                                if number == 5
                                else {
                                    "text": number,
                                    "args": (number - 1,),
                                    "callback": callback,
                                }
                            )
                        )
                    )
                    for number in range(1, 6)
                ]
            ]

        if current_page > total_pages - 3:
            return [
                [
                    {"text": "« 1", "args": (0,), "callback": callback},
                    {
                        "text": f"‹ {total_pages - 3}",
                        "args": (total_pages - 4,),
                        "callback": callback,
                    },
                ]
                + [
                    (
                        {
                            "text": f"· {number} ·",
                            "args": (number - 1,),
                            "callback": callback,
                        }
                        if number == current_page
                        else {
                            "text": number,
                            "args": (number - 1,),
                            "callback": callback,
                        }
                    )
                    for number in range(total_pages - 2, total_pages + 1)
                ]
            ]

        return [
            [
                {"text": "« 1", "args": (0,), "callback": callback},
                {
                    "text": f"‹ {current_page - 1}",
                    "args": (current_page - 2,),
                    "callback": callback,
                },
                {
                    "text": f"· {current_page} ·",
                    "args": (current_page - 1,),
                    "callback": callback,
                },
                {
                    "text": f"{current_page + 1} ›",
                    "args": (current_page,),
                    "callback": callback,
                },
                {
                    "text": f"{total_pages} »",
                    "args": (total_pages - 1,),
                    "callback": callback,
                },
            ]
        ]

    def _validate_markup(
        self: "InlineManager",
        buttons: HerokuReplyMarkup | None,
    ) -> list[list[dict[str, typing.Any]]]:
        if buttons is None:
            buttons = []

        if not isinstance(buttons, (list, dict)):
            logger.error(
                "Reply markup ommited because passed type is not valid (%s)",
                type(buttons),
            )
            return None

        buttons = self._normalize_markup(buttons)

        if not all(all(isinstance(button, dict) for button in row) for row in buttons):
            logger.error(
                "Reply markup ommited because passed invalid type for one of the"
                " buttons"
            )
            return None

        if not all(
            all(
                "url" in button
                or "callback" in button
                or "input" in button
                or "data" in button
                or "action" in button
                or "copy" in button
                or "web_app" in button
                or "switch_inline_query_current_chat" in button
                or "switch_inline_query" in button
                for button in row
            )
            for row in buttons
        ):
            logger.error(
                "Invalid button specified. "
                "Button must contain one of the following fields:\n"
                "  - `url`\n"
                "  - `callback`\n"
                "  - `input`\n"
                "  - `data`\n"
                "  - `action`\n"
                "  - `copy`\n"
                "  - `web_app`\n"
                "  - `switch_inline_query_current_chat`\n"
                "  - `switch_inline_query`"
            )
            return None

        return buttons
