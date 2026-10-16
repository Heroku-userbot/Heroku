import re

from herokutl.tl.types import Message


ALL_TAGS = [
    "no_commands",
    "only_commands",
    "out",
    "in",
    "only_messages",
    "editable",
    "no_media",
    "only_media",
    "only_photos",
    "only_videos",
    "only_audios",
    "only_docs",
    "only_stickers",
    "only_inline",
    "only_channels",
    "only_groups",
    "only_pm",
    "no_pm",
    "no_channels",
    "no_groups",
    "no_inline",
    "no_stickers",
    "no_docs",
    "no_audios",
    "no_videos",
    "no_photos",
    "no_forwards",
    "no_reply",
    "no_mention",
    "mention",
    "only_reply",
    "only_forwards",
    "startswith",
    "endswith",
    "contains",
    "regex",
    "filter",
    "from_id",
    "chat_id",
    "thumb_url",
    "alias",
    "aliases",
]


def find_failed_tag(m, func, *, mime_type, get_chat_id):
    reverse_mapping = {
        "out": lambda: getattr(m, "out", True),
        "in": lambda: not getattr(m, "out", True),
        "only_messages": lambda: isinstance(m, Message),
        "editable": (
            lambda: not getattr(m, "out", False)
            and not getattr(m, "fwd_from", False)
            and not getattr(m, "sticker", False)
            and not getattr(m, "via_bot_id", False)
        ),
        "no_media": lambda: (
            not isinstance(m, Message) or not getattr(m, "media", False)
        ),
        "only_media": lambda: isinstance(m, Message) and getattr(m, "media", False),
        "only_photos": lambda: mime_type(m).startswith("image/"),
        "only_videos": lambda: mime_type(m).startswith("video/"),
        "only_audios": lambda: mime_type(m).startswith("audio/"),
        "only_stickers": lambda: getattr(m, "sticker", False),
        "only_docs": lambda: getattr(m, "document", False),
        "only_inline": lambda: getattr(m, "via_bot_id", False),
        "only_channels": lambda: (
            getattr(m, "is_channel", False) and not getattr(m, "is_group", False)
        ),
        "no_channels": lambda: not getattr(m, "is_channel", False),
        "no_groups": (
            lambda: not getattr(m, "is_group", False)
            or getattr(m, "is_private", False)
            or getattr(m, "is_channel", False)
        ),
        "only_groups": (
            lambda: getattr(m, "is_group", False)
            or not getattr(m, "is_private", False)
            and not getattr(m, "is_channel", False)
        ),
        "no_pm": lambda: not getattr(m, "is_private", False),
        "only_pm": lambda: getattr(m, "is_private", False),
        "no_inline": lambda: not getattr(m, "via_bot_id", False),
        "no_stickers": lambda: not getattr(m, "sticker", False),
        "no_docs": lambda: not getattr(m, "document", False),
        "no_audios": lambda: not mime_type(m).startswith("audio/"),
        "no_videos": lambda: not mime_type(m).startswith("video/"),
        "no_photos": lambda: not mime_type(m).startswith("image/"),
        "no_forwards": lambda: not getattr(m, "fwd_from", False),
        "no_reply": lambda: not getattr(m, "reply_to_msg_id", False),
        "only_forwards": lambda: getattr(m, "fwd_from", False),
        "only_reply": lambda: getattr(m, "reply_to_msg_id", False),
        "mention": lambda: getattr(m, "mentioned", False),
        "no_mention": lambda: not getattr(m, "mentioned", False),
        "startswith": lambda: (
            isinstance(m, Message) and m.raw_text.startswith(func.startswith)
        ),
        "endswith": lambda: (
            isinstance(m, Message) and m.raw_text.endswith(func.endswith)
        ),
        "contains": lambda: isinstance(m, Message) and func.contains in m.raw_text,
        "filter": lambda: callable(func.filter) and func.filter(m),
        "from_id": lambda: getattr(m, "sender_id", None) == func.from_id,
        "chat_id": lambda: get_chat_id(m)
        == (
            func.chat_id
            if not str(func.chat_id).startswith("-100")
            else int(str(func.chat_id)[4:])
        ),
        "regex": lambda: (
            isinstance(m, Message) and re.search(func.regex, m.raw_text)
        ),
    }

    return next(
        (
            tag
            for tag in ALL_TAGS
            if getattr(func, tag, False)
            and tag in reverse_mapping
            and not reverse_mapping[tag]()
        ),
        None,
    )
