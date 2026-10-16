"""Main script, where all the fun starts"""

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

import argparse
import asyncio
import collections
import contextlib
import importlib
import json
import logging
import os
import random
import shutil
import signal
import sqlite3
import string
import sys
import traceback
import typing
from getpass import getpass
from pathlib import Path

from herokutl import events
from herokutl.errors import (
    ApiIdInvalidError,
    AuthKeyDuplicatedError,
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from herokutl.errors import AuthKeyNotFound
from herokutl.errors.rpcerrorlist import (
    AuthKeyUnregisteredError,
    SessionExpiredError,
    SessionRevokedError,
    UserDeactivatedBanError,
    UserDeactivatedError,
    YouBlockedUserError,
)
from herokutl.network.connection import (
    ConnectionTcpFull,
    ConnectionTcpMTProxyRandomizedIntermediate,
)
from herokutl.password import compute_check
from herokutl.sessions import MemorySession, SQLiteSession, StringSession
from herokutl.tl.functions.account import GetPasswordRequest
from herokutl.tl.functions.auth import CheckPasswordRequest
from herokutl.tl.functions.contacts import UnblockRequest

from . import database, loader, utils, version
from ._internal import (
    client_id_ctx,
    client_id_override,
    install_task_tracking,
    print_banner,
    restart,
    set_client_id,
    private_write,
    register_secret,
    register_secrets,
)
from .dispatcher import CommandDispatcher
from .qr import QRCode
from .secure import patcher
from .tl_cache import CustomTelegramClient
from .utils.other import allowed_ids as get_allowed_ids
from .translations import Translator
from .version import __version__


BASE_DIR = (
    "/data"
    if "DOCKER" in os.environ
    else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

SESSION_LOST_ERRORS = (
    AuthKeyUnregisteredError,
    AuthKeyDuplicatedError,
    AuthKeyNotFound,
    SessionRevokedError,
    SessionExpiredError,
    UserDeactivatedError,
    UserDeactivatedBanError,
)

BASE_PATH = Path(BASE_DIR)
CONFIG_PATH = BASE_PATH / "config.json"
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
_CONFIG_CACHE: dict | None = None
_CONFIG_MTIME_NS: int | None = None

# fmt: off
LATIN_MOCK = [
    "Amor", "Arbor", "Astra", "Aurum", "Bellum", "Caelum",
    "Calor", "Candor", "Carpe", "Celer", "Certo", "Cibus",
    "Civis", "Clemens", "Coetus", "Cogito", "Conexus",
    "Consilium", "Cresco", "Cura", "Cursus", "Decus",
    "Deus", "Dies", "Digitus", "Discipulus", "Dominus",
    "Donum", "Dulcis", "Durus", "Elementum", "Emendo",
    "Ensis", "Equus", "Espero", "Fidelis", "Fides",
    "Finis", "Flamma", "Flos", "Fortis", "Frater", "Fuga",
    "Fulgeo", "Genius", "Gloria", "Gratia", "Gravis",
    "Habitus", "Honor", "Hora", "Ignis", "Imago",
    "Imperium", "Inceptum", "Infinitus", "Ingenium",
    "Initium", "Intra", "Iunctus", "Iustitia", "Labor",
    "Laurus", "Lectus", "Legio", "Liberi", "Libertas",
    "Lumen", "Lux", "Magister", "Magnus", "Manus",
    "Memoria", "Mens", "Mors", "Mundo", "Natura",
    "Nexus", "Nobilis", "Nomen", "Novus", "Nox",
    "Oculus", "Omnis", "Opus", "Orbis", "Ordo", "Os",
    "Pax", "Perpetuus", "Persona", "Petra", "Pietas",
    "Pons", "Populus", "Potentia", "Primus", "Proelium",
    "Pulcher", "Purus", "Quaero", "Quies", "Ratio",
    "Regnum", "Sanguis", "Sapientia", "Sensus", "Serenus",
    "Sermo", "Signum", "Sol", "Solus", "Sors", "Spes",
    "Spiritus", "Stella", "Summus", "Teneo", "Terra",
    "Tigris", "Trans", "Tribuo", "Tristis", "Ultimus",
    "Unitas", "Universus", "Uterque", "Valde", "Vates",
    "Veritas", "Verus", "Vester", "Via", "Victoria",
    "Vita", "Vox", "Vultus", "Zephyrus", "Bimbalas", "Nywuctuu",
    "Anyone", "Draher", "Hackimo", "Silvyr",

]
# fmt: on


def generate_app_name() -> str:
    """
    Generate random app name
    :return: Random app name
    :example: "Cresco Cibus Consilium"
    """
    return " ".join(random.choices(LATIN_MOCK, k=3))


def get_app_name() -> str:
    """
    Generates random app name or gets the saved one of present
    :return: App name
    :example: "Cresco Cibus Consilium"
    """
    if not (app_name := get_config_key("app_name")):
        app_name = generate_app_name()
        save_config_key("app_name", app_name)

    return app_name


def generate_random_system_version():
    """
    Generates a random system version string similar to those used by Windows or Linux.

    This function generates a random version string that follows the format used by operating systems
    like Windows or Linux. The version string includes the major version, minor version, patch number,
    and build number, each of which is randomly generated within specified ranges. Additionally, it
    includes a random operating system name and version.

    :return: A randomly generated system version string.
    :example: "Windows 10.0.19042.1234" or "Ubuntu 20.04.19042.1234"
    """
    os_choices = [
        ("Windows", "3.1"),
        ("Windows", "95"),
        ("Windows", "98"),
        ("Windows", "ME"),
        ("Windows", "NT 4.0"),
        ("Windows", "2000"),
        ("Windows", "XP"),
        ("Windows", "Server 2003"),
        ("Windows", "Vista"),
        ("Windows", "7"),
        ("Windows", "8"),
        ("Windows", "8.1"),
        ("Windows", "10"),
        ("Windows", "11"),
        ("Windows", "Server 2016"),
        ("Windows", "Server 2019"),
        ("Windows", "Server 2022"),
        ("macOS", "10.9 Mavericks"),
        ("macOS", "10.10 Yosemite"),
        ("macOS", "10.11 El Capitan"),
        ("macOS", "10.12 Sierra"),
        ("macOS", "10.13 High Sierra"),
        ("macOS", "10.14 Mojave"),
        ("macOS", "10.15 Catalina"),
        ("macOS", "11 Big Sur"),
        ("macOS", "12 Monterey"),
        ("macOS", "13 Ventura"),
        ("macOS", "14 Sonoma"),
        ("iOS", "12.5.7"),
        ("iOS", "13.7"),
        ("iOS", "14.8"),
        ("iOS", "15.7"),
        ("iOS", "16.6"),
        ("iOS", "17.4"),
        ("iPadOS", "16.4"),
        ("Android", "4.4 KitKat"),
        ("Android", "5.0 Lollipop"),
        ("Android", "6.0 Marshmallow"),
        ("Android", "7.0 Nougat"),
        ("Android", "8.0 Oreo"),
        ("Android", "9 Pie"),
        ("Android", "10"),
        ("Android", "11"),
        ("Android", "12"),
        ("Android", "13"),
        ("Android", "14"),
        ("Android", "15"),
        ("Android", "16"),
        ("ChromeOS", "89"),
        ("ChromeOS", "96"),
        ("ChromeOS", "100"),
        ("ChromeOS", "110"),
        ("Ubuntu", "14.04"),
        ("Ubuntu", "16.04"),
        ("Ubuntu", "18.04"),
        ("Ubuntu", "19.10"),
        ("Ubuntu", "20.04"),
        ("Ubuntu", "21.04"),
        ("Ubuntu", "21.10"),
        ("Ubuntu", "22.04"),
        ("Ubuntu", "22.10"),
        ("Ubuntu", "23.04"),
        ("Ubuntu", "23.10"),
        ("Ubuntu", "24.04"),
        ("Debian", "7 wheezy"),
        ("Debian", "8 jessie"),
        ("Debian", "9 stretch"),
        ("Debian", "10 buster"),
        ("Debian", "11 bullseye"),
        ("Debian", "12 bookworm"),
        ("Fedora", "28"),
        ("Fedora", "29"),
        ("Fedora", "30"),
        ("Fedora", "31"),
        ("Fedora", "32"),
        ("Fedora", "33"),
        ("Fedora", "34"),
        ("Fedora", "35"),
        ("Fedora", "36"),
        ("Fedora", "37"),
        ("Fedora", "38"),
        ("Fedora", "39"),
        ("CentOS", "6"),
        ("CentOS", "7"),
        ("CentOS", "8"),
        ("CentOS Stream", "8"),
        ("CentOS Stream", "9"),
        ("AlmaLinux", "8.6"),
        ("AlmaLinux", "9.1"),
        ("Rocky Linux", "8.6"),
        ("Rocky Linux", "9.0"),
        ("Arch Linux", "rolling-2021.05.01"),
        ("Arch Linux", "rolling-2022.11.01"),
        ("Manjaro", "21.0"),
        ("Manjaro", "22.0"),
        ("Linux Mint", "18 Sarah"),
        ("Linux Mint", "19 Tara"),
        ("Linux Mint", "20 Ulyana"),
        ("Linux Mint", "21 Vanessa"),
        ("elementary OS", "5 Hera"),
        ("elementary OS", "6 Odin"),
        ("Pop!_OS", "20.04"),
        ("Pop!_OS", "22.04"),
        ("openSUSE Leap", "15.0"),
        ("openSUSE Leap", "15.3"),
        ("SUSE Enterprise", "15 SP1"),
        ("FreeBSD", "11.4"),
        ("FreeBSD", "12.3"),
        ("FreeBSD", "13.0"),
        ("FreeBSD", "14.0"),
        ("OpenBSD", "6.7"),
        ("OpenBSD", "7.0"),
        ("NetBSD", "9.2"),
        ("Solaris", "10"),
        ("Solaris", "11.4"),
        ("Haiku", "R1/beta3"),
        ("BeOS", "R5"),
        ("MorphOS", "3.18"),
        ("AROS", "2019"),
        ("ReactOS", "0.4.13"),
        ("QNX", "7.0"),
        ("Tizen", "5.5"),
        ("HarmonyOS", "2.0"),
        ("KaiOS", "2.5"),
        ("Raspberry Pi OS", "9 stretch"),
        ("Raspberry Pi OS", "10 buster"),
        ("Raspberry Pi OS", "11 bullseye"),
        ("Puppy Linux", "9.5"),
        ("Alpine Linux", "3.18.0"),
        ("Gentoo", "2023.0"),
        ("Slackware", "14.2"),
        ("TV OS", "Samsung Tizen 6"),
        ("Amazon Fire OS", "7"),
        ("MS-DOS", "6.22"),
        ("AmigaOS", "3.1"),
        ("Commodore", "64 OS"),
    ]
    os_name, os_version = random.choice(os_choices)

    version = f"{os_name} {os_version}"
    return version


def run_config():
    """Load configurator.py"""
    from . import configurator

    return configurator.api_config(None)


def _read_config() -> dict:
    global _CONFIG_CACHE, _CONFIG_MTIME_NS

    try:
        stat = CONFIG_PATH.stat()
    except FileNotFoundError:
        _CONFIG_CACHE = {}
        _CONFIG_MTIME_NS = None
        return {}

    if _CONFIG_CACHE is not None and _CONFIG_MTIME_NS == stat.st_mtime_ns:
        return _CONFIG_CACHE

    _CONFIG_CACHE = json.loads(CONFIG_PATH.read_text())
    register_secrets(_CONFIG_CACHE)
    _CONFIG_MTIME_NS = stat.st_mtime_ns
    return _CONFIG_CACHE


def get_config_key(key: str) -> str | bool:
    """
    Parse and return key from config
    :param key: Key name in config
    :return: Value of config key or `False`, if it doesn't exist
    """
    try:
        return _read_config().get(key, False)
    except FileNotFoundError:
        return False


def save_config_key(key: str, value: str) -> bool:
    """
    Save `key` with `value` to config
    :param key: Key name in config
    :param value: Desired value in config
    :return: `True` on success, otherwise `False`
    """
    global _CONFIG_CACHE, _CONFIG_MTIME_NS

    try:
        # Try to open our newly created json config
        config = _read_config().copy()
    except FileNotFoundError:
        # If it doesn't exist, just default config to none
        # It won't cause problems, bc after new save
        # we will create new one
        config = {}

    # Assign config value
    config[key] = value
    # And save config
    register_secrets(config)
    private_write(CONFIG_PATH, json.dumps(config, indent=4))
    _CONFIG_CACHE = config
    _CONFIG_MTIME_NS = CONFIG_PATH.stat().st_mtime_ns
    return True


def parse_arguments() -> dict:
    """
    Parses the arguments
    :returns: Dictionary with arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", "-p", action="append")
    parser.add_argument(
        "--qr-login",
        dest="qr_login",
        action="store_true",
        help=(
            "Use QR code login instead of phone number (will only work if scanned from"
            " another device)"
        ),
    )
    parser.add_argument(
        "--data-root",
        dest="data_root",
        default="",
        help="Root path to store session files in",
    )
    parser.add_argument(
        "--no-auth",
        dest="no_auth",
        action="store_true",
        help="Disable authentication and API token input, exitting if needed",
    )
    parser.add_argument(
        "--proxy-host",
        dest="proxy_host",
        action="store",
        help="Proxy host, without port",
    )
    parser.add_argument(
        "--proxy-port",
        dest="proxy_port",
        action="store",
        type=int,
        help="Proxy port",
    )
    parser.add_argument(
        "--type-proxy",
        dest="proxy_type",
        action="store",
        default="mtproxy",
        choices=("mtproxy", "socks5", "http"),
        help="Proxy type: mtproxy, socks5 or http",
    )
    parser.add_argument(
        "--proxy-secret",
        dest="proxy_secret",
        action="store",
        help="MTProto proxy secret; required for --type-proxy mtproxy",
    )
    parser.add_argument(
        "--root",
        dest="disable_root_check",
        action="store_true",
        help="Disable `force_insecure` warning",
    )
    parser.add_argument(
        "--sandbox",
        dest="sandbox",
        action="store_true",
        help="Die instead of restart",
    )
    parser.add_argument(
        "--no-tty",
        dest="tty",
        action="store_false",
        default=True,
        help="Do not print colorful output using ANSI escapes",
    )
    parser.add_argument(
        "--no-git",
        dest="no_git",
        action="store_true",
        help="Disable git checks and updates",
    )
    parser.add_argument(
        "--no-web",
        dest="no_web",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--wipe",
        "-w",
        dest="wipe",
        action="store_true",
        help="Remove saved sessions and config, then exit",
    )
    arguments = parser.parse_args()
    logging.debug(arguments)
    return arguments


class SuperList(list):
    """
    Makes able: await self.allclients.send_message("foo", "bar")
    """

    def __getattribute__(self, attr: str) -> typing.Any:
        if hasattr(list, attr):
            return list.__getattribute__(self, attr)

        for obj in self:
            attribute = getattr(obj, attr)
            if callable(attribute):
                if asyncio.iscoroutinefunction(attribute):

                    async def foobar(*args, **kwargs):
                        return [await getattr(_, attr)(*args, **kwargs) for _ in self]

                    return foobar
                return lambda *args, **kwargs: [
                    getattr(_, attr)(*args, **kwargs) for _ in self
                ]

            return [getattr(x, attr) for x in self]


class InteractiveAuthRequired(Exception):
    """Is being rased by Telethon, if phone is required"""


def raise_auth():
    """Raises `InteractiveAuthRequired`"""
    raise InteractiveAuthRequired()


class Heroku:
    """Main userbot instance, which can handle multiple clients"""

    def __init__(self):
        global BASE_DIR, BASE_PATH, CONFIG_PATH, SESSIONS_DIR
        self.omit_log = False
        self.arguments = parse_arguments()
        if self.arguments.no_git:
            os.environ["HEROKU_NO_GIT"] = "1"
        if self.arguments.data_root:
            BASE_DIR = self.arguments.data_root
            BASE_PATH = Path(BASE_DIR)
            CONFIG_PATH = BASE_PATH / "config.json"
            SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
        try:
            self.loop = asyncio.get_running_loop()

        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        install_task_tracking()

        self.clients = SuperList()
        self.ready = asyncio.Event()
        self._migrate_sessions()
        self._read_sessions()
        self._get_api_token()
        self._get_proxy()

    def _get_proxy(self):
        """
        Get proxy settings from --type-proxy, --proxy-host, --proxy-port
        and --proxy-secret
        and connection to use (depends on proxy - provided or not)
        """
        host = self.arguments.proxy_host
        port = self.arguments.proxy_port
        secret = self.arguments.proxy_secret
        proxy_type = (self.arguments.proxy_type or "mtproxy").lower()

        if not host and not port and not secret:
            self.proxy, self.conn = None, ConnectionTcpFull
            return

        if not host or not port:
            raise ValueError("--proxy-host and --proxy-port must be passed together")

        if proxy_type == "mtproxy":
            if not secret:
                raise ValueError("--proxy-secret is required for --type-proxy mtproxy")

            logging.debug("Using MTProxy: %s:%s", host, port)
            self.proxy = (host, port, secret)
            self.conn = ConnectionTcpMTProxyRandomizedIntermediate
            return

        if secret:
            raise ValueError(
                "--proxy-secret can only be used with --type-proxy mtproxy"
            )

        logging.debug("Using %s proxy: %s:%s", proxy_type, host, port)
        self.proxy = {
            "proxy_type": proxy_type,
            "addr": host,
            "port": port,
        }
        self.conn = ConnectionTcpFull

    def _migrate_sessions(self):
        os.makedirs(SESSIONS_DIR, mode=0o700, exist_ok=True)
        os.chmod(SESSIONS_DIR, 0o700)

        with os.scandir(BASE_DIR) as entries:
            legacy = [
                entry
                for entry in entries
                if entry.is_file()
                and entry.name.startswith("heroku-")
                and ".session" in entry.name
            ]

        for entry in legacy:
            target = os.path.join(SESSIONS_DIR, entry.name)
            if os.path.exists(target):
                continue

            try:
                shutil.move(entry.path, target)
            except OSError:
                logging.exception(
                    "Failed to migrate legacy session file %s", entry.path
                )

    def _read_sessions(self):
        """Gets sessions from environment and data directory"""
        self.sessions = []
        with os.scandir(SESSIONS_DIR) as entries:
            self.sessions += [
                SQLiteSession(entry.path.rsplit(".session", maxsplit=1)[0])
                for entry in entries
                if entry.is_file()
                and entry.name.startswith("heroku-")
                and entry.name.endswith(".session")
                and "-bot-" not in entry.name
            ]

    def _get_api_token(self):
        """Get API Token from disk or environment"""
        api_token_type = collections.namedtuple("api_token", ("ID", "HASH"))

        # Try to retrieve credintials from config, or from env vars
        try:
            # Legacy migration
            if not get_config_key("api_id"):
                api_id, api_hash = (
                    line.strip()
                    for line in (Path(BASE_DIR) / "api_token.txt")
                    .read_text()
                    .splitlines()
                )
                save_config_key("api_id", int(api_id))
                save_config_key("api_hash", api_hash)
                (Path(BASE_DIR) / "api_token.txt").unlink()
                logging.debug("Migrated api_token.txt to config.json")

            api_token = api_token_type(
                get_config_key("api_id"),
                get_config_key("api_hash"),
            )
        except FileNotFoundError:
            try:
                from . import api_token
            except ImportError:
                try:
                    api_token = api_token_type(
                        os.environ["api_id"],
                        os.environ["api_hash"],
                    )
                except KeyError:
                    api_token = None

        self.api_token = api_token

    async def _get_token(self):
        """Reads or waits for user to enter API credentials"""
        while self.api_token is None:
            if self.arguments.no_auth:
                return
            run_config()
            importlib.invalidate_caches()
            self._get_api_token()

    async def save_client_session(
        self,
        client: CustomTelegramClient,
        *,
        delay_restart: bool = False,
    ):
        if hasattr(client, "tg_id"):
            telegram_id = client.tg_id
        else:
            if not (me := await client.get_me()):
                raise RuntimeError("Attempted to save non-inited session")

            telegram_id = me.id
            client._tg_id = telegram_id
            client.tg_id = telegram_id
            client.hikka_me = me
            client.heroku_me = me

        session = SQLiteSession(
            os.path.join(
                SESSIONS_DIR,
                f"heroku-{telegram_id}",
            )
        )

        session.set_dc(
            client.session.dc_id,
            client.session.server_address,
            client.session.port,
        )

        session.auth_key = client.session.auth_key

        session.save()

        if not delay_restart:
            await client.disconnect()
            restart()

        client.session = session
        client.heroku_db = database.Database(client)
        await client.heroku_db.init()

        try:
            db = client.heroku_db
            existing = db.get("heroku.inline", "custom_bot", False)
        except Exception:
            existing = False

        if (
            getattr(self, "arguments", None)
            and getattr(self.arguments, "tty", False)
            and not existing
        ):
            while bot := input(
                "You can enter a custom bot username or leave it empty and Heroku will generate a random one: "
            ):
                bot = bot.strip()
                bot = bot.lstrip("@")
                if any(
                    ch not in (string.ascii_letters + string.digits + "_") for ch in bot
                ):
                    print(
                        "Invalid username: use only ASCII letters, digits and underscore (_)."
                    )
                    continue
                if not (bot.lower().endswith("bot")):
                    print("Invalid username: must end with 'bot'.")
                    continue
                try:
                    if await self._check_bot(client, bot):
                        db.set("heroku.inline", "custom_bot", bot)
                        print("Bot username saved!")
                        break
                    else:
                        print("Bot username is occupied. Try again or leave it empty")
                        continue
                except Exception:
                    print("Something went wrong")

        if delay_restart:
            await client.disconnect()
            await asyncio.sleep(3600)

    async def _phone_login(self, client: CustomTelegramClient) -> bool:
        phone = input(
            "\033[0;96mEnter phone: \033[0m" if self.arguments.tty else "Enter phone: "
        )

        await client.start(phone)

        me = await client.get_me()
        telegram_id = me.id
        client._tg_id = telegram_id
        client.tg_id = telegram_id
        client.hikka_me = me
        client.heroku_me = me

        db = database.Database(client)
        await db.init()

        while bot := input(
            "You can enter a custom bot username or leave it empty and Heroku will generate a random one: "
        ):
            try:
                if await self._check_bot(client, bot):
                    db.set("heroku.inline", "custom_bot", bot)
                    print("Bot username saved!")
                    break
                else:
                    print("Bot username is occupied. Try again or leave it empty")
                    continue
            except Exception:
                print("Something went wrong")

        await self.save_client_session(client)
        self.clients += [client]
        return True

    async def _check_bot(
        self,
        client: CustomTelegramClient,
        username: str,
    ) -> bool:
        username = username.strip("@")
        async with client.conversation("@BotFather", exclusive=False) as conv:
            try:
                m = await conv.send_message("/token")
            except YouBlockedUserError:
                await client(UnblockRequest(id="@BotFather"))
                m = await conv.send_message("/token")
            r = await conv.get_response()

            await m.delete()
            await r.delete()

            if hasattr(r, "reply_markup") and hasattr(r.reply_markup, "rows"):
                for row in r.reply_markup.rows:
                    for button in row.buttons:
                        if username != button.text.strip("@"):
                            continue

                        m = await conv.send_message("/cancel")
                        r = await conv.get_response()

                        await m.delete()
                        await r.delete()

                        return True

        try:
            await client.get_entity(f"{username}")
        except Exception:
            return True

    async def _initial_setup(self) -> bool:
        """Responsible for first start"""
        if self.arguments.no_auth:
            return False

        client = CustomTelegramClient(
            MemorySession(),
            self.api_token.ID,
            self.api_token.HASH,
            connection=self.conn,
            proxy=self.proxy,
            connection_retries=None,
            device_model=get_app_name(),
            system_version=generate_random_system_version(),
            app_version=".".join(map(str, __version__)) + " x64",
            lang_code="en",
            system_lang_code="en-US",
        )
        await client.connect()

        print(
            ("\033[0;96m{}\033[0m" if self.arguments.tty else "{}").format(
                "You can use QR-code to login from another device (your friend's"
                " phone, for example)."
            )
        )

        user_choice = input(
            "\033[0;96mUse QR code? [y/N]: \033[0m"
            if self.arguments.tty
            else "Use QR code? [y/N]: "
        ).lower()

        match user_choice:
            case "y":
                pass
            case _:
                return await self._phone_login(client)

        print("\033[0;96mLoading QR code...\033[0m")
        qr_login = await client.qr_login()

        def print_qr():
            qr = QRCode()
            qr.add_data(qr_login.url)
            print("\033[2J\033[3;1f")
            qr.print_ascii(invert=True)
            print("\033[0;96mScan the QR code above to log in.\033[0m")
            print("\033[0;96mPress Ctrl+C to cancel.\033[0m")

        async def qr_login_poll() -> bool:
            logged_in = False
            while not logged_in:
                try:
                    logged_in = await qr_login.wait(10)
                except asyncio.TimeoutError:
                    try:
                        await qr_login.recreate()
                        print_qr()
                    except SessionPasswordNeededError:
                        return True
                except SessionPasswordNeededError:
                    return True
                except KeyboardInterrupt:
                    print("\033[2J\033[3;1f")
                    return None

            return False

        match await qr_login_poll():
            case None:
                return await self._phone_login(client)

            case True:
                print_banner("2fa.txt")
                password = await client(GetPasswordRequest())
                while True:
                    _2fa = getpass(
                        f"\033[0;96mEnter 2FA password ({password.hint}): \033[0m"
                        if self.arguments.tty
                        else f"Enter 2FA password ({password.hint}): "
                    )
                    try:
                        await client._on_login(
                            (
                                await client(
                                    CheckPasswordRequest(
                                        compute_check(password, _2fa.strip())
                                    )
                                )
                            ).user
                        )
                    except PasswordHashInvalidError:
                        print("\033[0;91mInvalid 2FA password!\033[0m")
                    except FloodWaitError as e:
                        seconds, minutes, hours = (
                            e.seconds % 3600 % 60,
                            e.seconds % 3600 // 60,
                            e.seconds // 3600,
                        )
                        seconds, minutes, hours = (
                            f"{seconds} second(-s)",
                            f"{minutes} minute(-s) " if minutes else "",
                            f"{hours} hour(-s) " if hours else "",
                        )
                        print(
                            "\033[0;91mYou got FloodWait error! Please wait"
                            f" {hours}{minutes}{seconds}\033[0m"
                        )
                        return False
                    else:
                        break
            case False:
                pass

        print_banner("success.txt")
        print("\033[0;92mLogged in successfully!\033[0m")
        await self.save_client_session(client)
        self.clients += [client]

        return True

    async def _init_clients(self) -> bool:
        """
        Reads session from disk and inits them
        :returns: `True` if at least one client started successfully
        """
        for session in self.sessions.copy():
            try:
                client = CustomTelegramClient(
                    session,
                    self.api_token.ID,
                    self.api_token.HASH,
                    connection=self.conn,
                    proxy=self.proxy,
                    connection_retries=None,
                    device_model=get_app_name(),
                    system_version=generate_random_system_version(),
                    app_version=".".join(map(str, __version__)) + " x64",
                    lang_code="en",
                    system_lang_code="en-US",
                )
                if session.server_address == "0.0.0.0":
                    patcher.patch(client, session)

                await client.connect()

                if not await client.is_user_authorized():
                    logging.warning(
                        "Session %s is not authorized (terminated by Telegram or the"
                        " login wasn't finished), skipping it",
                        session.filename,
                    )
                    await client.disconnect()
                    self.sessions.remove(session)
                    continue

                client.phone = "None"

                self.clients += [client]
            except sqlite3.OperationalError:
                logging.error(
                    "Check that this is the only instance running. "
                    "If that doesn't help, delete the file '%s'",
                    session.filename,
                )
                continue
            except (TypeError, AuthKeyDuplicatedError) as e:
                logging.error(
                    "Session %s is unusable (%s) and is being deleted",
                    session.filename,
                    type(e).__name__,
                    exc_info=isinstance(e, TypeError),
                )
                Path(session.filename).unlink(missing_ok=True)
                self.sessions.remove(session)
            except (ValueError, ApiIdInvalidError):
                # Bad API hash/ID
                run_config()
                return False
            except PhoneNumberInvalidError:
                logging.error(
                    "Phone number is incorrect. Use international format (+XX...) "
                    "and don't put spaces in it."
                )
                self.sessions.remove(session)
            except (AuthKeyUnregisteredError, InteractiveAuthRequired):
                logging.error(
                    "Session %s was terminated and re-auth is required",
                    session.filename,
                )
                self.sessions.remove(session)

        return bool(self.sessions)

    async def amain_wrapper(self, client: CustomTelegramClient):
        """Wrapper around amain"""
        async with client:
            first = True
            me = await client.get_me()
            client._tg_id = me.id
            client.tg_id = me.id
            client.hikka_me = me
            client.heroku_me = me
            set_client_id(me.id)
            register_secret(StringSession.save(client.session))
            register_secret(getattr(me, "phone", None))

            async with self._allowed_ids_lock:
                if self._allowed_ids is None:
                    self._allowed_ids = await get_allowed_ids(client)

            await version.check_branch(me.id, self._allowed_ids, self)

            who = f"{me.id}" + (f" (@{me.username})" if me.username else "")
            try:
                while await self.amain(first, client):
                    first = False
            except SESSION_LOST_ERRORS as e:
                logging.error(
                    "Session of the account %s was terminated by Telegram (%s),"
                    " its userbot is stopped. Log in again to restore it",
                    who,
                    type(e).__name__,
                )
                return

            logging.error(
                "Client of the account %s is disconnected, its userbot is stopped"
                " (the session may have been terminated by Telegram)",
                who,
            )

    async def _badge(self, client: CustomTelegramClient):
        """Call the badge in shell"""
        try:
            if os.environ.get("HEROKU_NO_GIT") == "1":
                build = "unknown"
                upd = "Git disabled"
            else:
                import git

                with git.Repo() as repo:
                    build = repo.head.commit.hexsha
                    diff = repo.git.log([f"HEAD..origin/{version.branch}", "--oneline"])
                upd = "Update required" if diff else "Up-to-date"
            pref = client.heroku_db.get("heroku.main", "command_prefix", None)

            logo = (
                "                          _           \n"
                r"  /\  /\ ___  _ __  ___  | | __ _   _ "
                "\n"
                r" / /_/ // _ \| '__|/ _ \ | |/ /| | | |"
                "\n"
                "/ __  /|  __/| |  | (_) ||   < | |_| |\n"
                r"\/ /_/  \___||_|   \___/ |_|\_\ \__,_|"
                "\n\n"
                f"• Build: {build[:7]}\n"
                f"• Version: {'.'.join(list(map(str, list(__version__))))}\n"
                f"• {upd}\n"
            )
            if not self.omit_log:
                print(logo)
                logging.debug(
                    "\n🪐 Heroku %s #%s (%s) started",
                    ".".join(list(map(str, list(__version__)))),
                    build[:7],
                    upd,
                )
                self.omit_log = True

            try:
                log_chat_id = (
                    logging.getLogger().handlers[0].get_logid_by_client(client.tg_id)
                )
                message_thread_id = (
                    await logging.getLogger()
                    .handlers[0]
                    .get_logs_topic_id_by_client(client.tg_id)
                )

                await client.heroku_inline.bot.send_photo(
                    log_chat_id,
                    "https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/heroku_started.jpg",
                    caption=(
                        "{} <b>{} started!</b>\n\n<tg-emoji emoji-id=5231065262228250587>⚙</tg-emoji> <b>GitHub commit SHA: <a"
                        ' href="https://github.com/Heroku-userbot/Heroku/commit/{}">{}</a></b>\n<tg-emoji emoji-id=5873225338984599714>🔎</tg-emoji>'
                        " <b>Update status: {}</b>\n<tg-emoji emoji-id=5870903672937911120>🕶</tg-emoji> <b>Prefix:</b> <code>{}</code>"
                    ).format(
                        (
                            utils.get_platform_emoji()
                            if client.heroku_me.premium is True
                            else "🪐 Heroku"
                        ),
                        ".".join(list(map(str, list(__version__)))),
                        build,
                        build[:7],
                        upd,
                        "." if pref is None else pref,
                    ),
                    message_thread_id=message_thread_id,
                )
            except Exception as badge_error:
                logging.debug(f"Failed to send badge photo: {badge_error}")
            logging.debug(
                "· Started for %s · Prefix: «%s» ·",
                client.tg_id,
                client.heroku_db.get(__name__, "command_prefix", False) or ".",
            )
        except Exception:
            logging.exception("Badge error")

    async def _add_dispatcher(
        self,
        client: CustomTelegramClient,
        modules: loader.Modules,
        db: database.Database,
    ):
        """Inits and adds dispatcher instance to client"""
        dispatcher = CommandDispatcher(modules, client, db)
        client.dispatcher = dispatcher
        modules.check_security = dispatcher.check_security

        client.add_event_handler(
            dispatcher.handle_incoming,
            events.NewMessage,
        )

        client.add_event_handler(
            dispatcher.handle_incoming,
            events.ChatAction,
        )

        client.add_event_handler(
            dispatcher.handle_command,
            events.NewMessage(forwards=False),
        )

        client.add_event_handler(
            dispatcher.handle_command,
            events.MessageEdited(),
        )

        client.add_event_handler(
            dispatcher.handle_raw,
            events.Raw(),
        )

    async def amain(self, first: bool, client: CustomTelegramClient):
        """Entrypoint for async init, run once for each user"""
        client.parse_mode = "HTML"
        await client.start()

        db = database.Database(client)
        client.heroku_db = db
        await db.init()
        logging.debug("Got DB")
        logging.debug("Loading logging config...")

        translator = Translator(client, db)

        await translator.init()
        modules = loader.Modules(client, db, self.clients, translator)
        client.loader = modules

        await self._add_dispatcher(client, modules, db)

        await modules.register_all(None)
        modules.send_config()
        try:
            await modules.inline.register_manager()
        except Exception:
            logging.critical(
                "Inline manager initialization failed, continuing without the inline bot",
                exc_info=True,
            )
            modules.inline.init_complete = False

        await db.ensure_content_channel()
        await modules.send_ready()
        await modules.send_inline_ready()

        if first:
            await self._badge(client)

        await client.run_until_disconnected()

    @staticmethod
    def _loop_exception_handler(_, context: dict):
        """Log an error, caught by the event loop, with the task, which caused it"""
        culprit = (
            context.get("task") or context.get("future") or context.get("handle")
        )
        details = f" [{culprit!r}]" if culprit is not None else ""
        source = context.get("source_traceback")

        if source:
            details += "\nTask was created at:\n" + "".join(
                traceback.format_list(source[-5:])
            ).rstrip()

        owner = None

        if hasattr(culprit, "get_context"):
            with contextlib.suppress(Exception):
                owner = culprit.get_context().get(client_id_ctx)

        with client_id_override(owner):
            logging.error(
                "Exception on event loop! %s%s",
                context.get("message", "unknown error"),
                details,
                exc_info=context.get("exception"),
            )

    async def _main(self):
        """Main entrypoint"""
        await self._get_token()

        if (
            not self.clients and not self.sessions or not await self._init_clients()
        ) and not await self._initial_setup():
            return

        self.loop.set_exception_handler(self._loop_exception_handler)
        self._allowed_ids = None
        self._allowed_ids_lock = asyncio.Lock()
        await asyncio.gather(*[self.amain_wrapper(client) for client in self.clients])

    async def _shutdown_handler(self):
        for client in self.clients:
            inline = getattr(client.loader, "inline", None)
            if inline:
                for t in (inline._task, inline._cleaner_task):
                    if t:
                        t.cancel()
                try:
                    await inline._dp.stop_polling()
                    await inline.bot.session.close()
                except Exception:
                    pass
        for c in self.clients:
            await c.disconnect()
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()
        self.loop.stop()

    def main(self):
        """Main entrypoint"""
        if sys.platform != "win32":
            try:
                self.loop.add_signal_handler(
                    signal.SIGINT, lambda: asyncio.create_task(self._shutdown_handler())
                )
            except NotImplementedError:
                logging.warning("Signal handlers not supported on this platform.")
        else:
            logging.info("Running on Windows — skipping signal handler.")

        try:
            self.loop.run_until_complete(self._main())
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received.")
            self.loop.run_until_complete(self._shutdown_handler())
        except Exception as e:
            logging.exception("Unexpected exception in main loop: %s", e)
        finally:
            logging.info("Bye!")
            try:
                self.loop.run_until_complete(self._shutdown_handler())
            except Exception:
                pass


heroku = Heroku()
