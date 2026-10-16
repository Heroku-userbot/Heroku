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
import logging
import os
import re
import shlex
import time
import typing
from collections.abc import Callable
import signal

import herokutl

from .. import loader, utils

logger = logging.getLogger(__name__)

BANNER_OK = "https://x0.at/grz4.jpg"
BANNER_BAD = "https://x0.at/4AAH.jpg"


def hash_msg(message):
    return f"{str(utils.get_chat_id(message))}/{str(message.id)}"


async def read_stream(func: Callable, stream, delay: float):
    data = bytearray()
    dirty = False
    last_update = time.monotonic()
    interval = max(float(delay), 0.05)
    while True:
        try:
            chunk = await asyncio.wait_for(stream.read(4096), timeout=interval)
        except asyncio.TimeoutError:
            chunk = None
        if chunk == b"":
            if dirty:
                await func(data.decode(errors="replace"))
            return
        if chunk:
            data.extend(chunk)
            dirty = True
        if dirty and time.monotonic() - last_update >= interval:
            await func(data.decode(errors="replace"))
            dirty = False
            last_update = time.monotonic()


def sudo_stdin_command(command, shell="/bin/sh"):
    if os.path.basename(os.path.realpath(shell)) == "fish":
        return (
            "function sudo\n"
            "    command sudo -S -p '[heroku-sudo] password:' $argv\n"
            "end\n" + command
        )
    return (
        "sudo() { command sudo -S -p '[heroku-sudo] password:' \"$@\"; };\n"
        + command
    )


class MessageEditor:
    def __init__(
        self,
        message: herokutl.tl.types.Message,
        command: str,
        config,
        strings,
        request_message,
    ):
        self.message = message
        self.command = command
        self.stdout = ""
        self.stderr = ""
        self.rc = None
        self.redraws = 0
        self.config = config
        self.strings = strings
        self.request_message = request_message
        self.start_time = time.time()

    async def update_stdout(self, stdout):
        self.stdout = stdout
        await self.redraw()

    async def update_stderr(self, stderr):
        self.stderr = stderr
        await self.redraw()

    async def redraw(self):
        text = self.strings["running"].format(utils.escape_html(self.command))  # fmt: skip

        if self.rc is not None:
            text += self.strings["finished"].format(utils.escape_html(str(self.rc)))

        text += self.strings["stdout"]
        text += utils.escape_html(self.stdout[max(len(self.stdout) - 2048, 0) :])
        stderr = utils.escape_html(self.stderr[max(len(self.stderr) - 1024, 0) :])
        text += (self.strings["stderr"] + stderr) if stderr else ""
        text += self.strings["end"]

        if self.rc is not None:
            exec_time = time.time() - self.start_time
            text += self.strings["time_exec"].format(round(exec_time, 2))

        with contextlib.suppress(herokutl.errors.rpcerrorlist.MessageNotModifiedError):
            try:
                self.message = await utils.answer(self.message, text)
            except herokutl.errors.rpcerrorlist.MessageTooLongError as e:
                logger.error(e)
                logger.error(text)
        # The message is never empty due to the template header

    async def cmd_ended(self, rc):
        self.rc = rc
        self.state = 4
        await self.redraw()

    def update_process(self, process):
        pass


