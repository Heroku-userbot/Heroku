# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import contextlib
import io
import json
import logging
import re
import typing

import grapheme
import herokutl
from herokutl.errors import RPCError, WebpageMediaEmptyError
from herokutl.tl.custom import Message
from herokutl.tl.types import (
    Channel,
    Chat,
    InputDocument,
    InputReplyToMessage,
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    MessageReplyHeader,
)

from .other import _copy_tl
from .entity import get_chat_id, FormattingEntity

from ..inline.types import BotInlineCall, BotInlineMessage, InlineCall, InlineMessage
from ..types import HerokuReplyMarkup, ListLike

emoji_pattern = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f1e0-\U0001f1ff"  # flags (iOS)
    "]+",
    flags=re.UNICODE,
)

parser = herokutl.utils.sanitize_parse_mode("html")
logger = logging.getLogger(__name__)


def get_topic(message: Message) -> int | None:
    """
    Get topic id of message
    :param message: Message to get topic of
    :return: int or None if not present
    """
    if isinstance(message, (InlineCall, InlineMessage)):
        return message.form["top_msg_id"]

    if not isinstance(message, Message):
        return None

    reply_to = message.reply_to
    if isinstance(reply_to, MessageReplyHeader):
        if reply_to.forum_topic:
            return reply_to.reply_to_top_id or reply_to.reply_to_msg_id
        return None
    if isinstance(reply_to, InputReplyToMessage):
        return reply_to.top_msg_id
    return None


def mime_type(message: Message) -> str:
    """
    Get mime type of document in message
    :param message: Message with document
    :return: Mime type or empty string if not present
    """
    return (
        ""
        if not isinstance(message, Message) or not getattr(message, "media", False)
        else getattr(getattr(message, "media", False), "mime_type", False) or ""
    )


async def get_message_link(
    message: Message,
    chat: Chat | Channel | None = None,
) -> str:
    """
    Get link to message
    :param message: Message to get link of
    :param chat: Chat, where message was sent
    :return: Link to message
    """
    if message.is_private:
        return (
            f"tg://openmessage?user_id={get_chat_id(message)}&message_id={message.id}"
        )

    if not chat and not (chat := message.chat):
        chat = await message.get_chat()

    topic_affix = (
        f"?topic={message.reply_to.reply_to_msg_id}"
        if getattr(message.reply_to, "forum_topic", False)
        else ""
    )

    return (
        f"https://t.me/{chat.username}/{message.id}{topic_affix}"
        if getattr(chat, "username", False)
        else f"https://t.me/c/{chat.id}/{message.id}{topic_affix}"
    )


def smart_split(
    text: str,
    entities: list[FormattingEntity],
    length: int = 4096,
    split_on: ListLike = ("\n", " "),
    min_length: int = 1,
) -> typing.Iterator[str]:
    """
    Split the message into smaller messages.
    A grapheme will never be broken. Entities will be displaced to match the right location. No inputs will be mutated.
    The end of each message except the last one is stripped of characters from [split_on]
    :param text: the plain text input
    :param entities: the entities
    :param length: the maximum length of a single message
    :param split_on: characters (or strings) which are preferred for a message break
    :param min_length: ignore any matches on [split_on] strings before this number of characters into each message
    :return: iterator, which returns strings

    :example:
        >>> utils.smart_split(
            *herokutl.extensions.html.parse(
                "<b>Hello, world!</b>"
            )
        )
        <<< ["<b>Hello, world!</b>"]
    """

    # Authored by @bsolute

    encoded = text.encode("utf-16le")
    pending_entities = entities
    text_offset = 0
    bytes_offset = 0
    text_length = len(text)
    bytes_length = len(encoded)

    while text_offset < text_length:
        if bytes_offset + length * 2 >= bytes_length:
            yield parser.unparse(
                text[text_offset:],
                list(sorted(pending_entities, key=lambda x: (x.offset, -x.length))),
            )
            break

        codepoint_count = len(
            encoded[bytes_offset : bytes_offset + length * 2].decode(
                "utf-16le",
                errors="ignore",
            )
        )

        for search in split_on:
            search_index = text.rfind(
                search,
                text_offset + min_length,
                text_offset + codepoint_count,
            )
            if search_index != -1:
                break
        else:
            search_index = text_offset + codepoint_count

        split_index = grapheme.safe_split_index(text, search_index)

        split_offset_utf16 = (
            len(text[text_offset:split_index].encode("utf-16le"))
        ) // 2
        exclude = 0

        while (
            split_index + exclude < text_length
            and text[split_index + exclude] in split_on
        ):
            exclude += 1

        current_entities = []
        entities = pending_entities.copy()
        pending_entities = []

        for entity in entities:
            match True:
                case _ if (
                    entity.offset < split_offset_utf16
                    and entity.offset + entity.length > split_offset_utf16 + exclude
                ):
                    current_entities.append(
                        _copy_tl(
                            entity,
                            length=split_offset_utf16 - entity.offset,
                        )
                    )
                    pending_entities.append(
                        _copy_tl(
                            entity,
                            offset=0,
                            length=entity.offset
                            + entity.length
                            - split_offset_utf16
                            - exclude,
                        )
                    )
                case _ if (
                    entity.offset < split_offset_utf16 < entity.offset + entity.length
                ):
                    current_entities.append(
                        _copy_tl(
                            entity,
                            length=split_offset_utf16 - entity.offset,
                        )
                    )
                case _ if entity.offset < split_offset_utf16:
                    current_entities.append(entity)
                case _ if (
                    entity.offset + entity.length
                    > split_offset_utf16 + exclude
                    > entity.offset
                ):
                    pending_entities.append(
                        _copy_tl(
                            entity,
                            offset=0,
                            length=entity.offset
                            + entity.length
                            - split_offset_utf16
                            - exclude,
                        )
                    )
                case _ if entity.offset + entity.length > split_offset_utf16 + exclude:
                    pending_entities.append(
                        _copy_tl(
                            entity,
                            offset=entity.offset - split_offset_utf16 - exclude,
                        )
                    )

        current_text = text[text_offset:split_index]
        yield parser.unparse(
            current_text,
            list(sorted(current_entities, key=lambda x: (x.offset, -x.length))),
        )

        text_offset = split_index + exclude
        bytes_offset += len(current_text.encode("utf-16le"))


