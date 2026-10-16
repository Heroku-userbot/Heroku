"""Entry point. Checks for user and starts main script"""

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

import getpass
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ._internal import restart

if "--no-git" in sys.argv:
    os.environ["HEROKU_NO_GIT"] = "1"


def get_data_root():
    for index, arg in enumerate(sys.argv):
        if arg == "--data-root" and index + 1 < len(sys.argv):
            return Path(sys.argv[index + 1]).expanduser()

        if arg.startswith("--data-root="):
            return Path(arg.split("=", maxsplit=1)[1]).expanduser()

    return Path(
        "/data"
        if "DOCKER" in os.environ
        else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    )


def wipe_data():
    if not {"-w", "--wipe"} & set(sys.argv):
        return

    print(
        "Are you sure you want to completely delete all session files, "
        "their databases and modules? This action is irreversible [y/N]"
    )
    if input("> ").strip().lower() not in {"yes", "y"}:
        print("Cancelled")
        sys.exit(0)

    data_root = get_data_root()
    patterns = (
        "config.json",
        "config-*.json",
        "*.session",
        "*.session-journal",
        "api_token.txt",
    )
    dirs = ("loaded_modules", "sessions")
    removed = 0

    for pattern in patterns:
        for path in data_root.glob(pattern):
            if not path.is_file():
                continue

            path.unlink()
            removed += 1

    for dirname in dirs:
        path = data_root / dirname
        if not path.is_dir():
            continue

        shutil.rmtree(path)
        removed += 1

    print(f"Removed files: {removed}")
    sys.exit(0)


wipe_data()


def get_file_hash(filename):
    hasher = hashlib.sha256()
    try:
        with open(filename, "rb") as f:
            hasher.update(f.read())
        return hasher.hexdigest()
    except FileNotFoundError:
        return None


def deps():
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "-q",
                "--disable-pip-version-check",
                "--no-warn-script-location",
                "-r",
                "requirements.txt",
            ],
            check=True,
            timeout=600,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as e:
        print(
            f"\U0001f6ab pip failed with exit code {e.returncode}:\n"
            f"{(e.stdout or '') + (e.stderr or '')}".rstrip()
        )
        raise
    except subprocess.TimeoutExpired:
        print("\U0001f6ab pip didn't finish in 600 seconds")
        raise
    with open(".requirements_hash", "w") as f:
        f.write(get_file_hash("requirements.txt"))


if (
    getpass.getuser() == "root"
    and "--root" not in " ".join(sys.argv)
    and not {"-h", "--help"} & set(sys.argv)
    and all(trigger not in os.environ for trigger in {"DOCKER", "NO_SUDO"})
):
    print("\U0001f6ab" * 15)
    print("You attempted to run Heroku on behalf of root user")
    print("Please, create a new user and restart script")
    print("If this action was intentional, pass --root argument instead")
    print("\U0001f6ab" * 15)
    print()
    print("Type force_insecure to ignore this warning")
    print("Type no_sudo if your system has no sudo (Debian vibes)")
    inp = input("> ").lower()
    if inp != "force_insecure":
        sys.exit(1)
    elif inp == "no_sudo":
        os.environ["NO_SUDO"] = "1"
        print("Added NO_SUDO in your environment variables")
        restart()

if sys.version_info < (3, 10, 0):
    print("\U0001f6ab Error: you must use at least Python version 3.10.0")
elif __package__ != "heroku":
    print(
        "\U0001f6ab Error: you cannot run this as a script; you must execute as a package"
    )
else:
    try:
        import herokutl
    except Exception:
        pass
    else:
        try:
            import herokutl  # noqa: F811

            ver_ = tuple(
                int(match.group()) if (match := re.match(r"\d+", part)) else 0
                for part in herokutl.__version__.split(".")
            )
            if ver_ < (1, 7, 2):
                raise ImportError
        except ImportError:
            print("\U0001f504 Installing dependencies...")
            deps()
            restart()

    try:
        from . import log

        log.init()
        from . import main
    except ImportError as e:
        print(
            f"{str(e)}\n\U0001f504 Attempting dependencies installation... Just wait ⏱"
        )
        deps()
        restart()

    if "HEROKU_DO_NOT_RESTART" in os.environ:
        del os.environ["HEROKU_DO_NOT_RESTART"]
    if "HEROKU_DO_NOT_RESTART2" in os.environ:
        del os.environ["HEROKU_DO_NOT_RESTART2"]

    prev_hash = None
    if os.path.exists(".requirements_hash"):
        with open(".requirements_hash") as f:
            prev_hash = f.read().strip()

    if prev_hash != get_file_hash("requirements.txt"):
        print(
            "\U0001f504 Detected changes in requirements.txt, updating dependencies..."
        )
        deps()
        restart()

    main.heroku.main()
