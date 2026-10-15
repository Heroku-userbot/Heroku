# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import atexit as _atexit
import contextlib
import functools
import json
import logging
import os
import re
import secrets
import signal
import sys
import typing
import warnings

import herokutl
from herokutl import hints
from herokutl.tl.functions.channels import (
    EditAdminRequest,
    InviteToChannelRequest,
)
from herokutl.tl.types import (
    ChatAdminRights,
)

from ..tl_cache import CustomTelegramClient
from ..types import ListLike

parser = herokutl.utils.sanitize_parse_mode("html")
logger = logging.getLogger(__name__)


def ensure_child_watcher():
    """Ensure the active asyncio policy can spawn subprocesses."""
    if sys.platform == "win32" or sys.version_info >= (3, 14):
        return

    with warnings.catch_warnings():
        # get_child_watcher() is deprecated on 3.12/3.13; we use it knowingly.
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            asyncio.get_event_loop_policy().get_child_watcher()
            return
        except NotImplementedError:
            pass

        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        with contextlib.suppress(RuntimeError):
            asyncio.set_event_loop(asyncio.get_running_loop())


custom_placeholders = {}


def rand(size: int, /) -> str:
    """
    Return random string of len `size`
    :param size: Length of string
    :return: Random string
    """
    return "".join(
        [secrets.choice("abcdefghijklmnopqrstuvwxyz1234567890") for _ in range(size)]
    )


async def invite_inline_bot(
    client: CustomTelegramClient,
    peer: hints.EntityLike,
) -> None:
    """
    Invites inline bot to a chat
    :param client: Client to use
    :param peer: Peer to invite bot to
    :return: None
    :raise RuntimeError: If error occurred while inviting bot
    """

    try:
        await client(InviteToChannelRequest(peer, [client.loader.inline.bot_username]))
    except Exception as e:
        raise RuntimeError(
            f"Can't invite inline bot to old asset chat, which is required by module: {e}"
        )

    with contextlib.suppress(Exception):
        await client(
            EditAdminRequest(
                channel=peer,
                user_id=client.loader.inline.bot_username,
                admin_rights=ChatAdminRights(ban_users=True),
                rank="Heroku",
            )
        )


def run_sync(func, *args, **kwargs):
    """
    Run a non-async function in a new thread and return an awaitable
    :param func: Sync-only function to execute
    :return: Awaitable coroutine
    """
    return asyncio.get_event_loop().run_in_executor(
        None,
        functools.partial(func, *args, **kwargs),
    )


def run_async(loop: asyncio.AbstractEventLoop, coro: typing.Awaitable) -> typing.Any:
    """
    Run an async function as a non-async function, blocking till it's done
    :param loop: Event loop to run the coroutine in
    :param coro: Coroutine to run
    :return: Result of the coroutine
    """
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def merge(
    a: dict,
    b: dict,
    /,
    *,
    deep: bool = True,
) -> dict:
    """
    Merge with replace dictionary a to dictionary b
    :param a: Dictionary to merge
    :param b: Dictionary to merge to
    :return: Merged dictionary
    """
    for key, a_value in a.items():
        b_value = b.get(key)

        match (
            key not in b,
            isinstance(a_value, dict) and isinstance(b_value, dict) and deep,
            isinstance(a_value, list) and isinstance(b_value, list),
        ):
            case (True, _, _):
                b[key] = a_value
            case (False, True, _):
                b[key] = merge(a_value, b_value, deep=deep)
            case (False, False, True):
                b[key] = list(dict.fromkeys(b_value + a_value))
            case _:
                b[key] = a_value

    return b


def chunks(_list: ListLike, n: int, /) -> list[list[typing.Any]]:
    """
    Split provided `_list` into chunks of `n`
    :param _list: List to split
    :param n: Chunk size
    :return: List of chunks
    """
    return [_list[i : i + n] for i in range(0, len(_list), n)]


def atexit(
    func: typing.Callable,
    use_signal: int | None = None,
    *args,
    **kwargs,
) -> None:
    """
    Calls function on exit
    :param func: Function to call
    :param use_signal: If passed, `signal` will be used instead of `atexit`
    :param args: Arguments to pass to function
    :param kwargs: Keyword arguments to pass to function
    :return: None
    """
    if use_signal:
        signal.signal(use_signal, lambda *_: func(*args, **kwargs))
        return

    _atexit.register(functools.partial(func, *args, **kwargs))


def _copy_tl(o, **kwargs):
    d = o.to_dict()
    del d["_"]
    d.update(kwargs)
    return o.__class__(**d)


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human-readable format
    :param size_bytes: Size in bytes
    :return: Formatted string (e.g., '1.5 MB')
    """
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return ".1f"


def is_url(string: str) -> bool:
    """
    Check if string is a valid URL
    :param string: String to check
    :return: True if valid URL, False otherwise
    """
    import re

    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return url_pattern.match(string) is not None


def get_iso_time() -> str:
    """
    Get current time in ISO format
    :return: ISO formatted time string
    """
    from datetime import datetime

    return datetime.utcnow().isoformat() + "Z"


def safe_getattr(obj, attr, default=None):
    """
    Safely get attribute from object, returning default if not found
    :param obj: Object to get attribute from
    :param attr: Attribute name
    :param default: Default value if attribute not found
    :return: Attribute value or default
    """
    try:
        return getattr(obj, attr, default)
    except AttributeError:
        return default


ALLOWED_IDS_CHANNEL = "heroku_white"
ALLOWED_IDS_MESSAGE = 4
_ALLOWED_IDS_CACHE = os.path.join(
    (
        "/data"
        if "DOCKER" in os.environ
        else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    ),
    "allowed_ids_cache.json",
)


def _parse_ids(content: str) -> list[int]:
    return [int(i) for i in re.findall(r"\b\d+\b", re.sub(r"<[^>]+>", " ", content))]


async def allowed_ids(client) -> list[int] | None:
    """
    Read beta users ids from the public channel, fall back to the last
    successfully read list
    :return: allowed list ids or `None`
    """
    from .._internal import private_write

    try:
        message = await client.get_messages(
            ALLOWED_IDS_CHANNEL, ids=ALLOWED_IDS_MESSAGE
        )
        ids = _parse_ids(message.raw_text or "")
        if ids:
            with contextlib.suppress(Exception):
                private_write(_ALLOWED_IDS_CACHE, json.dumps(ids))
            return ids
    except Exception:
        logger.warning("Unable to load beta user list, using cache", exc_info=True)

    try:
        with open(_ALLOWED_IDS_CACHE, encoding="utf-8") as f:
            return [int(i) for i in json.load(f)]
    except Exception:
        return None
