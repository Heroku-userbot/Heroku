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

import contextlib
import itertools
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import typing
from io import StringIO
from types import ModuleType

import herokutl
from herokutl.errors.rpcerrorlist import MessageIdInvalidError
from herokutl.sessions import StringSession
from herokutl.tl.types import Message
from meval import meval

from .. import loader, main, utils
from ..log import HerokuException
from .._internal import redact

logger = logging.getLogger(__name__)


@loader.tds
class Evaluator(loader.Module):
    """Evaluates code in various languages"""

    strings = {"name": "Evaluator"}

    class _SecureDB:
        """
        Proxy class to protect sensitive DB fields from eval
        """

        def __init__(self, original_db):
            self._db = original_db

        def __getattr__(self, name):
            return getattr(self._db, name)

        def __getitem__(self, item):
            return self._db[item]

        def set(self, *args, **kwargs):
            if len(args) >= 2 and args[0] == "heroku.security" and args[1] == "owner":
                raise ValueError(
                    "⚠️ Security Protection: You cannot change the bot owner via evaluator."
                )

            return self._db.set(*args, **kwargs)

    @loader.command(alias="eval")
    async def e(self, message: Message):
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        skip_output = False
        if match := re.match(r"^(?:-so|--skip-output)(?:\s+|$)", args):
            skip_output = True
            args = args[match.end() :]

        if not args and reply and reply.text:
            args = reply.message

        shown = None
        if not args:
            for src in (message, reply):
                if src and src.file:
                    try:
                        args = (await src.download_media(bytes)).decode()
                    except UnicodeDecodeError:
                        logger.warning("File can't be decoded to execute code")
                        shown = "# File can't be decoded to execute code"
                    else:
                        if len(args) > 500:
                            shown = "# Code from file..."
                    break

        args = args.replace("\xa0", "\x20")
        shown = shown or args

        real_db = self.db
        self.db = self._SecureDB(real_db)

        output_print = StringIO()

        try:
            start_time = time.time()
            with contextlib.redirect_stdout(output_print):
                result = await meval(
                    args,
                    globals(),
                    **await self.getattrs(message),
                )
            print_output = output_print.getvalue()

        except Exception:
            item = HerokuException.from_exc_info(*sys.exc_info())
            print_output = output_print.getvalue()

            await utils.answer(
                message,
                self.strings["err"].format(
                    "4985626654563894116",
                    "python",
                    utils.escape_html(self.censor(shown)),
                    "error",
                    self.censor(
                        "\n".join(item.full_stack.splitlines()[:-1])
                        + "\n\n"
                        + "🚫 "
                        + item.full_stack.splitlines()[-1]
                    ),
                )
                + (
                    self.strings["print_outp"].format(
                        "python",
                        utils.escape_html(self.censor(print_output)),
                    )
                    if print_output
                    else ""
                ),
            )

            return
        finally:
            self.db = real_db

        if skip_output:
            return

        if callable(getattr(result, "stringify", None)):
            with contextlib.suppress(Exception):
                result = str(result.stringify())

        exec_time = time.time() - start_time

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings["eval_py"].format(
                    "4985626654563894116",
                    "python",
                    utils.escape_html(self.censor(shown)),
                )
                + (
                    self.strings["eval_result"].format(
                        "python", utils.escape_html(self.censor(str(result)))
                    )
                    if result or not print_output
                    else ""
                )
                + (
                    self.strings["print_outp"].format(
                        "python",
                        utils.escape_html(self.censor(print_output)),
                    )
                    if print_output
                    else ""
                )
                + (self.strings["time_exec"].format(round(exec_time, 2))),
            )

    @loader.command()
    async def ecpp(self, message: Message, c: bool = False):
        try:
            subprocess.check_output(
                ["gcc" if c else "g++", "--version"],
                stderr=subprocess.STDOUT,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            await utils.answer(
                message,
                self.strings["no_compiler"].format(
                    "4986046904228905931" if c else "4985844035743646190",
                    "C (gcc)" if c else "C++ (g++)",
                ),
            )
            return
        except Exception:
            await utils.answer(
                message,
                self.strings["no_compiler"].format(
                    "4986046904228905931" if c else "4985844035743646190",
                    "C (gcc)" if c else "C++ (g++)",
                ),
            )
            return

        code = utils.get_args_raw(message)
        message = await utils.answer(message, self.strings["compiling"])
        error = False
        with tempfile.TemporaryDirectory() as tmpdir:
            file = os.path.join(tmpdir, "code.cpp")
            with open(file, "w") as f:
                f.write(code)

            try:
                result = subprocess.check_output(
                    ["gcc" if c else "g++", "-o", "code", "code.cpp"],
                    cwd=tmpdir,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                ).decode()
            except subprocess.CalledProcessError as e:
                result = e.output.decode()
                error = True
            except subprocess.TimeoutExpired:
                result = "Compilation timeout"
                error = True

            if not result:
                try:
                    result = subprocess.check_output(
                        ["./code"],
                        cwd=tmpdir,
                        stderr=subprocess.STDOUT,
                        timeout=10,
                    ).decode()
                except subprocess.CalledProcessError as e:
                    result = e.output.decode()
                    error = True
                except subprocess.TimeoutExpired:
                    result = "Execution timeout"
                    error = True

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings["err" if error else "eval"].format(
                    "4986046904228905931" if c else "4985844035743646190",
                    "c" if c else "cpp",
                    utils.escape_html(code),
                    "error" if error else "output",
                    utils.escape_html(result),
                ),
            )

    @loader.command()
    async def ec(self, message: Message):
        await self.ecpp(message, c=True)

    @loader.command()
    async def ers(self, message: Message):
        try:
            subprocess.check_output(
                ["rustc", "--version"],
                stderr=subprocess.STDOUT,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            await utils.answer(
                message,
                self.strings["no_compiler"].format(
                    "5424780918776671920",
                    "Rust (rustc)",
                ),
            )
            return
        except Exception:
            await utils.answer(
                message,
                self.strings["no_compiler"].format(
                    "5424780918776671920",
                    "Rust (rustc)",
                ),
            )
            return

        code = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not code and reply and reply.text:
            code = reply.message

        message = await utils.answer(message, self.strings["compiling"])
        error = False
        with tempfile.TemporaryDirectory() as tmpdir:
            file = os.path.join(tmpdir, "code.rs")
            with open(file, "w") as f:
                f.write(code)

            try:
                result = subprocess.check_output(
                    ["rustc", "code.rs", "-o", "code"],
                    cwd=tmpdir,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                ).decode()
            except subprocess.CalledProcessError as e:
                result = e.output.decode()
                error = True
            except subprocess.TimeoutExpired:
                result = "Compilation timeout"
                error = True

            if not result:
                try:
                    result = subprocess.check_output(
                        ["./code"],
                        cwd=tmpdir,
                        stderr=subprocess.STDOUT,
                        timeout=10,
                    ).decode()
                except subprocess.CalledProcessError as e:
                    result = e.output.decode()
                    error = True
                except subprocess.TimeoutExpired:
                    result = "Execution timeout"
                    error = True

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings["err" if error else "eval"].format(
                    "5424780918776671920",
                    "rust",
                    utils.escape_html(code),
                    "error" if error else "output",
                    utils.escape_html(result),
                ),
            )

    @loader.command()
    async def eg(self, message: Message):
        try:
            subprocess.check_output(
                ["go", "version"],
                stderr=subprocess.STDOUT,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            await utils.answer(
                message,
                self.strings["no_compiler"].format(
                    "4994652309293105740",
                    "Go",
                ),
            )
            return
        except Exception:
            await utils.answer(
                message,
                self.strings["no_compiler"].format(
                    "4994652309293105740",
                    "Go",
                ),
            )
            return

        code = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not code and reply and reply.text:
            code = reply.message

        message = await utils.answer(message, self.strings["compiling"])
        error = False
        with tempfile.TemporaryDirectory() as tmpdir:
            file = os.path.join(tmpdir, "code.go")
            with open(file, "w") as f:
                f.write(code)

            try:
                result = subprocess.check_output(
                    ["go", "run", "code.go"],
                    cwd=tmpdir,
                    stderr=subprocess.STDOUT,
                    timeout=30,
                ).decode()
            except subprocess.CalledProcessError as e:
                result = e.output.decode()
                error = True
            except subprocess.TimeoutExpired:
                result = "Execution timeout"
                error = True

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings["err" if error else "eval"].format(
                    "4994652309293105740",
                    "go",
                    utils.escape_html(code),
                    "error" if error else "output",
                    utils.escape_html(result),
                ),
            )

    @loader.command()
    async def enode(self, message: Message):
        try:
            subprocess.check_output(
                ["node", "--version"],
                stderr=subprocess.STDOUT,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            await utils.answer(
                message,
                self.strings["no_compiler"].format(
                    "4985643941807260310",
                    "Node.js",
                ),
            )
            return
        except Exception:
            await utils.answer(
                message,
                self.strings["no_compiler"].format(
                    "4985643941807260310",
                    "Node.js",
                ),
            )
            return

        code = utils.get_args_raw(message)
        error = False
        with tempfile.TemporaryDirectory() as tmpdir:
            file = os.path.join(tmpdir, "code.js")
            with open(file, "w") as f:
                f.write(code)

            try:
                result = subprocess.check_output(
                    ["node", "code.js"],
                    cwd=tmpdir,
                    stderr=subprocess.STDOUT,
                    timeout=10,
                ).decode()
            except subprocess.CalledProcessError as e:
                result = e.output.decode()
                error = True
            except subprocess.TimeoutExpired:
                result = "Execution timeout"
                error = True

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings["err" if error else "eval"].format(
                    "4985643941807260310",
                    "javascript",
                    utils.escape_html(code),
                    "error" if error else "output",
                    utils.escape_html(result),
                ),
            )

    def censor(self, ret: str) -> str:
        ret = redact(ret)
        ret = ret.replace(str(self._client.heroku_me.phone), "&lt;phone&gt;")

        if redis := os.environ.get("REDIS_URL") or main.get_config_key("redis_uri"):
            ret = ret.replace(redis, f'redis://{"*" * 26}')

        if db := os.environ.get("DATABASE_URL") or main.get_config_key("db_uri"):
            ret = ret.replace(db, f'postgresql://{"*" * 26}')

        if btoken := self._db.get("heroku.inline", "bot_token", False):
            ret = ret.replace(
                btoken,
                f'{btoken.split(":")[0]}:{"*" * 26}',
            )

        if (lm := self.lookup("LoaderMod")) and (htoken := lm.get("token", False)):
            ret = ret.replace(htoken, f'eugeo_{"*" * 26}')

        ret = ret.replace(
            StringSession.save(self._client.session),
            "StringSession(**************************)",
        )

        return ret

    async def getattrs(self, message: Message) -> dict:
        reply = await message.get_reply_message()
        return {
            "message": message,
            "client": self._client,
            "reply": reply,
            "r": reply,
            "event": message,
            "chat": message.to_id,
            "herokutl": herokutl,
            "telethon": herokutl,
            "hikkatl": herokutl,
            "utils": utils,
            "main": main,
            "loader": loader,
            "c": self._client,
            "m": message,
            "lookup": self.lookup,
            "self": self,
            "db": self.db,
            **self.get_sub(herokutl.tl.functions),
            **self.get_sub(herokutl.tl.types),
        }

    def get_sub(self, obj: typing.Any, _depth: int = 1) -> dict:
        """Get all callable capitalised objects in an object recursively, ignoring _*"""
        return {
            **dict(
                filter(
                    lambda x: x[0][0] != "_"
                    and x[0][0].upper() == x[0][0]
                    and callable(x[1]),
                    obj.__dict__.items(),
                )
            ),
            **dict(
                itertools.chain.from_iterable(
                    [
                        self.get_sub(y[1], _depth + 1).items()
                        for y in filter(
                            lambda x: x[0][0] != "_"
                            and isinstance(x[1], ModuleType)
                            and x[1] != obj
                            and x[1].__package__.rsplit(".", _depth)[0]
                            == "herokutl.tl",
                            obj.__dict__.items(),
                        )
                    ]
                )
            ),
        }
