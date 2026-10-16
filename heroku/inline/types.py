import logging
import secrets
import typing

from herokutl.tl import types

from .._internal import normalize_rich_html

HerokuReplyMarkup = typing.Union[list[list[dict]], list[dict], dict]

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from .core import InlineManager


class InlineMessage:
    """Message sent via inline bot."""

    def __init__(
        self,
        inline_manager: "InlineManager",
        unit_id: str,
        inline_message_id,
    ):
        self.inline_message_id = inline_message_id
        self.unit_id = unit_id
        self.inline_manager = inline_manager
        self._units = inline_manager._units
        self.form = (
            {"id": unit_id, **self._units[unit_id]} if unit_id in self._units else {}
        )

    async def edit(self, *args, **kwargs) -> "InlineMessage":
        rich_message = kwargs.pop("rich_message", None)
        if rich_message is not None:
            rich_markup = (
                self.inline_manager.generate_markup(kwargs.get("reply_markup"))
                if kwargs.get("reply_markup") is not None
                else None
            )
            await self.inline_manager.bot.edit_rich_message(
                rich_message,
                inline_message_id=self.inline_message_id,
                reply_markup=rich_markup,
            )
            return self

        kwargs.pop("unit_id", None)
        kwargs.pop("inline_message_id", None)

        return await self.inline_manager._edit_unit(
            *args,
            unit_id=self.unit_id,
            inline_message_id=self.inline_message_id,
            **kwargs,
        )

    async def delete(self) -> bool:
        entity = self._units.get(self.unit_id)
        if not entity:
            if hasattr(self, "original_call"):
                return await self.original_call.answer("msg not found", alert=True)
            return False

        await self.inline_manager._client.delete_messages(
            entity.get("chat"),
            entity.get("message_id"),
        )
        if hasattr(self, "original_call"):
            return await self.original_call.answer("")
        return True

    async def unload(self) -> bool:
        return await self.inline_manager._unload_unit(unit_id=self.unit_id)


class _User:
    def __init__(self, user_id: int | None):
        self.id = user_id


class _Chat:
    def __init__(self, chat_id: int | None, type_: str = "private"):
        self.id = chat_id
        self.type = type_


class _MessageProxy:
    def __init__(
        self,
        inline_manager: "InlineManager",
        *,
        chat_id: int | None,
        message_id: int | None,
        sender_id: int | None = None,
        text: str = "",
        message=None,
    ):
        self.inline_manager = inline_manager
        self.chat = _Chat(chat_id)
        self.chat_id = chat_id
        self.message_id = message_id
        self.id = message_id
        self.from_user = _User(sender_id)
        self.sender_id = sender_id
        self.text = text
        self.raw_text = text
        self.message = text
        self._message = message
        self.message_thread_id = getattr(message, "message_thread_id", None)

    async def answer(self, text: str, **kwargs):
        return await self.inline_manager.bot.send_message(
            self.chat_id,
            text,
            reply_markup=kwargs.get("reply_markup"),
            message_thread_id=kwargs.get("message_thread_id"),
            rich_message=kwargs.get("rich_message"),
        )

    async def answer_photo(
        self, photo, *, caption: str = None, reply_markup=None, **kwargs
    ):
        return await self.inline_manager.bot.send_photo(
            self.chat_id,
            photo,
            caption=caption,
            reply_markup=reply_markup,
            message_thread_id=kwargs.get("message_thread_id"),
        )

    async def edit_text(self, text: str, *, reply_markup=None, **kwargs):
        return await self.inline_manager.bot.client.edit_message(
            self.chat_id,
            self.message_id,
            text,
            parse_mode="HTML",
            buttons=reply_markup,
        )