def array_sum(array: list[list[typing.Any]], /) -> list[typing.Any]:
    """
    Performs basic sum operation on array
    :param array: Array to sum
    :return: Sum of array
    """
    result = []
    for item in array:
        result += item

    return result


async def _send_rich_message(
    message: Message,
    html: typing.Any,
    *,
    reply_to: int | None = None,
    reply_markup=None,
    silent: bool | None = None,
):
    return await message.client.send_rich_message(
        message.peer_id,
        html,
        reply_to=reply_to,
        buttons=reply_markup,
        silent=silent,
    )


async def _edit_rich_message(
    message: Message,
    html: typing.Any,
    *,
    reply_markup=None,
):
    return await message.client.edit_rich_message(
        message.peer_id,
        message,
        html,
        buttons=reply_markup,
    )


async def _edit_inline_rich_message(
    message,
    rich_message: str,
    reply_markup=None,
):
    unit = getattr(message, "form", None) or {}
    caller = unit.get("caller")
    if caller is None:
        caller = unit.get("chat")
    if caller is None:
        caller = getattr(message, "chat_id", None)
    if caller is not None and hasattr(message, "inline_manager"):
        with contextlib.suppress(Exception):
            await message.delete()
        return await message.inline_manager.form(
            "",
            caller,
            reply_markup=reply_markup or [],
            rich_message=rich_message,
            reply_to=unit.get("top_msg_id"),
            silent=True,
            ttl=600,
        )
    rich_markup = (
        message.inline_manager.generate_markup(reply_markup)
        if reply_markup is not None
        else None
    )
    if isinstance(message, (InlineMessage, InlineCall)):
        await message.inline_manager.bot.edit_rich_message(
            rich_message,
            inline_message_id=message.inline_message_id,
            reply_markup=rich_markup,
        )
    else:
        await message.inline_manager.bot.edit_rich_message(
            rich_message,
            chat_id=message.chat_id,
            message_id=message.message_id,
            reply_markup=rich_markup,
        )
    return message


async def answer_with_media_fallback(message, *args, **kwargs):
    try:
        return await answer(message, *args, **kwargs)
    except RPCError as error:
        if not isinstance(error, WebpageMediaEmptyError) and getattr(
            error, "message", None
        ) not in {"RICH_MESSAGE_PHOTO_NO_MEDIA_FOUND", "EXTERNAL_MEDIA_NOT_SUPPORTED"}:
            raise
        rich_message = kwargs.get("rich_message")
        if rich_message:
            without_images = re.sub(
                r"<img\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>",
                "",
                rich_message,
                flags=re.IGNORECASE,
            )
            if without_images == rich_message:
                raise
            kwargs["rich_message"] = without_images
        elif not kwargs.get("file"):
            raise
        kwargs.pop("file", None)
        kwargs.pop("invert_media", None)
        kwargs["link_preview"] = False
    return await answer(message, *args, **kwargs)


