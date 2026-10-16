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
import copy
import inspect
import logging
import time
import typing
from collections.abc import Callable

from herokutl import TelegramClient
from herokutl import helpers
from herokutl import utils as tl_utils
from herokutl.extensions import html as html_parser
from herokutl.extensions.messagepacker import MessagePacker
from herokutl._updates import ChannelState, Entity, EntityType, SessionState
from herokutl.errors.rpcerrorlist import TopicDeletedError
from herokutl.hints import EntityLike
from herokutl.network import MTProtoSender, mtprotosender
from herokutl.network.requeststate import RequestState
from herokutl.tl import functions
from herokutl.tl.alltlobjects import LAYER
from herokutl.tl.functions.channels import GetFullChannelRequest
from herokutl.tl.functions.users import GetFullUserRequest
from herokutl.tl.tlobject import TLRequest
from herokutl.tl.types import (
    ChannelFull,
    InputReplyToMessage,
    InputRichMessage,
    InputRichMessageHTML,
    InputRichMessageMarkdown,
    InputSendMessageRichMessageDraftAction,
    Message,
    Updates,
    UpdatesCombined,
    UpdateShort,
    User,
    UserFull,
)
from herokutl.utils import is_list_like

from ._internal import normalize_rich_html, tag_client_id
from .types import (
    CacheRecordEntity,
    CacheRecordFullChannel,
    CacheRecordFullUser,
    CacheRecordPerms,
    Module,
)

if typing.TYPE_CHECKING:
    from .database import Database
    from .dispatcher import CommandDispatcher
    from .loader import Modules
    from .inline.core import InlineManager

logger = logging.getLogger(__name__)


class HerokuMessagePacker(MessagePacker):
    async def get(self):
        if not self._deque:
            self._ready.clear()
            await self._ready.wait()

        rejected = set()
        for _ in range(len(self._deque)):
            state = self._deque.popleft()
            try:
                if not isinstance(state, RequestState):
                    raise TypeError("Outgoing queue item is not a RequestState")
                if id(state.after) in rejected:
                    raise ValueError("Previous ordered request could not be serialized")
                if not isinstance(state.data, bytes):
                    self._log.warning(
                        "Invalid outgoing payload: state=%s request=%s data=%s; "
                        "serializing the request again",
                        type(state).__name__,
                        type(state.request).__name__,
                        type(state.data).__name__,
                    )
                    replacement = RequestState(state.request, after=state.after)
                    try:
                        if not isinstance(replacement.data, bytes):
                            raise TypeError("RequestState did not serialize to bytes")
                        state.data = replacement.data
                    finally:
                        replacement.future.cancel()
            except Exception as error:
                rejected.add(id(state))
                self._log.error(
                    "Rejected invalid outgoing state %s: %s",
                    type(state).__name__,
                    type(error).__name__,
                )
                future = getattr(state, "future", None)
                if isinstance(future, asyncio.Future) and not future.done():
                    future.set_exception(error)
            else:
                self._deque.append(state)

        if not self._deque:
            return None, None
        return await super().get()



mtprotosender.MessagePacker = HerokuMessagePacker


def hashable(value: typing.Any) -> bool:
    """
    Determine whether `value` can be hashed.

    This is a copy of `collections.abc.Hashable` from Python 3.8.
    """

    try:
        hash(value)
    except TypeError:
        return False

    return True


