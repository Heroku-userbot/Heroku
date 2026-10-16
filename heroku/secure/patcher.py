import functools
import logging
import os
import re
import stat
from pathlib import Path

from herokutl.sessions import SQLiteSession

from ..tl_cache import CustomTelegramClient
from .customtl import ConnectionTcpFull, MTProtoState


def patch(client: CustomTelegramClient, session: SQLiteSession):
    if os.environ.get("HEROKU_ALLOW_INSECURE_PROXY") != "1":
        raise RuntimeError(
            "Unencrypted session proxy is disabled. Use a normal Telegram session "
            "or explicitly set HEROKU_ALLOW_INSECURE_PROXY=1 for a trusted local proxy."
        )
    session_id = re.findall(r"\d+", session.filename)[-1]
    socket_path = (
        Path(__file__).parent.parent.parent / f"heroku-{session_id}-proxy.sock"
    )
    metadata = socket_path.lstat()
    if (
        not stat.S_ISSOCK(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & 0o077
    ):
        raise PermissionError("Session proxy must be an owner-only Unix socket")
    client._sender._state = MTProtoState(session.auth_key, client._sender._loggers)
    client._connection = ConnectionTcpFull
    client.connect = functools.partial(client.connect, unix_socket_path=socket_path)

    logging.warning("Patched mtprotostate")
