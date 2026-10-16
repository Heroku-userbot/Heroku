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
import json
import logging
import os
import string
import time
from pathlib import Path

from herokutl.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from herokutl.sessions import MemorySession, SQLiteSession
from herokutl.tl.custom import Message
from herokutl.tl.types import User
from herokutl.utils import parse_phone

from .. import loader, main, security, utils
from ..loader import LOADED_MODULES_PATH
from .._internal import private_write, register_secret, restart
from ..inline.types import InlineCall
from ..tl_cache import CustomTelegramClient
from ..version import __version__

logger = logging.getLogger(__name__)


@loader.tds
class HerokuWebMod(loader.Module):
    """Inline account management"""

    strings = {"name": "HerokuAccounts"}

    @loader.command()
    async def addacc(self, message: Message):
        if "JAMHOST" in os.environ:
            await utils.answer(message, self.strings["host_denied"])
            return

        user_id = utils.get_args(message)
        if not user_id:
            reply: Message = await message.get_reply_message()
            user_id = reply.sender_id if reply else None
        else:
            user_id = user_id[0]

        user = None
        if user_id:
            try:
                user_id = int(user_id)
            except ValueError:
                pass

            try:
                user = await self._client.get_entity(user_id)
            except Exception as e:
                logger.error(f"Error while fetching user: {e}")

        if not user or not isinstance(user, User) or user.bot:
            await utils.answer(message, self.strings["invalid_target"])
            return

        if user.id == self.tg_id or "force_insecure" in message.text.lower():
            await self._inline_login(message, user)
            return

        try:
            if not await self.inline.form(
                self.strings["add_user_confirm"].format(
                    utils.escape_html(user.first_name),
                    user.id,
                ),
                message=message,
                reply_markup=[
                    {
                        "text": self.strings["btn_yes"],
                        "callback": self._inline_login,
                        "args": (user,),
                    },
                    {"text": self.strings["btn_no"], "action": "close"},
                ],
                photo="",
            ):
                raise Exception

        except Exception:
            await utils.answer(
                message,
                self.strings["add_user_insecure"].format(
                    utils.escape_html(user.first_name),
                    user.id,
                    utils.escape_html(self.get_prefix()),
                    user.id,
                ),
            )
        return

    async def donate(self, call: InlineCall):
        await call.edit(
            self.strings["donate"],
            reply_markup=[
                [
                    {"text": "CryptoBot", "url": "http://t.me/send?start=IVJdKAOn8ihG"}
                ],
                [
                    {"text": "TON", "url": "ton://transfer/UQD_vekSRxbCmgBnYLhPFaeN5ilviOh8onpOXa8VDFmhZBLO?text=%D0%9C%D1%8F%D0%B2"}
                ],
                [
                    {"text": "DALink", "url": "https://dalink.to/zetgo"}
                ],
                [
                    {"text": self.strings["feedback_me"], "url": "https://t.me/ZetGo"}
                ],
            ],
        )

    async def _inline_login(
        self,
        call: Message | InlineCall,
        user: User,
        after_fail: bool = False,
        is_switch: bool = False,
    ):
        reply_markup = [
            {
                "text": self.strings["enter_number"],
                "input": self.strings["your_phone_number"],
                "handler": self.inline_phone_handler,
                "args": (user, is_switch),
            }
        ]

        fail = self.strings["incorrect_number"] if after_fail else ""

        await utils.answer(
            call,
            fail + self.strings["enter_number_format"],
            reply_markup=reply_markup,
            always_allow=[user.id],
        )

    def _get_client(self) -> CustomTelegramClient:
        return CustomTelegramClient(
            MemorySession(),
            main.heroku.api_token.ID,
            main.heroku.api_token.HASH,
            connection=main.heroku.conn,
            proxy=main.heroku.proxy,
            connection_retries=None,
            device_model=main.get_app_name(),
            system_version="Windows 10",
            app_version=".".join(map(str, __version__)) + " x64",
            lang_code="en",
            system_lang_code="en-US",
        )

    def _clone_switch_db(self, old_id: int, new_id: int) -> dict:
        data = json.loads(json.dumps(dict(self._db)))

        inline_data = data.setdefault("heroku.inline", {})
        if isinstance(inline_data, dict):
            inline_data["bot_token"] = None
            inline_data["custom_bot"] = False
            inline_data.pop("bot_id", None)

        security_data = data.setdefault(security.__name__, {})
        for key in ("owner", "all_users"):
            users = security_data.get(key, [])
            if isinstance(users, list):
                users = [user for user in users if user != old_id]
                if new_id not in users:
                    users.append(new_id)
                security_data[key] = users

        return data

    def _archive_identity_file(self, path: Path, suffix: int) -> Path | None:
        if not path.exists():
            return None

        archived = path.with_name(f"{path.name}.bak-switch-{suffix}")
        if archived.exists():
            raise RuntimeError(f"Backup file already exists: {archived.name}")

        path.rename(archived)
        return archived

    def _restore_identity_file(
        self,
        original: Path,
        archived: Path | None,
        created: bool = False,
    ) -> None:
        if archived and archived.exists():
            if original.exists():
                original.unlink()
            archived.rename(original)
        elif created and original.exists():
            original.unlink()

    async def _copy_switch_db(self, new_id: int, data: dict) -> None:
        redis = getattr(self._db, "_redis", None)
        if redis:
            await utils.run_sync(
                lambda: redis.set(str(new_id), json.dumps(data, ensure_ascii=True))
            )

        private_write(
            Path(main.BASE_PATH) / f"config-{new_id}.json",
            json.dumps(data, ensure_ascii=False, indent=4),
        )

    async def _save_switch_session(
        self,
        client: CustomTelegramClient,
        new_id: int,
    ) -> None:
        session = SQLiteSession(os.path.join(main.SESSIONS_DIR, f"heroku-{new_id}"))
        session.set_dc(
            client.session.dc_id,
            client.session.server_address,
            client.session.port,
        )
        session.auth_key = client.session.auth_key
        session.save()
        await client.disconnect()

    def _switch_loaded_modules(self, old_id: int, new_id: int, suffix: int) -> list:
        moved = []
        for path in LOADED_MODULES_PATH.glob(f"*_{old_id}.py"):
            target = path.with_name(
                path.name.removesuffix(f"_{old_id}.py") + f"_{new_id}.py"
            )
            backup = None
            if target.exists():
                backup = self._archive_identity_file(target, suffix)

            record = [path, target, backup, False]
            moved.append(record)
            path.rename(target)
            record[3] = True

        return moved

    def _restore_loaded_modules(self, moved: list) -> None:
        for original, target, backup, renamed in reversed(moved):
            if renamed and target.exists() and not original.exists():
                target.rename(original)
            if backup and backup.exists():
                backup.rename(target)

    async def _switch_account(self, client: CustomTelegramClient) -> None:
        old_id = self.tg_id
        me = await client.get_me()
        if not me:
            raise RuntimeError("New session is not authorized")

        new_id = me.id
        if old_id == new_id:
            await main.heroku.save_client_session(client, delay_restart=False)
            return

        suffix = int(time.time())
        base = Path(main.SESSIONS_DIR)
        old_session = base / f"heroku-{old_id}.session"
        old_journal = base / f"heroku-{old_id}.session-journal"
        old_config = Path(main.BASE_PATH) / f"config-{old_id}.json"
        new_session = base / f"heroku-{new_id}.session"
        new_journal = base / f"heroku-{new_id}.session-journal"
        new_config = Path(main.BASE_PATH) / f"config-{new_id}.json"
        new_files = {new_session, new_journal, new_config}
        redis = getattr(self._db, "_redis", None)
        redis_backup = None

        db_data = self._clone_switch_db(old_id, new_id)
        archived = []
        moved_modules = []

        try:
            if redis:
                redis_backup = await utils.run_sync(lambda: redis.get(str(new_id)))

            for path in (
                old_session,
                old_journal,
                old_config,
                new_session,
                new_journal,
                new_config,
            ):
                archived.append((path, self._archive_identity_file(path, suffix)))

            await self._copy_switch_db(new_id, db_data)
            await self._save_switch_session(client, new_id)
            moved_modules = self._switch_loaded_modules(old_id, new_id, suffix)
        except Exception:
            logger.exception("Account switch migration failed")
            if redis:
                if redis_backup is None:
                    await utils.run_sync(lambda: redis.delete(str(new_id)))
                else:
                    await utils.run_sync(lambda: redis.set(str(new_id), redis_backup))

            try:
                self._restore_loaded_modules(moved_modules)
            except Exception:
                logger.exception(
                    "Failed to restore loaded modules after switch failure"
                )

            for original, backup in reversed(archived):
                try:
                    self._restore_identity_file(
                        original,
                        backup,
                        original in new_files,
                    )
                except Exception:
                    logger.exception(
                        "Failed to restore %s after switch failure",
                        original,
                    )
            raise

    async def schedule_restart(self, call, client, is_switch: bool = False):
        await utils.answer(call, self.strings["login_successful"])
        # Yeah-yeah, ikr, but it's the only way to restart
        await asyncio.sleep(1)
        try:
            if is_switch:
                await self._switch_account(client)
                restart()
            else:
                await main.heroku.save_client_session(client, delay_restart=False)
                restart()
        except Exception as e:
            logger.exception("Failed to finish inline login")
            await utils.answer(
                call,
                self.strings["switch_failed"].format(utils.escape_html(str(e))),
                reply_markup={"text": self.strings["btn_no"], "action": "close"},
            )

    async def inline_phone_handler(self, call, data, user, is_switch: bool = False):
        register_secret(data)
        if not (phone := parse_phone(data)):
            await self._inline_login(call, user, after_fail=True, is_switch=is_switch)
            return

        client = self._get_client()

        await client.connect()
        try:
            await client.send_code_request(phone)
        except FloodWaitError as e:
            await utils.answer(
                call,
                self.strings["floodwait_error"].format(e.seconds),
                reply_markup={"text": self.strings["btn_no"], "action": "close"},
            )
            return
        except PhoneNumberInvalidError:
            await self._inline_login(call, user, after_fail=True, is_switch=is_switch)
            return

        reply_markup = {
            "text": self.strings["enter_code"],
            "input": self.strings["login_code"],
            "handler": self.inline_code_handler,
            "args": (
                client,
                phone,
                user,
                is_switch,
            ),
        }

        await utils.answer(
            call,
            self.strings["code_sent"],
            reply_markup=reply_markup,
            always_allow=[user.id],
        )

    async def inline_code_handler(
        self, call, data, client, phone, user, is_switch: bool = False
    ):
        register_secret(data)
        _code_markup = {
            "text": self.strings["enter_code"],
            "input": self.strings["login_code"],
            "handler": self.inline_code_handler,
            "args": (
                client,
                phone,
                user,
                is_switch,
            ),
        }
        if not data or len(data) != 5:
            await utils.answer(
                call,
                self.strings["invalid_code"],
                reply_markup=_code_markup,
                always_allow=[user.id],
            )
            return

        if any(c not in string.digits for c in data):
            await utils.answer(
                call,
                self.strings["invalid_code_digits"],
                reply_markup=_code_markup,
                always_allow=[user.id],
            )
            return

        try:
            await client.sign_in(phone, code=data)
        except SessionPasswordNeededError:
            reply_markup = [
                {
                    "text": self.strings["enter_2fa"],
                    "input": self.strings["your_2fa"],
                    "handler": self.inline_2fa_handler,
                    "args": (
                        client,
                        phone,
                        user,
                        is_switch,
                    ),
                },
            ]
            await utils.answer(
                call,
                self.strings["2fa_enabled"],
                reply_markup=reply_markup,
                always_allow=[user.id],
            )
            return
        except PhoneCodeExpiredError:
            reply_markup = [
                {
                    "text": self.strings["request_code"],
                    "callback": self.inline_phone_handler,
                    "args": (phone, user, is_switch),
                }
            ]
            await utils.answer(
                call,
                self.strings["code_expired"],
                reply_markup=reply_markup,
                always_allow=[user.id],
            )
            return
        except PhoneCodeInvalidError:
            await utils.answer(
                call,
                self.strings["invalid_code"],
                reply_markup=_code_markup,
                always_allow=[user.id],
            )
            return
        except FloodWaitError as e:
            await utils.answer(
                call,
                self.strings["floodwait_error"].format(e.seconds),
                reply_markup={"text": self.strings["btn_no"], "action": "close"},
            )
            return

        asyncio.ensure_future(self.schedule_restart(call, client, is_switch=is_switch))

    @loader.command()
    async def switchacc(self, message: Message):
        if "JAMHOST" in os.environ:
            await utils.answer(message, self.strings["host_denied"])
            return

        user = await self._client.get_entity(self.tg_id)

        if "force_insecure" in message.raw_text.lower():
            await self._inline_login(message, user, is_switch=True)
            return

        try:
            if not await self.inline.form(
                self.strings["switch_confirm"],
                message=message,
                reply_markup=[
                    {
                        "text": self.strings["btn_yes"],
                        "callback": self._inline_login,
                        "args": (user, False, True),
                    },
                    {"text": self.strings["btn_no"], "action": "close"},
                ],
                photo="",
            ):
                raise RuntimeError("Inline form was not created")
        except Exception:
            await utils.answer(
                message,
                self.strings["switch_insecure"].format(
                    utils.escape_html(self.get_prefix())
                ),
            )

    async def inline_2fa_handler(
        self, call, data, client, phone, user, is_switch: bool = False
    ):
        register_secret(data)
        _2fa_markup = {
            "text": self.strings["enter_2fa"],
            "input": self.strings["your_2fa"],
            "handler": self.inline_2fa_handler,
            "args": (
                client,
                phone,
                user,
                is_switch,
            ),
        }
        if not data:
            await utils.answer(
                call,
                self.strings["invalid_password"],
                reply_markup=_2fa_markup,
                always_allow=[user.id],
            )
            return

        try:
            await client.sign_in(phone, password=data)
        except PasswordHashInvalidError:
            await utils.answer(
                call,
                self.strings["invalid_password"],
                reply_markup=_2fa_markup,
                always_allow=[user.id],
            )
            return
        except FloodWaitError as e:
            await utils.answer(
                call,
                self.strings["floodwait_error"].format(e.seconds),
                reply_markup={"text": self.strings["btn_no"], "action": "close"},
            )
            return

        asyncio.ensure_future(self.schedule_restart(call, client, is_switch=is_switch))