class CustomTelegramClient(TelegramClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._heroku_entity_cache: dict[
            str | int,
            CacheRecordEntity,
        ] = {}

        self._heroku_perms_cache: dict[
            str | int,
            CacheRecordPerms,
        ] = {}

        self._heroku_fullchannel_cache: dict[
            str | int,
            CacheRecordFullChannel,
        ] = {}

        self._heroku_fulluser_cache: dict[
            str | int,
            CacheRecordFullUser,
        ] = {}

        self._forbidden_constructors: list[int] = []

        self._raw_updates_processor: None | (
            typing.Callable[
                [Updates | UpdatesCombined | UpdateShort],
                typing.Any,
            ]
        ) = None
        self.dispatcher: "CommandDispatcher"
        self.tg_id: int
        self._tg_id: int
        self.heroku_me: "User"
        self.hikka_me: "User"
        self.heroku_db: "Database"
        self.loader: "Modules"
        self.heroku_inline: "InlineManager"

    @staticmethod
    def _rich_output_block_to_input(block):
        from herokutl.tl.types import (
            InputGeoPoint,
            InputGeoPointEmpty,
            InputPageBlockMap,
        )

        block = copy.deepcopy(block)
        if type(block).__name__ == "PageBlockMap":
            geo = block.geo
            if type(geo).__name__ == "GeoPoint":
                geo = InputGeoPoint(
                    lat=geo.lat,
                    long=geo.long,
                    accuracy_radius=geo.accuracy_radius,
                )
            else:
                geo = InputGeoPointEmpty()
            return InputPageBlockMap(
                geo=geo,
                zoom=block.zoom,
                w=block.w,
                h=block.h,
                caption=block.caption,
            )

        for field in ("blocks", "items"):
            value = getattr(block, field, None)
            if isinstance(value, list):
                setattr(
                    block,
                    field,
                    [CustomTelegramClient._rich_output_block_to_input(item) for item in value],
                )
        return block

    @staticmethod
    def _rich_output_to_input(rich_message):
        if type(rich_message).__name__ != "RichMessage":
            return rich_message

        photos = [
            tl_utils.get_input_photo(photo)
            for photo in getattr(rich_message, "photos", [])
        ]
        documents = [
            tl_utils.get_input_document(document)
            for document in getattr(rich_message, "documents", [])
        ]
        return InputRichMessage(
            blocks=[
                CustomTelegramClient._rich_output_block_to_input(block)
                for block in getattr(rich_message, "blocks", [])
            ],
            rtl=getattr(rich_message, "rtl", None),
            photos=photos,
            documents=documents,
        )

    @staticmethod
    def _rich_input(
        html: str | None = None,
        markdown: str | None = None,
        rich_message=None,
        *,
        rtl: bool | None = None,
        noautolink: bool | None = None,
    ):
        if rich_message is not None:
            return CustomTelegramClient._rich_output_to_input(rich_message)
        if html is not None:
            return InputRichMessageHTML(
                html=normalize_rich_html(html), rtl=rtl, noautolink=noautolink
            )
        if markdown is not None:
            return InputRichMessageMarkdown(
                markdown=markdown,
                rtl=rtl,
                noautolink=noautolink,
            )
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
                from .utils.rich import rich_message_to_html

                text, _ = html_parser.parse(rich_message_to_html(rich_message))
                return text or " "
            except Exception:
                return " "
        return " "

    async def send_rich_message(
        self,
        entity: EntityLike,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        reply_to: int | None = None,
        top_msg_id: int | None = None,
        buttons=None,
        silent: bool | None = None,
        rtl: bool | None = None,
        noautolink: bool | None = None,
    ):
        input_entity = await self.get_input_entity(entity)
        rich_input = self._rich_input(
            html,
            markdown,
            rich_message,
            rtl=rtl,
            noautolink=noautolink,
        )
        request = functions.messages.SendMessageRequest(
            peer=input_entity,
            message=self._rich_fallback_text(html, markdown, rich_message),
            no_webpage=True,
            silent=silent,
            reply_to=(
                InputReplyToMessage(
                    reply_to_msg_id=reply_to,
                    top_msg_id=top_msg_id,
                )
                if reply_to is not None
                else None
            ),
            reply_markup=self.build_reply_markup(buttons),
            rich_message=rich_input,
        )
        return self._get_response_message(request, await self(request), input_entity)

    async def edit_rich_message(
        self,
        entity: EntityLike,
        message,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        buttons=None,
        rtl: bool | None = None,
        noautolink: bool | None = None,
    ):
        input_entity = await self.get_input_entity(entity)
        rich_input = self._rich_input(
            html,
            markdown,
            rich_message,
            rtl=rtl,
            noautolink=noautolink,
        )
        request = functions.messages.EditMessageRequest(
            peer=input_entity,
            id=tl_utils.get_message_id(message),
            no_webpage=True,
            reply_markup=self.build_reply_markup(buttons),
            rich_message=rich_input,
        )
        return self._get_response_message(request, await self(request), input_entity)

    async def get_rich_message(self, entity: EntityLike, message, *, raw=True):
        input_entity = await self.get_input_entity(entity)
        result = await self(
            functions.messages.GetRichMessageRequest(
                peer=input_entity,
                id=tl_utils.get_message_id(message),
            )
        )
        rich_message = result.messages[0].rich_message if result.messages else None
        if raw or rich_message is None:
            return rich_message
        from .utils.rich import rich_message_to_html

        return rich_message_to_html(rich_message)

    async def translate_rich_message(
        self,
        to_lang: str,
        *,
        entity: EntityLike | None = None,
        messages=None,
        rich_messages=None,
        tone: str | None = None,
        raw=True,
    ):
        input_entity = (
            await self.get_input_entity(entity) if entity is not None else None
        )
        result = await self(
            functions.messages.TranslateRichMessageRequest(
                to_lang=to_lang,
                peer=input_entity,
                id=(
                    [tl_utils.get_message_id(message) for message in messages]
                    if messages is not None
                    else None
                ),
                text=rich_messages,
                tone=tone,
            )
        )
        translated = result.result
        if raw:
            return translated
        from .utils.rich import rich_message_to_html

        return [rich_message_to_html(item) for item in translated]

    async def compose_rich_message(
        self,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        proofread: bool | None = None,
        emojify: bool | None = None,
        translate_to_lang: str | None = None,
        tone=None,
        raw=True,
    ):
        result = await self(
            functions.messages.ComposeRichMessageWithAIRequest(
                proofread=proofread,
                emojify=emojify,
                text=self._rich_input(html, markdown, rich_message),
                translate_to_lang=translate_to_lang,
                tone=tone,
            )
        )
        composed = result.result
        if raw:
            return composed
        from .utils.rich import rich_message_to_html

        return rich_message_to_html(composed)

    async def save_rich_draft(
        self,
        entity: EntityLike,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        reply_to: int | None = None,
        rtl: bool | None = None,
        noautolink: bool | None = None,
    ):
        input_entity = await self.get_input_entity(entity)
        return await self(
            functions.messages.SaveDraftRequest(
                peer=input_entity,
                message="",
                reply_to=(
                    InputReplyToMessage(reply_to) if reply_to is not None else None
                ),
                rich_message=self._rich_input(
                    html,
                    markdown,
                    rich_message,
                    rtl=rtl,
                    noautolink=noautolink,
                ),
            )
        )

    async def send_rich_typing(
        self,
        entity: EntityLike,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        top_msg_id: int | None = None,
        can_stop: bool | None = None,
        keep_on_stop: bool | None = None,
    ):
        input_entity = await self.get_input_entity(entity)
        return await self(
            functions.messages.SetTypingRequest(
                peer=input_entity,
                top_msg_id=top_msg_id,
                action=InputSendMessageRichMessageDraftAction(
                    rich_message=self._rich_input(html, markdown, rich_message),
                    can_stop=can_stop,
                    keep_on_stop=keep_on_stop,
                ),
            )
        )

    async def send_rich_ephemeral(
        self,
        entity: EntityLike,
        receiver_id: EntityLike,
        html: str | None = None,
        *,
        markdown: str | None = None,
        rich_message=None,
        reply_to: int | None = None,
    ):
        input_entity = await self.get_input_entity(entity)
        return await self(
            functions.ephemeral.SendMessageRequest(
                peer=input_entity,
                receiver_id=receiver_id,
                message="",
                reply_to=(
                    InputReplyToMessage(reply_to) if reply_to is not None else None
                ),
                rich_message=self._rich_input(html, markdown, rich_message),
            )
        )

    rich_send_ephemeral = send_rich_ephemeral

    rich_get_message = get_rich_message
    rich_translate = translate_rich_message
    rich_answer_ai = compose_rich_message
    rich_save_draft = save_rich_draft
    rich_send_typing = send_rich_typing

    async def connect(self, unix_socket_path: str | None = None):
        if self.session is None:
            raise ValueError(
                "TelegramClient instance cannot be reused after logging out"
            )

        match True:
            case _ if self._loop is None:
                self._loop = helpers.get_running_loop()
            case _ if self._loop != helpers.get_running_loop():
                raise RuntimeError(
                    "The asyncio event loop must not change after connection (see the FAQ"
                    " for details)"
                )

        connection = self._connection(
            self.session.server_address,
            self.session.port,
            self.session.dc_id,
            loggers=self._log,
            proxy=self._proxy,
            local_addr=self._local_addr,
        )

        if unix_socket_path is not None:
            connection.set_unix_socket(unix_socket_path)

        if not await self._sender.connect(connection):
            # We don't want to init or modify anything if we were already connected
            return

        self.session.auth_key = self._sender.auth_key
        self.session.save()

        if self._catch_up:
            ss = SessionState(0, 0, False, 0, 0, 0, 0, None)
            cs = []

            for entity_id, state in self.session.get_update_states():
                if entity_id == 0:
                    # TODO current session doesn't store self-user info but adding that is breaking on downstream session impls
                    ss = SessionState(
                        0,
                        0,
                        False,
                        state.pts,
                        state.qts,
                        int(state.date.timestamp()),
                        state.seq,
                        None,
                    )
                else:
                    cs.append(ChannelState(entity_id, state.pts))

            self._message_box.load(ss, cs)
            for state in cs:
                try:
                    entity = self.session.get_input_entity(state.channel_id)
                except ValueError:
                    self._log[__name__].warning(
                        "No access_hash in cache for channel %s, will not catch up",
                        state.channel_id,
                    )
                else:
                    self._mb_entity_cache.put(
                        Entity(
                            EntityType.CHANNEL, entity.channel_id, entity.access_hash
                        )
                    )

        self._init_request.query = functions.help.GetConfigRequest()

        req = self._init_request
        if self._no_updates:
            req = functions.InvokeWithoutUpdatesRequest(req)

        await self._sender.send(functions.InvokeWithLayerRequest(LAYER, req))

        if self._message_box.is_empty():
            me = await self.get_me()
            if me:
                await self._on_login(
                    me
                )  # also calls GetState to initialize the MessageBox

        self._updates_handle = self.loop.create_task(self._update_loop())
        self._keepalive_handle = self.loop.create_task(self._keepalive_loop())

    @property
    def raw_updates_processor(self) -> Callable | None:
        return self._raw_updates_processor

    @raw_updates_processor.setter
    def raw_updates_processor(self, value: Callable):
        if self._raw_updates_processor is not None:
            raise ValueError("raw_updates_processor is already set")

        if not callable(value):
            raise ValueError("raw_updates_processor must be callable")

        self._raw_updates_processor = value

    @property
    def heroku_entity_cache(self) -> dict[int, CacheRecordEntity]:
        return self._heroku_entity_cache

    @property
    def heroku_perms_cache(self) -> dict[int, CacheRecordPerms]:
        return self._heroku_perms_cache

    @property
    def heroku_fullchannel_cache(self) -> dict[int, CacheRecordFullChannel]:
        return self._heroku_fullchannel_cache

    @property
    def heroku_fulluser_cache(self) -> dict[int, CacheRecordFullUser]:
        return self._heroku_fulluser_cache

    @property
    def forbidden_constructors(self) -> list[str]:
        return self._forbidden_constructors

    async def force_get_entity(self, *args, **kwargs):
        """Forcefully makes a request to Telegram to get the entity."""

        return await self.get_entity(*args, force=True, **kwargs)

    @tag_client_id("tg_id")
    async def get_entity(
        self,
        entity: EntityLike,
        exp: int = 5 * 60,
        force: bool = False,
    ):
        """
        Gets the entity and cache it

        :param entity: Entity to fetch
        :param exp: Expiration time of the cache record and maximum time of already cached record
        :param force: Whether to force refresh the cache (make API request)
        :return: :obj:`Entity`
        """

        if not hashable(entity):
            try:
                hashable_entity = next(
                    getattr(entity, attr)
                    for attr in {"user_id", "channel_id", "chat_id", "id"}
                    if getattr(entity, attr, None)
                )
            except StopIteration:
                logger.debug(
                    "Can't parse hashable from entity %s, using legacy resolve",
                    entity,
                )
                return await super().get_entity(entity)
        else:
            hashable_entity = entity

        if str(hashable_entity).startswith("-100"):
            hashable_entity = int(str(hashable_entity)[4:])

        if (
            not force
            and hashable_entity
            and hashable_entity in self._heroku_entity_cache
            and (
                not exp
                or self._heroku_entity_cache[hashable_entity].ts + exp > time.time()
            )
        ):
            logger.debug(
                "Using cached entity %s (%s)",
                entity,
                type(self._heroku_entity_cache[hashable_entity].entity).__name__,
            )
            return copy.deepcopy(self._heroku_entity_cache[hashable_entity].entity)

        resolved_entity = await super().get_entity(entity)

        if resolved_entity:
            cache_record = CacheRecordEntity(hashable_entity, resolved_entity, exp)
            self._heroku_entity_cache[hashable_entity] = cache_record
            logger.debug("Saved hashable_entity %s to cache", hashable_entity)

            if getattr(resolved_entity, "id", None):
                logger.debug("Saved resolved_entity id %s to cache", resolved_entity.id)
                self._heroku_entity_cache[resolved_entity.id] = cache_record

            if getattr(resolved_entity, "username", None):
                logger.debug(
                    "Saved resolved_entity username @%s to cache",
                    resolved_entity.username,
                )
                self._heroku_entity_cache[f"@{resolved_entity.username}"] = cache_record
                self._heroku_entity_cache[resolved_entity.username] = cache_record

        return copy.deepcopy(resolved_entity)

    @tag_client_id("tg_id")
    async def get_perms_cached(
        self,
        entity: EntityLike,
        user: EntityLike | None = None,
        exp: int = 5 * 60,
        force: bool = False,
    ):
        """
        Gets the permissions of the user in the entity and cache it

        :param entity: Entity to fetch
        :param user: User to fetch
        :param exp: Expiration time of the cache record and maximum time of already cached record
        :param force: Whether to force refresh the cache (make API request)
        :return: :obj:`ChatPermissions`
        """

        entity = await self.get_entity(entity)
        user = await self.get_entity(user) if user else None

        if not hashable(entity) or not hashable(user):
            try:
                hashable_entity = next(
                    getattr(entity, attr)
                    for attr in {"user_id", "channel_id", "chat_id", "id"}
                    if getattr(entity, attr, None)
                )
            except StopIteration:
                logger.debug(
                    "Can't parse hashable from entity %s, using legacy method",
                    entity,
                )
                return await self.get_permissions(entity, user)

            try:
                hashable_user = next(
                    getattr(user, attr)
                    for attr in {"user_id", "channel_id", "chat_id", "id"}
                    if getattr(user, attr, None)
                )
            except StopIteration:
                logger.debug(
                    "Can't parse hashable from user %s, using legacy method",
                    user,
                )
                return await self.get_permissions(entity, user)
        else:
            hashable_entity = entity
            hashable_user = user

        if str(hashable_entity).isdigit() and int(hashable_entity) < 0:
            hashable_entity = int(str(hashable_entity)[4:])

        if str(hashable_user).isdigit() and int(hashable_user) < 0:
            hashable_user = int(str(hashable_user)[4:])

        if (
            not force
            and hashable_entity
            and hashable_user
            and hashable_user in self._heroku_perms_cache.get(hashable_entity, {})
            and (
                not exp
                or self._heroku_perms_cache[hashable_entity][hashable_user].ts + exp
                > time.time()
            )
        ):
            logger.debug("Using cached perms %s (%s)", hashable_entity, hashable_user)
            return copy.deepcopy(
                self._heroku_perms_cache[hashable_entity][hashable_user].perms
            )

        resolved_perms = await self.get_permissions(entity, user)

        if resolved_perms:
            cache_record = CacheRecordPerms(
                hashable_entity,
                hashable_user,
                resolved_perms,
                exp,
            )
            self._heroku_perms_cache.setdefault(hashable_entity, {})[
                hashable_user
            ] = cache_record
            logger.debug("Saved hashable_entity %s perms to cache", hashable_entity)

            def save_user(key: str | int):
                nonlocal self, cache_record, user, hashable_user
                if getattr(user, "id", None):
                    self._heroku_perms_cache.setdefault(key, {})[user.id] = cache_record

                if getattr(user, "username", None):
                    self._heroku_perms_cache.setdefault(key, {})[
                        f"@{user.username}"
                    ] = cache_record
                    self._heroku_perms_cache.setdefault(key, {})[
                        user.username
                    ] = cache_record

            if getattr(entity, "id", None):
                logger.debug("Saved resolved_entity id %s perms to cache", entity.id)
                save_user(entity.id)

            if getattr(entity, "username", None):
                logger.debug(
                    "Saved resolved_entity username @%s perms to cache",
                    entity.username,
                )
                save_user(f"@{entity.username}")
                save_user(entity.username)

        return copy.deepcopy(resolved_perms)

    async def get_fullchannel(
        self,
        entity: EntityLike,
        exp: int = 300,
        force: bool = False,
    ) -> ChannelFull:
        """
        Gets the FullChannelRequest and cache it

        :param entity: Channel to fetch ChannelFull of
        :param exp: Expiration time of the cache record and maximum time of already cached record
        :param force: Whether to force refresh the cache (make API request)
        :return: :obj:`ChannelFull`
        """
        if not hashable(entity):
            try:
                hashable_entity = next(
                    getattr(entity, attr)
                    for attr in {"channel_id", "chat_id", "id"}
                    if getattr(entity, attr, None)
                )
            except StopIteration:
                logger.debug(
                    (
                        "Can't parse hashable from entity %s, using legacy fullchannel"
                        " request"
                    ),
                    entity,
                )
                return await self(GetFullChannelRequest(channel=entity))
        else:
            hashable_entity = entity

        if str(hashable_entity).isdigit() and int(hashable_entity) < 0:
            hashable_entity = int(str(hashable_entity)[4:])

        if (
            not force
            and self._heroku_fullchannel_cache.get(hashable_entity)
            and not self._heroku_fullchannel_cache[hashable_entity].expired
            and self._heroku_fullchannel_cache[hashable_entity].ts + exp > time.time()
        ):
            return self._heroku_fullchannel_cache[hashable_entity].full_channel

        result = await self(GetFullChannelRequest(channel=entity))
        self._heroku_fullchannel_cache[hashable_entity] = CacheRecordFullChannel(
            hashable_entity,
            result,
            exp,
        )
        return result

    async def get_fulluser(
        self,
        entity: EntityLike,
        exp: int = 300,
        force: bool = False,
    ) -> UserFull:
        """
        Gets the FullUserRequest and cache it

        :param entity: User to fetch UserFull of
        :param exp: Expiration time of the cache record and maximum time of already cached record
        :param force: Whether to force refresh the cache (make API request)
        :return: :obj:`UserFull`
        """
        if not hashable(entity):
            try:
                hashable_entity = next(
                    getattr(entity, attr)
                    for attr in {"user_id", "chat_id", "id"}
                    if getattr(entity, attr, None)
                )
            except StopIteration:
                logger.debug(
                    (
                        "Can't parse hashable from entity %s, using legacy fulluser"
                        " request"
                    ),
                    entity,
                )
                return await self(GetFullUserRequest(entity))
        else:
            hashable_entity = entity

        if str(hashable_entity).isdigit() and int(hashable_entity) < 0:
            hashable_entity = int(str(hashable_entity)[4:])

        if (
            not force
            and self._heroku_fulluser_cache.get(hashable_entity)
            and not self._heroku_fulluser_cache[hashable_entity].expired
            and self._heroku_fulluser_cache[hashable_entity].ts + exp > time.time()
        ):
            return self._heroku_fulluser_cache[hashable_entity].full_user

        result = await self(GetFullUserRequest(entity))
        self._heroku_fulluser_cache[hashable_entity] = CacheRecordFullUser(
            hashable_entity,
            result,
            exp,
        )
        return result

    @staticmethod
    def _find_message_obj_in_frame(
        chat_id: int,
        frame: inspect.FrameInfo,
    ) -> Message | None:
        """
        Finds the message object from the frame
        """
        logger.debug("Finding message object in frame %s", frame)
        return next(
            (
                obj
                for obj in frame.frame.f_locals.values()
                if isinstance(obj, Message)
                and getattr(obj.reply_to, "forum_topic", False)
                and chat_id == getattr(obj.peer_id, "channel_id", None)
            ),
            None,
        )

    async def _find_message_obj_in_stack(
        self,
        chat: EntityLike,
        stack: list[inspect.FrameInfo],
    ) -> Message | None:
        """
        Finds the message object from the stack
        """
        chat_id = (await self.get_entity(chat, exp=0)).id
        logger.debug("Finding message object in stack for chat %s", chat_id)
        return next(
            (
                self._find_message_obj_in_frame(chat_id, frame_info)
                for frame_info in stack
                if self._find_message_obj_in_frame(chat_id, frame_info)
            ),
            None,
        )

    async def _find_topic_in_stack(
        self,
        chat: EntityLike,
        stack: list[inspect.FrameInfo],
    ) -> Message | None:
        """
        Finds the message object from the stack
        """
        message = await self._find_message_obj_in_stack(chat, stack)
        return (
            (message.reply_to.reply_to_top_id or message.reply_to.reply_to_msg_id)
            if message
            else None
        )

    async def _topic_guesser(
        self,
        native_method: typing.Callable[..., typing.Awaitable[Message]],
        stack: list[inspect.FrameInfo],
        *args,
        **kwargs,
    ):
        no_retry = kwargs.pop("_topic_no_retry", False)
        try:
            return await native_method(*args, **kwargs)
        except TopicDeletedError:
            if no_retry:
                raise

            logger.debug("Topic deleted, trying to guess topic id")

            topic = await self._find_topic_in_stack(args[0], stack)

            logger.debug("Guessed topic id: %s", topic)

            if not topic:
                raise

            kwargs["reply_to"] = topic
            kwargs["_topic_no_retry"] = True
            return await self._topic_guesser(native_method, stack, *args, **kwargs)

    async def send_file(self, *args, **kwargs) -> Message:
        return await self._topic_guesser(
            super().send_file,
            inspect.stack(),
            *args,
            **kwargs,
        )

    async def send_message(self, *args, **kwargs) -> Message:
        return await self._topic_guesser(
            super().send_message,
            inspect.stack(),
            *args,
            **kwargs,
        )

    async def _call(
        self,
        sender: MTProtoSender,
        request: TLRequest,
        ordered: bool = False,
        flood_sleep_threshold: int | None = None,
    ):
        """
        Calls the given request and handles user-side forbidden constructors

        :param sender: Sender to use
        :param request: Request to send
        :param ordered: Whether to send the request ordered
        :param flood_sleep_threshold: Flood sleep threshold
        :return: The result of the request
        """

        # ⚠️⚠️  WARNING!  ⚠️⚠️
        # If you are a module developer, and you'll try to bypass this protection to
        # force user join your channel, you will be added to SCAM modules
        # list and you will be banned from Heroku federation.
        # Let USER decide, which channel he will follow. Do not be so petty
        # I hope, you understood me.
        # Thank you

        not_tuple = False
        if not is_list_like(request):
            not_tuple = True
            request = (request,)

        new_request = []

        for item in request:
            if item.CONSTRUCTOR_ID in self._forbidden_constructors and next(
                (
                    frame_info.frame.f_locals["self"]
                    for frame_info in inspect.stack()
                    if hasattr(frame_info, "frame")
                    and hasattr(frame_info.frame, "f_locals")
                    and isinstance(frame_info.frame.f_locals, dict)
                    and "self" in frame_info.frame.f_locals
                    and isinstance(frame_info.frame.f_locals["self"], Module)
                    and not getattr(
                        frame_info.frame.f_locals["self"], "__origin__", ""
                    ).startswith("<core")
                ),
                None,
            ):
                logger.debug(
                    "🎉 I protected you from unintented %s (%s)!",
                    item.__class__.__name__,
                    item,
                )
                continue

            new_request += [item]

        if not new_request:
            return

        return await super()._call(
            sender,
            new_request[0] if not_tuple else tuple(new_request),
            ordered,
            flood_sleep_threshold,
        )

    def _internal_forbid_ctor(self, constructors: list):
        self._forbidden_constructors.extend(constructors)
        self._forbidden_constructors = list(set(self._forbidden_constructors))

    def forbid_constructor(self, constructor: int):
        """
        Forbids the given constructor to be called

        :param constructor: Constructor id to forbid
        """
        self._internal_forbid_ctor([constructor])

    def forbid_constructors(self, constructors: list):
        """
        Forbids the given constructors to be called.

        :param constructors: Constructor ids to forbid
        """
        self._internal_forbid_ctor(constructors)

    def _handle_update(
        self: "CustomTelegramClient",
        update: Updates | UpdatesCombined | UpdateShort,
    ):
        if self._raw_updates_processor is not None:
            self._raw_updates_processor(update)

        super()._handle_update(update)
