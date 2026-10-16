# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import inspect
import logging
import random
import re
import string
import time
import typing
from urllib.parse import urlparse

import emoji
import herokutl
import requests
from herokutl import hints
from herokutl.tl.custom.message import Message
from herokutl.tl.functions.account import UpdateNotifySettingsRequest
from herokutl.tl.functions.channels import CreateChannelRequest, EditPhotoRequest
from herokutl.tl.functions.messages import (
    CreateForumTopicRequest,
    EditForumTopicRequest,
    GetDialogFiltersRequest,
    GetForumTopicsByIDRequest,
    GetForumTopicsRequest,
    SetHistoryTTLRequest,
    UpdateDialogFilterRequest,
)
from herokutl.tl.types import (
    Channel,
    ForumTopic,
    ForumTopicDeleted,
    InputPeerNotifySettings,
    MessageEntityBankCard,
    MessageEntityBlockquote,
    MessageEntityBold,
    MessageEntityBotCommand,
    MessageEntityCashtag,
    MessageEntityCode,
    MessageEntityEmail,
    MessageEntityHashtag,
    MessageEntityItalic,
    MessageEntityMention,
    MessageEntityMentionName,
    MessageEntityPhone,
    MessageEntityPre,
    MessageEntitySpoiler,
    MessageEntityStrike,
    MessageEntityTextUrl,
    MessageEntityUnderline,
    MessageEntityUnknown,
    MessageEntityUrl,
    PeerChannel,
    PeerChat,
    PeerUser,
    UpdateNewChannelMessage,
    User,
)

from .._internal import fw_protect
from ..tl_cache import CustomTelegramClient
from ..types import Module
from .other import invite_inline_bot, run_sync

FormattingEntity = typing.Union[
    MessageEntityUnknown,
    MessageEntityMention,
    MessageEntityHashtag,
    MessageEntityBotCommand,
    MessageEntityUrl,
    MessageEntityEmail,
    MessageEntityBold,
    MessageEntityItalic,
    MessageEntityCode,
    MessageEntityPre,
    MessageEntityTextUrl,
    MessageEntityMentionName,
    MessageEntityPhone,
    MessageEntityCashtag,
    MessageEntityUnderline,
    MessageEntityStrike,
    MessageEntityBlockquote,
    MessageEntityBankCard,
    MessageEntitySpoiler,
]

parser = herokutl.utils.sanitize_parse_mode("html")
logger = logging.getLogger(__name__)

TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9\-]*)(?:\s[^<>]*)?>")

TELEGRAM_HTML_TAGS = {
    "strong",
    "b",
    "em",
    "i",
    "tg-spoiler",
    "u",
    "del",
    "s",
    "blockquote",
    "code",
    "pre",
    "a",
    "tg-emoji",
    "emoji",
}


def get_lang_flag(countrycode: str) -> str:
    """
    Gets an emoji of specified countrycode
    :param countrycode: 2-letter countrycode
    :return: Emoji flag
    """
    if (
        len(
            code := [
                c
                for c in countrycode.lower()
                if c in string.ascii_letters + string.digits
            ]
        )
        == 2
    ):
        return "".join([chr(ord(c.upper()) + (ord("🇦") - ord("A"))) for c in code])

    return countrycode


def get_entity_url(
    entity: User | Channel,
    openmessage: bool = False,
) -> str:
    """
    Get link to object, if available
    :param entity: Entity to get url of
    :param openmessage: Use tg://openmessage link for users
    :return: Link to object or empty string
    """
    return (
        (
            f"tg://openmessage?id={entity.id}"
            if openmessage
            else f"tg://user?id={entity.id}"
        )
        if isinstance(entity, User)
        else (
            f"tg://resolve?domain={entity.username}"
            if getattr(entity, "username", None)
            else ""
        )
    )


