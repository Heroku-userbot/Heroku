import io
import typing

from herokutl import Button
from herokutl.extensions import html as html_parser
from herokutl import utils as tl_utils
from herokutl.tl import types
from herokutl.tl.functions.messages import (
    EditInlineBotMessageRequest,
    EditMessageRequest,
    SendMessageRequest,
    SetInlineBotResultsRequest,
)
from herokutl.tl.types import (
    DocumentAttributeAudio,
    InputReplyToMessage,
    InputRichMessageHTML,
    InputRichMessageMarkdown,
)
from herokutl.tl import TLObject

from .._internal import normalize_rich_html


class TelethonBot:
    def __init__(self, client):
        self.client = client

    async def __call__(self, value):
        if isinstance(value, TLObject):
            return await self.client(value)
        if hasattr(value, "__await__"):
            return await value
        return value

    def __getattr__(self, item: str):
        return getattr(self.client, item)

    @staticmethod
    def _normalise_file(file):
        if isinstance(file, bytes):
            media = io.BytesIO(file)
            media.name = "file"
            return media

        if hasattr(file, "data"):
            media = io.BytesIO(file.data)
            media.name = getattr(file, "filename", "file")
            return media

        if hasattr(file, "seek"):
            try:
                file.seek(0)
            except Exception:
                pass

        return file

    @staticmethod
    def _thread_kwargs(message_thread_id: int | None) -> dict:
        return {"reply_to": message_thread_id} if message_thread_id else {}

    @staticmethod
    def _with_message_id_alias(message):
        if (
            message is not None
            and not hasattr(message, "message_id")
            and hasattr(message, "id")
        ):
            try:
                message.message_id = message.id
            except Exception:
                pass

        return message

    def _build_reply_markup(self, reply_markup):
        if reply_markup is None:
            return None
        if isinstance(
            reply_markup,
            (
                types.ReplyInlineMarkup,
                types.ReplyKeyboardMarkup,
                types.ReplyKeyboardHide,
                types.ReplyKeyboardForceReply,
            ),
        ):
            return reply_markup
        return self.client.build_reply_markup(reply_markup)

    @staticmethod
    def _peer_owner_id(peer) -> int:
        if isinstance(peer, types.PeerUser):
            return peer.user_id
        if isinstance(peer, types.PeerChannel):
            return peer.channel_id
        if isinstance(peer, types.PeerChat):
            return peer.chat_id
        raise TypeError(f"Unsupported inline peer type: {type(peer)!r}")

    @classmethod
    def _coerce_inline_message_id(cls, inline_message_id):
        if inline_message_id is None:
            return None

        if isinstance(
            inline_message_id,
            (types.InputBotInlineMessageID, types.InputBotInlineMessageID64),
        ):
            return inline_message_id

        if not isinstance(inline_message_id, str):
            raise TypeError(
                "inline_message_id must be str or InputBotInlineMessageID/64, "
                f"got {type(inline_message_id)!r}"
            )

        message_id, peer, dc_id, access_hash = tl_utils.resolve_inline_message_id(
            inline_message_id
        )

        if peer is None:
            raise ValueError(f"Invalid inline_message_id: {inline_message_id!r}")

        return types.InputBotInlineMessageID64(
            dc_id=dc_id,
            owner_id=cls._peer_owner_id(peer),
            id=message_id,
            access_hash=access_hash,
        )

    @staticmethod
    def _coerce_input_media(media):
        if media is None:
            return None

        if isinstance(
            media,
            (
                types.InputMediaDocument,
                types.InputMediaPhoto,
                types.InputMediaUploadedDocument,
                types.InputMediaUploadedPhoto,
                types.InputMediaWebPage,
                types.InputMediaEmpty,
            ),
        ):
            return media

        try:
            return tl_utils.get_input_media(media)
        except TypeError as e:
            raise TypeError(
                "For inline media edits pass a TL InputMedia object "
                "(InputMediaDocument, InputMediaPhoto, etc.), not raw bytes/path."
            ) from e

    async def get_me(self):
        return await self.client.get_me()

    async def send_message(
        self,
        chat_id,
        text: str = "",
        *,
        reply_markup=None,
        message_thread_id: int | None = None,
        disable_notification: bool | None = None,
        rich_message: str | None = None,
        **kwargs,
    ):
        if rich_message is not None:
            return await self.send_rich_message(
                chat_id,
                rich_message,
                reply_markup=reply_markup,
                message_thread_id=message_thread_id,
                disable_notification=disable_notification,
            )

        return self._with_message_id_alias(
            await self.client.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                buttons=reply_markup,
                silent=(
                    disable_notification
                    if disable_notification is not None
                    else kwargs.get("disable_notification")
                ),
                link_preview=not kwargs.get("disable_web_page_preview", False),
                **self._thread_kwargs(message_thread_id),
            )
        )

    @staticmethod
    def _rich_input(html=None, markdown=None, rich_message=None):
        if rich_message is not None:
            return rich_message
        if html is not None:
            return InputRichMessageHTML(html=normalize_rich_html(html))
        if markdown is not None:
            return InputRichMessageMarkdown(markdown=markdown)
        raise ValueError("One of html, markdown or rich_message is required")

    @staticmethod
    def _rich_fallback_text(html=None, markdown=None, rich_message=None):
        if html:
            text, _ = html_parser.parse(html)
            return text or " "
        if markdown:
            return str(markdown) or " "
        if rich_message is not None:
            rich_html = getattr(rich_message, "html", None)
            if rich_html:
                text, _ = html_parser.parse(rich_html)
                return text or " "
            rich_markdown = getattr(rich_message, "markdown", None)
            if rich_markdown:
                return str(rich_markdown)
            try:
                from ..utils.rich import rich_message_to_html

                text, _ = html_parser.parse(rich_message_to_html(rich_message))
                return text or " "
            except Exception:
                return " "
        return " "

    async def send_rich_message(
        self,
        chat_id,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        reply_markup=None,
        message_thread_id: int | None = None,
        disable_notification: bool | None = None,
    ):
        if html is not None and not isinstance(html, str):
            raise TypeError("html must be a str")

        entity = await self.client.get_input_entity(chat_id)
        rich_input = self._rich_input(html, markdown, rich_message)
        request = SendMessageRequest(
            peer=entity,
            message=self._rich_fallback_text(html, markdown, rich_message),
            no_webpage=True,
            silent=disable_notification,
            reply_to=(
                InputReplyToMessage(message_thread_id)
                if message_thread_id is not None
                else None
            ),
            reply_markup=self.client.build_reply_markup(reply_markup),
            rich_message=rich_input,
        )
        result = await self.client(request)
        return self.client._get_response_message(request, result, entity)

    async def edit_rich_message(
        self,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        inline_message_id=None,
        chat_id=None,
        message_id=None,
        reply_markup=None,
    ):
        if html is not None and not isinstance(html, str):
            raise TypeError("html must be a str")

        markup = self._build_reply_markup(reply_markup)
        rich_input = self._rich_input(html, markdown, rich_message)
        fallback_text = self._rich_fallback_text(html, markdown, rich_message)
        if inline_message_id is not None:
            request = EditInlineBotMessageRequest(
                id=self._coerce_inline_message_id(inline_message_id),
                message=fallback_text,
                no_webpage=True,
                rich_message=rich_input,
                reply_markup=markup,
            )
            return await self.client(request)

        entity = await self.client.get_input_entity(chat_id)
        request = EditMessageRequest(
            peer=entity,
            id=message_id,
            message=fallback_text,
            no_webpage=True,
            rich_message=rich_input,
            reply_markup=markup,
        )
        return await self.client(request)

    async def send_document(
        self,
        chat_id,
        document,
        *,
        caption: str | None = None,
        reply_markup=None,
        message_thread_id: int | None = None,
        **kwargs,
    ):
        return self._with_message_id_alias(
            await self.client.send_file(
                chat_id,
                self._normalise_file(document),
                caption=caption,
                parse_mode="HTML",
                force_document=True,
                buttons=reply_markup,
                silent=kwargs.get("disable_notification"),
                **self._thread_kwargs(message_thread_id),
            )
        )

    async def send_photo(
        self,
        chat_id,
        photo,
        *,
        caption: str | None = None,
        reply_markup=None,
        message_thread_id: int | None = None,
        **kwargs,
    ):
        return self._with_message_id_alias(
            await self.client.send_file(
                chat_id,
                self._normalise_file(photo),
                caption=caption,
                parse_mode="HTML",
                buttons=reply_markup,
                silent=kwargs.get("disable_notification"),
                **self._thread_kwargs(message_thread_id),
            )
        )

    async def send_audio(
        self,
        chat_id,
        audio,
        *,
        title: str | None = None,
        performer: str | None = None,
        duration: int | None = None,
        thumbnail=None,
        reply_markup=None,
        message_thread_id: int | None = None,
        **kwargs,
    ):
        attributes = [
            DocumentAttributeAudio(
                duration=duration or 0,
                title=title,
                performer=performer,
            )
        ]
        return self._with_message_id_alias(
            await self.client.send_file(
                chat_id,
                self._normalise_file(audio),
                attributes=attributes,
                thumb=(
                    self._normalise_file(thumbnail) if thumbnail is not None else None
                ),
                buttons=reply_markup,
                silent=kwargs.get("disable_notification"),
                **self._thread_kwargs(message_thread_id),
            )
        )

    async def delete_message(self, chat_id, message_id):
        return await self.client.delete_messages(chat_id, message_id)

    async def answer_inline_query(
        self,
        inline_query_id: int,
        results: list,
        *,
        cache_time: int = 0,
        is_personal: bool = False,
        next_offset: str | None = None,
        **kwargs,
    ):
        prepared = []
        for item in results:
            if hasattr(item, "__await__"):
                item = await item
            prepared.append(item)

        return await self.client(
            SetInlineBotResultsRequest(
                query_id=inline_query_id,
                results=prepared,
                cache_time=cache_time,
                private=is_personal,
                next_offset=next_offset or "",
                gallery=kwargs.get("gallery", False),
            )
        )

    async def edit_message_media(
        self,
        *,
        inline_message_id: typing.Any = None,
        chat_id: typing.Any = None,
        message_id: typing.Any = None,
        media=None,
        reply_markup: typing.Any = None,
        **kwargs,
    ):
        if inline_message_id is not None:
            inline_id = self._coerce_inline_message_id(inline_message_id)
            input_media = self._coerce_input_media(media)
            markup = self._build_reply_markup(reply_markup)
            return await self.client(
                EditInlineBotMessageRequest(
                    id=inline_id,
                    media=input_media,
                    reply_markup=markup,
                )
            )

        return await self.client.edit_message(
            chat_id,
            message_id,
            file=media,
            buttons=reply_markup,
        )

    async def edit_message_text(
        self,
        *,
        text: str,
        inline_message_id: typing.Any = None,
        chat_id: typing.Any = None,
        message_id: typing.Any = None,
        reply_markup: typing.Any = None,
        disable_web_page_preview: bool = True,
        **kwargs: typing.Any,
    ) -> typing.Any:
        markup = self._build_reply_markup(reply_markup)

        if inline_message_id is not None:
            inline_id = self._coerce_inline_message_id(inline_message_id)
            return await self.client.edit_message(
                inline_id,
                text,
                parse_mode="HTML",
                link_preview=not disable_web_page_preview,
                buttons=markup,
            )

        return await self.client.edit_message(
            chat_id,
            message_id,
            text,
            parse_mode="HTML",
            link_preview=not disable_web_page_preview,
            buttons=markup,
        )

    async def edit_message_reply_markup(
        self,
        *,
        inline_message_id: typing.Any = None,
        chat_id: typing.Any = None,
        message_id: typing.Any = None,
        reply_markup: typing.Any = None,
    ):
        markup = self._build_reply_markup(reply_markup)

        if inline_message_id is not None:
            inline_id = self._coerce_inline_message_id(inline_message_id)
            return await self.client(
                EditInlineBotMessageRequest(
                    id=inline_id,
                    reply_markup=markup,
                )
            )

        return await self.client.edit_message(
            chat_id,
            message_id,
            buttons=markup,
        )


