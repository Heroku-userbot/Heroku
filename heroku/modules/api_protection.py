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
import io
import json
import logging
import random
import re
import sys
import time

from herokutl.tl import functions
from herokutl.tl.tlobject import TLRequest
from herokutl.tl.types import Message
from herokutl.utils import is_list_like

from .. import loader, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

GROUPS = [
    "auth",
    "account",
    "users",
    "contacts",
    "messages",
    "updates",
    "photos",
    "upload",
    "help",
    "channels",
    "bots",
    "payments",
    "stickers",
    "phone",
    "langpack",
    "folders",
    "stats",
]


CONSTRUCTORS = {
    (entity_name[0].lower() + entity_name[1:]).rsplit("Request", 1)[0]: getattr(
        cur_entity, "CONSTRUCTOR_ID"
    )
    for group in GROUPS
    for entity_name in dir(getattr(functions, group))
    if hasattr(
        (cur_entity := getattr(getattr(functions, group), entity_name)), "__bases__"
    )
    and TLRequest in cur_entity.__bases__
    and hasattr(cur_entity, "CONSTRUCTOR_ID")
}


_MODULE_FRAME_RE = re.compile(r"heroku\.modules\.([^>]+)")
_MODULE_UID_RE = re.compile(r"%(.)")


def _module_name(uid: str) -> str:
    name = _MODULE_UID_RE.sub(lambda m: "." if m[1] == "d" else m[1], uid)
    return name.rsplit("/", 1)[-1].removesuffix(".py") if "/" in name else name


def _current_task_label() -> str:
    try:
        task = asyncio.current_task()
    except RuntimeError:
        return "<no loop>"

    if not task:
        return "<no task>"

    code = getattr(task.get_coro(), "cr_code", None)
    qualname = (
        getattr(code, "co_qualname", None) or getattr(code, "co_name", None) or "?"
    )

    return f"<task {task.get_name()}: {qualname}>"


def find_call_chain(*, limit: int = 4, skip: int = 1) -> str:
    try:
        frame = sys._getframe(skip + 1)
        chain = []

        while frame and len(chain) < limit:
            code = frame.f_code
            if match := _MODULE_FRAME_RE.search(code.co_filename):
                chain += [f"{_module_name(match[1])}:{frame.f_lineno}:{code.co_name}"]

            frame = frame.f_back

        return " -> ".join(reversed(chain)) if chain else _current_task_label()
    except Exception:
        logger.debug("Failed to resolve call chain", exc_info=True)
        return "<unknown>"


@loader.tds
class APIRatelimiterMod(loader.Module):
    """Helps userbot avoid spamming Telegram API"""

    strings = {"name": "APILimiter"}

    def __init__(self):
        self._ratelimiter: list[tuple] = []
        self._suspend_until = 0
        self._lock = False
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "time_sample",
                15,
                lambda: self.strings["_cfg_time_sample"],
                validator=loader.validators.Integer(minimum=1),
            ),
            loader.ConfigValue(
                "threshold",
                100,
                lambda: self.strings["_cfg_threshold"],
                validator=loader.validators.Integer(minimum=10),
            ),
            loader.ConfigValue(
                "local_floodwait",
                30,
                lambda: self.strings["_cfg_local_floodwait"],
                validator=loader.validators.Integer(minimum=10, maximum=3600),
            ),
            loader.ConfigValue(
                "forbidden_methods",
                ["joinChannel", "importChatInvite"],
                lambda: self.strings["_cfg_forbidden_methods"],
                validator=loader.validators.MultiChoice(
                    [
                        "sendReaction",
                        "joinChannel",
                        "importChatInvite",
                    ]
                ),
                on_change=self.on_forbidden_methods_update,
            ),
        )

    async def client_ready(self):
        asyncio.ensure_future(self._install_protection())

    async def on_forbidden_methods_update(self):
        self._client.forbid_constructors(
            list(
                map(
                    lambda x: CONSTRUCTORS[x],
                    self.config["forbidden_methods"],
                )
            )
        )

    async def _install_protection(self):
        await asyncio.sleep(30)  # Restart lock
        if getattr(self._client._call, "_heroku_overwritten", False):
            raise loader.SelfUnload("Already installed")

        old_call = self._client._call

        async def new_call(
            sender: "MTProtoSender",  # type: ignore  # noqa: F821
            request: TLRequest,
            ordered: bool = False,
            flood_sleep_threshold: int = None,
        ):
            req = (request,) if not is_list_like(request) else request
            for r in req:
                if (
                    time.perf_counter() > self._suspend_until
                    and not self.get(
                        "disable_protection",
                        True,
                    )
                    and (
                        r.__module__.rsplit(".", maxsplit=1)[1]
                        in {"messages", "account", "channels"}
                    )
                ):
                    await asyncio.sleep(random.randint(1, 5) / 100)
                    request_name = type(r).__name__
                    self._ratelimiter += [
                        (
                            request_name,
                            time.perf_counter(),
                            find_call_chain(),
                        )
                    ]

                    self._ratelimiter = list(
                        filter(
                            lambda x: time.perf_counter() - x[1]
                            < int(self.config["time_sample"]),
                            self._ratelimiter,
                        )
                    )

                    if (
                        len(self._ratelimiter) > int(self.config["threshold"])
                        and not self._lock
                    ):
                        self._lock = True
                        report_bytes = json.dumps(
                            self._ratelimiter,
                            indent=4,
                        ).encode()
                        report = io.BytesIO(report_bytes)
                        report.name = "local_fw_report.json"

                        await self.inline.bot.send_document(
                            self.tg_id,
                            report,
                            caption=self.inline.sanitise_text(
                                self.strings["warning"].format(
                                    self.config["local_floodwait"],
                                    prefix=utils.escape_html(self.get_prefix()),
                                )
                            ),
                        )

                        # It is intented to use time.sleep instead of asyncio.sleep
                        time.sleep(int(self.config["local_floodwait"]))
                        self._lock = False

            return await old_call(sender, request, ordered, flood_sleep_threshold)

        self._client._call = new_call
        self._client._old_call_rewritten = old_call
        self._client._call._heroku_overwritten = True
        logger.debug("Successfully installed ratelimiter")

    async def on_unload(self):
        if hasattr(self._client, "_old_call_rewritten"):
            self._client._call = self._client._old_call_rewritten
            delattr(self._client, "_old_call_rewritten")
            logger.debug("Successfully uninstalled ratelimiter")

    @loader.command()
    async def suspend_api_protect(self, message: Message):
        if not (args := utils.get_args_raw(message)) or not args.isdigit():
            await utils.answer(message, self.strings["args_invalid"])
            return

        self._suspend_until = time.perf_counter() + int(args)
        await utils.answer(message, self.strings["suspended_for"].format(args))

    @loader.command()
    async def api_fw_protection(self, message: Message):
        await self.inline.form(
            message=message,
            text=self.strings["u_sure"],
            reply_markup=[
                {"text": self.strings["btn_no"], "action": "close"},
                {"text": self.strings["btn_yes"], "callback": self._finish},
            ],
        )

    async def _finish(self, call: InlineCall):
        state = self.get("disable_protection", True)
        self.set("disable_protection", not state)
        await call.edit(self.strings["on" if state else "off"])
