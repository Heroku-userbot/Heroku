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
import atexit
import base64
import contextlib
import contextvars
import functools
import html
import inspect
import logging
import os
import random
import re
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit

_secrets = set()
_secret_names = re.compile(
    r"(?:token|password|passwd|secret|api_?hash|api_?key|auth_?key|"
    r"string_?session|session_?string|private_?key|basic_auth|redis_uri|"
    r"redis_url|database_url|db_uri|credentials)", re.I
)


def register_secret(value):
    if isinstance(value, dict):
        for item in value.values():
            register_secret(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            register_secret(item)
    elif isinstance(value, str) and len(value) >= 4:
        _secrets.update((value, html.escape(value), quote(value, safe="")))
        if ":" in value:
            _secrets.add(base64.b64encode(value.encode()).decode())


def register_secrets(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if _secret_names.search(str(key)):
                register_secret(value)
            elif isinstance(value, (dict, list, tuple)):
                register_secrets(value)
    elif isinstance(data, (list, tuple)):
        for value in data:
            register_secrets(value)


def redact(text):
    text = str(text)
    for secret in sorted(_secrets.copy(), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY]", text, flags=re.S,
    )
    text = re.sub(r"\b\d{5,16}:[A-Za-z0-9_-]{30,}\b", "[REDACTED]", text)
    text = re.sub(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}\b", "[REDACTED]", text)
    text = re.sub(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9+/_.=-]+", r"\1 [REDACTED]", text)
    text = re.sub(r"(\w+://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
    text = re.sub(
        r"(?i)([\"']?(?:[\w.-]*(?:token|password|passwd|secret|api_key|api_hash|"
        r"auth_key|session_string|basic_auth))[\"']?\s*[:=]\s*)"
        r"(?:\"[^\"]*\"|'[^']*'|[^\s&,;<>]+)",
        r"\1[REDACTED]", text,
    )
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


class PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = super()._open()
        if hasattr(os, "fchmod"):
            os.fchmod(stream.fileno(), 0o600)
        else:
            os.chmod(self.baseFilename, 0o600)
        return stream


def private_write(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing to write private data through a symlink")
    if isinstance(data, str):
        data = data.encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


register_secrets(dict(os.environ))


_EMOJI_OPEN = re.compile(
    r"<emoji\s+document_id\s*=\s*[\"']?(\d+)[\"']?\s*>", re.IGNORECASE
)


def normalize_rich_html(html_text):
    if not isinstance(html_text, str):
        return html_text
    html_text = _EMOJI_OPEN.sub(r'<tg-emoji emoji-id="\1">', html_text)
    return re.sub(r"</emoji\s*>", "</tg-emoji>", html_text, flags=re.IGNORECASE)


def validate_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or any(ord(char) < 33 or char == "\\" for char in url)
    ):
        raise ValueError("Code downloads require an HTTPS URL without credentials")
    parsed.port
    return parsed


def auth_for_url(url, auth, trusted_url):
    target = validate_url(url)
    if not auth or not trusted_url:
        return None
    trusted = validate_url(trusted_url)
    if (target.hostname, target.port or 443) != (trusted.hostname, trusted.port or 443):
        return None
    path = unquote(target.path)
    root = unquote(trusted.path).rstrip("/") + "/"
    if (
        ".." in path.split("/") or "%" in path or "\\" in path
        or not path.startswith(root)
    ):
        return None
    return tuple(auth.split(":", 1))


def fetch_text(url, *, auth=None, trusted_url=None, max_size=5 * 1024 * 1024):
    import requests

    with requests.Session() as session:
        session.trust_env = False
        for _ in range(6):
            validate_url(url)
            session.cookies.clear()
            with session.get(
                url,
                auth=auth_for_url(url, auth, trusted_url),
                allow_redirects=False,
                timeout=(10, 30),
                stream=True,
            ) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["Location"])
                    continue
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > max_size:
                        raise ValueError("Downloaded content exceeds the size limit")
                return content.decode("utf-8-sig")
    raise requests.TooManyRedirects("Too many redirects while downloading code")


client_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "heroku_client_id",
    default=None,
)


def get_client_id() -> int | None:
    """Get id of the client, which owns the current execution context"""
    return client_id_ctx.get()


def set_client_id(client_id: int | None):
    """Bind the current execution context and its future tasks to the client"""
    if isinstance(client_id, int):
        client_id_ctx.set(client_id)


def resolve_client_id(instance, path: str) -> int | None:
    """Read client id from the attribute chain of `instance`"""
    value = instance
    for attr in path.split("."):
        value = getattr(value, attr, None)
        if value is None:
            return None

    return value if isinstance(value, int) else None


@contextlib.contextmanager
def client_id_override(client_id: int | None):
    """Bind the block to the client, detaching it from the outer one if `None`"""
    token = client_id_ctx.set(client_id)
    try:
        yield
    finally:
        try:
            client_id_ctx.reset(token)
        except ValueError:
            pass