class BotInlineMessage:
    """Message sent through the inline bot itself."""

    def __init__(
        self,
        inline_manager: "InlineManager",
        unit_id: str | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
        message=None,
    ):
        if message is not None:
            chat_id = message.chat_id
            message_id = message.id

        self.chat_id = chat_id
        self.unit_id = unit_id
        self.inline_manager = inline_manager
        self.message_id = message_id
        self.id = message_id
        self._units = inline_manager._units
        self.form = (
            {"id": unit_id, **self._units[unit_id]}
            if unit_id and unit_id in self._units
            else {}
        )
        self._message = message
        self.text = getattr(message, "raw_text", "") if message is not None else ""
        self.raw_text = self.text
        self.message = self.text
        self.from_user = _User(getattr(message, "sender_id", None))
        self.sender_id = getattr(message, "sender_id", None)
        self.chat = _Chat(chat_id)

    async def answer(self, text: str, **kwargs):
        return await self.inline_manager.bot.send_message(
            self.chat_id,
            text,
            reply_markup=kwargs.get("reply_markup"),
            message_thread_id=kwargs.get("message_thread_id"),
            rich_message=kwargs.get("rich_message"),
        )

    async def answer_photo(
        self, photo, *, caption: str = None, reply_markup=None, **kwargs
    ):
        return await self.inline_manager.bot.send_photo(
            self.chat_id,
            photo,
            caption=caption,
            reply_markup=reply_markup,
            message_thread_id=kwargs.get("message_thread_id"),
        )

    async def edit(self, *args, **kwargs) -> "BotMessage":
        rich_message = kwargs.pop("rich_message", None)
        if rich_message is not None:
            rich_markup = (
                self.inline_manager.generate_markup(kwargs.get("reply_markup"))
                if kwargs.get("reply_markup") is not None
                else None
            )
            await self.inline_manager.bot.edit_rich_message(
                rich_message,
                chat_id=self.chat_id,
                message_id=self.message_id,
                reply_markup=rich_markup,
            )
            return self

        kwargs.pop("unit_id", None)
        kwargs.pop("message_id", None)
        kwargs.pop("chat_id", None)

        return await self.inline_manager._edit_unit(
            *args,
            unit_id=self.unit_id,
            chat_id=self.chat_id,
            message_id=self.message_id,
            **kwargs,
        )

    async def delete(self) -> bool:
        return await self.inline_manager._delete_unit_message(
            self,
            unit_id=self.unit_id,
            chat_id=self.chat_id,
            message_id=self.message_id,
        )

    async def unload(self, *args, **kwargs) -> bool:
        kwargs.pop("unit_id", None)
        return await self.inline_manager._unload_unit(
            *args,
            unit_id=self.unit_id,
            **kwargs,
        )


class _CallbackMixin:
    def _init_callback(self, call, inline_manager: "InlineManager"):
        self.original_call = call
        self.inline_manager = inline_manager
        self.data = (
            call.data.decode("utf-8", errors="ignore")
            if isinstance(call.data, (bytes, bytearray))
            else call.data
        )
        self.id = call.id
        self.from_user = _User(call.sender_id)
        self.sender_id = call.sender_id
        self.chat_id = call.chat_id
        self.message_id = call.message_id
        self.inline_message_id = (
            call.query.msg_id
            if isinstance(
                getattr(call.query, "msg_id", None),
                (types.InputBotInlineMessageID, types.InputBotInlineMessageID64),
            )
            else None
        )
        self.message = _MessageProxy(
            inline_manager,
            chat_id=call.chat_id,
            message_id=call.message_id,
            sender_id=call.sender_id,
        )

    async def answer(
        self,
        text: str | None = None,
        *,
        show_alert: bool = False,
        alert: bool | None = None,
        **kwargs,
    ):
        return await self.original_call.answer(
            text,
            alert=show_alert if alert is None else alert,
            cache_time=kwargs.get("cache_time", 0),
            url=kwargs.get("url"),
        )


class InlineCall(_CallbackMixin, InlineMessage):
    """Callback query for an inline message."""

    def __init__(
        self,
        call,
        inline_manager: "InlineManager",
        unit_id: str | None,
    ):
        self._init_callback(call, inline_manager)
        InlineMessage.__init__(
            self,
            inline_manager,
            unit_id,
            self.inline_message_id,
        )


