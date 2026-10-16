# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import logging
import os
import subprocess
from typing import Literal

import git
import herokutl

from .. import version

parser = herokutl.utils.sanitize_parse_mode("html")
logger = logging.getLogger(__name__)


def _is_no_git() -> bool:
    return os.environ.get("HEROKU_NO_GIT") == "1"


# GeekTG Compatibility
def get_git_info() -> tuple[str, str]:
    """
    Get git info
    :return: Git info
    """
    if _is_no_git():
        return ("", "")
    hash_ = get_git_hash() or ""
    return (
        hash_,
        f"https://github.com/Heroku-userbot/Heroku/commit/{hash_}" if hash_ else "",
    )


def get_git_hash() -> str | Literal[False]:
    """
    Get current Heroku git hash
    :return: Git commit hash
    """
    if _is_no_git():
        return False
    try:
        with git.Repo() as repo:
            return repo.head.commit.hexsha
    except Exception:
        return False


def get_commit_url() -> str:
    """
    Get current Heroku git commit url
    :return: Git commit url
    """
    if _is_no_git():
        return "Unknown"
    try:
        hash_ = get_git_hash()
        if not hash_:
            return "Unknown"
        return f'<a href="https://github.com/Heroku-userbot/Heroku/commit/{hash_}">#{hash_[:7]}</a>'
    except Exception:
        return "Unknown"


def get_git_status() -> str:
    """
    :return: 'Clean' or 'X files modified'.
    """
    if _is_no_git():
        return "Git disabled"
    try:
        process = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if process.returncode != 0:
            return "Not a Git repo"

        output = process.stdout.strip()

        if not output:
            return "Clean"

        count = len(output.splitlines())
        word = "file" if count == 1 else "files"
        return f"{count} {word} modified"

    except subprocess.TimeoutExpired:
        return "Unknown"
    except Exception:
        return "Unknown"


def get_last_commit_message() -> str:
    """
    Get the message of the last commit
    :return: Last commit message
    """
    if _is_no_git():
        return "Unknown"
    try:
        with git.Repo() as repo:
            message = repo.head.commit.message
            if isinstance(message, bytes):
                return message.decode(errors="replace").strip()
            return message.strip()
    except Exception:
        return "Unknown"


def get_commit_count() -> int:
    """
    Get the total number of commits in the repository
    :return: Number of commits
    """
    if _is_no_git():
        return 0
    try:
        with git.Repo() as repo:
            return len(list(repo.iter_commits()))
    except Exception:
        return 0


def is_up_to_date():
    with git.Repo(search_parent_directories=True) as repo:
        diff = any(repo.iter_commits(f"HEAD..origin/{version.branch}", max_count=1))
        return not diff