def get_link(user: User | Channel, /) -> str:
    """
    Get telegram permalink to entity
    :param user: User or channel
    :return: Link to entity
    """
    return get_entity_url(user)



def remove_emoji(text: str) -> str:
    """
    Removes all emoji from text
    """

    allchars = [str for str in text]
    emoji_list = [c for c in allchars if c in emoji.EMOJI_DATA]
    clean_text = "".join([str for str in text if not any(i in str for i in emoji_list)])
    return clean_text


def remove_html(text: str, escape: bool = False, keep_emojis: bool = False) -> str:
    """
    Removes HTML tags from text
    :param text: Text to remove HTML from
    :param escape: Escape HTML
    :param keep_emojis: Keep custom emojis
    :return: Text without HTML
    """
    cleaned = re.sub(
        (
            r"(<\/?a.*?>|<\/?b>|<\/?i>|<\/?u>|<\/?strong>|<\/?em>|<\/?code.*?>|<\/?strike>|<\/?del>|<\/?pre.*?>|<\/?blockquote.*?>)"
            if keep_emojis
            else r"(<\/?a.*?>|<\/?b>|<\/?i>|<\/?u>|<\/?strong>|<\/?em>|<\/?code.*?>|<\/?strike>|<\/?del>|<\/?pre.*?>|<\/?emoji.*?>|<\/?tg-emoji.*?>|<\/?blockquote.*?>)"
        ),
        "",
        text,
    )

    if not escape:
        return cleaned

    # When custom emojis are kept, don't blindly escape_html the whole
    # string - that would turn the surviving <tg-emoji>/<emoji> tags into
    # literal &lt;tg-emoji...&gt; text instead of rendering as emojis.
    return escape_non_html(cleaned) if keep_emojis else escape_html(cleaned)


def check_url(url: str) -> bool:
    """
    Statically checks url for validity
    :param url: URL to check
    :return: True if valid, False otherwise
    """
    try:
        return bool(urlparse(url).netloc)
    except Exception:
        return False


async def is_private_asset_channel(client, peer, *, allow_participants: bool = False) -> bool:
    try:
        entity = await client.get_entity(peer, force=True)
        if (
            not isinstance(entity, Channel)
            or not entity.creator
            or entity.username
            or any(getattr(name, "active", False) for name in (entity.usernames or []))
        ):
            return False
        if allow_participants:
            return True
        allowed = {client.tg_id}
        inline = getattr(getattr(client, "loader", None), "inline", None)
        bot_id = getattr(inline, "bot_id", None)
        if bot_id:
            allowed.add(bot_id)
        participants = await client.get_participants(entity, limit=len(allowed) + 1)
        return (
            bool(participants)
            and client.tg_id in {user.id for user in participants}
            and all(user.id in allowed for user in participants)
            and getattr(participants, "total", len(participants)) <= len(allowed)
        )
    except Exception:
        return False