def web_document(
    url: str | None,
    *,
    mime_type: str = "image/jpeg",
    width: int = 128,
    height: int = 128,
) -> types.InputWebDocument | None:
    if not url:
        return None

    return types.InputWebDocument(
        url=url,
        size=0,
        mime_type=mime_type,
        attributes=[
            types.DocumentAttributeImageSize(
                w=width,
                h=height,
            )
        ],
    )


def make_button(
    *,
    text: str,
    style: str | None = None,
    icon: str | None = None,
    url: str | None = None,
    data: str | bytes | None = None,
    switch_inline_query_current_chat: str | None = None,
    switch_inline_query: str | None = None,
    web_app: str | dict | None = None,
    copy_text: str | None = None,
):
    if url is not None:
        return Button.url(text, url, style=style, icon=icon)

    if data is not None:
        return Button.inline(text, data, style=style, icon=icon)

    if switch_inline_query_current_chat is not None:
        return Button.switch_inline(
            text,
            switch_inline_query_current_chat,
            same_peer=True,
            style=style,
            icon=icon,
        )

    if switch_inline_query is not None:
        return Button.switch_inline(
            text,
            switch_inline_query,
            same_peer=False,
            style=style,
            icon=icon,
        )

    if web_app is not None:
        app_url = web_app if isinstance(web_app, str) else web_app["url"]
        return types.KeyboardInlineButton(text, types.InlineButtonTypeWebView(url=app_url))

    if copy_text is not None:
        return types.KeyboardInlineButton(text, types.InlineButtonTypeCopy(copy_text=copy_text))

    return Button.inline(text, text, style=style, icon=icon)
