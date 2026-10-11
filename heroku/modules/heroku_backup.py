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
import contextlib
import datetime
import io
import logging
import os
import re
import time
import zipfile
import orjson

from pathlib import Path

from herokutl.tl.types import Message

from .. import loader, utils
from ..inline.types import BotInlineCall

logger = logging.getLogger(__name__)


@loader.tds
class HerokuBackupMod(loader.Module):
    """Handles database and modules backups"""

    strings = {"name": "HerokuBackup"}

    async def _assert_backup_destination(self):
        if not await utils.is_private_asset_channel(
            self._client, self._content_channel_id, allow_participants=True
        ):
            raise PermissionError("Refusing to send backup to an unsafe content channel")

    async def client_ready(self):
        self._content_channel_id = await utils.wait_for_content_channel(self._db)

    async def inline_ready(self):
        if not self.get("period"):
            await self.inline.bot.send_photo(
                self.tg_id,
                photo="https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/unit_alpha.jpg",
                caption=self.strings["period"],
                reply_markup=self.inline.generate_markup(
                    utils.chunks(
                        [
                            {
                                "text": f"🕰 {i} h",
                                "callback": self._set_backup_period,
                                "args": (i,),
                            }
                            for i in [1, 2, 4, 6, 8, 12, 24, 48, 168]
                        ],
                        3,
                    )
                    + [
                        [
                            {
                                "text": "🚫 Never",
                                "callback": self._set_backup_period,
                                "args": (0,),
                            }
                        ]
                    ]
                ),
            )

    async def _set_backup_period(self, call: BotInlineCall, value: int):
        if not value:
            self.set("period", "disabled")
            await self.inline.bot(
                call.answer(
                    self.strings["never_bot"].format(prefix=self.get_prefix()),
                    show_alert=True,
                )
            )
            await call.delete()
            return

        self.set("period", value * 60 * 60)
        self.set("last_backup", round(time.time()))

        await self.inline.bot(
            call.answer(
                self.strings["saved_bot"].format(prefix=self.get_prefix()),
                show_alert=True,
            )
        )
        await call.delete()

    @loader.command()
    async def set_backup_period(self, message: Message):
        """[time] | set your backup bd period"""
        if (
            not (args := utils.get_args_raw(message))
            or not args.isdigit()
            or int(args) not in range(200)
        ):
            await utils.answer(message, self.strings["invalid_args"])
            return

        if not int(args):
            self.set("period", "disabled")
            await utils.answer(
                message,
                f"<b>{self.strings['never'].format(prefix=self.get_prefix())}</b>",
            )
            return

        period = int(args) * 60 * 60
        self.set("period", period)
        self.set("last_backup", round(time.time()))
        await utils.answer(
            message, f"<b>{self.strings['saved'].format(prefix=self.get_prefix())}</b>"
        )

    @loader.loop(interval=1, autostart=True)
    async def handler(self):
        try:
            if self.get("period") == "disabled":
                raise loader.StopLoop

            if not self.get("period"):
                await asyncio.sleep(3)
                return

            if not self.get("last_backup"):
                self.set("last_backup", round(time.time()))
                await asyncio.sleep(self.get("period"))
                return

            await asyncio.sleep(
                self.get("last_backup") + self.get("period") - time.time()
            )

            db = io.BytesIO(
                orjson.dumps(
                    self._db, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS
                )
            )
            db.name = "db.json"

            mods = io.BytesIO()
            with zipfile.ZipFile(mods, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                    for file in files:
                        if file.endswith(f"{self.tg_id}.py"):
                            with open(os.path.join(root, file), "rb") as f:
                                zipf.writestr(file, f.read())
                zipf.writestr(
                    "db_mods.json",
                    orjson.dumps(
                        self.lookup("LoaderMod").get("loaded_modules", {}),
                        option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS,
                    ),
                )

            mods.seek(0)
            mods.name = "mods.zip"

            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("db.json", db.getvalue())
                z.writestr("mods.zip", mods.getvalue())

            archive.name = f"backup-{datetime.datetime.now():%d-%m-%Y-%H-%M}.backup"

            backup_topic_id = await utils.get_topic_id(self._db, "Backups")
            if not backup_topic_id:
                logger.error("Backups topic not found in database")
                return

            await self._assert_backup_destination()
            await self.inline.bot.send_document(
                int(f"-100{self._content_channel_id}"),
                archive,
                reply_markup=self.inline.generate_markup(
                    [
                        [
                            {
                                "text": "↪️ Restore this",
                                "data": "heroku/backupall/restore/confirm",
                            }
                        ]
                    ]
                ),
                message_thread_id=backup_topic_id,
            )

            self.set("last_backup", round(time.time()))
        except loader.StopLoop:
            raise
        except Exception:
            logger.exception("HerokuBackup failed")
            await asyncio.sleep(60)

    @loader.callback_handler()
    async def restore(self, call: BotInlineCall):
        if not call.data.startswith("heroku/backupall/restore"):
            return

        if call.data == "heroku/backupall/restore/confirm":
            await utils.answer(
                call,
                "❓ <b>Are you sure?</b>",
                reply_markup={
                    "text": "✅ Yes",
                    "data": "heroku/backupall/restore",
                },
            )
            return

        try:
            file = await (
                await self._client.get_messages(
                    self._content_channel_id, ids=[call.message.message_id]
                )
            )[0].download_media(bytes)

            zipfile_bytes = io.BytesIO(file)
            with zipfile.ZipFile(zipfile_bytes) as zf:
                with zf.open("db.json") as f:
                    db_data = orjson.loads(f.read().decode())

                with contextlib.suppress(KeyError):
                    db_data["heroku.inline"].pop("bot_token")

                if not self._db.process_db_autofix(db_data):
                    raise RuntimeError("Attempted to restore broken database")

                self._db.clear()
                self._db.update(**db_data)
                self._db.save()

                with zf.open("mods.zip") as modzip_bytes:
                    with zipfile.ZipFile(io.BytesIO(modzip_bytes.read())) as modzip:
                        with modzip.open("db_mods.json", "r") as modules:
                            db_mods = orjson.loads(modules.read().decode())
                            if isinstance(db_mods, dict):
                                self.lookup("LoaderMod").set("loaded_modules", db_mods)

                        for name in modzip.namelist():
                            if name == "db_mods.json" or not Path(name).name.endswith(
                                ".py"
                            ):
                                continue

                            path = loader.LOADED_MODULES_PATH / Path(name).name
                            with modzip.open(name, "r") as module:
                                path.write_bytes(module.read())

            await self.inline.bot(
                call.answer(self.strings["all_restored_bot"], show_alert=True)
            )
            await self.invoke("restart", "-f", peer=call.message.chat.id)
        except Exception:
            logger.exception("Restore from backupall failed")
            await self.inline.bot(
                call.answer(self.strings["reply_to_file"], show_alert=True)
            )

    def _convert(self, backup):
        fixed = re.sub(r"(hikka\.)(\S+\":)", lambda m: "heroku." + m.group(2), backup)
        txt = io.BytesIO(fixed.encode())
        txt.name = f"db-converted-{datetime.datetime.now():%d-%m-%Y-%H-%M}.json"
        return txt

    @staticmethod
    def _message_id(message) -> int:
        return getattr(message, "message_id", getattr(message, "id"))

    async def convert(self, call: BotInlineCall, ans, file):
        match ans:
            case "y":
                await utils.answer(call, self.strings["converting_db"])
                backup = self._convert(file)
                await utils.answer_file(
                    call,
                    backup,
                    caption=self.strings["backup_caption"].format(
                        prefix=utils.escape_html(self.get_prefix())
                    ),
                )
            case _:
                await utils.answer(
                    call,
                    self.strings["advice_converting"],
                    reply_markup=[[{"text": "🔻 Close", "action": "close"}]],
                )

    @loader.command()
    async def backupdb(self, message: Message):
        txt = io.BytesIO(
            orjson.dumps(self._db, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)
        )
        txt.name = f"db-backup-{datetime.datetime.now():%d-%m-%Y-%H-%M}.json"

        if not getattr(self, "_content_channel_id", None):
            self._content_channel_id = await utils.wait_for_content_channel(self._db)

        backup_topic_id = await utils.get_topic_id(self._db, "Backups")
        if not backup_topic_id:
            logger.error("Backups topic not found in database")
            await utils.answer(message, self.strings["backup_sent"])
            return

        await self._assert_backup_destination()
        backup_msg = await self.inline.bot.send_document(
            int(f"-100{self._content_channel_id}"),
            txt,
            caption=self.strings["backup_caption"].format(
                prefix=utils.escape_html(self.get_prefix())
            ),
            message_thread_id=backup_topic_id,
        )

        await utils.answer(
            message,
            self.strings["backup_sent"].format(
                f"https://t.me/c/{self._content_channel_id}/{backup_topic_id}/{self._message_id(backup_msg)}"
            ),
        )

    @loader.command()
    async def restoredb(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(
                message,
                self.strings["reply_to_file"],
            )
            return

        file = await reply.download_media(bytes)
        try:

            decoded_text = orjson.loads(file.decode())

        except UnicodeDecodeError:
            await utils.answer(
                message, self.strings["probably_zip"].format(self.get_prefix())
            )
            return
        if re.search(r'"(hikka\.)(\S+\":)', file.decode()):
            await utils.answer(
                message,
                self.strings["db_warning"],
                reply_markup=[
                    {
                        "text": "❌",
                        "callback": self.convert,
                        "args": (
                            "n",
                            file.decode(),
                        ),
                    },
                    {
                        "text": "✅",
                        "callback": self.convert,
                        "args": (
                            "y",
                            file.decode(),
                        ),
                    },
                ],
            )
            return

        with contextlib.suppress(KeyError):
            decoded_text["heroku.inline"].pop("bot_token")

        if not self._db.process_db_autofix(decoded_text):
            raise RuntimeError("Attempted to restore broken database")

        self._db.clear()
        self._db.update(**decoded_text)
        self._db.save()

        await utils.answer(message, self.strings["db_restored"])
        await self.invoke("restart", "-f", peer=message.peer_id)

    @loader.command()
    async def backupmods(self, message: Message):
        mods_quantity = len(self.lookup("LoaderMod").get("loaded_modules", {}))

        result = io.BytesIO()
        result.name = "mods.zip"

        db_mods = orjson.dumps(
            self.lookup("LoaderMod").get("loaded_modules", {}),
            option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS,
        )

        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                for file in files:
                    if file.endswith(f"{self.tg_id}.py"):
                        with open(os.path.join(root, file), "rb") as f:
                            zipf.writestr(file, f.read())
                            mods_quantity += 1

            zipf.writestr("db_mods.json", db_mods)

        archive = io.BytesIO(result.getvalue())
        archive.name = f"mods-{datetime.datetime.now():%d-%m-%Y-%H-%M}.zip"

        if not getattr(self, "_content_channel_id", None):
            self._content_channel_id = await utils.wait_for_content_channel(self._db)

        backup_topic_id = await utils.get_topic_id(self._db, "Backups")
        if not backup_topic_id:
            logger.error("Backups topic not found in database")
            await utils.answer_file(
                message,
                archive,
                caption=self.strings["modules_backup"].format(
                    mods_quantity,
                    utils.escape_html(self.get_prefix()),
                ),
            )
            return

        await self._assert_backup_destination()
        backup_msg = await self.inline.bot.send_document(
            int(f"-100{self._content_channel_id}"),
            archive,
            caption=self.strings["modules_backup"].format(
                mods_quantity,
                utils.escape_html(self.get_prefix()),
            ),
            message_thread_id=backup_topic_id,
        )

        await utils.answer(
            message,
            self.strings["backup_sent"].format(
                f"https://t.me/c/{self._content_channel_id}/{backup_topic_id}/{self._message_id(backup_msg)}"
            ),
        )

    @loader.command()
    async def restoremods(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(message, self.strings["reply_to_file"])
            return

        file = await reply.download_media(bytes)
        try:
            decoded_text = orjson.loads(file.decode())
        except Exception:
            try:
                file = io.BytesIO(file)
                file.name = "mods.zip"

                with zipfile.ZipFile(file) as zf:
                    with zf.open("db_mods.json", "r") as modules:
                        db_mods = orjson.loads(modules.read().decode())
                        if isinstance(db_mods, dict) and all(
                            (
                                isinstance(key, str)
                                and isinstance(value, str)
                                and utils.check_url(value)
                            )
                            for key, value in db_mods.items()
                        ):
                            self.lookup("LoaderMod").set("loaded_modules", db_mods)

                    for name in zf.namelist():
                        if name == "db_mods.json" or not Path(name).name.endswith(
                            ".py"
                        ):
                            continue

                        path = loader.LOADED_MODULES_PATH / Path(name).name
                        with zf.open(name, "r") as module:
                            path.write_bytes(module.read())
            except Exception:
                logger.exception("Unable to restore modules")
                await utils.answer(message, self.strings["reply_to_file"])
                return
        else:
            if not isinstance(decoded_text, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in decoded_text.items()
            ):
                raise RuntimeError("Invalid backup")

            self.lookup("LoaderMod").set("loaded_modules", decoded_text)

        await utils.answer(message, self.strings["mods_restored"])
        await self.invoke("restart", "-f", peer=message.peer_id)

    @loader.command()
    async def backupall(self, message: Message):
        db = io.BytesIO(
            orjson.dumps(self._db, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)
        )
        db.name = "db.json"

        mods = io.BytesIO()
        with zipfile.ZipFile(mods, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(loader.LOADED_MODULES_DIR):
                for file in files:
                    if file.endswith(f"{self.tg_id}.py"):
                        with open(os.path.join(root, file), "rb") as f:
                            zipf.writestr(file, f.read())
            zipf.writestr(
                "db_mods.json",
                orjson.dumps(
                    self.lookup("LoaderMod").get("loaded_modules", {}),
                    option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS,
                ),
            )

        mods.seek(0)
        mods.name = "mods.zip"

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("db.json", db.getvalue())
            z.writestr("mods.zip", mods.getvalue())

        archive.name = f"heroku-{datetime.datetime.now():%d-%m-%Y-%H-%M}.backup"

        backup_topic_id = await utils.get_topic_id(self._db, "Backups")
        if not backup_topic_id:
            logger.error("Backups topic not found in database")
            await utils.answer(
                message,
                "<b>Backups topic not found in database. Please run quickstart to create it.</b>",
            )
            return

        await self._assert_backup_destination()
        backup_msg = await self.inline.bot.send_document(
            int(f"-100{self._content_channel_id}"),
            archive,
            caption=self.strings["backupall_info"].format(
                prefix=utils.escape_html(self.get_prefix()),
            ),
            reply_markup=self.inline.generate_markup(
                [
                    [
                        {
                            "text": "↪️ Restore this",
                            "data": "heroku/backupall/restore/confirm",
                        },
                    ],
                ],
            ),
            message_thread_id=backup_topic_id,
        )

        await utils.answer(
            message,
            self.strings["backupall_sent"].format(
                f"https://t.me/c/{self._content_channel_id}/{backup_topic_id}/{self._message_id(backup_msg)}"
            ),
        )

    @loader.command()
    async def restoreall(self, message: Message):
        if not (reply := await message.get_reply_message()) or not reply.media:
            await utils.answer(message, self.strings["reply_to_file"])
            return

        status_message = await utils.answer(message, self.strings["restoring_backup"])
        file = await reply.download_media(bytes)
        try:
            zipfile_bytes = io.BytesIO(file)
            with zipfile.ZipFile(zipfile_bytes) as zf:
                with zf.open("db.json") as f:
                    db_data = orjson.loads(f.read().decode())

                with contextlib.suppress(KeyError):
                    db_data["heroku.inline"].pop("bot_token")

                if not self._db.process_db_autofix(db_data):
                    raise RuntimeError("Attempted to restore broken database")

                self._db.clear()
                self._db.update(**db_data)
                self._db.save()

                with zf.open("mods.zip") as modzip_bytes:
                    with zipfile.ZipFile(io.BytesIO(modzip_bytes.read())) as modzip:
                        with modzip.open("db_mods.json", "r") as modules:
                            db_mods = orjson.loads(modules.read().decode())
                            if isinstance(db_mods, dict):
                                self.lookup("LoaderMod").set("loaded_modules", db_mods)

                        for name in modzip.namelist():
                            if name == "db_mods.json" or not Path(name).name.endswith(
                                ".py"
                            ):
                                continue

                            path = loader.LOADED_MODULES_PATH / Path(name).name
                            with modzip.open(name, "r") as module:
                                path.write_bytes(module.read())
        except Exception:
            logger.exception("Restore all failed")
            await utils.answer(status_message, self.strings["reply_to_file"])
            return

        await utils.answer(status_message, self.strings["all_restored"])
        await self.invoke("restart", "-f", peer=message.peer_id)
