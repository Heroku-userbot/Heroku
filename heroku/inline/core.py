"""Inline buttons, galleries and other Telethon bot stuff"""

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
import logging
import os
import sqlite3
import time
import typing

from herokutl import TelegramClient, events
from herokutl.errors.rpcerrorlist import (
    AccessTokenExpiredError,
    AccessTokenInvalidError,
    AuthKeyUnregisteredError,
    FloodWaitError,
    InputUserDeactivatedError,
    UserIsBlockedError,
    YouBlockedUserError,
)
from herokutl.sessions import SQLiteSession
from herokutl.tl.functions.contacts import UnblockRequest
from herokutl.tl.functions.messages import (
    GetDialogFiltersRequest,
    SetTypingRequest,
    UpdateDialogFilterRequest,
)
from herokutl.tl.types import (
    DialogFilter,
    InputPeerUser,
    Message,
    SendMessageTypingAction,
    UpdateBotChatBoost,
    UpdateBotChatInviteRequester,
    UpdateBotGuestChatQuery,
    UpdateBotInlineSend,
    UpdateBotMessageReaction,
    UpdateBotMessageReactions,
    UpdateBotPrecheckoutQuery,
    UpdateBotShippingQuery,
    UpdateChannelParticipant,
    UpdateChatParticipant,
    UpdateMessagePoll,
    UpdateMessagePollVote,
)
from herokutl.utils import get_display_name

from .. import main, utils
from ..database import Database
from ..tl_cache import CustomTelegramClient
from ..translations import Translator
from .bot_pm import BotPM
from .events import Events
from .form import Form
from .gallery import Gallery
from .list import List
from .query_gallery import QueryGallery
from .tl import TelethonBot, web_document
from .token_obtainment import TokenObtainment
from .utils import Utils

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from ..loader import Modules

BotUpdateType = typing.Literal[
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "inline_query",
    "callback_query",
    "chosen_inline_result",
    "shipping_query",
    "pre_checkout_query",
    "poll",
    "poll_answer",
    "my_chat_member",
    "chat_member",
    "chat_join_request",
    "message_reaction",
    "message_reaction_count",
    "chat_boost",
    "removed_chat_boost",
    "guest_message",
]

_BOT_UPDATE_EVENTS: dict[BotUpdateType, typing.Callable[[], object]] = {
    # Default updates
    "message": lambda: events.NewMessage(),
    "edited_message": lambda: events.MessageEdited(),
    "channel_post": lambda: events.NewMessage(),
    "edited_channel_post": lambda: events.MessageEdited(),
    "inline_query": lambda: events.InlineQuery(),
    "callback_query": lambda: events.CallbackQuery(),
    # Raw-based
    "chosen_inline_result": lambda: events.Raw(types=UpdateBotInlineSend),
    "shipping_query": lambda: events.Raw(types=UpdateBotShippingQuery),
    "pre_checkout_query": lambda: events.Raw(types=UpdateBotPrecheckoutQuery),
    "poll": lambda: events.Raw(types=UpdateMessagePoll),
    "poll_answer": lambda: events.Raw(types=UpdateMessagePollVote),
    "my_chat_member": lambda: events.Raw(
        types=(UpdateChatParticipant, UpdateChannelParticipant)
    ),
    "chat_member": lambda: events.Raw(
        types=(UpdateChatParticipant, UpdateChannelParticipant)
    ),
    "chat_join_request": lambda: events.Raw(types=UpdateBotChatInviteRequester),
    "message_reaction": lambda: events.Raw(types=UpdateBotMessageReaction),
    "message_reaction_count": lambda: events.Raw(types=UpdateBotMessageReactions),
    "chat_boost": lambda: events.Raw(types=UpdateBotChatBoost),
    "removed_chat_boost": lambda: events.Raw(types=UpdateBotChatBoost),
    "guest_message": lambda: events.Raw(types=UpdateBotGuestChatQuery),
}


