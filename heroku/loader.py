"""Registers modules"""

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
import builtins
import contextlib
import contextvars
import importlib
import importlib.machinery
import importlib.util
import inspect
import logging
import os
import re
import sys
import typing
from functools import partial, wraps
from pathlib import Path
from types import FunctionType
from uuid import uuid4

from herokutl.tl.tlobject import TLObject

from . import main, security, utils, validators
from ._internal import resolve_client_id, set_client_id, tag_client_id
from .database import Database
from .inline.core import BotUpdateType, InlineManager
from .translations import Strings, Translator
from .types import (
    Command,
    ConfigCategory,
    ConfigValue,
    CoreOverwriteError,
    CoreUnloadError,
    InlineDownError,
    InlineMessage,
    JSONSerializable,
    Library,
    LibraryConfig,
    LoadError,
    Module,
    ModuleConfig,
    SelfSuspend,
    SelfUnload,
    StopLoop,
    StringLoader,
    get_callback_handlers,
    get_commands,
    get_inline_handlers,
)

if typing.TYPE_CHECKING:
    from .tl_cache import CustomTelegramClient

__all__ = [
    "Modules",
    "InfiniteLoop",
    "Command",
    "CoreOverwriteError",
    "CoreUnloadError",
    "InlineDownError",
    "InlineMessage",
    "JSONSerializable",
    "Library",
    "LibraryConfig",
    "LoadError",
    "Module",
    "SelfSuspend",
    "SelfUnload",
    "StopLoop",
    "StringLoader",
    "get_commands",
    "get_inline_handlers",
    "get_callback_handlers",
    "validators",
    "Database",
    "InlineManager",
    "Strings",
    "Translator",
    "ConfigCategory",
    "ConfigValue",
    "ModuleConfig",
    "owner",
    "group_owner",
    "group_admin_add_admins",
    "group_admin_change_info",
    "group_admin_ban_users",
    "group_admin_delete_messages",
    "group_admin_pin_messages",
    "group_admin_invite_users",
    "group_admin",
    "group_member",
    "pm",
    "unrestricted",
    "inline_everyone",
    "loop",
    "need_update",
]

logger = logging.getLogger(__name__)

owner = security.owner

# deprecated
sudo = security.sudo
support = security.support
# /deprecated

group_owner = security.group_owner
group_admin_add_admins = security.group_admin_add_admins
group_admin_change_info = security.group_admin_change_info
group_admin_ban_users = security.group_admin_ban_users
group_admin_delete_messages = security.group_admin_delete_messages
group_admin_pin_messages = security.group_admin_pin_messages
group_admin_invite_users = security.group_admin_invite_users
group_admin = security.group_admin
group_member = security.group_member
pm = security.pm
unrestricted = security.unrestricted
inline_everyone = security.inline_everyone


async def stop_placeholder() -> bool:
    return True


class Placeholder:
    """Placeholder"""


VALID_PIP_PACKAGES = re.compile(
    r"^\s*# ?requires:(?: ?)((?:{url} )*(?:{url}))\s*$".format(
        url=r"[-[\]_.~:/?#@!$&'()*+,;%<=>a-zA-Z0-9]+"
    ),
    re.MULTILINE,
)

VALID_APT_PACKAGES = re.compile(
    r"^\s*# ?packages:(?: ?)((?:{url} )*(?:{url}))\s*$".format(
        url=r"[-[\]_.~:/?#@!$&'()*+,;%<=>a-zA-Z0-9]+"
    ),
    re.MULTILINE,
)

IMPORT_PIP_ALIASES = {
    "sklearn": "scikit-learn",
    "pil": "Pillow",
    "herokutl": "Heroku-TL-New",
    "markdown_it": "markdown-it-py",
}

USER_INSTALL = "PIP_TARGET" not in os.environ and "VIRTUAL_ENV" not in os.environ

native_import = builtins.__import__
_IMPORT_DEPTH = contextvars.ContextVar("_IMPORT_DEPTH", default=0)
_MAX_IMPORT_DEPTH = 80


def patched_import(name: str, *args, **kwargs):
    depth = _IMPORT_DEPTH.get()
    if depth > _MAX_IMPORT_DEPTH:
        return native_import(name, *args, **kwargs)
    token = _IMPORT_DEPTH.set(depth + 1)
    try:
        match name:
            case s if s.startswith("telethon"):
                return native_import("herokutl" + name[8:], *args, **kwargs)
            case s if s.startswith("hikkatl"):
                return native_import("herokutl" + name[7:], *args, **kwargs)
            case s if s.startswith("hikkalls"):
                return native_import(name, *args, **kwargs)
            case s if s.startswith("hikka"):
                return native_import("heroku" + name[5:], *args, **kwargs)

        return native_import(name, *args, **kwargs)
    finally:
        _IMPORT_DEPTH.reset(token)


builtins.__import__ = patched_import