async def asset_channel(
    client: CustomTelegramClient,
    title: str,
    description: str,
    *,
    channel: bool = False,
    silent: bool = False,
    archive: bool = False,
    invite_bot: bool = False,
    avatar: str | None = None,
    ttl: int | None = None,
    forum: bool = False,
    hide_general: bool = False,
    _folder: str | None = None,
    allow_participants: bool = False,
) -> tuple[Channel, bool]:
    """
    Create new channel (if needed) and return its entity
    :param client: Telegram client to create channel by
    :param title: Channel title
    :param description: Description
    :param channel: Whether to create a channel or supergroup
    :param silent: Automatically mute channel
    :param archive: Automatically archive channel
    :param invite_bot: Add inline bot and assure it's in chat
    :param avatar: Url to an avatar to set as pfp of created peer
    :param ttl: Time to live for messages in channel
    :param forum: Whether to create a forum channel
    :param hide_general: Hide '#General' topic
    :return: Peer and bool: is channel new or pre-existent
    """

    if not hasattr(client, "_channels_cache"):
        client._channels_cache = {}

    if (
        title in client._channels_cache
        and client._channels_cache[title]["exp"] > time.time()
    ):
        peer = client._channels_cache[title]["peer"]
        if await is_private_asset_channel(
            client, peer, allow_participants=allow_participants
        ):
            return peer, False

    async for d in client.iter_dialogs():
        if d.title == title and await is_private_asset_channel(
            client, d.entity, allow_participants=allow_participants
        ):
            client._channels_cache[title] = {"peer": d.entity, "exp": int(time.time())}
            if invite_bot:
                if all(
                    participant.id != client.loader.inline.bot_id
                    for participant in await client.get_participants(
                        d.entity, limit=100
                    )
                ):
                    await fw_protect()
                    await invite_inline_bot(client, d.entity)

            return d.entity, False

    await fw_protect()

    peer = (
        await client(
            CreateChannelRequest(
                title,
                description,
                broadcast=channel,
                megagroup=not channel,
                forum=forum,
            )
        )
    ).chats[0]

    if invite_bot:
        await fw_protect()
        await invite_inline_bot(client, peer)

    if silent:
        await fw_protect()
        await dnd(client, peer, archive)
    elif archive:
        await fw_protect()
        await client.edit_folder(peer, 1)

    if avatar:
        await fw_protect()
        await set_avatar(client, peer, avatar)

    if hide_general and forum:
        await fw_protect()
        await client(EditForumTopicRequest(peer=peer, topic_id=1, hidden=True))

    if ttl:
        await fw_protect()
        await client(SetHistoryTTLRequest(peer=peer, period=ttl))

    if _folder:
        folders = (await client(GetDialogFiltersRequest())).filters

        try:
            folder = next(
                folder
                for folder in folders
                if not isinstance(folder, herokutl.tl.types.DialogFilterDefault)
                and folder.title.text.lower() == _folder.lower()
            )
        except Exception:
            folder = None

        if folder and not any(
            peer.id == getattr(folder_peer, "channel_id", None)
            for folder_peer in folder.include_peers
        ):
            folder.include_peers.append(await client.get_input_entity(peer))

            await client(
                UpdateDialogFilterRequest(
                    folder.id,
                    folder,
                )
            )

    client._channels_cache[title] = {"peer": peer, "exp": int(time.time())}
    return peer, True


if typing.TYPE_CHECKING:
    from ..database import Database


