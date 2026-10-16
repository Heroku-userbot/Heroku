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
import collections
import copy
import json
import logging
import os
import re
import time

try:
    import redis
except ImportError as e:
    if "RAILWAY" in os.environ:
        raise e


import typing

from herokutl.tl.types import Message, User

from . import main, utils
from ._internal import private_write, register_secrets
from .pointers import (
    BaseSerializingMiddlewareDict,
    BaseSerializingMiddlewareList,
    NamedTupleMiddlewareDict,
    NamedTupleMiddlewareList,
    PointerDict,
    PointerList,
)
from .tl_cache import CustomTelegramClient
from .types import JSONSerializable

__all__ = [
    "Database",
    "PointerList",
    "PointerDict",
    "NamedTupleMiddlewareDict",
    "NamedTupleMiddlewareList",
    "BaseSerializingMiddlewareDict",
    "BaseSerializingMiddlewareList",
]

logger = logging.getLogger(__name__)


class NoAssetsChannel(Exception):
    """Raised when trying to read/store asset with no asset channel present"""


class NoContentChannel(Exception):
    """Raised when trying to read/store asset with no content channel present"""


class Database(dict):
    def __init__(self, client: CustomTelegramClient):
        super().__init__()
        self._client: CustomTelegramClient = client
        self._next_revision_call: int = 0
        self._revisions: list[dict] = []
        self._me: User = None
        self._redis: redis.Redis = None
        self._saving_task: asyncio.Future = None

    def __repr__(self):
        return object.__repr__(self)

    def _redis_save_sync(self):
        with self._redis.pipeline() as pipe:
            pipe.set(
                str(self._client.tg_id),
                json.dumps(self, ensure_ascii=True),
            )
            pipe.execute()

    async def remote_force_save(self) -> bool:
        """Force save database to remote endpoint without waiting"""
        if not self._redis:
            return False

        await utils.run_sync(self._redis_save_sync)
        logger.debug("Published db to Redis")
        return True

    async def _redis_save(self) -> bool:
        """Save database to redis"""
        if not self._redis:
            return False

        await asyncio.sleep(5)
        await utils.run_sync(self._redis_save_sync)
        logger.debug("Published db to Redis")
        self._saving_task = None
        return True

    async def redis_init(self) -> bool:
        """Init redis database"""
        if REDIS_URI := (
            os.environ.get("REDIS_URL") or main.get_config_key("redis_uri")
        ):
            self._redis = redis.Redis.from_url(REDIS_URI)
        else:
            return False

    async def init(self):
        """Asynchronous initialization unit"""
        if os.environ.get("REDIS_URL") or main.get_config_key("redis_uri"):
            await self.redis_init()

        self._db_file = main.BASE_PATH / f"config-{self._client.tg_id}.json"
        self.read()

    async def ensure_content_channel(self):
        content_channel = None
        existing_channel_id = self.get("heroku.forums", "channel_id", None)

        if existing_channel_id:
            try:
                content_channel = await self._client.get_entity(existing_channel_id)
                if not await utils.is_private_asset_channel(
                    self._client, content_channel, allow_participants=True
                ):
                    raise PermissionError("Unsafe content channel")
                logger.debug(
                    "Found existing content channel with ID %s in database",
                    existing_channel_id,
                )
            except Exception as e:
                logger.warning(
                    f"Saved channel ID {existing_channel_id} not found or inaccessible: {e}"
                )
                content_channel = None
                self.set("heroku.forums", "forums_cache", {"heroku-userbot": {}})

        if not content_channel:
            async for dialog in self._client.iter_dialogs():
                if (
                    dialog.title == "heroku-userbot"
                    and await utils.is_private_asset_channel(
                        self._client, dialog.entity, allow_participants=True
                    )
                ):
                    content_channel = dialog.entity
                    logger.debug(
                        "Found existing channel '%s' with ID %s",
                        dialog.title,
                        dialog.entity.id,
                    )
                    self.set("heroku.forums", "channel_id", int(dialog.entity.id))
                    break

        if not content_channel:
            content_channel, _ = await utils.asset_channel(
                client=self._client,
                title="heroku-userbot",
                description="🪐 Content related to Heroku will be here",
                silent=True,
                invite_bot=True,
                avatar="https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/heroku.jpg",
                forum=True,
                hide_general=True,
                _folder="heroku",
                allow_participants=True,
            )
            self.set("heroku.forums", "channel_id", int(content_channel.id))

        return content_channel

    def read(self):
        """Read database and stores it in self"""
        if self._redis:
            try:
                self._update_from_read(
                    json.loads(
                        self._redis.get(
                            str(self._client.tg_id),
                        ).decode(),
                    ),
                )
            except Exception:
                logger.exception("Error reading redis database")
            return

        try:
            db = self._db_file.read_text()
            if re.search(r'"(hikka\.)(\S+\":)', db):
                logging.warning("Converting db after update")
                db = re.sub(r"(hikka\.)(\S+\":)", lambda m: "heroku." + m.group(2), db)
            if re.search(r'"(legacy\.)(\S+\":)', db):
                logging.warning("Converting db after update")
                db = re.sub(r"(legacy\.)(\S+\":)", lambda m: "heroku." + m.group(2), db)
            self._update_from_read(json.loads(db))
        except json.decoder.JSONDecodeError:
            logger.warning("Database read failed! Creating new one...")
        except FileNotFoundError:
            logger.debug("Database file not found, creating new one...")

    def _update_from_read(self, items: dict) -> None:
        """Update DB from persisted storage without write-protection checks."""
        register_secrets(items)
        super().update(items)

    def process_db_autofix(self, db: dict) -> bool:
        if not utils.is_serializable(db):
            return False

        for key, value in db.copy().items():
            if not isinstance(key, (str, int)):
                logger.warning(
                    "DbAutoFix: Dropped key %s, because it is not string or int",
                    key,
                )
                continue

            if not isinstance(value, dict):
                # If value is not a dict (module values), drop it,
                # otherwise it may cause problems
                del db[key]
                logger.warning(
                    "DbAutoFix: Dropped key %s, because it is non-dict, but %s",
                    key,
                    type(value),
                )
                continue

            for subkey in value:
                if not isinstance(subkey, (str, int)):
                    del db[key][subkey]
                    logger.warning(
                        (
                            "DbAutoFix: Dropped subkey %s of db key %s, because it is"
                            " not string or int"
                        ),
                        subkey,
                        key,
                    )
                    continue

        return True

    def save(self) -> bool:
        """Save database"""
        register_secrets(self)
        if not self.process_db_autofix(self):
            try:
                rev = self._revisions.pop()
                while not self.process_db_autofix(rev):
                    rev = self._revisions.pop()
            except IndexError:
                raise RuntimeError(
                    "Can't find revision to restore broken database from "
                    "database is most likely broken and will lead to problems, "
                    "so its save is forbidden."
                )

            self.clear()
            self.update(**rev)

            raise RuntimeError(
                "Rewriting database to the last revision because new one destructed it"
            )

        if self._next_revision_call < time.time():
            self._revisions += [dict(self)]
            self._next_revision_call = time.time() + 3

        while len(self._revisions) > 15:
            self._revisions.pop()

        if self._redis:
            if not self._saving_task:
                self._saving_task = asyncio.ensure_future(self._redis_save())
            return True

        try:
            private_write(self._db_file, json.dumps(self, indent=4))
        except Exception:
            logger.exception("Database save failed!")
            return False

        return True

    async def store_asset(self, message: Message) -> int:
        """
        Save assets
        returns asset_id as integer
        """

        try:
            _assets_topic_id = self.get("heroku.forums", "forums_cache", {})[
                "heroku-userbot"
            ]["Assets"]
        except (TypeError, KeyError):
            raise NoAssetsChannel("Tried to save asset to non-existing asset topic.")

        if not (_content_channel_id := self.get("heroku.forums", "channel_id", None)):
            raise NoContentChannel(
                "Tried to save asset with non-existing content channel."
            )

        return (
            (
                await self._client.send_message(
                    _content_channel_id, message, reply_to=_assets_topic_id
                )
            ).id
            if isinstance(message, Message)
            else (
                await self._client.send_message(
                    _content_channel_id,
                    file=message,
                    force_document=True,
                    message_thread_id=_assets_topic_id,
                )
            ).id
        )

    async def fetch_asset(self, asset_id: int) -> Message | None:
        """Fetch previously saved asset by its asset_id"""

        if not (_content_channel_id := self.get("heroku.forums", "channel_id", None)):
            raise NoContentChannel(
                "Tried to save asset with non-existing content channel."
            )

        try:
            _assets_topic_id = self.get("heroku.forums", "forums_cache", {})[
                "heroku-userbot"
            ]["Assets"]
        except (TypeError, KeyError):
            raise NoAssetsChannel("Tried to save asset to non-existing asset topic.")

        asset = await self._client.get_messages(
            _content_channel_id, reply_to=_assets_topic_id, ids=[asset_id]
        )

        return asset[0] if asset else None

    def get(
        self,
        owner: str,
        key: str,
        default: JSONSerializable | None = None,
    ) -> JSONSerializable:
        """Get database key snapshot"""
        return copy.deepcopy(self._get_raw(owner, key, default))

    def _get_raw(
        self,
        owner: str,
        key: str,
        default: JSONSerializable | None = None,
    ) -> JSONSerializable:
        """Get database key"""
        try:
            return self[owner][key]
        except KeyError:
            return default

    def set(self, owner: str, key: str, value: JSONSerializable) -> bool:
        """Set database key"""
        if not utils.is_serializable(owner):
            raise RuntimeError(
                "Attempted to write object to "
                f"{owner=} ({type(owner)=}) of database. It is not "
                "JSON-serializable key which will cause errors"
            )

        if not utils.is_serializable(key):
            raise RuntimeError(
                "Attempted to write object to "
                f"{key=} ({type(key)=}) of database. It is not "
                "JSON-serializable key which will cause errors"
            )

        if not utils.is_serializable(value):
            raise RuntimeError(
                "Attempted to write object of "
                f"{key=} ({type(value)=}) to database. It is not "
                "JSON-serializable value which will cause errors"
            )

        super().setdefault(owner, {})[key] = value
        return self.save()

    def __setitem__(self, owner: str, value: JSONSerializable) -> None:
        if not utils.is_serializable(owner):
            raise RuntimeError(
                "Attempted to write object to "
                f"{owner=} ({type(owner)=}) of database. It is not "
                "JSON-serializable key which will cause errors"
            )

        if not utils.is_serializable(value):
            raise RuntimeError(
                "Attempted to write object of "
                f"{owner=} ({type(value)=}) to database. It is not "
                "JSON-serializable value which will cause errors"
            )

        super().__setitem__(owner, value)

    def update(self, *args, **kwargs) -> None:
        items = dict(*args, **kwargs)
        return super().update(items)

    def pointer(
        self,
        owner: str,
        key: str,
        default: JSONSerializable | None = None,
        item_type: typing.Any | None = None,
    ) -> JSONSerializable | PointerList | PointerDict:
        """Get a pointer to database key"""
        value = self._get_raw(owner, key, default)
        mapping = {
            list: PointerList,
            dict: PointerDict,
            collections.abc.Hashable: lambda v: v,
        }

        pointer_constructor = next(
            (pointer for type_, pointer in mapping.items() if isinstance(value, type_)),
            None,
        )

        if (current_value := self._get_raw(owner, key, None)) and type(
            current_value
        ) is not type(default):
            raise ValueError(
                f"Can't switch the type of pointer in database (current: {type(current_value)}, requested: {type(default)})"
            )

        if pointer_constructor is None:
            raise ValueError(
                f"Pointer for type {type(value).__name__} is not implemented"
            )

        if item_type is not None:
            if isinstance(value, list):
                for item in self._get_raw(owner, key, default):
                    if not isinstance(item, dict):
                        raise ValueError(
                            "Item type can only be specified for dedicated keys and"
                            " can't be mixed with other ones"
                        )

                return NamedTupleMiddlewareList(
                    pointer_constructor(self, owner, key, default),
                    item_type,
                )
            if isinstance(value, dict):
                for item in self._get_raw(owner, key, default).values():
                    if not isinstance(item, dict):
                        raise ValueError(
                            "Item type can only be specified for dedicated keys and"
                            " can't be mixed with other ones"
                        )

                return NamedTupleMiddlewareDict(
                    pointer_constructor(self, owner, key, default),
                    item_type,
                )

        return pointer_constructor(self, owner, key, default)