class InfiniteLoop:
    _task = None
    status = False
    module_instance = None  # Will be passed later

    def __init__(
        self,
        func: FunctionType,
        interval: int,
        autostart: bool,
        wait_before: bool,
        stop_clause: str | None,
    ):
        self.func = func
        self.interval = interval
        self._wait_before = wait_before
        self._stop_clause = stop_clause
        self.autostart = autostart
        self._wait_for_stop = asyncio.Event()

    def _stop(self, task):
        if self._task is task:
            self._task = None
            self.status = False
            self._wait_for_stop.set()
        if not task.cancelled():
            task.exception()

    @tag_client_id("module_instance.allmodules.client.tg_id")
    def stop(self, *args, **kwargs):
        self.status = False
        task = self._task
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            return asyncio.ensure_future(self._wait_for_stop.wait())
        return asyncio.ensure_future(stop_placeholder())

    @tag_client_id("module_instance.allmodules.client.tg_id")
    def start(self, *args, **kwargs):
        if getattr(self.module_instance, "_unloading", False):
            return
        if self._task is None:
            self._wait_for_stop.clear()
            self._task = asyncio.ensure_future(self.actual_loop(*args, **kwargs))
            self._task.add_done_callback(self._stop)

    async def actual_loop(self, *args, **kwargs):
        # Wait for loader to set attribute
        while not self.module_instance:
            await asyncio.sleep(0.01)

        set_client_id(
            resolve_client_id(self, "module_instance.allmodules.client.tg_id")
        )

        if isinstance(self._stop_clause, str) and self._stop_clause:
            self.module_instance.set(self._stop_clause, True)

        self.status = True

        while self.status:
            if self._wait_before:
                await asyncio.sleep(self.interval)

            if (
                isinstance(self._stop_clause, str)
                and self._stop_clause
                and not self.module_instance.get(self._stop_clause, False)
            ):
                break

            try:
                await self.func(self.module_instance, *args, **kwargs)
            except StopLoop:
                break
            except Exception:
                logger.exception("Error running loop!")

            if not self.status:
                break
            if not self._wait_before:
                await asyncio.sleep(self.interval)

    def __del__(self):
        if self._task and not self._task.done():
            with contextlib.suppress(RuntimeError):
                self._task.cancel()


def loop(
    interval: int = 5,
    autostart: bool | None = False,
    wait_before: bool | None = False,
    stop_clause: str | None = None,
) -> FunctionType:
    """
    Create new infinite loop from class method
    :param interval: Loop iterations delay
    :param autostart: Start loop once module is loaded
    :param wait_before: Insert delay before actual iteration, rather than after
    :param stop_clause: Database key, based on which the loop will run.
                       This key will be set to `True` once loop is started,
                       and will stop after key resets to `False`
    :attr status: Boolean, describing whether the loop is running
    """

    def wrapped(func):
        return InfiniteLoop(func, interval, autostart, wait_before, stop_clause)

    return wrapped


MODULES_NAME = "modules"
ru_keys = 'ёйцукенгшщзхъфывапролджэячсмитьбю.Ё"№;%:?ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭ/ЯЧСМИТЬБЮ,'
en_keys = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}ASDFGHJKL:\"|ZXCVBNM<>?"

BASE_DIR = (
    "/data"
    if "DOCKER" in os.environ
    else os.path.normpath(os.path.join(utils.get_base_dir(), ".."))
)

LOADED_MODULES_DIR = os.path.join(BASE_DIR, "loaded_modules")
MODULES_LANGPACKS_DIR = os.path.join(LOADED_MODULES_DIR, "langpacks")
LOADED_MODULES_PATH = Path(LOADED_MODULES_DIR)
MODULES_LANGPACKS_PATH = Path(MODULES_LANGPACKS_DIR)
LOADED_MODULES_PATH.mkdir(parents=True, exist_ok=True)
MODULES_LANGPACKS_PATH.mkdir(parents=True, exist_ok=True)


def _iter_module_files(
    directory: str | Path,
    *,
    suffix: str = ".py",
    include: typing.Callable[[str], bool] | None = None,
) -> list[str]:
    with os.scandir(directory) as entries:
        return [
            entry.path
            for entry in entries
            if entry.is_file()
            and entry.name.endswith(suffix)
            and not entry.name.startswith("_")
            and (include(entry.name) if include else True)
        ]


def translatable_docstring(cls):
    """Decorator that makes triple-quote docstrings translatable"""

    @wraps(cls.config_complete)
    def config_complete(self, *args, **kwargs):
        def proccess_decorators(mark: str, obj: str):
            nonlocal self
            for attr in dir(func_):
                if (
                    attr.endswith("_doc")
                    and attr.count("_") == 1
                    and isinstance(getattr(func_, attr), str)
                ):
                    var = f"strings_{attr.split('_')[0]}"
                    if not hasattr(self, var):
                        setattr(self, var, {})

                    getattr(self, var).setdefault(f"{mark}{obj}", getattr(func_, attr))

        for command_, func_ in get_commands(cls).items():
            proccess_decorators("_cmd_doc_", command_)
            try:
                func_.__doc__ = self.strings[f"_cmd_doc_{command_}"]
            except AttributeError:
                func_.__func__.__doc__ = self.strings[f"_cmd_doc_{command_}"]

        for inline_handler_, func_ in get_inline_handlers(cls).items():
            proccess_decorators("_ihandle_doc_", inline_handler_)
            try:
                func_.__doc__ = self.strings[f"_ihandle_doc_{inline_handler_}"]
            except AttributeError:
                func_.__func__.__doc__ = self.strings[f"_ihandle_doc_{inline_handler_}"]

        self.__doc__ = self.strings["_cls_doc"]

        return (
            self.config_complete._old_(self, *args, **kwargs)
            if not kwargs.pop("reload_dynamic_translate", None)
            else True
        )

    config_complete._old_ = cls.config_complete
    cls.config_complete = config_complete

    for command_, func in get_commands(cls).items():
        cls.strings[f"_cmd_doc_{command_}"] = inspect.getdoc(func)

    for inline_handler_, func in get_inline_handlers(cls).items():
        cls.strings[f"_ihandle_doc_{inline_handler_}"] = inspect.getdoc(func)

    cls.strings["_cls_doc"] = inspect.getdoc(cls)

    return cls


