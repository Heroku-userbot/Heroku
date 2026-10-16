"""Saves modules to disk and fetches them if remote storage is not available."""

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
import hashlib
import logging
import os

from . import utils
from ._internal import fetch_text, validate_url, private_write
from .tl_cache import CustomTelegramClient

logger = logging.getLogger(__name__)

MAX_FILESIZE = 1024 * 1024 * 5  # 5 MB
MAX_TOTALSIZE = 1024 * 1024 * 100  # 100 MB


class LocalStorage:
    """Saves modules to disk and fetches them if remote storage is not available."""

    def __init__(self):
        self._path = os.path.join(os.path.expanduser("~"), ".heroku", "modules_cache")
        self._tracked_total_size: int | None = None
        self._ensure_dirs()

    @property
    def _total_size(self) -> int:
        if self._tracked_total_size is None:
            self._tracked_total_size = sum(
                entry.stat().st_size
                for entry in os.scandir(self._path)
                if entry.is_file()
            )

        return self._tracked_total_size

    def _ensure_dirs(self):
        """Ensures that the local storage directory exists."""
        if not os.path.isdir(self._path):
            os.makedirs(self._path, mode=0o700)

    def _get_path(self, repo: str, module_name: str) -> str:
        return os.path.join(
            self._path,
            hashlib.sha256(f"{repo}_{module_name}".encode()).hexdigest() + ".py",
        )

    def save(self, repo: str, module_name: str, module_code: str):
        """
        Saves module to disk.
        :param repo: Repository name.
        :param module_name: Module name.
        :param module_code: Module source code.
        """
        size = len(module_code)
        if size > MAX_FILESIZE:
            logger.warning(
                "Module %s from %s is too large (%s bytes) to save to local cache.",
                module_name,
                repo,
                size,
            )
            return

        if self._total_size + size > MAX_TOTALSIZE:
            logger.warning(
                "Local storage is full, cannot save module %s from %s.",
                module_name,
                repo,
            )
            return

        path = self._get_path(repo, module_name)
        previous_size = os.path.getsize(path) if os.path.isfile(path) else 0

        private_write(path, module_code)

        self._tracked_total_size = self._total_size + size - previous_size
        logger.debug("Saved module %s from %s to local cache.", module_name, repo)

    def fetch(self, repo: str, module_name: str) -> str | None:
        """
        Fetches module from disk.
        :param repo: Repository name.
        :param module_name: Module name.
        :return: Module source code or None.
        """
        path = self._get_path(repo, module_name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8", newline="") as f:
                return f.read()

        return None


class RemoteStorage:
    def __init__(self, client: CustomTelegramClient):
        self._local_storage = LocalStorage()
        self._client = client

    async def preload(self, urls: list[str]):
        """Preloads modules from remote storage."""
        logger.debug("Preloading modules from remote storage.")
        for url in urls:
            logger.debug("Preloading module %s", url)

            with contextlib.suppress(Exception):
                await self.fetch(url)

            await asyncio.sleep(5)

    @staticmethod
    def _parse_url(url: str) -> tuple[str, str, str]:
        """
        Parses a URL into a repository and module name.
        :param url: URL to parse.
        :return: Tuple of (url, repo, module_name).
        """
        domain_name = url.split("/")[2]

        match domain_name:
            case "raw.githubusercontent.com":
                owner, repo, branch = url.split("/")[3:6]
                module_name = url.split("/")[-1].split(".")[0]
                repo = f"git+{owner}/{repo}:{branch}"
            case "github.com":
                owner, repo, _, branch = url.split("/")[3:7]
                module_name = url.split("/")[-1].split(".")[0]
                repo = f"git+{owner}/{repo}:{branch}"
            case _:
                repo, module_name = url.rsplit("/", maxsplit=1)
                repo = repo.strip("/")

        return url, repo, module_name

    async def fetch(
        self, url: str, auth: str | None = None, trusted_url: str | None = None
    ) -> str:
        """
        Fetches the module from the remote storage.
        :param url: URL to the module.
        :param auth: Optional authentication string in the format "username:password".
        :return: Module source code.
        """
        validate_url(url)
        url, repo, module_name = self._parse_url(url)
        try:
            content = await utils.run_sync(
                fetch_text,
                url,
                auth=auth,
                trusted_url=trusted_url,
            )
        except Exception:
            logger.debug(
                "Can't load module from remote storage. Trying local storage.",
                exc_info=True,
            )
            if module := self._local_storage.fetch(repo, module_name):
                logger.debug("Module source loaded from local storage.")
                return module

            raise

        self._local_storage.save(repo, module_name, content)

        return content