class BotInlineCall(_CallbackMixin, BotInlineMessage):
    """Callback query for a bot-sent message."""

    def __init__(
        self,
        call,
        inline_manager: "InlineManager",
        unit_id: str | None,
    ):
        self._init_callback(call, inline_manager)
        BotInlineMessage.__init__(
            self,
            inline_manager,
            unit_id,
            call.chat_id,
            call.message_id,
        )
        self.message = _MessageProxy(
            inline_manager,
            chat_id=call.chat_id,
            message_id=call.message_id,
            sender_id=call.sender_id,
        )


class InlineUnit:
    """InlineManager extension type. For internal use only."""

    def __init__(self):
        """Made just for type specification."""


class BotMessage(_MessageProxy):
    pass


class InlineQuery:
    """Telethon-backed inline query wrapper."""

    def __init__(self, inline_query):
        self.inline_query = inline_query
        self.id = inline_query.id
        self.query = inline_query.text or ""
        self.text = self.query
        self.from_user = _User(inline_query.sender_id)
        self.sender_id = inline_query.sender_id
        self.args = (
            self.query.split(maxsplit=1)[1] if len(self.query.split()) > 1 else ""
        )

    def __getattr__(self, item: str):
        return getattr(self.inline_query, item)

    async def rich_article(
        self,
        title: str,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        description: str | None = None,
        id: str | None = None,
        buttons=None,
    ):
        if rich_message is None:
            if html is not None:
                rich_message = types.InputRichMessageHTML(
                    html=normalize_rich_html(html)
                )
            elif markdown is not None:
                rich_message = types.InputRichMessageMarkdown(markdown=markdown)
            else:
                raise ValueError("One of html, markdown or rich_message is required")

        markup = (
            self.inline_query.builder._client.build_reply_markup(buttons)
            if buttons is not None
            else None
        )
        return types.InputBotInlineResult(
            id=id or secrets.token_urlsafe(15),
            type="article",
            title=title,
            description=description,
            send_message=types.InputBotInlineMessageRichMessage(
                rich_message=rich_message,
                reply_markup=markup,
            ),
        )

    async def answer(self, results=None, cache_time: int = 0, **kwargs):
        return await self.inline_query.answer(
            results or [],
            cache_time=cache_time,
            private=kwargs.pop("is_personal", kwargs.pop("private", False)),
            **kwargs,
        )

    async def _get_res(self, title: str, description: str, thumbnail_url: str) -> list:
        return [
            await self.inline_query.builder.article(
                title=title,
                description=description,
                text="😶‍🌫️ <i>There is nothing here...</i>",
                parse_mode="HTML",
                link_preview=False,
                thumb=(
                    self.inline_query.inline_manager._web_document(thumbnail_url)
                    if hasattr(self.inline_query, "inline_manager")
                    else None
                ),
            )
        ]

    async def e400(self):
        await self.answer(
            await self._get_res(
                title="🚫 400",
                description=(
                    "Bad request. You need to pass right arguments, follow module's"
                    " documentation"
                ),
                thumbnail_url="https://img.icons8.com/color/344/swearing-male--v1.png",
            ),
            cache_time=0,
        )

    async def e403(self):
        await self.answer(
            await self._get_res(
                title="🚫 403",
                description="You have no permissions to access this result",
                thumbnail_url="https://img.icons8.com/external-wanicon-flat-wanicon/344/external-forbidden-new-normal-wanicon-flat-wanicon.png",
            ),
            cache_time=0,
        )

    async def e404(self):
        await self.answer(
            await self._get_res(
                title="🚫 404",
                description="No results found",
                thumbnail_url="https://img.icons8.com/external-justicon-flat-justicon/344/external-404-error-responsive-web-design-justicon-flat-justicon.png",
            ),
            cache_time=0,
        )

    async def e426(self):
        await self.answer(
            await self._get_res(
                title="🚫 426",
                description="You need to update Heroku before sending this request",
                thumbnail_url="https://img.icons8.com/fluency/344/approve-and-update.png",
            ),
            cache_time=0,
        )

    async def e500(self):
        await self.answer(
            await self._get_res(
                title="🚫 500",
                description="Internal userbot error while processing request",
                thumbnail_url="https://img.icons8.com/fluency/344/high-priority.png",
            ),
            cache_time=0,
        )