tds = translatable_docstring  # Shorter name for modules to use


def ratelimit(func: Command) -> Command:
    """Decorator that causes ratelimiting for this command to be enforced more strictly"""
    func.ratelimit = True
    return func


def tag(*tags, **kwarg_tags):
    """
    Tag function (esp. watchers) with some tags
    Currently available tags:
        • `no_commands` - Ignore all userbot commands in watcher
        • `only_commands` - Capture only userbot commands in watcher
        • `out` - Capture only outgoing events
        • `in` - Capture only incoming events
        • `only_messages` - Capture only messages (not join events)
        • `editable` - Capture only messages, which can be edited (no forwards etc.)
        • `no_media` - Capture only messages without media and files
        • `only_media` - Capture only messages with media and files
        • `only_photos` - Capture only messages with photos
        • `only_videos` - Capture only messages with videos
        • `only_audios` - Capture only messages with audios
        • `only_docs` - Capture only messages with documents
        • `only_stickers` - Capture only messages with stickers
        • `only_inline` - Capture only messages with inline queries
        • `only_channels` - Capture only messages with channels
        • `only_groups` - Capture only messages with groups
        • `only_pm` - Capture only messages with private chats
        • `no_pm` - Exclude messages with private chats
        • `no_channels` - Exclude messages with channels
        • `no_groups` - Exclude messages with groups
        • `no_inline` - Exclude messages with inline queries
        • `no_stickers` - Exclude messages with stickers
        • `no_docs` - Exclude messages with documents
        • `no_audios` - Exclude messages with audios
        • `no_videos` - Exclude messages with videos
        • `no_photos` - Exclude messages with photos
        • `no_forwards` - Exclude forwarded messages
        • `no_reply` - Exclude messages with replies
        • `no_mention` - Exclude messages with mentions
        • `mention` - Capture only messages with mentions
        • `only_reply` - Capture only messages with replies
        • `only_forwards` - Capture only forwarded messages
        • `startswith` - Capture only messages that start with given text
        • `endswith` - Capture only messages that end with given text
        • `contains` - Capture only messages that contain given text
        • `regex` - Capture only messages that match given regex
        • `filter` - Capture only messages that pass given function
        • `from_id` - Capture only messages from given user
        • `chat_id` - Capture only messages from given chat
        • `thumb_url` - Works for inline command handlers. Will be shown in help
        • `alias` - Set single alias for a command
        • `aliases` - Set multiple aliases for a command

    Usage example:

    @loader.tag("no_commands", "out")
    @loader.tag("no_commands", out=True)
    @loader.tag(only_messages=True)
    @loader.tag("only_messages", "only_pm", regex=r"^[.] ?heroku$", from_id=00000000)

    💡 These tags can be used directly in `@loader.watcher`:
    @loader.watcher("no_commands", out=True)
    """

    def inner(func: Command) -> Command:
        for _tag in tags:
            setattr(func, _tag, True)

        for _tag, value in kwarg_tags.items():
            setattr(func, _tag, value)

        return func

    return inner


def _mark_method(mark: str, *args, **kwargs) -> typing.Callable[..., Command]:
    """
    Mark method as a method of a class
    """

    def decorator(func: Command) -> Command:
        setattr(func, mark, True)
        for arg in args:
            setattr(func, arg, True)

        for kwarg, value in kwargs.items():
            setattr(func, kwarg, value)

        return func

    return decorator


def command(*args, **kwargs):
    """
    Decorator that marks function as userbot command
    """
    return _mark_method("is_command", *args, **kwargs)


def debug_method(*args, **kwargs):
    """
    Decorator that marks function as IDM (Internal Debug Method)
    :param name: Name of the method
    """
    return _mark_method("is_debug_method", *args, **kwargs)


def inline_handler(*args, **kwargs):
    """
    Decorator that marks function as inline handler
    """
    return _mark_method("is_inline_handler", *args, **kwargs)


def watcher(*args, **kwargs):
    """
    Decorator that marks function as watcher
    """
    return _mark_method("is_watcher", *args, **kwargs)


def callback_handler(*args, **kwargs):
    """
    Decorator that marks function as callback handler
    """
    return _mark_method("is_callback_handler", *args, **kwargs)


def raw_handler(*updates: TLObject):
    """
    Decorator that marks function as raw telethon events handler
    Use it to prevent zombie-event-handlers, left by unloaded modules
    :param updates: Update(-s) to handle
    ⚠️ Do not try to simulate behavior of this decorator by yourself!
    ⚠️ This feature won't work, if you dynamically declare method with decorator!
    """

    def inner(func: Command) -> Command:
        func.is_raw_handler = True
        func.updates = updates
        func.id = uuid4().hex
        return func

    return inner


def need_update(*update_types: BotUpdateType):
    """
    Decorator that marks a method as a handler for Telegram Bot API update types
    The method will be registered in the inline bot's dispatcher when the module loads, and unregistered when the module unloads.
    """

    def inner(func: Command) -> Command:
        func.is_bot_update_handler = True
        func.bot_update_types = list(update_types)
        func.id = uuid4().hex
        return func

    return inner