class SudoMessageEditor(MessageEditor):
    def __init__(self, message, command, config, strings, request_message):
        super().__init__(message, command, config, strings, request_message)
        self.process = None
        self.inline_editor = None
        self._output_lock = asyncio.Lock()

    def update_process(self, process):
        self.process = process

    async def update_stderr(self, stderr):
        async with self._output_lock:
            self.stderr = stderr
            if self.inline_editor is None and InlineMessageEditor.password_requested(stderr):
                module = self.request_message.client.loader.lookup("TerminalMod")
                editor = InlineMessageEditor(
                    None, self.command, self.strings, self.config
                )
                editor.stdout = self.stdout
                editor.stderr = self.stderr
                editor.start_time = self.start_time
                editor.update_process(self.process)
                editor.owner_id = self.request_message.client.heroku_me.id
                editor.observe_password_prompt()
                form = await module.inline.form(
                    message=self.message,
                    text=editor.render_text(),
                    reply_markup=editor.get_reply_markup(),
                    force_me=True,
                    on_unload=editor.on_unload,
                )
                if not form:
                    if self.process.stdin and not self.process.stdin.is_closing():
                        self.process.stdin.close()
                    return
                editor.form = form
                self.inline_editor = editor
                module._inline_sessions[form.unit_id] = editor
            elif self.inline_editor is not None:
                await self.inline_editor.update_stderr(stderr)
            else:
                await self.redraw()

    async def update_stdout(self, stdout):
        async with self._output_lock:
            self.stdout = stdout
            if self.inline_editor is not None:
                await self.inline_editor.update_stdout(stdout)
            else:
                await self.redraw()

    async def cmd_ended(self, rc):
        async with self._output_lock:
            self.rc = rc
            if self.inline_editor is not None:
                await self.inline_editor.cmd_ended(rc)
            else:
                await self.redraw()


class RawMessageEditor(SudoMessageEditor):
    def __init__(
        self,
        message,
        command,
        config,
        strings,
        request_message,
        show_done=False,
    ):
        super().__init__(message, command, config, strings, request_message)
        self.show_done = show_done

    async def redraw(self):
        logger.debug(self.rc)

        match self.rc:
            case None:
                text = (
                    "<code>"
                    + utils.escape_html(self.stdout[max(len(self.stdout) - 4095, 0) :])
                    + "</code>"
                )
            case 0:
                text = (
                    "<code>"
                    + utils.escape_html(self.stdout[max(len(self.stdout) - 4090, 0) :])
                    + "</code>"
                )
            case _:
                text = (
                    "<code>"
                    + utils.escape_html(self.stderr[max(len(self.stderr) - 4095, 0) :])
                    + "</code>"
                )

        if self.rc is not None and self.show_done:
            text += "\n" + self.strings["done"]

        logger.debug(text)

        with contextlib.suppress(
            herokutl.errors.rpcerrorlist.MessageNotModifiedError,
            herokutl.errors.rpcerrorlist.MessageEmptyError,
            ValueError,
        ):
            try:
                await utils.answer(self.message, text)
            except herokutl.errors.rpcerrorlist.MessageTooLongError as e:
                logger.error(e)
                logger.error(text)