async def answer(
    message: Message | InlineCall | InlineMessage,
    response: str = "",
    *,
    reply_markup: HerokuReplyMarkup | None = None,
    rich_message: str | None = None,
    rich: bool = False,
    **kwargs,
) -> InlineCall | InlineMessage | Message:
    """
    Use this to give the response to a command
    :param message: Message to answer to. Can be a tl message or heroku inline object
    :param response: Response to send
    :param reply_markup: Reply markup to send. If specified, inline form will be used
    :return: Message or inline object

    :example:
        >>> await utils.answer(message, "Hello world!")
        >>> await utils.answer(
            message,
            "https://some-url.com/photo.jpg",
            caption="Hello, this is your photo!",
            asfile=True,
        )
        >>> await utils.answer(
            message,
            "Hello world!",
            reply_markup={"text": "Hello!", "data": "world"},
            silent=True,
            disable_security=True,
        )
    """
    # Compatibility with FTG\GeekTG

    if isinstance(message, list) and message:
        message = message[0]

    if rich and rich_message is None:
        if not isinstance(response, str):
            raise TypeError("response must be a string when rich=True")
        rich_message = response

    if rich_message is not None:
        rich_filter = getattr(message, "_heroku_grep_rich", None)
        if callable(rich_filter):
            rich_message = rich_filter(rich_message)

        if isinstance(
            message,
            (InlineMessage, InlineCall, BotInlineMessage, BotInlineCall),
        ):
            return await _edit_inline_rich_message(
                message,
                rich_message,
                reply_markup=reply_markup,
            )

        if reply_markup or not getattr(
            getattr(message.client, "heroku_me", None), "premium", False
        ):
            inline = message.client.loader.inline
            form_kwargs = {
                key: kwargs[key]
                for key in (
                    "force_me", "always_allow", "manual_security",
                    "disable_security", "on_unload",
                )
                if key in kwargs
            }
            return await inline.form(
                text=response or "Rich message",
                message=message if message.out else get_chat_id(message),
                rich_message=rich_message,
                reply_markup=inline._normalize_markup(reply_markup)
                if reply_markup else [],
                reply_to=kwargs.get("reply_to")
                or getattr(message, "reply_to_msg_id", None)
                or get_topic(message),
                silent=kwargs.get("silent", True),
                ttl=kwargs.get("ttl", 600),
                **form_kwargs,
            )

        edit = message.out and not message.via_bot_id and not message.fwd_from
        if edit:
            return await _edit_rich_message(
                message,
                rich_message,
                reply_markup=reply_markup,
            )

        return await _send_rich_message(
            message,
            rich_message,
            reply_to=kwargs.pop("reply_to", None)
            or getattr(message, "reply_to_msg_id", None)
            or get_topic(message),
            reply_markup=reply_markup,
            silent=kwargs.pop("silent", None),
        )

    if reply_markup is not None:
        if not isinstance(reply_markup, (list, dict)):
            raise ValueError("reply_markup must be a list or dict")

        if reply_markup:
            kwargs.pop("message", None)
            kwargs.pop("parse_mode", None)
            if isinstance(message, (InlineMessage, InlineCall, BotInlineCall)):
                await message.edit(response, reply_markup, **kwargs)
                return

            reply_markup = message.client.loader.inline._normalize_markup(reply_markup)
            result = await message.client.loader.inline.form(
                response,
                message=message if message.out else get_chat_id(message),
                reply_markup=reply_markup,
                **kwargs,
            )
            return result

    if isinstance(message, (InlineMessage, InlineCall, BotInlineCall)):
        await message.edit(response)
        return message

    kwargs.setdefault("link_preview", False)

    edit = message.out and not message.via_bot_id and not message.fwd_from
    match True:
        case _ if not edit:
            kwargs.setdefault(
                "reply_to",
                getattr(message, "reply_to_msg_id", None),
            )
        case _ if "reply_to" in kwargs:
            kwargs.pop("reply_to")

    parse_mode = herokutl.utils.sanitize_parse_mode(
        kwargs.pop(
            "parse_mode",
            message.client.parse_mode,
        )
    )

    if isinstance(response, str) and not kwargs.pop("asfile", False):
        text, entities = parse_mode.parse(response) if parse_mode else (response, [])

        if len(text) >= 4096 and not hasattr(message, "heroku_grepped"):
            try:
                if not message.client.loader.inline.init_complete:
                    raise

                strings = list(smart_split(text, entities, 4096))

                if len(strings) > 10:
                    raise

                list_ = await message.client.loader.inline.list(
                    message=message,
                    strings=strings,
                )

                if not list_:
                    raise

                return list_
            except Exception:
                file = io.BytesIO(text.encode("utf-8"))
                file.name = "command_result.txt"

                result = await message.client.send_file(
                    message.peer_id,
                    file,
                    caption=message.client.loader.lookup("translations").strings(
                        "too_long"
                    ),
                    reply_to=kwargs.get("reply_to") or get_topic(message),
                )

                if message.out:
                    await message.delete()

                return result

        if edit:
            result = await message.edit(
                text,
                parse_mode=lambda t: (t, entities),
                **kwargs,
            )
        else:
            file = kwargs.pop("file", None)
            invert_media = kwargs.pop("invert_media", False)

            if file is not None and invert_media:
                reply_to = kwargs.pop("reply_to", None)

                sent = await message.respond(
                    text,
                    parse_mode=lambda t: (t, entities),
                    reply_to=reply_to,
                    **kwargs,
                )

                result = await sent.edit(
                    text,
                    file=file,
                    parse_mode=lambda t: (t, entities),
                    invert_media=True,
                    **{k: v for k, v in kwargs.items() if k != "reply_to"},
                )
            elif file is not None:
                reply_to = kwargs.pop(
                    "reply_to",
                    getattr(message, "reply_to_msg_id", get_topic(message)),
                )
                result = await message.client.send_file(
                    message.peer_id,
                    file,
                    caption=text,
                    parse_mode=lambda t: (t, entities),
                    reply_to=reply_to,
                    **kwargs,
                )
                if message.out:
                    await message.delete()
            else:
                result = await message.respond(
                    text,
                    parse_mode=lambda t: (t, entities),
                    **kwargs,
                )
    elif isinstance(response, Message):
        if message.media is None and (
            response.media is None
            or isinstance(
                response.media,
                (MessageMediaWebPage, MessageMediaPhoto, MessageMediaDocument),
            )
        ):
            result = await message.edit(
                response.message,
                file=response.media,
                parse_mode=lambda t: (t, response.entities or []),
                link_preview=isinstance(response.media, MessageMediaWebPage),
            )
        else:
            result = await message.respond(response, **kwargs)
    else:
        if isinstance(response, bytes):
            response = io.BytesIO(response)
        elif isinstance(response, str):
            response = io.BytesIO(response.encode("utf-8"))

        if name := kwargs.pop("filename", None):
            response.name = name

        if message.media is not None and edit:
            result = await message.edit(file=response, **kwargs)
        else:
            kwargs.setdefault(
                "reply_to",
                getattr(message, "reply_to_msg_id", get_topic(message)),
            )
            result = await message.client.send_file(message.peer_id, response, **kwargs)
            if message.out:
                await message.delete()

    return result