class Modules:
    """Stores all registered modules"""

    def __init__(
        self,
        client: "CustomTelegramClient",  # type: ignore  # noqa: F821
        db: Database,
        allclients: list,
        translator: Translator,
    ):
        self._initial_registration = True
        self.commands = {}
        self._command_handlers = {}
        self.inline_handlers = {}
        self.callback_handlers = {}
        self.aliases = {}
        self.modules: list["Module" | None] = []  # skipcq: PTC-W0052
        self.libraries = []
        self.watchers = []
        self._log_handlers = []
        self._core_commands = []
        self.__approve = []
        self.allclients = allclients
        self.client = client
        self._db = db
        self.db = db
        self.translator = translator
        self.secure_boot = False
        self._ready_sent = False
        asyncio.ensure_future(self._junk_collector())
        self.inline = InlineManager(self.client, self._db, self)
        self.client.heroku_inline = self.inline

    async def _junk_collector(self):
        """
        Periodically reloads commands, inline handlers, callback handlers and watchers from loaded
        modules to prevent zombie handlers
        """
        while True:
            await asyncio.sleep(30)
            commands = {}
            command_handlers = {}
            inline_handlers = {}
            callback_handlers = {}
            watchers = []
            for module in self.modules:
                for name, handler in module.heroku_commands.items():
                    commands[name.lower()] = handler
                    command_handlers.setdefault(name.lower(), []).append(handler)
                inline_handlers.update(module.heroku_inline_handlers)
                callback_handlers.update(module.heroku_callback_handlers)
                watchers.extend(module.heroku_watchers.values())

            self.commands = commands
            self._command_handlers = command_handlers
            self.inline_handlers = inline_handlers
            self.callback_handlers = callback_handlers
            self.watchers = watchers

            logger.debug(
                (
                    "Reloaded %s commands,"
                    " %s inline handlers,"
                    " %s callback handlers and"
                    " %s watchers"
                ),
                len(self.commands),
                len(self.inline_handlers),
                len(self.callback_handlers),
                len(self.watchers),
            )

    async def register_all(
        self,
        mods: list[str] | None = None,
        no_external: bool = False,
    ) -> list[Module]:
        """Load all modules in the module directory"""
        external_mods = []

        if not mods:
            mods = _iter_module_files(os.path.join(utils.get_base_dir(), MODULES_NAME))

            self.secure_boot = self._db.get(__name__, "secure_boot", False)

            external_mods = (
                []
                if self.secure_boot
                else [
                    Path(mod).resolve()
                    for mod in _iter_module_files(
                        LOADED_MODULES_DIR,
                        include=lambda name: name.endswith(f"{self.client.tg_id}.py"),
                    )
                ]
            )

        loaded = []
        loaded += await self._register_modules(mods)

        if not no_external:
            loaded += await self._register_modules(external_mods, "<file>")

        return loaded

    @tag_client_id("client.tg_id")
    async def _register_modules(
        self,
        modules: list,
        origin: str = "<core>",
    ) -> list[Module]:
        loaded = []

        for mod in modules:
            try:
                mod_shortname = os.path.basename(mod).rsplit(".py", maxsplit=1)[0]
                module_name = f"{__package__}.{MODULES_NAME}.{mod_shortname}"
                user_friendly_origin = (
                    "<core {}>" if origin == "<core>" else "<file {}>"
                ).format(module_name)

                logger.debug("Loading %s from filesystem", module_name)

                spec = importlib.machinery.ModuleSpec(
                    module_name,
                    StringLoader(
                        Path(mod).read_text(encoding="utf-8"), user_friendly_origin
                    ),
                    origin=user_friendly_origin,
                )

                loaded += [await self.register_module(spec, module_name, origin)]

                logger.debug("Successfully loaded %s from filesystem", module_name)
            except Exception as e:
                logger.exception("Failed to load module %s due to %s:", mod, e)

        return loaded

    @tag_client_id("client.tg_id")
    async def register_module(
        self,
        spec: importlib.machinery.ModuleSpec,
        module_name: str,
        origin: str = "<core>",
        save_fs: bool = False,
    ) -> Module:
        """Register single module from importlib spec"""
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        source_data = (
            spec.loader.data.decode()
            if hasattr(spec.loader, "data") and spec.loader.data
            else None
        )

        async def _exec_module():
            attempted = False
            while True:
                try:
                    spec.loader.exec_module(module)
                    break
                except ImportError as e:
                    if not spec.loader.data or attempted:
                        raise

                    data = spec.loader.data
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="ignore")

                    match = VALID_PIP_PACKAGES.search(data)
                    if not match:
                        raise

                    requirements = list(
                        filter(
                            lambda x: not x.startswith(("-", "_", ".")),
                            map(
                                str.strip,
                                match.group(1).split(),
                            ),
                        )
                    )

                    exc_name = (getattr(e, "name", None) or "").lower()

                    requirements.extend(
                        [IMPORT_PIP_ALIASES.get(exc_name, exc_name or e.name or "")]
                    )

                    result = await self.lookup("LoaderMod").install_requirements(
                        requirements
                    )

                    importlib.invalidate_caches()

                    if not result:
                        raise

                    attempted = True

        await _exec_module()

        ret = None

        ret = next(
            (
                value()
                for value in vars(module).values()
                if inspect.isclass(value) and issubclass(value, Module)
            ),
            None,
        )

        if hasattr(module, "__version__"):
            ret.__version__ = module.__version__

        if ret is None:
            ret = module.register(module_name)
            if not isinstance(ret, Module):
                raise TypeError(f"Instance is not a Module, it is {type(ret)}")

        ret.__origin__ = origin

        ret.__source__ = (
            source_data if source_data else inspect.getsource(ret.__class__)
        )

        if not hasattr(ret, "name"):
            ret.name = ret.strings["name"]

        await self.complete_registration(ret)

        cls_name = ret.__class__.__name__

        if save_fs:
            path = os.path.join(
                LOADED_MODULES_DIR,
                f"{cls_name}_{self.client.tg_id}.py",
            )

            if origin == "<string>":
                Path(path).write_text(spec.loader.data.decode(), encoding="utf-8")

                logger.debug("Saved class %s to path %s", cls_name, path)

        return ret

    def add_aliases(self, aliases: dict):
        """Saves aliases and applies them to <core>/<file> modules"""
        self.aliases.update(aliases)
        for alias, cmd in aliases.items():
            self.add_alias(alias, *cmd.split(maxsplit=1))

    def register_raw_handlers(self, instance: Module):
        """Register event handlers for a module"""
        for name, handler in utils.iter_attrs(instance):
            if getattr(handler, "is_raw_handler", False):
                self.client.dispatcher.raw_handlers.append(handler)
                logger.debug(
                    "Registered raw handler %s for %s. ID: %s",
                    name,
                    instance.__class__.__name__,
                    handler.id,
                )

    def register_bot_update_handlers(self, instance: Module):
        """Register bot update handlers for a module"""
        for name, handler in utils.iter_attrs(instance):
            if not getattr(handler, "is_bot_update_handler", False):
                continue

            for update_type in getattr(handler, "bot_update_types", []):
                self.inline.register_bot_update_handler(
                    f"{handler.id}_{update_type}",
                    update_type,
                    handler,
                )
                logger.debug(
                    "Registered bot update handler %s (%s) for module %s, update type %s",
                    name,
                    handler.id,
                    instance.__class__.__name__,
                    update_type,
                )

    def unregister_bot_update_handlers(self, instance: Module, purpose: str):
        """Unregister bot update handlers for a module"""
        for name, handler in utils.iter_attrs(instance):
            if not getattr(handler, "is_bot_update_handler", False):
                continue

            for update_type in getattr(handler, "bot_update_types", []):
                self.inline.unregister_bot_update_handler(f"{handler.id}_{update_type}")
                logger.debug(
                    "Unregistered bot update handler %s of module %s for %s",
                    name,
                    instance.__class__.__name__,
                    purpose,
                )

    @property
    def _remove_core_protection(self) -> bool:
        from . import main

        return self._db.get(main.__name__, "remove_core_protection", False)

    @tag_client_id("client.tg_id")
    def register_commands(self, instance: Module):
        """Register commands from instance"""
        if instance.__origin__.startswith("<core"):
            self._core_commands += list(
                map(lambda x: x.lower(), list(instance.heroku_commands))
            )

        for _command, cmd in instance.heroku_commands.items():
            # Restrict overwriting core modules' commands
            if (
                not self._remove_core_protection
                and _command.lower() in self._core_commands
                and not instance.__origin__.startswith("<core")
            ):
                with contextlib.suppress(Exception):
                    self.modules.remove(instance)

                raise CoreOverwriteError(command=_command)

            name = _command.lower()
            handlers = self._command_handlers.setdefault(name, [])
            if cmd not in handlers:
                handlers.append(cmd)
            self.commands[name] = cmd

        for alias, cmd in self.aliases.copy().items():
            _cmd = cmd.split(maxsplit=1)
            if _cmd[0] in instance.heroku_commands:
                self.add_alias(alias, *_cmd)

        self.register_inline_stuff(instance)

    def register_inline_stuff(self, instance: Module):
        for name, func in instance.heroku_inline_handlers.copy().items():
            if name.lower() in self.inline_handlers:
                if (
                    hasattr(func, "__self__")
                    and hasattr(self.inline_handlers[name], "__self__")
                    and (
                        func.__self__.__class__.__name__
                        != self.inline_handlers[name].__self__.__class__.__name__
                    )
                ):
                    logger.debug(
                        "Duplicate inline_handler %s of %s",
                        name,
                        instance.__class__.__name__,
                    )

                logger.debug(
                    "Replacing inline_handler %s for %s",
                    self.inline_handlers[name],
                    instance.__class__.__name__,
                )

            self.inline_handlers.update({name.lower(): func})

        for name, func in instance.heroku_callback_handlers.copy().items():
            if name.lower() in self.callback_handlers and (
                hasattr(func, "__self__")
                and hasattr(self.callback_handlers[name], "__self__")
                and func.__self__.__class__.__name__
                != self.callback_handlers[name].__self__.__class__.__name__
            ):
                logger.debug(
                    "Duplicate callback_handler %s of %s",
                    name,
                    instance.__class__.__name__,
                )

            self.callback_handlers.update({name.lower(): func})

    def unregister_inline_stuff(self, instance: Module, purpose: str):
        for name, func in instance.heroku_inline_handlers.copy().items():
            if name.lower() in self.inline_handlers and (
                hasattr(func, "__self__")
                and hasattr(self.inline_handlers[name], "__self__")
                and func.__self__.__class__.__name__
                == self.inline_handlers[name].__self__.__class__.__name__
            ):
                del self.inline_handlers[name.lower()]
                logger.debug(
                    "Unregistered inline_handler %s of %s for %s",
                    name,
                    instance.__class__.__name__,
                    purpose,
                )

        for name, func in instance.heroku_callback_handlers.copy().items():
            if name.lower() in self.callback_handlers and (
                hasattr(func, "__self__")
                and hasattr(self.callback_handlers[name], "__self__")
                and func.__self__.__class__.__name__
                == self.callback_handlers[name].__self__.__class__.__name__
            ):
                del self.callback_handlers[name.lower()]
                logger.debug(
                    "Unregistered callback_handler %s of %s for %s",
                    name,
                    instance.__class__.__name__,
                    purpose,
                )

        def owned(handler):
            while isinstance(handler, partial):
                handler = handler.func
            return getattr(handler, "__self__", None) is instance

        for key, entry in list(getattr(self.inline, "_custom_map", {}).items()):
            if owned(entry.get("handler")):
                del self.inline._custom_map[key]
        for unit in getattr(self.inline, "_units", {}).values():
            unit["buttons"] = [
                [
                    button
                    for button in row
                    if not owned(button.get("callback"))
                    and not owned(button.get("handler"))
                ]
                for row in unit.get("buttons", [])
            ]
            if owned(unit.get("on_unload")):
                unit.pop("on_unload")

    @tag_client_id("client.tg_id")
    def register_watchers(self, instance: Module):
        """Register watcher from instance"""
        for _watcher in self.watchers:
            if _watcher.__self__.__class__.__name__ == instance.__class__.__name__:
                logger.debug("Removing watcher %s for update", _watcher)
                self.watchers.remove(_watcher)

        for _watcher in instance.heroku_watchers.values():
            self.watchers += [_watcher]

    def lookup(
        self,
        modname: str,
    ) -> bool | Module | Library:
        return next(
            (lib for lib in self.libraries if lib.name.lower() == modname.lower()),
            False,
        ) or next(
            (
                mod
                for mod in self.modules
                if mod.__class__.__name__.lower() == modname.lower()
                or getattr(mod, "name", "").lower() == modname.lower()
            ),
            False,
        )

    @property
    def get_approved_channel(self):
        return self.__approve.pop(0) if self.__approve else None

    def get_prefix(self, ent_id: int = None) -> str:
        """Get command prefix"""
        from . import main

        return utils.user_prefixes(self._db, main.__name__, ent_id, self.client.tg_id)[
            0
        ]

    def get_prefixes(self) -> set[str]:
        """Get all command prefixes"""
        from . import main

        prefixes = utils.user_prefixes(self._db, main.__name__)
        for value in self._db.get(main.__name__, "command_prefixes", {}).values():
            prefixes.extend(utils.normalize_prefixes(value))
        return set(prefixes)

    @tag_client_id("client.tg_id")
    async def complete_registration(self, instance: Module):
        """Complete registration of instance"""
        instance.allmodules = self
        instance.internal_init()

        for module in self.modules:
            if module.__class__.__name__ == instance.__class__.__name__:
                if not self._remove_core_protection and module.__origin__.startswith(
                    "<core"
                ):
                    raise CoreOverwriteError(
                        module=(
                            module.__class__.__name__[:-3]
                            if module.__class__.__name__.endswith("Mod")
                            else module.__class__.__name__
                        )
                    )

                logger.debug("Removing module %s for update", module)
                await self._shutdown_module(module, "update")
                if module in self.modules:
                    self.modules.remove(module)

        self.modules += [instance]

    def find_alias(
        self,
        alias: str,
        include_legacy: bool = False,
    ) -> str | None:
        if not alias:
            return None

        for command_name, _command in self.commands.items():
            aliases = []
            if getattr(_command, "alias", None) and not (
                aliases := getattr(_command, "aliases", None)
            ):
                aliases = [_command.alias]

            if not aliases:
                continue

            if any(
                alias.lower() == _alias.lower()
                and alias.lower() not in self._core_commands
                for _alias in aliases
            ):
                return command_name

        if alias in self.aliases and include_legacy:
            return self.aliases[alias]

        return None

    def dispatch(self, _command: str):
        text, handlers = self.dispatch_candidates(_command)
        return text, handlers[-1] if handlers else None

    def dispatch_candidates(self, _command: str):
        for text in (
            _command,
            self.aliases.get(_command.lower()),
            self.find_alias(_command),
        ):
            if not text:
                continue
            name = text.split()[0].lower()
            if name not in self.commands:
                continue
            disabled = self._db.get(main.__name__, "disabled_modules", [])
            disabled_commands = self._db.get(main.__name__, "disabled_commands", {})
            handlers = self._command_handlers.get(name, [self.commands[name]])
            available = []
            for handler in handlers:
                module_name = handler.__self__.__class__.__name__
                if module_name in disabled or name in {
                    item.lower() for item in disabled_commands.get(module_name, [])
                }:
                    continue
                available.append(handler)
            return text, available
        return _command, []

    def send_config(self, skip_hook: bool = False):
        """Configure modules"""
        for mod in self.modules:
            self.send_config_one(mod, skip_hook)

    @tag_client_id("client.tg_id")
    def send_config_one(self, mod: Module, skip_hook: bool = False):
        """Send config to single instance"""
        if hasattr(mod, "config"):
            modcfg = self._db.get(
                mod.__class__.__name__,
                "__config__",
                {},
            )
            try:
                for conf in mod.config:
                    with contextlib.suppress(validators.ValidationError):
                        mod.config.set_no_raise(
                            conf,
                            (
                                modcfg[conf]
                                if conf in modcfg
                                else os.environ.get(f"{mod.__class__.__name__}.{conf}")
                                or mod.config.getdef(conf)
                            ),
                        )
            except AttributeError:
                logger.warning(
                    "Got invalid config instance. Expected `ModuleConfig`, got %s, %s",
                    type(mod.config),
                    mod.config,
                )

        if not hasattr(mod, "name"):
            mod.name = mod.strings["name"]

        if skip_hook:
            return

        if not hasattr(mod, "strings"):
            mod.strings = {}

        mod.strings = Strings(mod, self.translator)
        mod.translator = self.translator

        try:
            mod.config_complete()
        except Exception as e:
            logger.exception("Failed to send mod config complete signal due to %s", e)
            raise

    async def send_ready_one_wrapper(self, *args, **kwargs):
        """Wrapper for send_ready_one"""
        try:
            await self.send_ready_one(*args, **kwargs)
        except Exception as e:
            logger.exception("Failed to send mod init complete signal due to %s", e)

    async def send_ready(self):
        """Send all data to all modules"""
        await asyncio.gather(
            *[self.send_ready_one_wrapper(mod) for mod in self.modules]
        )
        self._ready_sent = True

    @tag_client_id("client.tg_id")
    async def send_inline_ready_one(self, mod: Module):
        try:
            await mod.inline_ready()
        except Exception:
            logger.exception("Failed to call `inline_ready` of %s", mod)

    async def send_inline_ready(self):
        if not (self._ready_sent and self.inline.init_complete):
            return

        await asyncio.gather(
            *[self.send_inline_ready_one(mod) for mod in self.modules.copy()]
        )

    @tag_client_id("client.tg_id")
    async def send_ready_one(
        self,
        mod: Module,
        no_self_unload: bool = False,
        from_dlmod: bool = False,
    ):
        if from_dlmod:
            try:
                if len(inspect.signature(mod.on_dlmod).parameters) == 2:
                    await mod.on_dlmod(self.client, self._db)
                else:
                    await mod.on_dlmod()
            except Exception:
                logger.info("Can't process `on_dlmod` hook", exc_info=True)

        try:
            if len(inspect.signature(mod.client_ready).parameters) == 2:
                await mod.client_ready(self.client, self._db)
            else:
                await mod.client_ready()
        except SelfUnload as e:
            if no_self_unload:
                raise e

            logger.debug("Unloading %s, because it raised SelfUnload", mod)
            await self._shutdown_module(mod, "failed initialization")
            if mod in self.modules:
                self.modules.remove(mod)
            return
        except SelfSuspend as e:
            if no_self_unload:
                raise e

            logger.debug("Suspending %s, because it raised SelfSuspend", mod)
            return
        except Exception as e:
            logger.exception(
                (
                    "Failed to send mod init complete signal for %s due to %s,"
                    " attempting unload"
                ),
                mod,
                e,
            )
            await self._shutdown_module(mod, "failed initialization")
            if mod in self.modules:
                self.modules.remove(mod)
            raise

        pack_url = None
        # Check for pack_url and load translations
        if hasattr(mod, "__source__"):
            pack_url = next(
                (
                    line.replace(" ", "").split("#packurl:", maxsplit=1)[1]
                    for line in mod.__source__.splitlines()
                    if line.replace(" ", "").startswith("#packurl:")
                ),
                None,
            )

            if pack_url and (
                transations := await self.translator.load_module_translations(
                    pack_url,
                    MODULES_LANGPACKS_PATH
                    / f"{self.client.tg_id}_{mod.__class__.__name__}.yml",
                    cache_only=not from_dlmod,
                )
            ):
                mod.strings.external_strings = transations

        for _, method in utils.iter_attrs(mod):
            if isinstance(method, InfiniteLoop):
                setattr(method, "module_instance", mod)

                if method.autostart:
                    method.start()

                logger.debug("Added module %s to method %s", mod, method)

        self.unregister_commands(mod, "update")
        self.unregister_raw_handlers(mod, "update")
        self.unregister_bot_update_handlers(mod, "update")

        self.register_commands(mod)
        self.register_watchers(mod)
        self.register_raw_handlers(mod)
        self.register_bot_update_handlers(mod)

        if pack_url and not from_dlmod:

            async def refresh_translations():
                translations = await self.translator.load_module_translations(
                    pack_url,
                    MODULES_LANGPACKS_PATH
                    / f"{self.client.tg_id}_{mod.__class__.__name__}.yml",
                )
                if translations:
                    mod.strings.external_strings = translations

            mod.create_task(refresh_translations())

        if self._ready_sent and self.inline.init_complete:
            await self.send_inline_ready_one(mod)

    def get_classname(self, name: str) -> str:
        return next(
            (
                module.__class__.__module__
                for module in reversed(self.modules)
                if name in (module.name, module.__class__.__module__)
            ),
            name,
        )

    @tag_client_id("client.tg_id")
    async def unload_module(self, classname: str) -> list[str]:
        """Remove module and all stuff from it"""
        worked = []

        for module in self.modules.copy():
            if classname.lower() in (
                module.name.lower(),
                module.__class__.__name__.lower(),
            ):
                if not self._remove_core_protection and module.__origin__.startswith(
                    "<core"
                ):
                    raise CoreUnloadError(module.__class__.__name__)

                worked += [module.__class__.__name__]

                name = module.__class__.__name__
                path = os.path.join(
                    LOADED_MODULES_DIR,
                    f"{name}_{self.client.tg_id}.py",
                )

                if os.path.isfile(path):
                    os.remove(path)
                    logger.debug("Removed %s file at path %s", name, path)

                logger.debug("Removing module %s for unload", module)
                self.modules.remove(module)

                await self._shutdown_module(module, "unload")

        logger.debug("Worked: %s", worked)
        return worked

    async def _shutdown_module(self, module: Module, purpose: str):
        existing = getattr(module, "_shutdown_task", None)
        if existing is None:
            module._unloading = True
            caller = asyncio.current_task()
            existing = asyncio.create_task(
                self._finish_shutdown(module, purpose, caller)
            )
            module._shutdown_task = existing
        await asyncio.shield(existing)

    async def _wait_module_tasks(self, tasks, module, phase):
        if not tasks:
            return
        done, pending = await asyncio.wait(tasks, timeout=5)
        for task in done:
            if not task.cancelled():
                error = task.exception()
                if error is not None:
                    logger.error(
                        "Module %s failed during %s",
                        module,
                        phase,
                        exc_info=(type(error), error, error.__traceback__),
                    )
        for task in pending:
            task.cancel()
            task.add_done_callback(self._consume_shutdown_result)
        if pending:
            logger.warning(
                "Module %s: %s timed out (%s tasks)", module, phase, len(pending)
            )

    @staticmethod
    def _consume_shutdown_result(task):
        if not task.cancelled():
            task.exception()

    async def _finish_shutdown(self, module: Module, purpose: str, caller):
        for unregister in (
            self.unregister_raw_handlers,
            self.unregister_bot_update_handlers,
            self.unregister_commands,
            self.unregister_watchers,
            self.unregister_inline_stuff,
        ):
            try:
                unregister(module, purpose)
            except Exception:
                logger.exception(
                    "Unable to unregister %s for %s", unregister.__name__, module
                )
        tasks = set(getattr(module, "_managed_tasks", ()))
        for _, method in utils.iter_attrs(module):
            if isinstance(method, InfiniteLoop):
                method.status = False
                if method._task is not None:
                    tasks.add(method._task)
        tasks.discard(caller)
        tasks.discard(asyncio.current_task())
        for task in tasks:
            if not task.done():
                task.cancel()
        await self._wait_module_tasks(tasks, module, "task cancellation")

        async def unload():
            await module.on_unload()

        await self._wait_module_tasks(
            {asyncio.create_task(unload())}, module, "on_unload"
        )

    def unregister_loops(self, instance: Module, purpose: str):
        for name, method in utils.iter_attrs(instance):
            if isinstance(method, InfiniteLoop):
                logger.debug(
                    "Stopping loop for %s in module %s, method %s",
                    purpose,
                    instance.__class__.__name__,
                    name,
                )
                method.stop()

    def unregister_commands(self, instance: Module, purpose: str):
        for name, handlers in list(self._command_handlers.items()):
            remaining = [
                handler
                for handler in handlers
                if handler.__self__.__class__.__name__ != instance.__class__.__name__
            ]
            if remaining:
                self._command_handlers[name] = remaining
                self.commands[name] = remaining[-1]
            else:
                del self._command_handlers[name]
                self.commands.pop(name, None)
                for alias, command in list(self.aliases.items()):
                    if purpose != "update" and command.split()[0].lower() == name:
                        del self.aliases[alias]

    def unregister_watchers(self, instance: Module, purpose: str):
        for _watcher in self.watchers.copy():
            if _watcher.__self__.__class__.__name__ == instance.__class__.__name__:
                logger.debug(
                    "Removing watcher %s of module %s for %s",
                    _watcher,
                    instance.__class__.__name__,
                    purpose,
                )
                self.watchers.remove(_watcher)

    def unregister_raw_handlers(self, instance: Module, purpose: str):
        """Unregister event handlers for a module"""
        for handler in self.client.dispatcher.raw_handlers.copy():
            if handler.__self__.__class__.__name__ == instance.__class__.__name__:
                self.client.dispatcher.raw_handlers.remove(handler)
                logger.debug(
                    "Unregistered raw handler of module %s for %s. ID: %s",
                    instance.__class__.__name__,
                    purpose,
                    handler.id,
                )

    def add_alias(self, alias: str, cmd: str, args: str = None) -> bool:
        """Make an alias"""
        if cmd not in self.commands:
            return False

        self.aliases[alias.lower().strip()] = f"{cmd} {args}" if args else cmd
        return True

    def remove_alias(self, alias: str) -> bool:
        """Remove an alias"""
        return bool(self.aliases.pop(alias.lower().strip(), None))

    async def log(self, *args, **kwargs):
        """Unnecessary placeholder for logging"""

    async def reload_translations(self) -> bool:
        if not await self.translator.init():
            return False

        for module in self.modules:
            try:
                module.config_complete(reload_dynamic_translate=True)
            except Exception as e:
                logger.debug(
                    "Can't complete dynamic translations reload of %s due to %s",
                    module,
                    e,
                )

        return True