class InlineMessageEditor:
    """Streams command output into an inline form via form.edit()"""

    def __init__(self, form, command: str, strings, config, reply_markup=None):
        self.form = form
        self.command = command
        self.stdout = ""
        self.stderr = ""
        self.rc = None
        self.strings = strings
        self.config = config
        self.reply_markup = reply_markup
        self.start_time = time.time()
        self.process = None
        self.owner_id = getattr(getattr(form, "inline_manager", None), "_me", None)
        self.waiting_password = False
        self._prompt_end = 0
        self._password_token = None
        self._auth_notice = ""
        self._edit_lock = asyncio.Lock()

    @staticmethod
    def password_requested(stderr):
        return re.search(
            r"(?:\[heroku-sudo\] password:|\[sudo\] (?:password for|пароль для) [^\r\n]+:)\s*$",
            stderr,
        )

    def observe_password_prompt(self):
        prompt = self.password_requested(self.stderr)
        if (
            prompt
            and prompt.end() > self._prompt_end
            and self.rc is None
            and self.process is not None
            and self.process.returncode is None
        ):
            self._auth_notice = self.strings[
                "sudo_password_retry" if self._prompt_end else "sudo_password_required"
            ]
            self._prompt_end = prompt.end()
            self._password_token = utils.rand(24)
            self.waiting_password = True

    def get_reply_markup(self):
        if self.waiting_password and self.rc is None:
            return [[{
                "text": self.strings["btn_input_password"],
                "input": self.strings["sudo_password_input"],
                "handler": self.input_password,
                "args": (self._password_token,),
            }]]
        return self.reply_markup(self) if callable(self.reply_markup) else self.reply_markup or []

    async def input_password(self, call, query: str, token: str):
        if getattr(call.from_user, "id", None) != self.owner_id:
            return
        if (
            not self.waiting_password
            or token != self._password_token
            or self.rc is not None
            or self.process is None
            or self.process.returncode is not None
            or self.process.stdin is None
            or self.process.stdin.is_closing()
        ):
            return
        if not query or any(char in query for char in "\r\n\x00"):
            return
        self.waiting_password = False
        self._password_token = None
        self._auth_notice = ""
        try:
            self.process.stdin.write(query.encode() + b"\n")
            await self.process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            del query
        await self.redraw()

    def on_unload(self):
        if self.waiting_password:
            self.waiting_password = False
            self._password_token = None
            if self.process and self.process.stdin and not self.process.stdin.is_closing():
                self.process.stdin.close()

    def reset(self, command: str):
        self.command = command
        self.stdout = ""
        self.stderr = ""
        self.rc = None
        self.start_time = time.time()
        self.process = None
        self.waiting_password = False
        self._prompt_end = 0
        self._password_token = None
        self._auth_notice = ""

    def update_process(self, process):
        self.process = process

    async def update_stdout(self, stdout):
        self.stdout = stdout
        await self.redraw()

    async def update_stderr(self, stderr):
        self.stderr = stderr
        self.observe_password_prompt()
        await self.redraw()

    def render_text(self):
        text = self.strings["running"].format(utils.escape_html(self.command))

        if self.rc is not None:
            text += self.strings["finished"].format(utils.escape_html(str(self.rc)))

        text += self.strings["stdout"]
        text += utils.escape_html(self.stdout[max(len(self.stdout) - 2048, 0) :])
        stderr = utils.escape_html(self.stderr[max(len(self.stderr) - 1024, 0) :])
        text += (self.strings["stderr"] + stderr) if stderr else ""
        text += self.strings["end"]

        if self.rc is not None:
            exec_time = time.time() - self.start_time
            text += self.strings["time_exec"].format(round(exec_time, 2))

        if self.waiting_password and self.rc is None:
            text += "\n" + self._auth_notice
        return text

    async def redraw(self):
        async with self._edit_lock:
            if self.form is not None:
                with contextlib.suppress(Exception):
                    await self.form.edit(
                        self.render_text(), reply_markup=self.get_reply_markup()
                    )

    async def cmd_ended(self, rc):
        self.rc = rc
        self.waiting_password = False
        self._password_token = None
        self._auth_notice = ""
        await self.redraw()