async def asset_forum_topic(
    client: CustomTelegramClient,
    db: "Database",
    peer: hints.Entity,
    title: str,
    description: str | None = None,
    icon_emoji_id: int | None = None,
    invite_bot: bool = False,
) -> ForumTopic:
    entity = await client.get_entity(peer)

    if not isinstance(entity, Channel):
        raise TypeError(
            f"Expected entity to be 'Channel', but got '{type(entity).__name__}'"
        )

    async def create_topic() -> ForumTopic:
        result = await client(
            CreateForumTopicRequest(
                peer=entity,
                title=title,
                icon_emoji_id=(icon_emoji_id if client.heroku_me.premium else None),
            )
        )

        await fw_protect()

        await client.send_message(
            entity=entity,
            message=(
                description
                if description
                else f"<tg-emoji emoji-id=\"5258503720928288433\">ℹ️</tg-emoji> <b>Content related to <i>'{title}'</i> will be here</b>"
            ),
            reply_to=result.updates[0].id,
        )

        await fw_protect()

        result = await client(
            GetForumTopicsByIDRequest(peer=entity, topics=[result.updates[0].id])
        )

        return result.topics[0]

    forums_cache = db.pointer("heroku.forums", "forums_cache", {})

    async def _search_topic(topic_title: str) -> int | None:
        result = await client(
            GetForumTopicsRequest(
                peer=entity,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )
        await fw_protect()
        for found_topic in result.topics:
            if isinstance(found_topic, ForumTopicDeleted):
                continue
            if found_topic.title == topic_title:
                forums_cache.setdefault(entity.title, {})[topic_title] = found_topic.id
                return found_topic.id
        return None

    if topic_id := forums_cache.get(entity.title, {}).get(title) or await _search_topic(
        title
    ):
        await fw_protect()
        new_topic = await client(
            GetForumTopicsByIDRequest(peer=entity, topics=[topic_id])
        )
        new_topic = new_topic.topics[0]

        if isinstance(new_topic, ForumTopicDeleted):
            logger.warning(
                f"Topic: '{title}' was found in the database but does not exist in the channel and will be recreated"
            )
            await fw_protect()
            new_topic = await create_topic()
            forums_cache[entity.title][title] = new_topic.id

    else:
        await fw_protect()
        new_topic = await create_topic()
        forums_cache.setdefault(entity.title, {})[title] = new_topic.id

    if invite_bot:
        await fw_protect()
        if all(
            p.id != client.loader.inline.bot_id
            for p in await client.get_participants(entity, limit=20)
        ):
            await fw_protect()
            await invite_inline_bot(client, entity)

    return new_topic


async def wait_for_content_channel(db: "Database", delay: float = 10) -> int:
    cid = db.get("heroku.forums", "channel_id", None)

    while not cid:
        logger.warning(
            "Heroku content channel not found in database. Sleeping 10 seconds..."
        )
        await asyncio.sleep(delay)
        cid = db.get("heroku.forums", "channel_id", None)

    return cid


async def get_topic_id(db: "Database", topic_name: str) -> int | None:
    """
    Get forum topic ID from database
    :param db: Database instance
    :param topic_name: Topic name (e.g., "Assets", "Logs", "Backups")
    :return: Topic ID or None if not found
    """
    try:
        forums_cache = db.get("heroku.forums", "forums_cache", {})
        return forums_cache.get("heroku-userbot", {}).get(topic_name)
    except Exception:
        return None


async def set_avatar(
    client: CustomTelegramClient,
    peer: hints.Entity,
    avatar: str,
) -> bool:
    """
    Sets an entity avatar
    :param client: Client to use
    :param peer: Peer to set avatar to
    :param avatar: Avatar to set
    :return: True if avatar was set, False otherwise
    """
    if isinstance(avatar, str) and check_url(avatar):
        f = (
            await run_sync(
                requests.get,
                avatar,
            )
        ).content
    elif isinstance(avatar, bytes):
        f = avatar
    else:
        return False

    await fw_protect()
    res = await client(
        EditPhotoRequest(
            channel=peer,
            photo=await client.upload_file(f, file_name="photo.png"),
        )
    )

    await fw_protect()

    try:
        await client.delete_messages(
            peer,
            message_ids=[
                next(
                    update
                    for update in res.updates
                    if isinstance(update, UpdateNewChannelMessage)
                ).message.id
            ],
        )
    except Exception:
        pass

    return True


async def get_target(message: Message, arg_no: int = 0) -> int | None:
    """
    Get target from message
    :param message: Message to get target from
    :param arg_no: Argument number to get target from
    :return: Target
    """
    from .args import get_args

    if any(
        isinstance(entity, MessageEntityMentionName)
        for entity in (message.entities or [])
    ):
        e = sorted(
            filter(lambda x: isinstance(x, MessageEntityMentionName), message.entities),
            key=lambda x: x.offset,
        )[0]
        return e.user_id

    if len(get_args(message)) > arg_no:
        user = get_args(message)[arg_no]
    elif message.is_reply:
        return (await message.get_reply_message()).sender_id
    elif hasattr(message.peer_id, "user_id"):
        user = message.peer_id.user_id
    else:
        return None

    try:
        entity = await message.client.get_entity(user)
    except ValueError:
        return None
    else:
        if isinstance(entity, User):
            return entity.id


async def get_user(message: Message) -> User | None:
    """
    Get user who sent message, searching if not found easily
    :param message: Message to get user from
    :return: User who sent message
    """
    try:
        return await message.get_sender()
    except ValueError:  # Not in database. Lets go looking for them.
        logger.debug("User not in session cache. Searching...")

    if isinstance(message.peer_id, PeerUser):
        await message.client.get_dialogs()
        return await message.get_sender()

    if isinstance(message.peer_id, (PeerChannel, PeerChat)):
        async for user in message.client.iter_participants(
            message.peer_id,
            aggressive=True,
        ):
            if user.id == message.sender_id:
                return user

        logger.error("User isn't in the group where they sent the message")
        return None

    logger.error("`peer_id` is not a user, chat or channel")
    return None


def get_chat_id(message: Message) -> int:
    """
    Get the chat ID, but without -100 if its a channel
    :param message: Message to get chat ID from
    :return: Chat ID
    """
    return herokutl.utils.resolve_id(
        getattr(message, "chat_id", None)
        or getattr(getattr(message, "chat", None), "id", None)
    )[0]


def get_entity_id(entity: hints.Entity) -> int:
    """
    Get entity ID
    :param entity: Entity to get ID from
    :return: Entity ID
    """
    return herokutl.utils.get_peer_id(entity)


def escape_html(text: str, /) -> str:  # sourcery skip
    """
    Pass all untrusted/potentially corrupt input here
    :param text: Text to escape
    :return: Escaped text
    """
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_non_html(text: str) -> str:
    """
    Escape all characters that can be parsed as HTML tags, but are not supported by Telegram
    :param text: Text to escape
    :return: Escaped text
    """
    out = []
    last = 0
    for m in TAG_RE.finditer(text):
        out.append(escape_html(text[last : m.start()]))
        out.append(
            m.group(0)
            if m.group(1).lower() in TELEGRAM_HTML_TAGS
            else escape_html(m.group(0))
        )
        last = m.end()

    out.append(escape_html(text[last:]))

    return "".join(out)


def escape_quotes(text: str, /) -> str:
    """
    Escape quotes to html quotes
    :param text: Text to escape
    :return: Escaped text
    """
    return escape_html(text).replace('"', "&quot;")


def relocate_entities(
    entities: list[FormattingEntity],
    offset: int,
    text: str | None = None,
) -> list[FormattingEntity]:
    """
    Move all entities by offset (truncating at text)
    :param entities: List of entities
    :param offset: Offset to move by
    :param text: Text to truncate at
    :return: List of entities
    """
    length = len(text) if text is not None else 0

    for ent in entities.copy() if entities else ():
        ent.offset += offset
        if ent.offset < 0:
            ent.length += ent.offset
            ent.offset = 0
        if text is not None and ent.offset + ent.length > length:
            ent.length = length - ent.offset
        if ent.length <= 0:
            entities.remove(ent)

    return entities


def find_caller(
    stack: list[inspect.FrameInfo] | None = None,
) -> typing.Any:
    """
    Attempts to find command in stack
    :param stack: Stack to search in
    :return: Command-caller or None
    """
    caller = next(
        (
            frame_info
            for frame_info in stack or inspect.stack()
            if hasattr(frame_info, "function")
            and any(
                inspect.isclass(cls_)
                and issubclass(cls_, Module)
                and cls_ is not Module
                for cls_ in frame_info.frame.f_globals.values()
            )
        ),
        None,
    )

    if not caller:
        return next(
            (
                frame_info.frame.f_locals["func"]
                for frame_info in stack or inspect.stack()
                if hasattr(frame_info, "function")
                and frame_info.function == "future_dispatcher"
                and (
                    "CommandDispatcher"
                    in getattr(getattr(frame_info, "frame", None), "f_globals", {})
                )
            ),
            None,
        )

    return next(
        (
            getattr(cls_, caller.function, None)
            for cls_ in caller.frame.f_globals.values()
            if inspect.isclass(cls_) and issubclass(cls_, Module)
        ),
        None,
    )


async def dnd(
    client: CustomTelegramClient,
    peer: hints.Entity,
    archive: bool = True,
) -> bool:
    """
    Mutes and optionally archives peer
    :param peer: Anything entity-link
    :param archive: Archive peer, or just mute?
    :return: `True` on success, otherwise `False`
    """
    try:
        await client(
            UpdateNotifySettingsRequest(
                peer=peer,
                settings=InputPeerNotifySettings(
                    show_previews=False,
                    silent=True,
                    mute_until=2**31 - 1,
                ),
            )
        )

        if archive:
            await fw_protect()
            await client.edit_folder(peer, 1)
    except Exception:
        logger.exception("utils.dnd error")
        return False

    return True


def ascii_face() -> str:
    """
    Returnes cute ASCII-art face
    :return: ASCII-art face
    """
    return escape_html(
        random.choice(
            [
                "ヽ(๑◠ܫ◠๑)ﾉ",
                "(◕ᴥ◕ʋ)",
                "ᕙ(`▽´)ᕗ",
                "(✿◠‿◠)",
                "(▰˘◡˘▰)",
                "(˵ ͡° ͜ʖ ͡°˵)",
                "ʕっ•ᴥ•ʔっ",
                "( ͡° ᴥ ͡°)",
                "(๑•́ ヮ •̀๑)",
                "٩(^‿^)۶",
                "(っˆڡˆς)",
                "ψ(｀∇´)ψ",
                "⊙ω⊙",
                "٩(^ᴗ^)۶",
                "(´・ω・)っ由",
                "( ͡~ ͜ʖ ͡°)",
                "✧♡(◕‿◕✿)",
                "โ๏௰๏ใ ื",
                "∩｡• ᵕ •｡∩ ♡",
                "(♡´౪`♡)",
                "(◍＞◡＜◍)⋈。✧♡",
                "╰(✿´⌣`✿)╯♡",
                "ʕ•ᴥ•ʔ",
                "ᶘ ◕ᴥ◕ᶅ",
                "▼・ᴥ・▼",
                "ฅ^•ﻌ•^ฅ",
                "(΄◞ิ౪◟ิ‵)",
                "٩(^ᴗ^)۶",
                "ᕴｰᴥｰᕵ",
                "ʕ￫ᴥ￩ʔ",
                "ʕᵕᴥᵕʔ",
                "ʕᵒᴥᵒʔ",
                "ᵔᴥᵔ",
                "(✿╹◡╹)",
                "(๑￫ܫ￩)",
                "ʕ·ᴥ·　ʔ",
                "(ﾉ≧ڡ≦)",
                "(≖ᴗ≖✿)",
                "（〜^∇^ )〜",
                "( ﾉ･ｪ･ )ﾉ",
                "~( ˘▾˘~)",
                "(〜^∇^)〜",
                "ヽ(^ᴗ^ヽ)",
                "(´･ω･`)",
                "₍ᐢ•ﻌ•ᐢ₎*･ﾟ｡",
                "(。・・)_且",
                "(=｀ω´=)",
                "(*•‿•*)",
                "(*ﾟ∀ﾟ*)",
                "(☉⋆‿⋆☉)",
                "ɷ◡ɷ",
                "ʘ‿ʘ",
                "(。-ω-)ﾉ",
                "( ･ω･)ﾉ",
                "(=ﾟωﾟ)ﾉ",
                "(・ε・`*) …",
                "ʕっ•ᴥ•ʔっ",
                "(*˘︶˘*)",
                "ಥ_ಥ",
                "･ﾟ･(｡>д<｡)･ﾟ･",
                "(┬┬＿┬┬)",
                "(◞‸◟ㆀ)",
                " ˚‧º·(˚ ˃̣̣̥⌓˂̣̣̥ )‧º·˚",
            ]
        )
    )