async def answer_file(
    message: Message | InlineCall | InlineMessage,
    file: str | bytes | io.IOBase | InputDocument,
    caption: str | None = None,
    **kwargs,
):
    """
    Use this to answer a message with a document
    :param message: Message to answer
    :param file: File to send - url, path or bytes
    :param caption: Caption to send
    :param kwargs: Extra kwargs to pass to `send_file`
    :return: Sent message

    :example:
        >>> await utils.answer_file(message, "test.txt")
        >>> await utils.answer_file(
            message,
            "https://mods.hikariatama.ru/badges/artai.jpg",
            "This is the cool module, check it out!",
        )
    """
    if isinstance(message, (InlineCall, InlineMessage)):
        message = message.form["caller"]

    if topic := get_topic(message):
        kwargs.setdefault("reply_to", topic)

    try:
        response = await message.client.send_file(
            message.peer_id,
            file,
            caption=caption,
            **kwargs,
        )
    except Exception:
        if caption:
            logger.warning(
                "Failed to send file, sending plain text instead", exc_info=True
            )
            return await answer(message, caption, **kwargs)

        raise

    with contextlib.suppress(Exception):
        await message.delete()

    return response


def censor(
    obj: typing.Any,
    to_censor: typing.Iterable[str] | None = None,
    replace_with: str = "redacted_{count}_chars",
):
    """
    May modify the original object, but don't rely on it
    :param obj: Object to censor, preferrably telethon
    :param to_censor: Iterable of strings to censor
    :param replace_with: String to replace with, {count} will be replaced with the number of characters
    :return: Censored object
    """
    if to_censor is None:
        to_censor = ["phone"]

    for k, v in vars(obj).items():
        if k in to_censor:
            setattr(obj, k, replace_with.format(count=len(v)))
        elif k[0] != "_" and hasattr(v, "__dict__"):
            setattr(obj, k, censor(v, to_censor, replace_with))

    return obj


def is_serializable(x: typing.Any, /) -> bool:
    """
    Checks if object is JSON-serializable
    :param x: Object to check
    :return: True if object is JSON-serializable, False otherwise
    """
    try:
        json.dumps(x)
        return True
    except Exception:
        return False


def extract_urls(text: str) -> list[str]:
    """
    Extract all URLs from text
    :param text: Text to extract URLs from
    :return: List of URLs
    """
    url_regex = re.compile(r"https?://[^\s]+")
    return url_regex.findall(text)


def has_media(message: Message) -> bool:
    """
    Check if message contains media
    :param message: Message to check
    :return: True if message has media, False otherwise
    """
    return isinstance(
        message.media, (MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage)
    )