@loader.tds
class TerminalMod(loader.Module):
    """Runs commands"""

    strings = {
        "name": "Terminal",
    }

    COMMAND_PROTECT = "command_protect"
    DANGEROUS_RM_TARGETS = {
        "/",
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/lib",
        "/lib64",
        "/opt",
        "/proc",
        "/root",
        "/sbin",
        "/sys",
        "/usr",
        "/var",
    }
    DANGEROUS_RM_FILES = {
        "/etc/passwd",
        "/etc/shadow",
    }
    DANGEROUS_COMMANDS = [
        r"dd\s+.*if=.*of=/dev/",
        r"mkfs\.",
        r"fdisk\s+\/dev/",
        r"\\x72\\x6d\\x20\\x2d\\x72\\x66\\x20\\x2f",
        r"chmod\s+.*000\s+.*\/",
        r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:",
        r"cat\s+.*\/dev\/urandom\s+>\s+\/dev\/[hsv]d[a-z]",
        r"ln\s+.*-s\s+\/\s+\/dev\/null",
        r"echo\s+[\"']?[A-Za-z0-9+/=]{20,}[\"']?\s*\|\s*base64\s+-d\s*\|\s*(sh|bash|zsh)",
        r"base64\s+-d\s*\|\s*(sh|bash|zsh|dash|ksh)",
        r"echo\s+.+\|\s*base64\s+--decode\s*\|\s*(sh|bash|zsh|dash|ksh)",
        r"curl\s+.*\|\s*(sh|bash|zsh|dash|ksh)",
        r"wget\s+.*-O\s*-\s*\|\s*(sh|bash|zsh|dash|ksh)",
        r"curl\s+.*-o\s*/etc/",
        r"wget\s+.*-O\s*/etc/",
        r"mv\s+.*\s+/etc/passwd",
        r"mv\s+.*\s+/etc/shadow",
        r">\s*/etc/passwd",
        r">\s*/etc/shadow",
        r"nc\s+.*-e\s+(sh|bash|zsh)",
        r"ncat\s+.*-e\s+(sh|bash|zsh)",
        r"python[23]?\s+-c\s+[\"']import\s+os",
        r"python[23]?\s+-c\s+[\"']import\s+socket",
        r"perl\s+-e\s+[\"']use\s+Socket",
        r"php\s+-r\s+[\"'].*exec\(",
        r"openssl\s+s_client.*\|\s*(sh|bash)",
        r"socat\s+.*exec:",
        r"chmod\s+[0-9]*[s][0-9]*\s+",
        r"kill\s+-9\s+1\b",
        r"truncate\s+-s\s+0\s+/etc/",
        r"shred\s+",
        r"wipe\s+",
    ]

    @staticmethod
    def _split_command(cmd: str) -> list[str]:
        try:
            lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            return list(lexer)
        except ValueError:
            return []

    @classmethod
    def _is_dangerous_rm_target(cls, target: str) -> bool:
        if not target or target.startswith("-"):
            return False

        target = target.rstrip()
        normalized = os.path.normpath(target)

        if normalized in cls.DANGEROUS_RM_TARGETS | cls.DANGEROUS_RM_FILES:
            return True

        if normalized == "/":
            return target in {"/*", "/**"}

        for dangerous_target in cls.DANGEROUS_RM_TARGETS - {"/"}:
            if normalized in {f"{dangerous_target}/*", f"{dangerous_target}/**"}:
                return True

        return False

    @classmethod
    def _has_dangerous_rm(cls, cmd: str) -> bool:
        tokens = cls._split_command(cmd)
        if not tokens:
            return False

        separators = {";", "&&", "||", "|", "&"}
        rm_names = {"rm", "/bin/rm", "/usr/bin/rm"}

        for index, token in enumerate(tokens):
            if token not in rm_names:
                continue

            for target in tokens[index + 1 :]:
                if target in separators:
                    break

                if target == "--":
                    continue

                if cls._is_dangerous_rm_target(target):
                    return True

        return False

    def _is_dangerous(self, cmd: str) -> bool:
        if not self.config[self.COMMAND_PROTECT]:
            return False

        if self._has_dangerous_rm(cmd):
            return True

        for pattern in self.DANGEROUS_COMMANDS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return True
        return False

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "FLOOD_WAIT_PROTECT",
                2,
                lambda: self.strings["fw_protect"],
                validator=loader.validators.Integer(minimum=0),
            ),
            loader.ConfigValue(
                self.COMMAND_PROTECT,
                True,
                lambda: self.strings["command_protect"],
                validator=loader.validators.Boolean(),
            ),
        )
        self.activecmds = {}
        self._inline_pending: dict[str, str] = {}
        self._inline_sessions: dict[str, InlineMessageEditor] = {}

    def _build_inline_exec_markup(
        self,
        uid: str | None = None,
    ) -> list[list[dict[str, str]]]:
        if not uid:
            return []

        return [
            [
                {
                    "text": self.strings["btn_execute"],
                    "data": f"terminal/exec/{uid}",
                }
            ]
        ]

    def _build_inline_continue_markup(
        self,
        editor: InlineMessageEditor,
        session_uid: str,
    ) -> list[list[dict[str, typing.Any]]]:
        if editor.rc is None:
            return []

        return [
            [
                {
                    "text": self.strings["btn_continue"],
                    "input": self.strings["btn_continue"],
                    "handler": self.inline__continue_input,
                    "args": (session_uid,),
                }
            ]
        ]

    def _register_inline_session(self, session_uid: str, inline_message_id: str):
        self.inline._units[session_uid] = {
            "type": "form",
            "text": self.strings["exec_running"],
            "buttons": [],
            "caller": None,
            "chat": None,
            "message_id": None,
            "top_msg_id": None,
            "uid": session_uid,
            "inline_message_id": inline_message_id,
        }

    @loader.command(alias="exec")
    async def terminalcmd(self, message):
        user_command = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not user_command and reply and reply.message:
            user_command = reply.message

        if self._is_dangerous(user_command):
            await utils.answer(
                message,
                self.strings["dangerous_command"].format(
                    utils.escape_html(user_command)
                ),
            )
            return

        await self.run_command(message, user_command)

    @loader.inline_handler()
    async def exec_inline_handler(self, query):
        """Execute terminal command via inline"""
        raw = query.query.strip()
        if raw.lower().startswith("exec"):
            raw = raw[4:].strip()

        # Truncate command preview to 15 characters for display
        def short_cmd(cmd: str) -> str:
            return cmd[:15] + "..." if len(cmd) > 15 else cmd

        if not raw:
            await query.answer(
                [
                    await query.builder.article(
                        title=self.strings["inline_hint"],
                        description=self.strings["inline_hint_desc"],
                        text=self.strings["inline_hint"],
                        parse_mode="HTML",
                        thumb=self.inline._web_document(
                            BANNER_OK, width=640, height=640
                        ),
                        id="hint",
                    )
                ],
                cache_time=0,
                private=True,
            )
            return

        if self._is_dangerous(raw):
            await query.answer(
                [
                    await query.builder.article(
                        title=self.strings["inline_hint"],
                        description=short_cmd(raw),
                        text=self.strings["dangerous_command"].format(
                            utils.escape_html(raw)
                        ),
                        parse_mode="HTML",
                        thumb=self.inline._web_document(
                            BANNER_BAD, width=640, height=640
                        ),
                        id="dangerous",
                    )
                ],
                cache_time=0,
                private=True,
            )
            return

        uid = utils.rand(8)
        self._inline_pending[uid] = raw

        await query.answer(
            [
                await query.builder.article(
                    title=self.strings["inline_hint"],
                    description=short_cmd(raw),
                    text=self.strings["exec_confirm"].format(utils.escape_html(raw)),
                    parse_mode="HTML",
                    thumb=self.inline._web_document(BANNER_OK, width=640, height=640),
                    buttons=self.inline.generate_markup(
                        self._build_inline_exec_markup(uid)
                    ),
                    id=uid,
                )
            ],
            cache_time=0,
            private=True,
        )

    @loader.callback_handler()
    async def exec_callback(self, call):
        if not call.data.startswith("terminal/exec/"):
            return

        uid = call.data.split("/")[2]
        cmd = self._inline_pending.pop(uid, None)

        if not cmd:
            await call.answer("Command not found or already executed", show_alert=True)
            return

        if self._is_dangerous(cmd):
            await call.answer(
                self.strings["dangerous_command"].format(cmd),
                show_alert=True,
            )
            return

        self._register_inline_session(uid, call.inline_message_id)

        from ..inline.types import InlineMessage

        form = InlineMessage(
            inline_manager=self.inline,
            unit_id=uid,
            inline_message_id=call.inline_message_id,
        )

        await form.edit(self.strings["exec_running"])

        editor = InlineMessageEditor(
            form=form,
            command=cmd,
            strings=self.strings,
            config=self.config,
            reply_markup=lambda current_editor: self._build_inline_continue_markup(
                current_editor,
                uid,
            ),
        )
        self._inline_sessions[uid] = editor

        asyncio.ensure_future(self._run_inline(cmd, editor))

    async def inline__continue_input(self, call, query: str, session_uid: str):
        editor = self._inline_sessions.get(session_uid)

        if not editor:
            return

        query = query.strip()
        if not query:
            return

        cmd = f"{editor.command} {query}".strip()

        if self._is_dangerous(cmd):
            await editor.form.edit(
                self.strings["dangerous_command"].format(utils.escape_html(cmd)),
                reply_markup=self._build_inline_continue_markup(editor, session_uid),
            )
            return

        editor.reset(cmd)
        await editor.form.edit(self.strings["exec_running"])
        asyncio.ensure_future(self._run_inline(cmd, editor))

    async def _run_inline(self, cmd: str, editor: InlineMessageEditor):
        shell = os.environ.get("SHELL") or "/bin/sh"
        utils.ensure_child_watcher()

        try:
            sproc = await asyncio.create_subprocess_exec(
                shell,
                "-c",
                sudo_stdin_command(cmd, shell),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=utils.get_base_dir(),
                preexec_fn=os.setsid,
            )
        except Exception as e:
            with contextlib.suppress(Exception):
                await editor.form.edit(
                    self.strings["exec_error"].format(utils.escape_html(str(e)))
                )
            return

        editor.update_process(sproc)
        await editor.redraw()

        await asyncio.gather(
            read_stream(
                editor.update_stdout,
                sproc.stdout,
                self.config["FLOOD_WAIT_PROTECT"],
            ),
            read_stream(
                editor.update_stderr,
                sproc.stderr,
                self.config["FLOOD_WAIT_PROTECT"],
            ),
        )

        await editor.cmd_ended(await sproc.wait())

    async def run_command(
        self,
        message: herokutl.tl.types.Message,
        cmd: str,
        editor: MessageEditor | None = None,
    ):

        if self._is_dangerous(cmd):
            await utils.answer(
                message,
                self.strings["dangerous_command"].format(utils.escape_html(cmd)),
            )
            return

        shell = os.environ.get("SHELL") or "/bin/sh"
        utils.ensure_child_watcher()

        try:
            sproc = await asyncio.create_subprocess_exec(
                shell,
                "-c",
                sudo_stdin_command(cmd, shell),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=utils.get_base_dir(),
                preexec_fn=os.setsid,
            )
        except Exception as e:
            await utils.answer(
                message,
                self.strings["exec_error"].format(utils.escape_html(str(e))),
            )
            return

        if editor is None:
            editor = SudoMessageEditor(message, cmd, self.config, self.strings, message)

        editor.update_process(sproc)

        self.activecmds[hash_msg(message)] = sproc

        await editor.redraw()

        await asyncio.gather(
            read_stream(
                editor.update_stdout,
                sproc.stdout,
                self.config["FLOOD_WAIT_PROTECT"],
            ),
            read_stream(
                editor.update_stderr,
                sproc.stderr,
                self.config["FLOOD_WAIT_PROTECT"],
            ),
        )

        await editor.cmd_ended(await sproc.wait())
        del self.activecmds[hash_msg(message)]

    def _find_inline_editor_by_message(
        self,
        message: herokutl.tl.types.Message,
    ) -> InlineMessageEditor | None:
        text = getattr(message, "raw_text", None) or getattr(message, "text", "")
        running_editors = [
            editor
            for editor in self._inline_sessions.values()
            if editor.process and editor.rc is None
        ]

        if not running_editors:
            return None

        matched_editors = [
            editor
            for editor in running_editors
            if editor.command and editor.command in text
        ]

        if len(matched_editors) == 1:
            return matched_editors[0]

        if len(running_editors) == 1 and getattr(message, "via_bot_id", None) in {
            self.inline.bot_id,
            None,
        }:
            return running_editors[0]

        return None

    @loader.command(alias="kill")
    async def terminatecmd(self, message):
        if not message.is_reply:
            await utils.answer(message, self.strings["what_to_kill"])
            return

        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, self.strings["no_cmd"])
            return

        process = self.activecmds.get(hash_msg(reply))
        inline_editor = None

        if process is None:
            inline_editor = self._find_inline_editor_by_message(reply)
            process = inline_editor.process if inline_editor else None

        if process is None:
            await utils.answer(message, self.strings["no_cmd"])
            return

        try:
            signal_type = (
                signal.SIGKILL
                if "-f" in utils.get_args_raw(message)
                else signal.SIGTERM
            )
            os.killpg(process.pid, signal_type)
        except Exception:
            logger.exception("Killing process failed")
            await utils.answer(message, self.strings["kill_fail"])
        else:
            await utils.answer(message, self.strings["killed"])
