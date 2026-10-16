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
import os
import time
import traceback
import typing
from collections.abc import Callable
from urllib.parse import urlparse

from herokutl.errors.rpcerrorlist import (
    ChatSendInlineForbiddenError,
    FloodWaitError,
    MediaPrevInvalidError,
    MessageIdInvalidError,
)
from herokutl.tl.types import Message

from .. import main, utils
from .._internal import tag_client_id
from ..types import HerokuReplyMarkup
from .types import InlineMessage, InlineUnit

if typing.TYPE_CHECKING:
    from ..inline.core import InlineManager

logger = logging.getLogger(__name__)


class ListGalleryHelper:
    def __init__(self, lst: list[str]):
        self.lst = lst
        self._current_index = -1

    def __call__(self) -> str:
        self._current_index += 1
        return self.lst[self._current_index % len(self.lst)]

    def by_index(self, index: int) -> str:
        return self.lst[index % len(self.lst)]


class Gallery(InlineUnit):
    @tag_client_id("_client.tg_id")
    async def gallery(
        self: "InlineManager",
        message: Message | int,
        next_handler: Callable | list[str],
        caption: list[str] | str | Callable = "",
        *,
        custom_buttons: HerokuReplyMarkup | None = None,
        force_me: bool = False,
        always_allow: list[int] | None = None,
        manual_security: bool = False,
        disable_security: bool = False,
        ttl: int | bool = False,
        on_unload: Callable | None = None,
        preload: bool | int = False,
        gif: bool = False,
        silent: bool = False,
        _reattempt: bool = False,
    ) -> bool | InlineMessage:
        """
        Send inline gallery to chat
        :param caption: Caption for photo, or Callable, returning caption
        :param message: Where to send inline. Can be either `Message` or `int`
        :param next_handler: Callback function, which must return url for next photo or list with photo urls
        :param custom_buttons: Custom buttons to add above native ones
        :param force_me: Either this gallery buttons must be pressed only by owner scope or no
        :param always_allow: Users, that are allowed to press buttons in addition to previous rules
        :param ttl: Time, when the gallery is going to be unloaded. Unload means, that the gallery
                    will become unusable. Pay attention, that ttl can't
                    be bigger, than default one (1 day) and must be either `int` or `False`
        :param on_unload: Callback, called when gallery is unloaded and/or closed. You can clean up trash
                          or perform another needed action
        :param preload: Either to preload gallery photos beforehand or no. If yes - specify threshold to
                        be loaded. Toggle this attribute, if your callback is too slow to load photos
                        in real time
        :param gif: Whether the gallery will be filled with gifs. If you omit this argument and specify
                    gifs in `next_handler`, Heroku will try to determine the filetype of these images
        :param manual_security: By default, Heroku will try to inherit inline buttons security from the caller (command)
                                If you want to avoid this, pass `manual_security=True`
        :param disable_security: By default, Heroku will try to inherit inline buttons security from the caller (command)
                                 If you want to disable all security checks on this gallery in particular, pass `disable_security=True`
        :param silent: Whether the gallery must be sent silently (w/o "Opening gallery..." message)
        :return: If gallery is sent, returns :obj:`InlineMessage`, otherwise returns `False`
        """
        custom_buttons = self._validate_markup(custom_buttons)

        if not (
            isinstance(caption, str)
            or isinstance(caption, list)
            and all(isinstance(item, str) for item in caption)
        ) and not callable(caption):
            logger.error(
                (
                    "Invalid type for `caption`. Expected `str` or `list` or"
                    " `Callable`, got `%s`"
                ),
                type(caption),
            )
            return False

        if isinstance(caption, list):
            caption = ListGalleryHelper(lst=caption)

        if not isinstance(manual_security, bool):
            logger.error(
                "Invalid type for `manual_security`. Expected `bool`, got `%s`",
                type(manual_security),
            )
            return False

        if not isinstance(silent, bool):
            logger.error(
                "Invalid type for `silent`. Expected `bool`, got `%s`", type(silent)
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
                "Invalid type for `force_me`. Expected `bool`, got `%s`", type(force_me)
            )
            return False

        if not isinstance(gif, bool):
            logger.error("Invalid type for `gif`. Expected `bool`, got `%s`", type(gif))
            return False

        if (
            not isinstance(preload, (bool, int))
            or isinstance(preload, bool)
            and preload
        ):
            logger.error(
                "Invalid type for `preload`. Expected `int` or `False`, got `%s`",
                type(preload),
            )
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
                "Invalid type for `ttl`. Expected `int` or `False`, got `%s`", type(ttl)
            )
            return False

        if isinstance(next_handler, list):
            if all(isinstance(i, str) for i in next_handler):
                next_handler = ListGalleryHelper(lst=next_handler)
            else:
                logger.error(
                    (
                        "Invalid type for `next_handler`. Expected `Callable` or `list`"
                        " of `str`, got `%s`"
                    ),
                    type(next_handler),
                )
                return False

        unit_id = utils.rand(16)
        btn_call_data = utils.rand(10)

        try:
            if isinstance(next_handler, ListGalleryHelper):
                photo_url = next_handler.lst
            else:
                photo_url = await self._call_photo(next_handler)
                if not photo_url:
                    return False
        except Exception:
            logger.exception("Error while parsing first photo in gallery")
            return False

        perms_map = None if manual_security else self._find_caller_sec_map()

        self._units[unit_id] = {
            "type": "gallery",
            "caption": caption,
            "caller": message,
            "chat": None,
            "message_id": None,
            "top_msg_id": utils.get_topic(message),
            "uid": unit_id,
            "photo_url": photo_url if isinstance(photo_url, str) else photo_url[0],
            "next_handler": next_handler,
            "btn_call_data": btn_call_data,
            "photos": [photo_url] if isinstance(photo_url, str) else photo_url,
            "current_index": 0,
            "future": asyncio.Event(),
            **({"ttl": round(time.time()) + ttl} if ttl else {}),
            **({"force_me": force_me} if force_me else {}),
            **({"disable_security": disable_security} if disable_security else {}),
            **({"on_unload": on_unload} if callable(on_unload) else {}),
            **({"preload": preload} if preload else {}),
            **({"gif": gif} if gif else {}),
            **({"always_allow": always_allow} if always_allow else {}),
            **({"perms_map": perms_map} if perms_map else {}),
            **({"message": message} if isinstance(message, Message) else {}),
            **({"custom_buttons": custom_buttons} if custom_buttons else {}),
        }

        self._custom_map[btn_call_data] = {
            "handler": functools.partial(
                self._gallery_page,
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
                    + self.translator.getkey("inline.opening_gallery"),
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
            logger.exception("Error sending inline gallery")

            del self._units[unit_id]

            if _reattempt:
                logger.exception("Can't send gallery")

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

            kwargs = utils.get_kwargs()
            kwargs["_reattempt"] = True

            return await self.gallery(**kwargs)

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

        if not isinstance(next_handler, ListGalleryHelper):
            asyncio.ensure_future(self._load_gallery_photos(unit_id))

        return InlineMessage(self, unit_id, self._units[unit_id]["inline_message_id"])

    async def _call_photo(
        self: "InlineManager",
        callback: (
            typing.Callable[[], typing.Awaitable[str]]
            | typing.Callable[[], str]
            | list[str]
        ),
    ) -> str | bool:
        """Parses photo url from `callback`. Returns url on success, otherwise `False`"""
        match True:
            case _ if isinstance(callback, str):
                photo_url = callback
            case _ if isinstance(callback, list):
                photo_url = callback[0]
            case _ if asyncio.iscoroutinefunction(callback):
                photo_url = await callback()
            case _ if callable(callback):
                photo_url = callback()
            case _:
                logger.error(
                    (
                        "Invalid type for `next_handler`. Expected `str`, `list` or"
                        " `Callable`, got %s"
                    ),
                    type(callback),
                )
                return False

        if not isinstance(photo_url, (str, list)):
            logger.error(
                (
                    "Got invalid result from `next_handler`. Expected `str` or `list`,"
                    " got %s"
                ),
                type(photo_url),
            )
            return False

        return photo_url

    async def _load_gallery_photos(self: "InlineManager", unit_id: str):
        """Preloads photo. Should be called via ensure_future"""
        unit = self._units.get(unit_id)
        if not unit:
            return

        photo_url = await self._call_photo(unit["next_handler"])

        unit = self._units.get(unit_id)
        if not unit:
            return

        unit["photos"] += [photo_url] if isinstance(photo_url, str) else photo_url

        if unit.get("preload", False) and len(unit["photos"]) - unit[
            "current_index"
        ] < unit.get("preload", False):
            asyncio.ensure_future(self._load_gallery_photos(unit_id))

    async def _gallery_slideshow_loop(
        self: "InlineManager",
        call,
        unit_id: str | None = None,
    ):
        while True:
            await asyncio.sleep(7)

            if unit_id not in self._units:
                return

            unit = self._units[unit_id]

            if not unit.get("slideshow", False):
                return

            if unit["current_index"] + 1 >= len(unit["photos"]) and isinstance(
                unit["next_handler"],
                ListGalleryHelper,
            ):
                unit.pop("slideshow", None)
                unit["current_index"] -= 1

            try:
                await self._gallery_page(
                    call,
                    unit["current_index"] + 1,
                    unit_id=unit_id,
                )
            except KeyError:
                if unit_id not in self._units:
                    return
                raise

    async def _gallery_slideshow(
        self: "InlineManager",
        call,
        unit_id: str | None = None,
    ):
        if not self._units[unit_id].get("slideshow", False):
            self._units[unit_id]["slideshow"] = True
            await self._bot_client.edit_message(
                call.inline_message_id,
                self._get_caption(unit_id, self._units[unit_id]["current_index"]),
                parse_mode="HTML",
                buttons=self._gallery_markup(unit_id),
            )
            await call.answer("✅ Slideshow on")
        else:
            del self._units[unit_id]["slideshow"]
            await self._bot_client.edit_message(
                call.inline_message_id,
                self._get_caption(unit_id, self._units[unit_id]["current_index"]),
                parse_mode="HTML",
                buttons=self._gallery_markup(unit_id),
            )
            await call.answer("🚫 Slideshow off")
            return

        asyncio.ensure_future(
            self._gallery_slideshow_loop(
                call,
                unit_id,
            )
        )

    async def _gallery_back(
        self: "InlineManager",
        call,
        unit_id: str | None = None,
    ):
        queue = self._units[unit_id]["photos"]

        if not queue:
            await call.answer("No way back", show_alert=True)
            return

        self._units[unit_id]["current_index"] -= 1

        if self._units[unit_id]["current_index"] < 0:
            self._units[unit_id]["current_index"] = 0
            await call.answer("No way back")
            return

        try:
            media, caption, force_document = self._get_current_media(unit_id)
            await self._bot_client.edit_message(
                call.inline_message_id,
                caption,
                parse_mode="HTML",
                file=media,
                force_document=force_document,
                buttons=self._gallery_markup(unit_id),
            )
        except FloodWaitError as e:
            await call.answer(
                f"Got FloodWait. Wait for {e.seconds} seconds",
                show_alert=True,
            )
        except Exception:
            logger.exception("Exception while trying to edit media")
            await call.answer("Error occurred", show_alert=True)
            return

    def _get_current_media(
        self: "InlineManager",
        unit_id: str,
    ) -> tuple[str, str, bool]:
        """Return current media, which should be updated in gallery"""
        media = self._get_next_photo(unit_id)
        try:
            path = urlparse(media).path
            ext = os.path.splitext(path)[1]
        except Exception:
            ext = None

        if self._units[unit_id].get("gif", False) or ext in {".gif", ".mp4"}:
            return (
                media,
                self._get_caption(
                    unit_id,
                    index=self._units[unit_id]["current_index"],
                ),
                True,
            )

        return (
            media,
            self._get_caption(
                unit_id,
                index=self._units[unit_id]["current_index"],
            ),
            False,
        )

    async def _gallery_page(
        self: "InlineManager",
        call,
        page: int | str,
        unit_id: str | None = None,
    ):
        match True:
            case _ if page == "slideshow":
                await self._gallery_slideshow(call, unit_id)
                return
            case _ if page == "close":
                deleted = await self._delete_unit_message(call, unit_id=unit_id)
                if deleted:
                    self._units.get(unit_id, {}).pop("slideshow", None)
                    await self._unload_unit(unit_id)
                try:
                    await call.answer(
                        "" if deleted else "Error occurred", show_alert=not deleted
                    )
                except Exception:
                    pass
                return
            case _ if page < 0:
                await call.answer("No way back")
                return
            case _ if page > len(self._units[unit_id]["photos"]) - 1 and isinstance(
                self._units[unit_id]["next_handler"], ListGalleryHelper
            ):
                await call.answer("No way forward")
                return

        self._units[unit_id]["current_index"] = page
        if not isinstance(self._units[unit_id]["next_handler"], ListGalleryHelper):
            if self._units[unit_id]["current_index"] >= len(
                self._units[unit_id]["photos"]
            ):
                await self._load_gallery_photos(unit_id)

            if self._units[unit_id]["current_index"] >= len(
                self._units[unit_id]["photos"]
            ):
                await call.answer("Can't load next photo")
                return

            if (
                len(self._units[unit_id]["photos"])
                - self._units[unit_id]["current_index"]
                < self._units[unit_id].get("preload", 0) // 2
            ):
                logger.debug("Started preload for gallery %s", unit_id)
                asyncio.ensure_future(self._load_gallery_photos(unit_id))

        try:
            media, caption, force_document = self._get_current_media(unit_id)
            await self._bot_client.edit_message(
                call.inline_message_id,
                caption,
                parse_mode="HTML",
                file=media,
                force_document=force_document,
                buttons=self._gallery_markup(unit_id),
            )
        except MediaPrevInvalidError:
            logger.debug("Error fetching photo content, attempting load next one")
            del self._units[unit_id]["photos"][self._units[unit_id]["current_index"]]
            self._units[unit_id]["current_index"] -= 1
            return await self._gallery_page(call, page, unit_id)
        except FloodWaitError as e:
            await call.answer(
                f"Got FloodWait. Wait for {e.seconds} seconds",
                show_alert=True,
            )
            return
        except MessageIdInvalidError:
            self._units.get(unit_id, {}).pop("slideshow", None)
            await self._unload_unit(unit_id)
            return
        except Exception:
            logger.exception("Exception while trying to edit media")
            await call.answer("Error occurred", show_alert=True)
            return

    def _get_next_photo(self: "InlineManager", unit_id: str) -> str:
        """Returns next photo"""
        try:
            return self._units[unit_id]["photos"][self._units[unit_id]["current_index"]]
        except IndexError:
            logger.error(
                "Got IndexError in `_get_next_photo`. %s / %s",
                self._units[unit_id]["current_index"],
                len(self._units[unit_id]["photos"]),
            )
            return self._units[unit_id]["photos"][0]

    def _get_caption(self: "InlineManager", unit_id: str, index: int = 0) -> str:
        """Calls and returnes caption for gallery"""
        caption = self._units[unit_id].get("caption", "")
        if isinstance(caption, ListGalleryHelper):
            return caption.by_index(index)

        return (
            caption
            if isinstance(caption, str)
            else caption() if callable(caption) else ""
        )

    def _gallery_markup(self: "InlineManager", unit_id: str):
        """Generates Telethon markup for `gallery`"""
        callback = functools.partial(self._gallery_page, unit_id=unit_id)
        unit = self._units[unit_id]
        return self.generate_markup(
            (
                unit.get("custom_buttons", [])
                + self.build_pagination(
                    unit_id=unit_id,
                    callback=callback,
                    total_pages=len(unit["photos"]),
                )
                + [
                    [
                        *(
                            [
                                {
                                    "text": "⏪",
                                    "callback": callback,
                                    "args": (unit["current_index"] - 1,),
                                }
                            ]
                            if unit["current_index"] > 0
                            else []
                        ),
                        *(
                            [
                                {
                                    "text": (
                                        "🛑" if unit.get("slideshow", False) else "⏱"
                                    ),
                                    "callback": callback,
                                    "args": ("slideshow",),
                                }
                            ]
                            if unit["current_index"] < len(unit["photos"]) - 1
                            or not isinstance(unit["next_handler"], ListGalleryHelper)
                            else []
                        ),
                        *(
                            [
                                {
                                    "text": "⏩",
                                    "callback": callback,
                                    "args": (unit["current_index"] + 1,),
                                }
                            ]
                            if unit["current_index"] < len(unit["photos"]) - 1
                            or not isinstance(unit["next_handler"], ListGalleryHelper)
                            else []
                        ),
                    ]
                ]
            )
            + [[{"text": "🔻 Close", "callback": callback, "args": ("close",)}]]
        )

    async def _gallery_inline_handler(self: "InlineManager", inline_query):
        for unit in self._units.copy().values():
            if (
                inline_query.from_user.id == self._me
                and inline_query.query == unit["uid"]
                and unit["type"] == "gallery"
            ):
                try:
                    try:
                        path = urlparse(unit["photo_url"]).path
                        ext = os.path.splitext(path)[1]
                    except Exception:
                        ext = None

                    args = {
                        "text": self._get_caption(unit["uid"], index=0),
                        "parse_mode": "HTML",
                        "buttons": self._gallery_markup(unit["uid"]),
                        "id": utils.rand(20),
                        "title": "Processing inline gallery",
                    }

                    if unit.get("gif", False) or ext in {".gif", ".mp4"}:
                        await inline_query.answer(
                            [
                                await inline_query.builder.document(
                                    unit["photo_url"],
                                    type="gif",
                                    **args,
                                )
                            ]
                        )
                        return

                    await inline_query.answer(
                        [
                            await inline_query.builder.photo(
                                unit["photo_url"],
                                id=args["id"],
                                text=args["text"],
                                parse_mode=args["parse_mode"],
                                buttons=args["buttons"],
                            )
                        ],
                        cache_time=0,
                    )
                except Exception as e:
                    if unit["uid"] in self._error_events:
                        self._error_events[unit["uid"]].set()
                        self._error_events[unit["uid"]] = e
