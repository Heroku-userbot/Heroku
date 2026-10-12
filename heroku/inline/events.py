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
import inspect
import logging
import typing
from asyncio import Event

from herokutl.tl.types import UpdateBotInlineSend

from .. import utils, security
from .types import BotInlineCall, InlineCall, InlineQuery, InlineUnit

if typing.TYPE_CHECKING:
    from ..inline.core import InlineManager

logger = logging.getLogger(__name__)


class Events(InlineUnit):
    async def _message_handler(self: "InlineManager", message):
        """Processes incoming messages"""
        if not message.is_private:
            return

        wrapped_message = self._bot_message(message)
        match True:
            case _ if (
                wrapped_message.chat.type != "private"
                or wrapped_message.text == "/start heroku init"
            ):
                return

        for mod in self._allmodules.modules:
            if (
                not hasattr(mod, "bot_watcher")
                or wrapped_message.text == "/start"
                and mod.__class__.__name__ != "InlineStuff"
            ):
                continue

            try:
                await mod.bot_watcher(wrapped_message)
            except Exception:
                logger.exception("Error on running bot watcher!")

    def _bot_message(self: "InlineManager", message):
        from .types import BotInlineMessage

        return BotInlineMessage(self, message=message)

    async def _inline_handler(self: "InlineManager", inline_query):
        """Inline query handler (forms' calls)"""
        wrapped_query = InlineQuery(inline_query=inline_query)
        inline_query.inline_manager = self
        if (
            not self._db.get(security.__name__, "allow_inline_query", False)
            and wrapped_query.from_user.id
            not in self._client.dispatcher.security.all_users
        ):
            return

        if not (query := wrapped_query.query):
            await self._query_help(wrapped_query)
            return

        cmd = query.split()[0].lower()
        if (
            cmd in self._allmodules.inline_handlers
            and await self.check_inline_security(
                func=self._allmodules.inline_handlers[cmd],
                user=wrapped_query.from_user.id,
            )
        ):
            try:
                if not (
                    result := await self._allmodules.inline_handlers[cmd](wrapped_query)
                ):
                    return
            except Exception:
                logger.exception("Error on running inline watcher!")
                return

            if isinstance(result, dict):
                result = [result]

            if not isinstance(result, list):
                logger.error(
                    "Got invalid type from inline handler. It must be `dict`, got `%s`",
                    type(result),
                )
                await wrapped_query.e500()
                return

            for res in result:
                mandatory = ["message", "photo", "gif", "video", "file"]
                if all(item not in res for item in mandatory):
                    logger.error(
                        (
                            "Got invalid type from inline handler. It must contain one"
                            " of `%s`"
                        ),
                        mandatory,
                    )
                    await wrapped_query.e500()
                    return

                if "file" in res and "mime_type" not in res:
                    logger.error(
                        "Got invalid type from inline handler. It contains field"
                        " `file`, so it must contain `mime_type` as well"
                    )

            try:
                await wrapped_query.answer(
                    [
                        await self._build_inline_result(wrapped_query, res)
                        for res in result
                    ],
                    cache_time=0,
                )
            except Exception:
                logger.exception(
                    "Exception when answering inline query with result from %s",
                    cmd,
                )
                return

        await self._form_inline_handler(wrapped_query)
        await self._gallery_inline_handler(wrapped_query)
        await self._list_inline_handler(wrapped_query)

    async def _build_inline_result(
        self: "InlineManager", query: InlineQuery, res: dict
    ):
        result_id = utils.rand(20)
        text_key = "message" if "message" in res else "caption"
        text = res.get(text_key)
        if (
            isinstance(text, str)
            and query.from_user.id == self._me
            and self._needs_premium_emoji_pre_edit(text)
        ):
            while len(self._pre_edits) >= 100:
                self._pre_edits.pop(next(iter(self._pre_edits)))
            self._pre_edits[result_id] = (text, res.get("reply_markup"))
            res = {
                **res,
                text_key: "🪐",
                "reply_markup": [[{"text": "­", "data": "­"}]],
            }

        buttons = self.generate_markup(res.get("reply_markup"))
        match True:
            case _ if "message" in res:
                return await query.builder.article(
                    title=self.sanitise_text(res["title"]),
                    description=self.sanitise_text(res.get("description")),
                    text=self.sanitise_text(res["message"]),
                    parse_mode="HTML",
                    link_preview=False,
                    thumb=self._web_document(res.get("thumb")),
                    buttons=buttons,
                    id=result_id,
                )
            case _ if "photo" in res:
                return await query.builder.photo(
                    res["photo"],
                    text=self.sanitise_text(res.get("caption")),
                    parse_mode="HTML",
                    buttons=buttons,
                    id=result_id,
                )
            case _ if "gif" in res:
                return await query.builder.document(
                    res["gif"],
                    title=self.sanitise_text(res.get("title")),
                    type="gif",
                    text=self.sanitise_text(res.get("caption")),
                    parse_mode="HTML",
                    buttons=buttons,
                    id=result_id,
                )
            case _ if "video" in res:
                return await query.builder.document(
                    res["video"],
                    title=self.sanitise_text(res.get("title")),
                    description=self.sanitise_text(res.get("description")),
                    type="video",
                    mime_type="video/mp4",
                    text=self.sanitise_text(res.get("caption")),
                    parse_mode="HTML",
                    buttons=buttons,
                    id=result_id,
                )
            case _:
                return await query.builder.document(
                    res["file"],
                    title=self.sanitise_text(res.get("title")),
                    description=self.sanitise_text(res.get("description")),
                    mime_type=res["mime_type"],
                    text=self.sanitise_text(res.get("caption")),
                    parse_mode="HTML",
                    buttons=buttons,
                    id=result_id,
                )

    async def _callback_query_handler(
        self: "InlineManager",
        call,
        reply_markup: None | (list[list[dict[str, typing.Any]]]) = None,
    ):
        """Callback query handler (buttons' presses)"""
        if reply_markup is None:
            reply_markup = []

        call_data = (
            call.data.decode("utf-8", errors="ignore")
            if isinstance(call.data, (bytes, bytearray))
            else call.data
        )
        user_id = call.sender_id

        for func in self._allmodules.callback_handlers.values():
            if await self.check_inline_security(func=func, user=user_id):
                try:
                    await func(
                        (InlineCall if call.via_inline else BotInlineCall)(
                            call, self, None
                        ),
                    )
                except Exception:
                    logger.exception("Error on running callback watcher!")
                    await call.answer(
                        "Error occured while processing request. More info in logs",
                        alert=True,
                    )
                    continue

        for unit_id, unit in self._units.copy().items():
            for button in utils.array_sum(unit.get("buttons", [])):
                if not isinstance(button, dict):
                    logger.warning(
                        "Can't process update, because of corrupted button: %s",
                        button,
                    )
                    continue

                if button.get("_callback_data") == call_data:
                    match True:
                        case _ if (
                            button.get("disable_security", False)
                            or unit.get("disable_security", False)
                            or (unit.get("force_me", False) and user_id == self._me)
                            or not unit.get("force_me", False)
                            and (
                                await self.check_inline_security(
                                    func=unit.get(
                                        "perms_map",
                                        lambda: self._client.dispatcher.security._default,
                                    )(),
                                    user=user_id,
                                )
                                if "message" in unit
                                else False
                            )
                        ):
                            pass
                        case _ if user_id not in (
                            self._client.dispatcher.security._owner
                            + unit.get("always_allow", [])
                            + button.get("always_allow", [])
                        ):
                            await call.answer(
                                self.translator.getkey("inline.button403")
                            )
                            return

                    try:
                        result = await button["callback"](
                            (InlineCall if call.via_inline else BotInlineCall)(
                                call, self, unit_id
                            ),
                            *button.get("args", []),
                            **button.get("kwargs", {}),
                        )
                    except Exception:
                        logger.exception("Error on running callback watcher!")
                        await call.answer(
                            (
                                "Error occurred while processing request. More info in"
                                " logs"
                            ),
                            alert=True,
                        )
                        return

                    return result

        if call_data in self._custom_map:
            match True:
                case _ if (
                    self._custom_map[call_data].get("disable_security", False)
                    or (
                        self._custom_map[call_data].get("force_me", False)
                        and user_id == self._me
                    )
                    or not self._custom_map[call_data].get("force_me", False)
                    and (
                        await self.check_inline_security(
                            func=self._custom_map[call_data].get(
                                "perms_map",
                                lambda: self._client.dispatcher.security._default,
                            )(),
                            user=user_id,
                        )
                        if "message" in self._custom_map[call_data]
                        else False
                    )
                ):
                    pass
                case (
                    _
                ) if user_id not in self._client.dispatcher.security._owner and user_id not in self._custom_map[
                    call_data
                ].get(
                    "always_allow", []
                ):
                    await call.answer(self.translator.getkey("inline.button403"))
                    return

            await self._custom_map[call_data]["handler"](
                (InlineCall if call.via_inline else BotInlineCall)(call, self, None),
                *self._custom_map[call_data].get("args", []),
                **self._custom_map[call_data].get("kwargs", {}),
            )
            return

    async def _chosen_inline_handler(
        self: "InlineManager",
        chosen_inline_query,
    ):
        if not isinstance(chosen_inline_query, UpdateBotInlineSend):
            return

        if pre_edit := self._pre_edits.pop(chosen_inline_query.id, None):
            if chosen_inline_query.msg_id:
                await asyncio.sleep(0.3)
                text, reply_markup = pre_edit
                await self.bot.edit_message_text(
                    text=self.sanitise_text(text),
                    inline_message_id=chosen_inline_query.msg_id,
                    reply_markup=self.generate_markup(reply_markup),
                )
            return

        query = chosen_inline_query.query

        if not query:
            return

        for unit_id, unit in self._units.items():
            if (
                unit_id == query
                and "future" in unit
                and isinstance(unit["future"], Event)
                and chosen_inline_query.user_id == self._me
            ):
                unit["inline_message_id"] = chosen_inline_query.msg_id
                unit["future"].set()
                return

        for unit_id, unit in self._units.copy().items():
            for button in utils.array_sum(unit.get("buttons", [])):
                if (
                    "_switch_query" in button
                    and "input" in button
                    and button["_switch_query"] == query.split()[0]
                    and chosen_inline_query.user_id
                    in [self._me]
                    + self._client.dispatcher.security._owner
                    + unit.get("always_allow", [])
                ):
                    query = query.split(maxsplit=1)[1] if len(query.split()) > 1 else ""

                    class ChosenInlineCall:
                        data = b""
                        chat_id = None
                        message_id = None

                        def __init__(self, update):
                            self.id = update.id
                            self.sender_id = update.user_id
                            self.query = update
                            self.query.msg_id = update.msg_id

                        async def answer(self, *args, **kwargs):
                            return None

                    try:
                        return await button["handler"](
                            InlineCall(
                                ChosenInlineCall(chosen_inline_query), self, unit_id
                            ),
                            query,
                            *button.get("args", []),
                            **button.get("kwargs", {}),
                        )
                    except Exception:
                        logger.exception(
                            "Exception while running chosen query watcher!"
                        )
                        return

    async def _query_help(self: "InlineManager", inline_query: InlineQuery):
        _help = []
        for name, fun in self._allmodules.inline_handlers.items():
            if not await self.check_inline_security(
                func=fun,
                user=inline_query.from_user.id,
            ):
                continue

            try:
                doc = inspect.getdoc(fun)
            except Exception:
                doc = "🦥 No docs"

            try:
                thumb = getattr(fun, "thumb_url", None) or fun.__self__.heroku_meta_pic
            except Exception:
                thumb = None

            thumb = thumb or "https://img.icons8.com/fluency/50/000000/info-squared.png"

            _help += [
                (
                    await inline_query.builder.article(
                        title=self.translator.getkey("inline.command").format(name),
                        description=doc,
                        text=(
                            self.translator.getkey("inline.command_msg").format(
                                utils.escape_html(name),
                                utils.escape_html(doc),
                            )
                        ),
                        parse_mode="HTML",
                        link_preview=False,
                        thumb=self._web_document(thumb),
                        buttons=self.generate_markup(
                            {
                                "text": self.translator.getkey("inline.run_command"),
                                "switch_inline_query_current_chat": f"{name} ",
                            }
                        ),
                        id=utils.rand(20),
                    ),
                    (
                        f"🎹 <code>@{self.bot_username} {utils.escape_html(name)}</code>"
                        f" - {utils.escape_html(doc)}\n"
                    ),
                )
            ]

        if not _help:
            await inline_query.answer(
                [
                    await inline_query.builder.article(
                        title=self.translator.getkey("inline.show_inline_cmds"),
                        description=self.translator.getkey("inline.no_inline_cmds"),
                        text=self.translator.getkey("inline.no_inline_cmds_msg"),
                        parse_mode="HTML",
                        link_preview=False,
                        thumb=self._web_document(
                            "https://img.icons8.com/fluency/50/000000/info-squared.png"
                        ),
                        id=utils.rand(20),
                    )
                ],
                cache_time=0,
            )
            return

        await inline_query.answer(
            [
                await inline_query.builder.article(
                    title=self.translator.getkey("inline.show_inline_cmds"),
                    description=(
                        self.translator.getkey("inline.inline_cmds").format(len(_help))
                    ),
                    text=(
                        self.translator.getkey("inline.inline_cmds_msg").format(
                            "\n".join(map(lambda x: x[1], _help))
                        )
                    ),
                    parse_mode="HTML",
                    link_preview=False,
                    thumb=self._web_document(
                        "https://img.icons8.com/fluency/50/000000/info-squared.png"
                    ),
                    id=utils.rand(20),
                )
            ]
            + [i[0] for i in _help],
            cache_time=0,
        )