class InlineManager(
    Utils,
    Events,
    TokenObtainment,
    Form,
    Gallery,
    QueryGallery,
    List,
    BotPM,
):
    """
    Inline buttons, galleries and other Telethon bot stuff
    :param client: Telegram client
    :param db: Database instance
    :param allmodules: All modules
    :type client: heroku.tl_cache.CustomTelegramClient
    :type db: heroku.database.Database
    :type allmodules: heroku.loader.Modules
    """

    def __init__(
        self,
        client: CustomTelegramClient,
        db: Database,
        allmodules: "Modules",  # type: ignore  # noqa: F821
    ):
        """Initialize InlineManager to create forms"""
        self._client = client
        self._db = db
        self._allmodules = allmodules
        self.translator: Translator = allmodules.translator

        self._units: dict[str, dict] = {}
        self._custom_map: dict[str, callable] = {}
        self.fsm: dict[str, str] = {}
        self._error_events: dict[str, asyncio.Event] = {}

        self._markup_ttl = 60 * 60 * 24
        self.init_complete = False

        self._token = db.get("heroku.inline", "bot_token", False)

        self._me: int = None
        self._name: str = None
        self._bot_client: TelegramClient = None
        self._task: asyncio.Future = None
        self._cleaner_task: asyncio.Future = None
        self.bot: TelethonBot = None
        self.bot_id: int = None
        self.bot_username: str = None

        self._bot_update_handlers: dict[str, tuple[str, typing.Callable]] = {}
        self._bot_handler_refs: dict[str, tuple[typing.Callable, object]] = {}

    async def _cleaner(self):
        """Cleans outdated inline units"""
        while True:
            for unit_id, unit in self._units.copy().items():
                if (unit.get("ttl") or (time.time() + self._markup_ttl)) < time.time():
                    await self._unload_unit(unit_id)

            await asyncio.sleep(5)

    @staticmethod
    def _web_document(url: str | None, **kwargs):
        return web_document(url, **kwargs)

    def _register_bot_handler(
        self,
        handler: typing.Callable,
        event_builder,
        *,
        handler_id: str | None = None,
    ):
        self._bot_client.add_event_handler(handler, event_builder)
        if handler_id:
            self._bot_handler_refs[handler_id] = (handler, event_builder)

    def _register_builtin_handlers(self):
        self._register_bot_handler(self._inline_handler, events.InlineQuery())
        self._register_bot_handler(self._callback_query_handler, events.CallbackQuery())
        self._register_bot_handler(
            self._chosen_inline_handler, events.Raw(types=UpdateBotInlineSend)
        )
        self._register_bot_handler(self._message_handler, events.NewMessage())

        for handler_id, (update_type, handler) in self._bot_update_handlers.items():
            self._attach_custom_handler(handler_id, update_type, handler)

    def _cleanup_stale_bot_sessions(self, bot_uid: str):
        prefix = f"heroku-{self._me}-bot-"
        keep_stem = f"{prefix}{bot_uid}"

        try:
            entries = list(os.scandir(main.SESSIONS_DIR))
        except FileNotFoundError:
            return

        for entry in entries:
            if not entry.is_file() or not entry.name.startswith(prefix):
                continue

            if entry.name.split(".session", 1)[0] == keep_stem:
                continue

            try:
                os.remove(entry.path)
            except OSError:
                logger.exception(
                    "Failed to remove stale bot session file %s", entry.path
                )

    async def register_manager(
        self,
        after_break: bool = False,
        ignore_token_checks: bool = False,
        force_new_bot: bool = False,
    ):
        """
        Register manager
        :param after_break: Loop marker
        :param ignore_token_checks: If `True`, will not check for token
        :param force_new_bot: If `True`, will not search for an existing bot
            in BotFather and will create a brand new one instead
        :type after_break: bool
        :type ignore_token_checks: bool
        :type force_new_bot: bool
        :return: None
        :rtype: None
        """
        self._me = self._client.tg_id
        self._name = get_display_name(self._client.heroku_me)

        if not ignore_token_checks:
            is_token_asserted = await self._assert_token(skip_search=force_new_bot)
            if not is_token_asserted:
                self.init_complete = False
                return

        self.init_complete = False

        if self._bot_client:
            try:
                await self._bot_client.disconnect()
            except Exception:
                pass

        bot_uid = self._token.split(":", 1)[0]
        self._cleanup_stale_bot_sessions(bot_uid)
        self._bot_client = TelegramClient(
            SQLiteSession(
                os.path.join(main.SESSIONS_DIR, f"heroku-{self._me}-bot-{bot_uid}")
            ),
            self._client.api_id,
            self._client.api_hash,
            receive_updates=True,
        )

        try:
            await self._bot_client.start(bot_token=self._token)
            self.bot = TelethonBot(self._bot_client)
            self._bot = self.bot
            self._register_builtin_handlers()
            bot_me = await self._bot_client.get_me()
            telegram_id = bot_me.id
            self._bot_client._tg_id = telegram_id
            self._bot_client.tg_id = telegram_id
            self._bot_client.hikka_me = bot_me
            self._bot_client.heroku_me = bot_me
            self.bot_username = bot_me.username
            self.bot_id = bot_me.id
        except (
            AccessTokenExpiredError,
            AccessTokenInvalidError,
            AuthKeyUnregisteredError,
        ):
            logger.critical("Token expired, revoking...")
            return await self._dp_revoke_token(False)
        except FloodWaitError as e:
            logger.error(
                "Inline bot authorization flood wait: %ss. "
                "Inline manager initialization skipped for this run.",
                e.seconds,
            )
            self.init_complete = False
            return False
        except sqlite3.OperationalError:
            logger.critical(
                "Bot session database is locked, could not start bot client",
                exc_info=True,
            )
            self.init_complete = False
            return False

        if self._db.get("heroku.inline", "needs_inline_setup", False):
            try:
                await self._configure_inline_bot(self.bot_username)
            except Exception:
                pass

            self._db.set("heroku.inline", "needs_inline_setup", False)

        result = await self._ping_bot(after_break)
        if result is not True:
            return result

        self.init_complete = True

        try:
            _folders = await self._client(GetDialogFiltersRequest())
            for folder in _folders.filters:
                if getattr(folder, "title", None) == "Heroku":
                    if any(
                        [
                            isinstance(peer, InputPeerUser) and peer.user_id == self.bot_id
                            for peer in folder.include_peer
                        ]
                    ):
                        break

                    pinned = [await self._client.get_input_entity(self.bot_id)]
                    include = folder.include_peers
                    exclude = folder.exclude_peers
                    emoticon = folder.emoticon
                    color = folder.color

                    await self._client(
                        UpdateDialogFilterRequest(
                            folder.id,
                            DialogFilter(
                                folder.id,
                                pinned_peers=pinned,
                                include_peers=include,
                                exclude_peers=exclude,
                                emoticon=emoticon,
                                color=color,
                            ),
                        )
                    )
                    break
        except Exception:
            logger.exception("Failed to add the bot to the Heroku folder")

        self._cleaner_task = asyncio.ensure_future(self._cleaner())
        asyncio.ensure_future(self._allmodules.send_inline_ready())

    async def _ping_bot(
        self,
        after_break: bool = False,
    ) -> bool:
        try:
            await self.bot(
                SetTypingRequest(self._client.tg_id, SendMessageTypingAction())
            )
            return True
        except UserIsBlockedError:
            await self._client(UnblockRequest(id=self.bot_id))
            return True
        except Exception:
            pass

        try:
            m = await self._client.send_message(self.bot_username, "/start heroku init")
        except (InputUserDeactivatedError, ValueError):
            logger.warning(
                "Inline bot @%s is deactivated (frozen) or not found, "
                "creating a new one",
                self.bot_username,
            )
            self._db.set("heroku.inline", "bot_token", None)
            self._token = False

            if not after_break:
                return await self.register_manager(True, force_new_bot=True)

            self.init_complete = False
            return False
        except YouBlockedUserError:
            await self._client(UnblockRequest(id=self.bot_username))
            try:
                m = await self._client.send_message(
                    self.bot_username, "/start heroku init"
                )
            except Exception:
                logger.critical("Can't unblock users bot", exc_info=True)
                return False
        except Exception:
            self.init_complete = False
            logger.critical("Initialization of inline manager failed!", exc_info=True)
            return False

        await self._client.delete_messages(self.bot_username, m)
        return True

    async def _stop(self):
        """Stop the bot"""
        if self._task:
            self._task.cancel()
        if self._bot_client:
            await self._bot_client.disconnect()
        if self._cleaner_task:
            self._cleaner_task.cancel()

    async def _restart_polling(self):
        """Kept for API compatibility; Telethon handlers are updated in-place."""
        return

    def _attach_custom_handler(
        self,
        handler_id: str,
        update_type: str,
        handler: typing.Callable,
    ):
        builder_factory = _BOT_UPDATE_EVENTS.get(update_type)
        if not builder_factory or not self._bot_client:
            return

        event_builder = builder_factory()
        self._register_bot_handler(handler, event_builder, handler_id=handler_id)

    def register_bot_update_handler(
        self,
        handler_id: str,
        update_type: str,
        handler: typing.Callable,
    ):
        """
        Register a bot update handler from a module
        :param handler_id: Unique handler ID (use uuid4)
        :param update_type: One of the supported Telegram update types
        :param handler: Async callable to handle the update
        """
        if update_type not in _BOT_UPDATE_EVENTS:
            logger.warning(
                "Unsupported bot update type: %s (handler_id=%s)",
                update_type,
                handler_id,
            )
            return

        self._bot_update_handlers[handler_id] = (update_type, handler)
        logger.debug(
            "Registered bot update handler %s for update type %s",
            handler_id,
            update_type,
        )

        if self.init_complete and self._bot_client:
            self._attach_custom_handler(handler_id, update_type, handler)

    def unregister_bot_update_handler(self, handler_id: str):
        """
        Unregister a bot update handler and rebuild dispatcher
        :param handler_id: Handler ID to remove
        """
        if handler_id not in self._bot_update_handlers:
            return

        del self._bot_update_handlers[handler_id]
        removed_ref = self._bot_handler_refs.pop(handler_id, None)
        logger.debug("Unregistered bot update handler %s", handler_id)

        if not self._bot_client:
            return

        refs = list(self._bot_handler_refs.values())
        if removed_ref:
            refs.append(removed_ref)

        for handler, event_builder in refs:
            self._bot_client.remove_event_handler(handler, event_builder)
        self._bot_handler_refs.clear()

        for hid, (update_type, handler) in self._bot_update_handlers.items():
            builder_factory = _BOT_UPDATE_EVENTS.get(update_type)
            if not builder_factory:
                continue
            event_builder = builder_factory()
            self._bot_client.add_event_handler(handler, event_builder)
            self._bot_handler_refs[hid] = (handler, event_builder)
        logger.debug("Rebuilt custom handlers after unregistering %s", handler_id)

    async def _invoke_unit(
        self,
        unit_id: str,
        message: Message,
        reply_to: Message | int | None = None,
    ) -> Message:
        event = asyncio.Event()
        self._error_events[unit_id] = event

        q: "InlineResults" = None  # type: ignore  # noqa: F821
        exception: Exception = None

        async def result_getter():
            nonlocal unit_id, q
            try:
                q = await self._client.inline_query(self.bot_username, unit_id)
            except Exception:
                logger.exception("Inline query for unit %s failed", unit_id)

        async def event_poller():
            nonlocal exception
            try:
                await asyncio.wait_for(event.wait(), timeout=10)
            except asyncio.TimeoutError:
                logger.debug("Inline query for unit %s timed out after 10s", unit_id)
                return
            if self._error_events.get(unit_id):
                exception = self._error_events[unit_id]

        result_getter_task = asyncio.ensure_future(result_getter())
        event_poller_task = asyncio.ensure_future(event_poller())

        _, pending = await asyncio.wait(
            [result_getter_task, event_poller_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        self._error_events.pop(unit_id, None)

        if exception:
            raise exception  # skipcq: PYL-E0702

        if not q:
            raise Exception("No query results")

        return await q[0].click(
            utils.get_chat_id(message) if isinstance(message, Message) else message,
            reply_to=(
                reply_to
                if reply_to is not None
                else (
                    message.reply_to_msg_id if isinstance(message, Message) else None
                )
            ),
        )