@contextlib.contextmanager
def client_id_scope(client_id: int | None):
    """Bind the block to the client, keeping the outer one if there is no id"""
    if not isinstance(client_id, int):
        yield
        return

    with client_id_override(client_id):
        yield


def tag_client_id(path: str) -> Callable:
    """Bind the decorated method to the client, read from `self.<path>`"""

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(self, *args, **kwargs):
                with client_id_scope(resolve_client_id(self, path)):
                    return await func(self, *args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            with client_id_scope(resolve_client_id(self, path)):
                return func(self, *args, **kwargs)

        return wrapper

    return decorator

_background_tasks: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> asyncio.Task:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def install_task_tracking():
    loop_cls = asyncio.base_events.BaseEventLoop
    if getattr(loop_cls.create_task, "_heroku_tracked", False):
        return

    original_create_task = loop_cls.create_task

    def create_task(self, coro, **kwargs):
        return _track_task(original_create_task(self, coro, **kwargs))

    create_task._heroku_tracked = True
    loop_cls.create_task = create_task

async def fw_protect():
    await asyncio.sleep(random.randint(1000, 2000) / 1000)


def get_startup_callback() -> Callable:
    return lambda *_: os.execl(
        sys.executable,
        sys.executable,
        "-m",
        os.path.relpath(os.path.abspath(os.path.dirname(os.path.abspath(__file__)))),
        *sys.argv[1:],
    )


def die():
    """Platform-dependent way to kill the current process group"""
    match True:
        case _ if "DOCKER" in os.environ:
            sys.exit(0)
        case _ if sys.platform == "win32":
            sys.exit(0)
        case _:
            os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)


def restart():
    if "--sandbox" in " ".join(sys.argv):
        exit(0)

    if "HEROKU_DO_NOT_RESTART2" in os.environ:
        print(
            "HerokuTL version 1.0.2 or higher is required, use `pip install heroku-tl-new -U` for update."
        )
        sys.exit(0)

    logging.getLogger().setLevel(logging.CRITICAL)

    print("🔄 Restarting...")

    if "HEROKU_DO_NOT_RESTART" not in os.environ:
        os.environ["HEROKU_DO_NOT_RESTART"] = "1"
    else:
        os.environ["HEROKU_DO_NOT_RESTART2"] = "1"

    if "DOCKER" in os.environ or sys.platform == "win32":
        atexit.register(get_startup_callback())
    else:
        signal.signal(signal.SIGTERM, get_startup_callback())
    die()


def print_banner(banner: str):
    print("\033[2J\033[3;1f")
    with open(
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "assets",
                banner,
            )
        ),
    ) as f:
        print(f.read())


def check_commit_ancestor(repo, branch):
    """Check if commit is ancestor of origin/master"""
    try:
        commit = repo.commit(branch).hexsha
        repo_path = repo.working_tree_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )

        proc = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                commit,
                "refs/remotes/origin/master",
            ],
            cwd=repo_path,
            capture_output=True,
            timeout=5,
        )
        if proc.returncode in (0, 1):
            return proc.returncode == 0
        return None
    except (subprocess.TimeoutExpired, Exception):
        return None


def get_branch_name(repo_path):
    """Get the current branch name using multiple methods (gitpython, HEAD, git cmd)"""
    branch_name = None

    try:
        import git

        with git.Repo(path=repo_path) as repo:
            branch_name = repo.active_branch.name
    except Exception:
        pass

    if not branch_name:
        try:
            head_path = os.path.join(repo_path, ".git", "HEAD")
            with open(head_path, encoding="utf-8") as f:
                content = f.read().strip()
            if content.startswith("ref:"):
                branch_name = content.split("/")[-1]
        except Exception:
            pass

    if not branch_name:
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                candidate = proc.stdout.strip()
                if candidate:
                    branch_name = candidate
        except (subprocess.TimeoutExpired, Exception):
            pass

    if isinstance(branch_name, str):
        branch_name = branch_name.strip().removeprefix("refs/heads/")

    return branch_name


def reset_to_master(repo_path):
    """Reset repository to master branch using gitpython or subprocess fallback"""
    try:
        import git

        with git.Repo(path=repo_path) as repo:
            repo.head.reset(index=True, working_tree=True)
            repo.heads.master.checkout(force=True)
    except Exception:
        try:
            subprocess.run(
                ["git", "reset", "--hard", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                timeout=5,
            )
            subprocess.run(
                ["git", "checkout", "master", "-f"],
                cwd=repo_path,
                capture_output=True,
                timeout=5,
            )
        except (subprocess.TimeoutExpired, Exception):
            pass


def restore_worktree(repo_path):
    """Restore working tree for allowed users. Try `git restore .`, fallback to `git reset --hard`.

    Returns True if an operation succeeded, False otherwise.
    """

    try:
        proc = subprocess.run(
            ["git", "restore", "."], cwd=repo_path, capture_output=True, timeout=5
        )
        if proc.returncode == 0:
            return True
    except (subprocess.TimeoutExpired, Exception):
        pass

    try:
        proc = subprocess.run(
            ["git", "reset", "--hard"], cwd=repo_path, capture_output=True, timeout=5
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False
