"""Loads and registers modules"""

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

import ast
import asyncio
import contextlib
import difflib
import functools
import hashlib
import importlib
import inspect
import io
import logging
import os
import re
import shutil
import sys
import time
import typing
import uuid
from collections import ChainMap
from importlib.machinery import ModuleSpec
from urllib.parse import urlparse

import requests
from herokutl.tl.custom import Message
from herokutl.errors.common import ScamDetectionError
from herokutl.errors.rpcerrorlist import MediaCaptionTooLongError
from herokutl.tl.functions.channels import JoinChannelRequest
from herokutl.tl.types import Channel, InputMediaWebPage

from .. import loader, main, utils
from .._internal import fetch_text, private_write
from .._local_storage import RemoteStorage
from ..inline.types import InlineCall
from ..types import CoreOverwriteError, CoreUnloadError

logger = logging.getLogger(__name__)


class FakeOne:
    def __eq__(self, other):
        return other == -1 or isinstance(other, FakeOne)

    def __bool__(self):
        return False


MODULE_LOADING_FORBIDDEN = FakeOne()
MODULE_LOADING_FAILED = 0
MODULE_LOADING_SUCCESS = 1


class ModuleInstallError(RuntimeError):
    """Raised when an external module install fails after download."""


@loader.tds
class LoaderMod(loader.Module):
    """Loads modules"""

    strings = {"name": "Loader"}

    def __init__(self):
        self.fully_loaded = False
        self._links_cache = {}
        self._storage: RemoteStorage = None
        self._modules_cache_dir = os.path.join(main.BASE_DIR, ".modules_cache")
        self._pending_module_updates = {}
        self._startup_updates_task = None

        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "MODULES_REPO",
                "https://raw.githubusercontent.com/coddrago/modules/main",
                lambda: self.strings["repo_config_doc"],
                validator=loader.validators.Link(),
            ),
            loader.ConfigValue(
                "ADDITIONAL_REPOS",
                [],
                lambda: self.strings["add_repo_config_doc"],
                validator=loader.validators.Series(validator=loader.validators.Link()),
            ),
            loader.ConfigValue(
                "share_link",
                doc=lambda: self.strings["share_link_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "basic_auth",
                None,
                lambda: self.strings["basic_auth_doc"],
                validator=loader.validators.Hidden(
                    loader.validators.RegExp(r"^.*:.*$")
                ),
            ),
            loader.ConfigValue(
                "command_emoji",
                "<tg-emoji emoji-id=5197195523794157505>▫️</tg-emoji>",
                lambda: "Emoji for command",
            ),
            loader.ConfigValue(
                "rich_mode",
                False,
                lambda: self.strings["rich_mode_doc"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "show_banner",
                True,
                lambda: self.strings["show_banner_doc"],
                validator=loader.validators.Boolean(),
            ),
        )

    async def _async_init(self):
        modules = list(
            filter(
                lambda x: not x.startswith(
                    "https://raw.githubusercontent.com/coddrago/modules/main"
                ),
                utils.array_sum(
                    map(
                        lambda x: list(x.values()),
                        (await self.get_repo_list()).values(),
                    )
                ),
            )
        )
        logger.debug("Modules: %s", modules)
        self.create_task(self._storage.preload(modules))

    async def client_ready(self):
        while not (settings := self.lookup("settings")):
            await asyncio.sleep(0.5)

        self._storage = RemoteStorage(self._client)

        self.allmodules.add_aliases(settings.get("aliases", {}))

        main.heroku.ready.set()

        self.create_task(self._update_modules())

    @loader.loop(interval=3, wait_before=True, autostart=True)
    async def _config_autosaver(self):
        for mod in self.allmodules.modules:
            if (
                not hasattr(mod, "config")
                or not mod.config
                or not isinstance(mod.config, loader.ModuleConfig)
            ):
                continue

            for option, config in mod.config._config.items():
                if not hasattr(config, "_save_marker"):
                    continue

                delattr(mod.config._config[option], "_save_marker")
                mod.pointer("__config__", {})[option] = config.value

        for lib in self.allmodules.libraries:
            if (
                not hasattr(lib, "config")
                or not lib.config
                or not isinstance(lib.config, loader.ModuleConfig)
            ):
                continue

            for option, config in lib.config._config.items():
                if not hasattr(config, "_save_marker"):
                    continue

                delattr(lib.config._config[option], "_save_marker")
                lib._lib_pointer("__config__", {})[option] = config.value

        self._db.save()

    def update_modules_in_db(self):
        if self.allmodules.secure_boot:
            return

        self.set(
            "loaded_modules",
            {
                **{
                    module.__class__.__name__: module.__origin__
                    for module in self.allmodules.modules
                    if module.__origin__.startswith("http")
                },
            },
        )

    def _get_banner_url(self, doc: str) -> str | None:
        match = re.search(r"# ?meta banner: ?(.+)", doc)
        return match.group(1).strip() if match else None

    def _repo_to_label(self, repo: str) -> str:
        parsed = urlparse(repo)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return repo

    async def _check_pass(self, message: Message | InlineCall) -> bool:
        if self.db.get("LoaderRestrictor", "passed", False):
            return False

        if not self.inline.init_complete:
            return False # in case the inline bot did not start successfully,
                         # allow the user to install the modules

        await utils.answer(
            message,
            self.strings["verify_required"].format(self.inline.bot_username),
        )
        return True

    @loader.command(alias="dlm")
    async def dlmod(self, message: Message, force_pm: bool = False):
        if await self._check_pass(message):
            return

        if args := utils.get_args(message):
            match args:
                case [single]:
                    args = single
                    await utils.answer(message, self.strings["finding_module_in_repos"])
                    if (
                        await self.download_and_install(args, message, force_pm)
                        == MODULE_LOADING_FORBIDDEN
                    ):
                        return

                    if self.fully_loaded:
                        self.update_modules_in_db()
                case _:
                    not_installed = []
                    loaded_modules = []

                    message = await utils.answer(
                        message, f"Installing {len(args)} modules..."
                    )

                    for arg in args:
                        result = await self.download_and_install(
                            arg, _loaded_modules=loaded_modules
                        )
                        if result != MODULE_LOADING_SUCCESS:
                            not_installed.append(arg)

                    if self.fully_loaded:
                        self.update_modules_in_db()

                    rich_mode = self.config["rich_mode"]
                    result_message = self._batch_loaded_message(
                        loaded_modules, not_installed, rich=rich_mode
                    )
                    await self._answer_loaded_message(
                        message, result_message, rich=rich_mode,
                    )
        else:
            await self.inline.list(
                message,
                [
                    self.strings["avail_header"]
                    + f"\n☁️ {repo.strip('/')}\n\n"
                    + "\n".join(
                        [
                            " | ".join(chunk)
                            for chunk in utils.chunks(
                                [
                                    f"<code>{i}</code>"
                                    for i in sorted(
                                        [
                                            utils.escape_html(
                                                i.split("/")[-1].split(".")[0]
                                            )
                                            for i in mods.values()
                                        ]
                                    )
                                ],
                                5,
                            )
                        ]
                    )
                    for repo, mods in (await self.get_repo_list()).items()
                ],
            )

    @loader.command()
    async def dlmall(self, message: Message):
        if await self._check_pass(message):
            return

        repos = [self.config["MODULES_REPO"]] + self.config["ADDITIONAL_REPOS"]
        repos = [r for r in repos if r.startswith("http")]
        buttons = [
            [
                {
                    "text": self._repo_to_label(repo),
                    "callback": self._inline__install_all_from_repo,
                    "args": (repo,),
                }
            ]
            for repo in repos
        ]
        await self.inline.form(
            self.strings["choose_repo"],
            message,
            reply_markup=buttons,
        )

    async def _inline__install_all_from_repo(
        self,
        call: InlineCall,
        repo: str,
    ):
        await call.edit(self.strings["installing_all_from_repo"])

        links = await self._get_repo(repo)

        if not links:
            await call.edit(self.strings["dlm_all_from_repo_error_nomods"])
            return

        not_installed = []

        for link in links:
            full_url = f"{repo.strip('/')}/{link}.py"
            result = await self.download_and_install(full_url)
            if result != MODULE_LOADING_SUCCESS:
                not_installed.append(link.split("/")[-1])

        installed_count = len(links) - len(not_installed)

        if installed_count == 0:
            await call.edit(self.strings["dlm_all_from_repo_error_nomods"])
        elif not_installed:
            failed_list = "\n".join(not_installed)
            await call.edit(
                self.strings["dlm_all_from_repo_error_somemods"]
                + "<blockquote expandable>"
                + failed_list
                + "</blockquote>"
            )
        else:
            await call.edit(self.strings["installed_all_from_repo"])

        if self.fully_loaded:
            self.update_modules_in_db()

    async def _get_modules_to_load(self):
        todo = self.get("loaded_modules", {})
        logger.debug("Loading modules: %s", todo)
        return todo

    async def _get_repo(self, repo: str) -> str:
        repo = repo.strip("/")

        if self._links_cache.get(repo, {}).get("exp", 0) >= time.time():
            return self._links_cache[repo]["data"]

        try:
            content = await utils.run_sync(
                fetch_text,
                f"{repo}/full.txt",
                auth=self.config["basic_auth"],
                trusted_url=self.config["MODULES_REPO"],
            )
        except (requests.RequestException, ValueError):
            logger.warning("Can't load repository contents", exc_info=True)
            return []

        self._links_cache[repo] = {
            "exp": time.time() + 5 * 60,
            "data": [link for link in content.strip().splitlines() if link],
        }

        return self._links_cache[repo]["data"]

    async def get_repo_list(
        self,
        only_primary: bool = False,
    ) -> dict:
        return {
            repo: {
                f"Mod/{repo_id}/{i}": f'{repo.strip("/")}/{link}.py'
                for i, link in enumerate(set(await self._get_repo(repo)))
            }
            for repo_id, repo in enumerate(
                [self.config["MODULES_REPO"]]
                + ([] if only_primary else self.config["ADDITIONAL_REPOS"])
            )
            if repo.startswith("http")
        }

    async def get_links_list(self) -> list[str]:
        links = await self.get_repo_list()
        main_repo = list(links.pop(self.config["MODULES_REPO"]).values())
        return main_repo + list(dict(ChainMap(*list(links.values()))).values())

    async def _find_link(self, module_name: str) -> str | bool:
        return next(
            filter(
                lambda link: link.lower().endswith(f"/{module_name.lower()}.py"),
                await self.get_links_list(),
            ),
            False,
        )

    async def _answer_loaded_message(
        self, message, text: str, *, rich: bool,
        reply_markup=None, **kwargs,
    ):
        """Send installation results using the selected message format."""
        if not rich:
            return await utils.answer_with_media_fallback(
                message, text, reply_markup=reply_markup, **kwargs,
            )
        return await utils.answer_with_media_fallback(
            message, rich_message=text, reply_markup=reply_markup, **kwargs,
        )

    def _loaded_command_name(self, name: str, handler) -> str:
        prefix = utils.escape_html(self.get_prefix())
        result = f"<code>{prefix}{utils.escape_html(name)}</code>"
        aliases = getattr(handler, "aliases", None) or []
        if not aliases and (alias := getattr(handler, "alias", None)):
            aliases = [alias]
        if aliases:
            result += " ({})".format(
                ", ".join(
                    f"<code>{prefix}{utils.escape_html(alias)}</code>"
                    for alias in aliases
                )
            )
        return result

    def _batch_loaded_message(
        self, modules: list, failed: list[str], *, rich: bool = True,
        command_lines: list[str] | None = None,
        single: bool = False,
    ) -> str:
        """Render batch results or a single module with description and commands."""
        header = (
            '<tg-emoji emoji-id="5134452506935427991">🪐</tg-emoji> '
            f"<b>{len(modules)} Modules loaded</b>"
        )
        parts = [] if single else [f"<p>{header}</p>" if rich else header]
        if rich and not single and self.config["show_banner"]:
            slides = []
            for module in modules:
                banner_url = getattr(module, "heroku_meta_banner", None)
                if not isinstance(banner_url, str):
                    continue
                try:
                    parsed = urlparse(banner_url)
                except ValueError:
                    continue
                if parsed.scheme in {"http", "https"} and parsed.netloc:
                    slides.append(f'<img src="{utils.escape_html(banner_url)}"/>')
            if slides:
                parts.insert(0, "<tg-slideshow>" + "".join(slides) + "</tg-slideshow>")
        emoji = self.config["command_emoji"]

        def section(title: str, lines: list[str], suffix: str = ""):
            if rich:
                parts.append(
                    f"<details><summary>{title}{suffix}</summary>"
                    + "".join(f"<p>{line}</p>" for line in lines)
                    + "</details>"
                )
            else:
                parts.append(f"\n\n<b>{title}</b>{suffix}")
                if lines:
                    parts.append(
                        "\n<blockquote expandable>"
                        + "\n".join(lines)
                        + "</blockquote>"
                    )

        for module in modules:
            strings = getattr(module, "strings", {})
            try:
                name = strings["name"]
            except (KeyError, TypeError, AttributeError):
                name = None
            if not name or name == "Unknown strings: name":
                base_strings = getattr(strings, "_base_strings", {})
                name = base_strings.get("name")
            if not name:
                class_strings = getattr(type(module), "strings", {})
                name = (
                    class_strings.get("name")
                    if isinstance(class_strings, dict)
                    else None
                )
            name = name or "Unnamed module"

            version = getattr(module, "__version__", None)
            if isinstance(version, (tuple, list)):
                version = ".".join(map(str, version))
            elif version is not None:
                version = str(version).strip()
            version_suffix = (
                f" <code>({utils.escape_html(version)})</code>" if version else ""
            )
            lines = []
            for command, handler in getattr(module, "commands", {}).items():
                description = inspect.getdoc(handler) or self.strings["undoc"]
                description = utils.escape_html(description)
                if rich:
                    description = description.replace("\n", "<br/>")
                lines.append(
                    f"{emoji} {self._loaded_command_name(command, handler)}"
                    f" - {description}"
                )
            lines = lines if command_lines is None else command_lines
            if single:
                title = (
                    '<tg-emoji emoji-id="5134452506935427991">🪐</tg-emoji> '
                    f"<b>{utils.escape_html(str(name))}</b>{version_suffix}"
                )
                parts.append(f"<p>{title}</p>" if rich else title)
                description = utils.escape_html(inspect.getdoc(module) or "")
                if description:
                    parts.append(
                        '<p><i><tg-emoji emoji-id="5879813604068298387">ℹ️</tg-emoji> '
                        + description.replace("\n", "<br/>") + "</i></p>"
                        if rich else "\n\n" + description
                    )
                if lines:
                    section("Commands", lines)
            else:
                section(
                    '<tg-emoji emoji-id="4916086774649848789">🔗</tg-emoji> '
                    + utils.escape_html(str(name)),
                    lines,
                    version_suffix,
                )
            placeholders = utils.help_placeholders(module.__class__.__name__, self)
            if placeholders:
                section(
                    self.strings["loaded_placeholders"],
                    [line.replace("\n", "<br/>") for line in placeholders]
                    if rich else placeholders,
                )
        if failed:
            section(
                "Not loaded",
                [f"<code>{utils.escape_html(name)}</code>" for name in failed],
            )
        return "".join(parts)

    async def download_and_install(
        self,
        module_name: str,
        message: Message | None = None,
        force_pm: bool = False,
        name: str | None = None,
        _loaded_modules: list | None = None,
    ) -> int:
        try:
            blob_link = False
            module_name = module_name.strip()
            if urlparse(module_name).netloc:
                url = module_name
                resolved_name = name
                if re.match(
                    r"^(https:\/\/github\.com\/.*?\/.*?\/blob\/.*\.py)|"
                    r"(https:\/\/gitlab\.com\/.*?\/.*?\/-\/blob\/.*\.py)$",
                    url,
                ):
                    url = url.replace("/blob/", "/raw/")
                    blob_link = True
            else:
                url = await self._find_link(module_name)
                resolved_name = name or module_name

                if not url:
                    logger.warning(
                        "Module %s was not found in configured repos", module_name
                    )
                    if message is not None:
                        await utils.answer(message, self.strings["no_module"])

                    return MODULE_LOADING_FAILED

            if message:
                message = await utils.answer(
                    message,
                    self.strings["installing"].format(module_name),
                )

            try:
                r = await self._storage.fetch(
                    url, auth=self.config["basic_auth"],
                    trusted_url=self.config["MODULES_REPO"],
                )
            except requests.exceptions.HTTPError as e:
                logger.warning(
                    "Failed to download module %s from %s: %s",
                    module_name,
                    url,
                    e,
                )
                if message is not None:
                    await utils.answer(message, self.strings["no_module"])

                return MODULE_LOADING_FAILED

            installed = await self.load_module(
                r,
                message,
                resolved_name,
                url,
                blob_link=blob_link,
                _raise_install_errors=True,
                _loaded_modules=_loaded_modules,
            )

            if not installed:
                raise ModuleInstallError(f"Module {module_name} was not installed")

            self._write_module_cache(url, r)
            return MODULE_LOADING_SUCCESS
        except Exception:
            logger.exception("Failed to install external module %s", module_name)
            return MODULE_LOADING_FAILED

    async def _inline__load(
        self,
        call: InlineCall,
        doc: str,
        path_: str,
        mode: str,
    ):
        if await self._check_pass(call):
            return

        await self.load_module(doc, call, origin=path_ or "<string>", save_fs=True)

    @loader.command(alias="lm")
    async def loadmod(self, message: Message):
        if await self._check_pass(message):
            return

        msg = message if message.file else (await message.get_reply_message())

        if msg is None or msg.media is None:
            await utils.answer(message, self.strings["provide_module"])
            return

        await utils.answer(message, self.strings["loading_module_via_file"])

        path_ = None
        doc = await msg.download_media(bytes)

        try:
            doc = doc.decode()
        except UnicodeDecodeError:
            await utils.answer(message, self.strings["bad_unicode"])
            return

        if path_ is not None:
            await self.load_module(doc, message, origin=path_, save_fs=True)
        else:
            await self.load_module(doc, message, save_fs=True)

    async def approve_internal(
        self,
        call: InlineCall,
        channel: "hints.EntityLike",  # type: ignore  # noqa
        event: asyncio.Event,
    ):
        """
        Don't you dare call it externally
        """
        await self._client(JoinChannelRequest(channel))
        event.status = True
        event.set()

        await call.edit(
            (
                "💫 <b>Joined <a"
                f' href="https://t.me/{channel.username}">{utils.escape_html(channel.title)}</a></b>'
            ),
            photo="https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/joined_jr.jpg",
        )

    async def install_requirements(self, requirements: list):
        is_venv = hasattr(sys, "real_prefix") or sys.prefix != getattr(
            sys, "base_prefix", sys.prefix
        )
        need_user_flag = loader.USER_INSTALL and not is_venv

        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "-q",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            *(["--user"] if need_user_flag else []),
            *requirements,
        ]

        utils.ensure_child_watcher()
        try:
            pip = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            out, err = await pip.communicate()
        except Exception:
            logger.exception("Pip requirements install failed to start: %s", cmd)
            return False

        if pip.returncode != 0:
            logger.error(
                "Pip requirements install failed (%s) with exit code %s: %s",
                " ".join(cmd),
                pip.returncode,
                (err or out).decode(errors="ignore").strip() or "<no output>",
            )
            return False

        return True

    async def install_packages(self, packages: list):
        try:
            is_root = os.geteuid() == 0

            def _which(names):
                for n in names:
                    p = shutil.which(n)
                    if p:
                        return p
                return None

            pm = None
            if _which(["apt", "apt-get"]):
                pm = "apt"
            elif _which(["apk"]):
                pm = "apk"
            elif _which(["dnf"]):
                pm = "dnf"
            elif _which(["yum"]):
                pm = "yum"
            elif _which(["pacman"]):
                pm = "pacman"
            elif _which(["brew"]):
                pm = "brew"

            if not pm:
                logger.error(
                    "Can't install system packages %s: no supported package manager found",
                    packages,
                )
                return False

            cmd = []
            if pm == "apt":
                tool = _which(["apt", "apt-get"])
                cmd = [tool, "install", "-y", *packages]
            elif pm == "apk":
                cmd = ["apk", "add", "--no-cache", *packages]
            elif pm == "dnf":
                cmd = ["dnf", "install", "-y", *packages]
            elif pm == "yum":
                cmd = ["yum", "install", "-y", *packages]
            elif pm == "pacman":
                cmd = ["pacman", "-Syu", "--noconfirm", *packages]
            elif pm == "brew":
                cmd = ["brew", "install", *packages]

            if not is_root and shutil.which("sudo"):
                cmd = ["sudo", *cmd]

            utils.ensure_child_watcher()
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            out, err = await proc.communicate()

            if proc.returncode != 0:
                logger.error(
                    "System package install failed (%s) with exit code %s: %s",
                    " ".join(cmd),
                    proc.returncode,
                    err.decode(errors="ignore") if err else out.decode(errors="ignore"),
                )
                return False

            return True
        except Exception:
            logger.exception("install_packages failed")
            return False

    async def load_module(
        self,
        doc: str,
        message: Message,
        name: str | None = None,
        origin: str = "<string>",
        did_requirements: bool = False,
        save_fs: bool = True,
        blob_link: bool = False,
        did_requires: bool = False,
        did_packages: bool = False,
        _raise_install_errors: bool = False,
        _loaded_modules: list | None = None,
    ) -> bool:
        module_label = name or origin

        if any(
            line.replace(" ", "") == "#scope:ffmpeg" for line in doc.splitlines()
        ) and os.system("ffmpeg -version 1>/dev/null 2>/dev/null"):
            logger.error(
                "Module %s requires ffmpeg, but ffmpeg is not installed",
                module_label,
            )
            if isinstance(message, Message):
                await utils.answer(message, self.strings["ffmpeg_required"])
            return False

        if (
            any(line.replace(" ", "") == "#scope:inline" for line in doc.splitlines())
            and not self.inline.init_complete
        ):
            logger.error(
                "Module %s requires inline mode, but inline initialization failed",
                module_label,
            )
            if isinstance(message, Message):
                await utils.answer(message, self.strings["inline_init_failed"])
            return False

        if re.search(r"# ?scope: ?heroku_min", doc):
            ver = re.search(r"# ?scope: ?heroku_min ((?:\d+\.){2}\d+)", doc).group(1)
            ver_ = tuple(map(int, ver.split(".")))
            if main.__version__ < ver_:
                logger.error(
                    "Module %s requires Heroku %s, current version is %s",
                    module_label,
                    ver,
                    ".".join(map(str, main.__version__)),
                )
                if isinstance(message, Message):
                    if getattr(message, "file", None):
                        m = utils.get_chat_id(message)
                        await message.edit("")
                    else:
                        m = message

                    await self.inline.form(
                        self.strings["version_incompatible"].format(ver),
                        m,
                        reply_markup=[
                            {
                                "text": self.lookup("updater").strings("btn_update"),
                                "callback": self.lookup("updater").inline_update,
                            },
                            {
                                "text": self.lookup("updater").strings("cancel"),
                                "action": "close",
                            },
                        ],
                    )
                return False

        developer = re.search(r"# ?meta developer: ?(.+)", doc)
        developer = developer.group(1) if developer else False

        if not did_requires:
            requirements = []
            try:
                requirements = list(
                    filter(
                        lambda x: not x.startswith(("-", "_", ".")),
                        map(
                            str.strip,
                            loader.VALID_PIP_PACKAGES.search(doc)[1].split(),
                        ),
                    )
                )
            except TypeError:
                pass

            if requirements:
                result = await self.install_requirements(requirements)
                if not result:
                    logger.error(
                        "Module %s requirements from #scope:requires failed to install: %s",
                        module_label,
                        requirements,
                    )
                    if message is not None:
                        await utils.answer(message, self.strings["requirements_failed"])

                    return False

                importlib.invalidate_caches()

                kwargs = utils.get_kwargs()
                kwargs["did_requires"] = True

                return await self.load_module(**kwargs)  # Try again

        if not did_packages:
            packages = []
            try:
                packages = list(
                    filter(
                        lambda x: not x.startswith(("-", "_", ".")),
                        map(
                            str.strip,
                            loader.VALID_APT_PACKAGES.search(doc)[1].split(),
                        ),
                    )
                )
            except TypeError:
                pass

            if packages:
                result = await self.install_packages(packages)

                if not result:
                    logger.error(
                        "Module %s system packages from #scope:packages failed to install: %s",
                        module_label,
                        packages,
                    )
                    if message is not None:
                        await utils.answer(message, self.strings["requirements_failed"])
                    return False

                importlib.invalidate_caches()

                kwargs = utils.get_kwargs()
                kwargs["did_packages"] = True

                return await self.load_module(**kwargs)

        blob_link = self.strings["blob_link"] if blob_link else ""

        if name is None:
            try:
                node = ast.parse(doc)
                uid = next(
                    n.name
                    for n in node.body
                    if isinstance(n, ast.ClassDef)
                    and any(
                        isinstance(base, ast.Attribute)
                        and base.value.id == "Module"
                        or isinstance(base, ast.Name)
                        and base.id == "Module"
                        for base in n.bases
                    )
                )
            except Exception:
                logger.debug(
                    "Can't parse classname from code, using legacy uid instead",
                    exc_info=True,
                )
                uid = "__extmod_" + str(uuid.uuid4())
        else:
            if name.startswith(self.config["MODULES_REPO"]):
                name = name.split("/")[-1].split(".py")[0]

            uid = name.replace("%", "%%").replace(".", "%d")

        module_name = f"heroku.modules.{uid}"

        async def restart_inline(call: InlineCall):
            await call.edit(self.strings["requirements_restarted"])
            await self.invoke("restart", "-f", message=message)

        async def core_overwrite(e: CoreOverwriteError):
            nonlocal message

            with contextlib.suppress(Exception):
                self.allmodules.modules.remove(instance)

            if not message:
                return

            await utils.answer(
                message,
                self.strings[f"overwrite_{e.type}"].format(
                    *(
                        (e.target,)
                        if e.type == "module"
                        else (utils.escape_html(self.get_prefix()), e.target)
                    )
                ),
            )

        try:
            try:
                spec = ModuleSpec(
                    module_name,
                    loader.StringLoader(doc, f"<external {module_name}>"),
                    origin=f"<external {module_name}>",
                )
                instance = await self.allmodules.register_module(
                    spec,
                    module_name,
                    origin,
                    save_fs=save_fs,
                )
            except ImportError as e:
                logger.info(
                    "Module loading failed, attemping dependency installation (%s)",
                    e.name,
                )
                requirements = [loader.IMPORT_PIP_ALIASES.get(e.name.lower(), e.name)]

                if not requirements:
                    raise Exception("Nothing to install") from e

                logger.debug("Installing requirements: %s", requirements)

                if did_requirements:
                    logger.error(
                        "Module %s still requires missing dependency %s after installation",
                        module_label,
                        e.name,
                    )
                    if message is not None:
                        await self.inline.form(
                            message=message,
                            text=self.strings["requirements_restart"].format(e.name),
                            reply_markup=[
                                {"text": "🚀 Restart", "callback": restart_inline}
                            ],
                        )

                    return False

                if message is not None:
                    await utils.answer(
                        message,
                        self.strings["requirements_installing"].format(
                            "\n".join(
                                f"{self.config['command_emoji']}" f" {req}"
                                for req in requirements
                            )
                        ),
                    )

                result = await self.install_requirements(requirements)
                if not result:
                    logger.error(
                        "Module %s dependency installation failed: %s",
                        module_label,
                        requirements,
                    )
                    if message is not None:
                        await utils.answer(message, self.strings["requirements_failed"])

                    return False

                importlib.invalidate_caches()

                kwargs = utils.get_kwargs()
                kwargs["did_requirements"] = True

                return await self.load_module(**kwargs)  # Try again
            except CoreOverwriteError as e:
                logger.error(
                    "Module %s tried to overwrite core %s %s",
                    module_label,
                    e.type,
                    e.target,
                )
                await core_overwrite(e)
                return False
            except (loader.LoadError, ScamDetectionError) as e:
                logger.error("Module %s failed security checks: %s", module_label, e)
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    if isinstance(e, loader.LoadError):
                        await utils.answer(
                            message,
                            (
                                "<tg-emoji emoji-id=5287372146039861774>❌</tg-emoji>"
                                f" <b>{utils.escape_html(str(e))}</b>"
                            ),
                        )
                    elif isinstance(e, ScamDetectionError):
                        await utils.answer(
                            message,
                            (
                                self.strings["scam_module"].format(
                                    name=instance.__class__.__name__,
                                    prefix=self.get_prefix(),
                                )
                            ),
                        )
                return False
        except Exception as e:
            logger.exception("Loading external module failed due to %s", e)

            if message is not None:
                await utils.answer(message, self.strings["load_failed"])

            return False

        if hasattr(instance, "__version__") and isinstance(instance.__version__, tuple):
            version = (
                "<b><i>"
                f" (v{'.'.join(list(map(str, list(instance.__version__))))})</i></b>"
            )
        else:
            version = ""

        try:
            try:
                self.allmodules.send_config_one(instance)

                async def inner_proxy():
                    nonlocal instance, message
                    while True:
                        if hasattr(instance, "heroku_wait_channel_approve"):
                            if message:
                                (
                                    module,
                                    channel,
                                    reason,
                                ) = instance.heroku_wait_channel_approve
                                message = await utils.answer(
                                    message,
                                    self.strings["wait_channel_approve"].format(
                                        module,
                                        channel.username,
                                        utils.escape_html(channel.title),
                                        utils.escape_html(reason),
                                        self.inline.bot_username,
                                    ),
                                )
                                return

                        await asyncio.sleep(0.1)

                task = asyncio.ensure_future(inner_proxy())
                await self.allmodules.send_ready_one(
                    instance,
                    no_self_unload=True,
                    from_dlmod=bool(message),
                )
                task.cancel()
            except CoreOverwriteError as e:
                logger.error(
                    "Module %s tried to overwrite core %s %s during ready stage",
                    module_label,
                    e.type,
                    e.target,
                )
                await core_overwrite(e)
                return False
            except (loader.LoadError, ScamDetectionError) as e:
                logger.error(
                    "Module %s failed during ready security checks: %s",
                    module_label,
                    e,
                )
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    if isinstance(e, loader.LoadError):
                        await utils.answer(
                            message,
                            (
                                "<tg-emoji emoji-id=5287372146039861774>❌</tg-emoji>"
                                f" <b>{utils.escape_html(str(e))}</b>"
                            ),
                        )
                    elif isinstance(e, ScamDetectionError):
                        await utils.answer(
                            message,
                            (
                                self.strings["scam_module"].format(
                                    name=instance.__class__.__name__,
                                    prefix=self.get_prefix(),
                                )
                            ),
                        )
                return False
            except loader.SelfUnload as e:
                logger.warning(
                    "Module %s unloaded itself during installation: %s",
                    module_label,
                    e,
                )
                with contextlib.suppress(Exception):
                    await self.allmodules.unload_module(instance.__class__.__name__)

                with contextlib.suppress(Exception):
                    self.allmodules.modules.remove(instance)

                if message:
                    await utils.answer(
                        message,
                        (
                            "<tg-emoji emoji-id=5287372146039861774>❌</tg-emoji>"
                            f" <b>{utils.escape_html(str(e))}</b>"
                        ),
                    )
                return False
            except loader.SelfSuspend as e:
                logger.warning(
                    "Module %s suspended itself during installation: %s",
                    module_label,
                    e,
                )
                if message:
                    await utils.answer(
                        message,
                        (
                            "🥶 <b>Module suspended itself\nReason:"
                            f" {utils.escape_html(str(e))}</b>"
                        ),
                    )
                return False
        except Exception as e:
            logger.exception("Module threw because of %s", e)

            if message is not None:
                await utils.answer(message, self.strings["load_failed"])

            return False

        instance.heroku_meta_pic = next(
            (
                line.replace(" ", "").split("#metapic:", maxsplit=1)[1]
                for line in doc.splitlines()
                if line.replace(" ", "").startswith("#metapic:")
            ),
            None,
        )

        pack_url = next(
            (
                line.replace(" ", "").split("#packurl:", maxsplit=1)[1]
                for line in doc.splitlines()
                if line.replace(" ", "").startswith("#packurl:")
            ),
            None,
        )

        if pack_url and (
            transations := await self.allmodules.translator.load_module_translations(
                pack_url,
                loader.MODULES_LANGPACKS_PATH
                / f"{self.client.tg_id}_{instance.__class__.__name__}.yml",
            )
        ):
            instance.strings.external_strings = transations

        for alias, cmd in self.lookup("settings").get("aliases", {}).items():
            _cmd = cmd.split(maxsplit=1)
            if _cmd[0] in instance.commands:
                self.allmodules.add_alias(alias, *_cmd)

        try:
            modname = instance.strings("name")
        except (KeyError, AttributeError):
            modname = getattr(instance, "name", instance.__class__.__name__)

        try:
            developer_entity = await (
                self._client.force_get_entity
                if (
                    developer in self._client.heroku_entity_cache
                    and getattr(
                        await self._client.get_entity(developer),
                        "left",
                        True,
                    )
                )
                else self._client.get_entity
            )(developer)
        except Exception:
            developer_entity = None

        if not isinstance(developer_entity, Channel):
            developer_entity = None

        if _loaded_modules is not None:
            instance.heroku_meta_banner = self._get_banner_url(doc)
            _loaded_modules.append(instance)

        if message is None:
            return True

        modhelp = []
        mod_doc = ""

        if instance.__doc__:
            mod_doc += (
                "<i>\n<tg-emoji emoji-id=5879813604068298387>ℹ️</tg-emoji>"
                f" {utils.escape_html(inspect.getdoc(instance))}</i>\n\n"
            )

        subscribe = ""
        subscribe_markup = None

        depends_from = []
        for key in dir(instance):
            value = getattr(instance, key)
            if isinstance(value, loader.Library):
                depends_from.append(
                    "<tg-emoji emoji-id=5197195523794157505>▫️</tg-emoji>"
                    " <code>{}</code> <b>{}</b> <code>{}</code>".format(
                        value.__class__.__name__,
                        self.strings["by"],
                        (
                            value.developer
                            if isinstance(getattr(value, "developer", None), str)
                            else "Unknown"
                        ),
                    )
                )
        placeholders = utils.help_placeholders(
            getattr(getattr(instance, "__class__"), "__name__"), self
        )

        depends_from = (
            self.strings["depends_from"].format("\n".join(depends_from))
            if depends_from
            else ""
        )

        rich_mode = self.config["rich_mode"]

        def loaded_msg(use_subscribe: bool = True):
            if not rich_mode:
                return self.strings["loaded"].format(
                    modname.strip(),
                    version,
                    utils.ascii_face(),
                    mod_doc if mod_doc else "",
                    "<blockquote expandable>{}</blockquote>".format("\n".join(modhelp)),
                    "\n<blockquote expandable>{}</blockquote>".format(
                        "\n".join(placeholders)
                    ),
                    developer if not subscribe or not use_subscribe else "",
                    depends_from,
                    (
                        self.strings["modlink"].format(origin)
                        if origin != "<string>" and self.config["share_link"]
                        else ""
                    ),
                    blob_link,
                    subscribe if use_subscribe else "",
                )
            result = self._batch_loaded_message(
                [instance], [], rich=True, single=True,
                command_lines=[
                    line.replace("\n", "<br/>") if rich_mode else line
                    for line in modhelp
                ],
            )
            if self.config["show_banner"]:
                banner_url = self._get_banner_url(doc)
                if banner_url and urlparse(banner_url).scheme in {"http", "https"}:
                    result = f'<img src="{utils.escape_html(banner_url)}"/>' + result
            extra = []
            if origin != "<string>" and self.config["share_link"]:
                extra.append(self.strings["modlink"].format(utils.escape_html(origin)))
            if use_subscribe and subscribe:
                extra.append(subscribe)
            for text in extra:
                result += (
                    "<p>" + text.replace("\n", "<br/>") + "</p>"
                    if rich_mode else "\n\n" + text
                )
            return result

        if developer:
            if developer.startswith("@") and developer not in self.get(
                "do_not_subscribe", []
            ):
                if (
                    developer_entity
                    and getattr(developer_entity, "left", True)
                    and self._db.get(main.__name__, "suggest_subscribe", True)
                ):
                    subscribe = self.strings["suggest_subscribe"].format(
                        f"@{utils.escape_html(developer_entity.username)}"
                    )
                    subscribe_markup = [
                        {
                            "text": self.strings["subscribe"],
                            "callback": self._inline__subscribe,
                            "args": (
                                developer_entity.id,
                                functools.partial(loaded_msg, use_subscribe=False),
                                True,
                                rich_mode,
                            ),
                        },
                        {
                            "text": self.strings["no_subscribe"],
                            "callback": self._inline__subscribe,
                            "args": (
                                developer,
                                functools.partial(loaded_msg, use_subscribe=False),
                                False,
                                rich_mode,
                            ),
                        },
                    ]

            developer = self.strings["developer"].format(utils.escape_html(developer))
        else:
            developer = ""

        banner_kwargs = {}
        if (
            self.config["show_banner"]
            and not subscribe_markup
            and not getattr(message, "document", None)
            or getattr(message, "web_preview", False)
        ):
            try:
                banner_url = self._get_banner_url(doc)
                if banner_url:
                    banner_kwargs = {
                        "file": InputMediaWebPage(banner_url, optional=True),
                        "invert_media": True,
                    }
            except Exception:
                pass

        if any(
            line.replace(" ", "") == "#scope:disable_onload_docs"
            for line in doc.splitlines()
        ):
            await self._answer_loaded_message(
                message,
                loaded_msg(),
                rich=rich_mode,
                reply_markup=subscribe_markup,
                **banner_kwargs,
            )
            return True

        for _name, fun in sorted(
            instance.commands.items(),
            key=lambda x: x[0],
        ):
            modhelp.append(
                (
                    "{} {} - {}"
                    if rich_mode else "{} {} {}"
                ).format(
                    f"{self.config['command_emoji']}",
                    self._loaded_command_name(_name, fun),
                    (
                        utils.escape_html(inspect.getdoc(fun))
                        if fun.__doc__
                        else self.strings["undoc"]
                    ),
                )
            )

        if self.inline.init_complete:
            for _name, fun in sorted(
                instance.inline_handlers.items(),
                key=lambda x: x[0],
            ):
                modhelp.append(
                    self.strings["ihandler"].format(
                        f"@{self.inline.bot_username} {_name}",
                        (
                            utils.escape_html(inspect.getdoc(fun))
                            if fun.__doc__
                            else self.strings["undoc"]
                        ),
                    )
                )

        try:
            await self._answer_loaded_message(
                message,
                loaded_msg(),
                rich=rich_mode,
                reply_markup=subscribe_markup,
                **banner_kwargs,
            )
        except MediaCaptionTooLongError:
            await self._answer_loaded_message(
                message, loaded_msg(False), rich=rich_mode,
            )

        return True

    async def _inline__subscribe(
        self,
        call: InlineCall,
        entity: int,
        msg: typing.Callable[[], str],
        subscribe: bool,
        rich: bool = False,
    ):
        if not subscribe:
            self.set("do_not_subscribe", self.get("do_not_subscribe", []) + [entity])
            await self._answer_loaded_message(call, msg(), rich=rich)
            await call.answer(self.strings["not_subscribed"])
            return

        await self._client(JoinChannelRequest(entity))
        await self._answer_loaded_message(call, msg(), rich=rich)
        await call.answer(self.strings["subscribed"])

    @loader.command(alias="ulm")
    async def unloadmod(self, message: Message):
        if not (raw_args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_class"])
            return

        args = raw_args
        force = False
        first_line = args.split("\n", 1)[0].strip()
        if first_line == "-f":
            force = True
            rest = args.split("\n", 1)
            args = rest[1].strip() if len(rest) > 1 else ""
        elif args.startswith("-f "):
            force = True
            args = args[3:].strip()

        if not args:
            await utils.answer(message, self.strings["no_class"])
            return

        raw_list = re.split(r"[,\n]", args)
        modules = [m.strip() for m in raw_list if m.strip()]

        if len(modules) == 1:
            if not self.lookup(modules[0]):
                suggestions = self._get_unload_suggestions(modules[0])
                if suggestions:
                    await self.inline.form(
                        self.strings["unload_suggestions"].format(
                            utils.escape_html(modules[0])
                        ),
                        message=message,
                        reply_markup=[
                            [
                                {
                                    "text": label,
                                    "callback": self._inline__unload_suggested,
                                    "args": (classname, force),
                                }
                            ]
                            for classname, label in suggestions
                        ]
                        + [
                            [
                                {
                                    "text": self.strings["cancel"].replace("🚫", "❌"),
                                    "action": "close",
                                }
                            ]
                        ],
                        silent=True,
                    )
                    return

            msg = await self.unload_module(modules[0], force=force)
        else:
            success = []
            errors = []
            msg = ""
            for module in modules:
                status = await self.unload_module(module)
                if "❌" in status or "🚫" in status or "😖" in status:
                    if "💡" in status:
                        status = status.split("<code>")[0]

                    errors.append(f"<code>{module}</code> — {status}")
                else:
                    success.append(f"<code>{module}</code>")

            if success:
                msg += self.strings["modules_unloaded"].format(
                    unloaded_num=len(success), unloaded=", ".join(success)
                )
            if errors:
                msg += "\n" + self.strings["modules_not_unloaded"].format(
                    not_unloaded=len(errors),
                    errors="\n".join(errors),
                )

        await utils.answer(message, msg)

    def _get_unload_suggestions(
        self,
        query: str,
        limit: int = 3,
    ) -> list[tuple[str, str]]:
        query = query.lower()
        scored = []

        for module in self.allmodules.modules:
            if self._is_core_module(module):
                continue

            classname = module.__class__.__name__
            public_name = str(getattr(module, "name", "") or module.strings["name"])
            names = {
                classname,
                classname[:-3] if classname.endswith("Mod") else classname,
                public_name,
            }
            score = max(
                difflib.SequenceMatcher(None, query, name.lower()).ratio()
                for name in names
                if name
            )
            label = public_name
            scored.append((score, classname.lower(), classname, label))

        return [
            (classname, label)
            for _, _, classname, label in sorted(scored, reverse=True)[:limit]
        ]

    def _is_core_module(self, module) -> bool:
        module_name = getattr(module.__class__, "__module__", "")
        if not module_name.startswith("heroku.modules."):
            return False

        module_file = module_name.rsplit(".", 1)[-1]
        return os.path.isfile(
            os.path.join(utils.get_base_dir(), "modules", f"{module_file}.py")
        )

    async def _inline__unload_suggested(
        self,
        call: InlineCall,
        module: str,
        force: bool = False,
    ):
        await call.edit(await self.unload_module(module, force=force))

    async def unload_module(self, module: str, force: bool = False) -> str:
        instance = self.lookup(module)

        if instance and self._is_core_module(instance):
            return self.strings["unload_core"].format(module)

        if instance and issubclass(instance.__class__, loader.Library):
            return self.strings["cannot_unload_lib"]

        try:
            worked = await self.allmodules.unload_module(module)
        except CoreUnloadError:
            return self.strings["unload_core"].format(module)

        if not self.allmodules.secure_boot:
            self.set(
                "loaded_modules",
                {
                    mod: link
                    for mod, link in self.get("loaded_modules", {}).items()
                    if mod not in worked
                },
            )

        msg = (
            self.strings["unloaded"].format(
                "<tg-emoji emoji-id=5784993237412351403>✅</tg-emoji>",
                ", ".join(
                    [(mod[:-3] if mod.endswith("Mod") else mod) for mod in worked]
                ),
            )
            if worked
            else self.strings["not_unloaded"]
        )
        for mod_name in worked:
            utils.unregister_placeholders(mod_name)

        if force and worked:
            try:
                for key in list(self._db.keys()):
                    if not isinstance(key, str):
                        continue
                    low = key.lower()
                    for mod_name in worked:
                        base = mod_name[:-3] if mod_name.endswith("Mod") else mod_name
                        candidates = {mod_name.lower(), base.lower()}
                        if any(
                            low == c
                            or low.startswith(c + ".")
                            or low.startswith(c + "_")
                            or c in low
                            for c in candidates
                        ):
                            try:
                                del self._db[key]
                            except Exception:
                                pass

                try:
                    self._db.save()
                except Exception:
                    logger.debug(
                        "Failed to save DB after force-unload cleanup", exc_info=True
                    )
            except Exception:
                logger.exception("Failed to cleanup DB for force unload")

        return msg

    @loader.command()
    async def clearmodules(self, message: Message):
        await self.inline.form(
            self.strings["confirm_clearmodules"],
            message,
            reply_markup=[
                {
                    "text": self.strings["clearmodules"],
                    "callback": self._inline__clearmodules,
                },
                {
                    "text": self.strings["cancel"],
                    "action": "close",
                },
            ],
        )

    @loader.command()
    async def addrepo(self, message: Message):
        if not (args := utils.get_args_raw(message)) or (
            not utils.check_url(args) and not utils.check_url(f"https://{args}")
        ):
            await utils.answer(message, self.strings["no_repo"])
            return

        if args.endswith("/"):
            args = args[:-1]

        if not args.startswith("https://") and not args.startswith("http://"):
            args = f"https://{args}"

        try:
            content = await utils.run_sync(
                fetch_text,
                f"{args}/full.txt",
                auth=self.config["basic_auth"],
                trusted_url=self.config["MODULES_REPO"],
            )
            if not content.strip():
                raise ValueError
        except Exception:
            await utils.answer(message, self.strings["no_repo"])
            return

        if args in self.config["ADDITIONAL_REPOS"]:
            await utils.answer(message, self.strings["repo_exists"].format(args))
            return

        self.config["ADDITIONAL_REPOS"] += [args]

        await utils.answer(message, self.strings["repo_added"].format(args))

    @loader.command()
    async def delrepo(self, message: Message):
        if not (args := utils.get_args_raw(message)) or not utils.check_url(args):
            await utils.answer(message, self.strings["no_repo"])
            return

        if args.endswith("/"):
            args = args[:-1]

        if args not in self.config["ADDITIONAL_REPOS"]:
            await utils.answer(message, self.strings["repo_not_exists"])
            return

        self.config["ADDITIONAL_REPOS"].remove(args)

        await utils.answer(message, self.strings["repo_deleted"].format(args))

    async def _inline__clearmodules(self, call: InlineCall):
        self.set("loaded_modules", {})
        self.set("always_update_modules", [])
        self._pending_module_updates.clear()
        shutil.rmtree(self._modules_cache_dir, ignore_errors=True)

        for file in os.scandir(loader.LOADED_MODULES_DIR):
            try:
                os.remove(file.path)
            except Exception:
                logger.debug("Failed to remove %s", file.path, exc_info=True)

        await utils.answer(call, self.strings["all_modules_deleted"])
        await self.lookup("Updater").restart_common(call)

    def _module_cache_path(self, url: str) -> str:
        key = hashlib.sha256(url.encode()).hexdigest()
        return os.path.join(self._modules_cache_dir, f"{key}.py")

    @staticmethod
    def _module_class_names(doc: str) -> set[str]:
        try:
            tree = ast.parse(doc)
        except (SyntaxError, ValueError):
            return set()

        return {
            node.name.casefold()
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and any(
                isinstance(base, ast.Name)
                and base.id == "Module"
                or isinstance(base, ast.Attribute)
                and base.attr == "Module"
                for base in node.bases
            )
        }

    @staticmethod
    def _extract_module_name(doc: str) -> str | None:
        try:
            tree = ast.parse(doc)
        except (SyntaxError, ValueError):
            return None

        return next(
            (
                node.name
                for node in tree.body
                if isinstance(node, ast.ClassDef)
                and any(
                    isinstance(base, ast.Name)
                    and base.id == "Module"
                    or isinstance(base, ast.Attribute)
                    and base.attr == "Module"
                    for base in node.bases
                )
            ),
            None,
        )

    def _is_core_module_update(self, url: str, doc: str) -> bool:
        path = [part.casefold() for part in urlparse(url).path.strip("/").split("/")]
        if any(
            path[index : index + 2] == ["heroku", "modules"]
            for index in range(len(path) - 1)
        ):
            return True

        classes = self._module_class_names(doc)
        return any(
            module.__class__.__name__.casefold() in classes
            and getattr(module, "__origin__", "").startswith("<core")
            for module in self.allmodules.modules
        )

    def _write_module_cache(self, url: str, doc: str) -> None:
        os.makedirs(self._modules_cache_dir, mode=0o700, exist_ok=True)
        path = self._module_cache_path(url)
        private_write(path, doc)

    async def _accept_module_update(
        self,
        call: InlineCall,
        token: str,
        always: bool = False,
    ):
        pending = self._pending_module_updates.pop(token, None)
        if pending is None:
            await call.edit(self.strings["module_update_expired"])
            return

        url, doc = pending
        if always:
            urls = set(self.get("always_update_modules", []))
            urls.add(url)
            self.set("always_update_modules", sorted(urls))

        installed = await self.load_module(
            doc,
            call,
            self._extract_module_name(doc),
            url,
            _raise_install_errors=True,
        )
        if not installed:
            await call.edit(self.strings["module_update_failed"])
            return

        self._write_module_cache(url, doc)
        self.update_modules_in_db()
        await call.edit(self.strings["module_update_installed"])

    async def _decline_module_update(self, call: InlineCall, token: str):
        self._pending_module_updates.pop(token, None)
        await call.edit(self.strings["module_update_declined"])

    async def _offer_module_update(self, url: str, doc: str) -> None:
        name = self._extract_module_name(doc) or url.rsplit("/", 1)[-1].removesuffix(
            ".py"
        )
        name = f'<a href="{utils.escape_html(url)}">{utils.escape_html(name)}</a>'
        token = uuid.uuid4().hex
        self._pending_module_updates[token] = (url, doc)

        for _ in range(120):
            if self.inline.init_complete and self.inline._bot_client:
                break
            await asyncio.sleep(1)
        else:
            self._pending_module_updates.pop(token, None)
            logger.error("Inline bot is not ready; module update prompt was not sent")
            return

        unit_id = utils.rand(16)
        buttons = [
            [
                {
                    "text": self.strings["module_update_yes"],
                    "callback": self._accept_module_update,
                    "args": (token, False),
                    "emoji_id": "5899757765743615694",
                    "style": "success",
                },
                {
                    "text": self.strings["module_update_no"],
                    "callback": self._decline_module_update,
                    "args": (token,),
                    "emoji_id": "5872829476143894491",
                    "style": "danger",
                },
            ],
            [
                {
                    "text": self.strings["module_update_always"],
                    "callback": self._accept_module_update,
                    "args": (token, True),
                    "emoji_id": "5879883461711367869",
                    "style": "primary",
                }
            ],
        ]
        self.inline._units[unit_id] = {
            "type": "form",
            "text": self.strings["module_update_prompt"].format(name),
            "buttons": buttons,
            "caller": None,
            "chat": int(self.tg_id),
            "message_id": None,
            "uid": unit_id,
            "force_me": True,
        }

        try:
            markup = self.inline.generate_markup(unit_id)
            sent = await self.inline.bot.send_message(
                int(self.tg_id),
                self.inline._units[unit_id]["text"],
                reply_markup=markup,
                disable_notification=True,
            )
            self.inline._units[unit_id]["message_id"] = sent.id
        except Exception:
            self._pending_module_updates.pop(token, None)
            self.inline._units.pop(unit_id, None)
            logger.exception(
                "Failed to send module update prompt from inline bot to owner %s",
                self.tg_id,
            )
            return

    async def _check_module_update(
        self,
        url: str,
        cached_doc: str | None = None,
        *,
        name: str | None = None,
        offer_update: bool = True,
    ) -> bool:
        if cached_doc is None:
            path = self._module_cache_path(url)
            if not os.path.isfile(path):
                return False

            try:
                with open(path, encoding="utf-8", newline="") as file:
                    cached_doc = file.read()
            except Exception:
                logger.exception("Failed to read cached module %s", url)
                return False

        try:
            remote_doc = await self._storage.fetch(
                url, auth=self.config["basic_auth"],
                trusted_url=self.config["MODULES_REPO"],
            )
        except Exception:
            logger.warning("Failed to check module update for %s", url, exc_info=True)
            return False

        cached_hash = hashlib.sha256(cached_doc.encode()).digest()
        remote_hash = hashlib.sha256(remote_doc.encode()).digest()
        if cached_hash == remote_hash:
            return False

        if self._is_core_module_update(url, remote_doc):
            self._write_module_cache(url, remote_doc)
            return True

        if url in self.get("always_update_modules", []):
            installed = await self.load_module(
                remote_doc,
                None,
                name,
                url,
                _raise_install_errors=True,
            )
            if installed:
                self._write_module_cache(url, remote_doc)
                self.update_modules_in_db()

            return bool(installed)

        if offer_update and not any(
            pending_url == url
            for pending_url, _ in self._pending_module_updates.values()
        ):
            await self._offer_module_update(url, remote_doc)

        return False

    async def _load_cached_module(self, url: str, name: str | None = None) -> bool:
        path = self._module_cache_path(url)
        cached = os.path.isfile(path)
        try:
            if cached:
                with open(path, encoding="utf-8", newline="") as file:
                    doc = file.read()
            else:
                doc = await self._storage.fetch(
                    url, auth=self.config["basic_auth"],
                    trusted_url=self.config["MODULES_REPO"],
                )

            if self._is_core_module_update(url, doc):
                if not cached:
                    self._write_module_cache(url, doc)
                return cached

            installed = await self.load_module(
                doc,
                None,
                name,
                url,
                _raise_install_errors=True,
            )
            if not installed:
                raise ModuleInstallError(f"Cached module {url} was not installed")
            if not cached:
                self._write_module_cache(url, doc)
        except Exception:
            logger.exception("Failed to load cached module %s", url)
            return False

        return cached

    async def _check_startup_updates(self, modules: dict):
        semaphore = asyncio.Semaphore(4)

        async def check(name, url):
            async with semaphore:
                try:
                    await self._check_module_update(url, name=name)
                except Exception:
                    logger.exception("Failed to update module %s", name)

        await asyncio.gather(*(check(name, url) for name, url in modules.items()))

    @loader.loop(interval=60, wait_before=True, autostart=True)
    async def _auto_update_modules(self):
        if not self.fully_loaded or self._storage is None:
            return

        if self._startup_updates_task and not self._startup_updates_task.done():
            return

        loaded_modules = self.get("loaded_modules", {})
        always_update_urls = set(self.get("always_update_modules", []))
        for name, url in loaded_modules.items():
            if url in always_update_urls:
                await self._check_module_update(url, offer_update=False, name=name)

    async def _update_modules(self):
        started = time.perf_counter()
        todo = await self._get_modules_to_load()
        updates = {}

        self._secure_boot = False

        if self._db.get(loader.__name__, "secure_boot", False):
            self._db.set(loader.__name__, "secure_boot", False)
            self._secure_boot = True
        else:
            for name, url in todo.items():
                module_started = time.perf_counter()
                if await self._load_cached_module(url, name):
                    updates[name] = url
                elapsed = time.perf_counter() - module_started
                if elapsed >= 1:
                    logger.debug("Module %s initialization took %.2fs", name, elapsed)

            self.update_modules_in_db()

            aliases = {
                alias: cmd
                for alias, cmd in self.lookup("settings").get("aliases", {}).items()
                if self.allmodules.add_alias(alias, *cmd.split(maxsplit=1))
            }

            self.lookup("settings").set("aliases", aliases)

        self.fully_loaded = True
        logger.debug(
            "External module startup completed in %.2fs",
            time.perf_counter() - started,
        )

        if not self._secure_boot:
            self._startup_updates_task = self.create_task(
                self._check_startup_updates(updates)
            )
            self.create_task(self._async_init())

        with contextlib.suppress(AttributeError):
            await self.lookup("Updater").full_restart_complete(self._secure_boot)

    def flush_cache(self) -> int:
        """Flush the cache of links to modules"""
        count = sum(map(len, self._links_cache.values()))
        self._links_cache = {}
        return count

    def inspect_cache(self) -> int:
        """Inspect the cache of links to modules"""
        return sum(map(len, self._links_cache.values()))

    async def reload_core(self) -> int:
        """Forcefully reload all core modules"""
        self.fully_loaded = False

        if self._secure_boot:
            self._db.set(loader.__name__, "secure_boot", True)

        if not self._db.get(main.__name__, "remove_core_protection", False):
            for module in self.allmodules.modules:
                if module.__origin__.startswith("<core"):
                    module.__origin__ = "<reload-core>"

        loaded = await self.allmodules.register_all(no_external=True)
        for instance in loaded:
            self.allmodules.send_config_one(instance)
            await self.allmodules.send_ready_one(
                instance,
                no_self_unload=False,
                from_dlmod=False,
            )

        self.fully_loaded = True
        return len(loaded)

    @loader.command()
    async def mlcmd(self, message: Message):
        """| send module via file"""
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["args"])
            return

        await utils.answer(message, self.strings["ml_load_module"])

        exact = True
        if not (
            class_name := next(
                (
                    module.strings("name")
                    for module in self.allmodules.modules
                    if args.lower()
                    in {
                        module.strings("name").lower(),
                        module.__class__.__name__.lower(),
                    }
                ),
                None,
            )
        ):
            if not (
                class_name := next(
                    reversed(
                        sorted(
                            [
                                module.strings["name"].lower()
                                for module in self.allmodules.modules
                            ]
                            + [
                                module.__class__.__name__.lower()
                                for module in self.allmodules.modules
                            ],
                            key=lambda x: difflib.SequenceMatcher(
                                None,
                                args.lower(),
                                x,
                            ).ratio(),
                        )
                    ),
                    None,
                )
            ):
                await utils.answer(message, self.strings["404"])
                return

            exact = False

        try:
            module = self.lookup(class_name)
            sys_module = inspect.getmodule(module)
        except Exception:
            await utils.answer(message, self.strings["404"])
            return

        module_data = sys_module.__loader__.data
        if isinstance(module_data, str):
            module_data = module_data.encode("utf-8")

        module_doc = (
            module_data.decode("utf-8", errors="ignore")
            if isinstance(module_data, (bytes, bytearray))
            else str(module_data)
        )

        if any(
            line.replace(" ", "") == "#scope:no_ml" for line in module_doc.splitlines()
        ):
            await utils.answer(
                message,
                self.strings["no_ml"].format(utils.escape_html(class_name)),
            )
            return

        link = module.__origin__

        text = (
            f"<b>🧳 {utils.escape_html(class_name)}</b>"
            if not utils.check_url(link)
            else (
                f'📼 <b><a href="{link}">Link</a> for'
                f" {utils.escape_html(class_name)}:</b>"
                f' <code>{link}</code>\n\n{self.strings["not_exact"] if not exact else ""}'
            )
        )

        text = (
            self.strings["link"].format(
                class_name=utils.escape_html(class_name),
                url=link,
                not_exact=self.strings["not_exact"] if not exact else "",
                prefix=utils.escape_html(self.get_prefix()),
            )
            if utils.check_url(link)
            else self.strings["file"].format(
                class_name=utils.escape_html(class_name),
                not_exact=self.strings["not_exact"] if not exact else "",
                prefix=utils.escape_html(self.get_prefix()),
            )
        )

        file = io.BytesIO(module_data)
        file.name = f"{class_name}.py"
        file.seek(0)

        await utils.answer(
            message,
            text,
            file=file,
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

    def _format_result(
        self,
        result: dict,
        query: str,
        no_translate: bool = False,
    ) -> str:
        commands = "\n".join(
            [
                f"▫️ <code>{utils.escape_html(self.get_prefix())}{utils.escape_html(cmd)}</code>:"
                f" <b>{utils.escape_html(cmd_doc)}</b>"
                for cmd, cmd_doc in result["module"]["commands"].items()
            ]
        )

        kwargs = {
            "name": utils.escape_html(result["module"]["name"]),
            "dev": utils.escape_html(result["module"]["dev"]),
            "commands": commands,
            "cls_doc": utils.escape_html(result["module"]["cls_doc"]),
            "mhash": result["module"]["hash"],
            "query": utils.escape_html(query),
            "prefix": utils.escape_html(self.get_prefix()),
        }

        strings = (
            self.strings.get("result", "en")
            if self.config["translate"] and not no_translate
            else self.strings["result"]
        )

        text = strings.format(**kwargs)

        if len(text) > 1980:
            kwargs["commands"] = "..."
            text = strings.format(**kwargs)

        return text
