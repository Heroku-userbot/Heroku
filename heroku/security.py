"""Checks the commands' security"""

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

import logging
import time
import typing
from collections.abc import Callable

from herokutl.hints import EntityLike
from herokutl.tl.functions.messages import GetFullChatRequest
from herokutl.tl.types import ChatParticipantAdmin, ChatParticipantCreator, Message
from herokutl.utils import get_display_name

from . import main, utils
from .database import Database
from .tl_cache import CustomTelegramClient
from .types import Command

logger = logging.getLogger(__name__)

OWNER = 1 << 0
SUDO = 1 << 1
SUPPORT = 1 << 2
GROUP_OWNER = 1 << 3
GROUP_ADMIN_ADD_ADMINS = 1 << 4
GROUP_ADMIN_CHANGE_INFO = 1 << 5
GROUP_ADMIN_BAN_USERS = 1 << 6
GROUP_ADMIN_DELETE_MESSAGES = 1 << 7
GROUP_ADMIN_PIN_MESSAGES = 1 << 8
GROUP_ADMIN_INVITE_USERS = 1 << 9
GROUP_ADMIN = 1 << 10
GROUP_MEMBER = 1 << 11
PM = 1 << 12
EVERYONE = 1 << 13

BITMAP = {
    "OWNER": OWNER,
    "GROUP_OWNER": GROUP_OWNER,
    "GROUP_ADMIN_ADD_ADMINS": GROUP_ADMIN_ADD_ADMINS,
    "GROUP_ADMIN_CHANGE_INFO": GROUP_ADMIN_CHANGE_INFO,
    "GROUP_ADMIN_BAN_USERS": GROUP_ADMIN_BAN_USERS,
    "GROUP_ADMIN_DELETE_MESSAGES": GROUP_ADMIN_DELETE_MESSAGES,
    "GROUP_ADMIN_PIN_MESSAGES": GROUP_ADMIN_PIN_MESSAGES,
    "GROUP_ADMIN_INVITE_USERS": GROUP_ADMIN_INVITE_USERS,
    "GROUP_ADMIN": GROUP_ADMIN,
    "GROUP_MEMBER": GROUP_MEMBER,
    "PM": PM,
    "EVERYONE": EVERYONE,
}

GROUP_ADMIN_ANY = (
    GROUP_ADMIN_ADD_ADMINS
    | GROUP_ADMIN_CHANGE_INFO
    | GROUP_ADMIN_BAN_USERS
    | GROUP_ADMIN_DELETE_MESSAGES
    | GROUP_ADMIN_PIN_MESSAGES
    | GROUP_ADMIN_INVITE_USERS
    | GROUP_ADMIN
)

DEFAULT_PERMISSIONS = OWNER
PUBLIC_PERMISSIONS = GROUP_OWNER | GROUP_ADMIN_ANY | GROUP_MEMBER | PM

ALL = (1 << 13) - 1


class SecurityGroup(typing.NamedTuple):
    """Represents a security group"""

    name: str
    users: list[int]
    permissions: list[dict]


def owner(func: Command) -> Command:
    return _sec(func, OWNER)


def _deprecated(name: str) -> Callable:
    def decorator(func: Command) -> Command:
        logger.debug("Using deprecated decorator `%s`, which will have no effect", name)
        return func

    return decorator


sudo = _deprecated("sudo")
support = _deprecated("support")


def group_owner(func: Command) -> Command:
    return _sec(func, GROUP_OWNER)


def group_admin_add_admins(func: Command) -> Command:
    return _sec(func, GROUP_ADMIN_ADD_ADMINS)


def group_admin_change_info(func: Command) -> Command:
    return _sec(func, GROUP_ADMIN_CHANGE_INFO)


def group_admin_ban_users(func: Command) -> Command:
    return _sec(func, GROUP_ADMIN_BAN_USERS)


def group_admin_delete_messages(func: Command) -> Command:
    return _sec(func, GROUP_ADMIN_DELETE_MESSAGES)


def group_admin_pin_messages(func: Command) -> Command:
    return _sec(func, GROUP_ADMIN_PIN_MESSAGES)


def group_admin_invite_users(func: Command) -> Command:
    return _sec(func, GROUP_ADMIN_INVITE_USERS)


def group_admin(func: Command) -> Command:
    return _sec(func, GROUP_ADMIN)


def group_member(func: Command) -> Command:
    return _sec(func, GROUP_MEMBER)


def pm(func: Command) -> Command:
    return _sec(func, PM)


def unrestricted(func: Command) -> Command:
    return _sec(func, ALL)


def inline_everyone(func: Command) -> Command:
    return _sec(func, EVERYONE)


def _sec(func: Command, flags: int) -> Command:
    prev = getattr(func, "security", 0)
    func.security = prev | OWNER | flags
    return func


class SecurityManager:
    """Manages command execution security policy"""

    def __init__(self, client: CustomTelegramClient, db: Database):
        self._client = client
        self._db = db
        self._cache: dict[int, dict] = {}
        self._last_warning: int = 0
        self._sgroups: dict[str, SecurityGroup] = {}
        self._rights_last_reload: float = 0.0
        self._rights_reload_interval: float = 1.0

        self._any_admin = self.any_admin = db.get(__name__, "any_admin", False)
        self._default = self.default = db.get(__name__, "default", DEFAULT_PERMISSIONS)
        self._tsec_chat = self.tsec_chat = db.pointer(__name__, "tsec_chat", [])
        self._tsec_user = self.tsec_user = db.pointer(__name__, "tsec_user", [])
        self._owner = self.owner = db.pointer(__name__, "owner", [])
        self._all_users = self.all_users = db.pointer(__name__, "all_users", [])

        self._reload_rights(force=True)

    def apply_sgroups(self, sgroups: dict[str, SecurityGroup]):
        """Apply security groups"""
        self._sgroups = sgroups

    def _reload_rights(self, *, force: bool = False):
        """
        Internal method to ensure that account owner is always in the owner list,
        to clear out outdated tsec rules and to remove prefixes of users, that is
        not in any security group
        """
        now = time.monotonic()
        if not force and now - self._rights_last_reload < self._rights_reload_interval:
            return

        self._rights_last_reload = now
        dirty = False

        if self._client.tg_id not in self._owner:
            self._owner.append(self._client.tg_id)
            dirty = True

        for info in self._tsec_user.copy():
            if info["expires"] and info["expires"] < time.time():
                self._tsec_user.remove(info)
                dirty = True

        for info in self._tsec_chat.copy():
            if info["expires"] and info["expires"] < time.time():
                self._tsec_chat.remove(info)
                dirty = True

        sgroup_users = []
        for g in self._sgroups.values():
            for u in g.users:
                sgroup_users.append(u)

        tsec_users = [rule["target"] for rule in self._tsec_user]
        ub_owners = self.owner.copy()

        all_users = set(sgroup_users + tsec_users + ub_owners)

        if set(self._all_users) != all_users:
            self._all_users.clear()
            self._all_users.extend(all_users)
            dirty = True

        prefixes = self._db.get(main.__name__, "command_prefixes", {})
        valid_prefixes = prefixes.copy()

        for id_ in prefixes.copy():
            try:
                allowed = int(id_) in all_users
            except (TypeError, ValueError):
                allowed = False

            if not allowed:
                del valid_prefixes[id_]

        if valid_prefixes != prefixes:
            prefixes.clear()
            prefixes.update(valid_prefixes)
            dirty = True

        if dirty:
            self._db.set(main.__name__, "command_prefixes", prefixes)

    def add_rule(
        self,
        target_type: str,
        target: EntityLike,
        rule: str,
        duration: int,
    ):
        """
        Adds a targeted security rule

        :param target_type: "user" or "chat"
        :param target: target entity
        :param rule: rule name
        :param duration: rule duration in seconds
        :return: None
        """
        match target_type:
            case "chat":
                target_list = self._tsec_chat
            case "user":
                target_list = self._tsec_user
            case _:
                raise ValueError(f"Invalid target_type: {target_type}")

        if all(
            not rule.startswith(rule_type)
            for rule_type in {"command", "module", "inline"}
        ):
            raise ValueError(f"Invalid rule: {rule}")

        if duration < 0:
            raise ValueError(f"Invalid duration: {duration}")

        target_list.append(
            {
                "target": target.id,
                "rule_type": rule.split("/")[0],
                "rule": rule.split("/", maxsplit=1)[1],
                "expires": int(time.time() + duration) if duration else 0,
                "entity_name": get_display_name(target),
                "entity_url": utils.get_entity_url(target),
            }
        )
        self._reload_rights(force=True)

    def remove_rules(self, target_type: str, target_id: int) -> bool:
        """
        Removes all targeted security rules for the given target

        :param target_type: "user" or "chat"
        :param target_id: target entity ID
        :return: True if any rules were removed
        """
        match target_type:
            case "user":
                target_list = self.tsec_user
            case "chat":
                target_list = self.tsec_chat
            case _:
                return False

        any_ = False
        for rule in target_list.copy():
            if rule["target"] == target_id:
                target_list.remove(rule)
                any_ = True

        if any_:
            self._reload_rights(force=True)

        return any_

    def remove_rule(self, target_type: str, target_id: int, rule_cont: str) -> bool:
        """
        Removes targeted security rules for the given target

        :param target_type: "user" or "chat"
        :param target_id: target entity ID
        :param rule_cont: rule name (module or command)
        :return: True if any rules were removed
        """
        match target_type:
            case "user":
                target_list = self.tsec_user
            case "chat":
                target_list = self.tsec_chat
            case _:
                return False

        any_ = False
        for rule in target_list.copy():
            if rule["target"] == target_id and rule["rule"] == rule_cont:
                target_list.remove(rule)
                any_ = True

        if any_:
            self._reload_rights(force=True)

        return any_

    def get_flags(self, func: Command | int) -> int:
        """
        Gets the security flags for the given function

        :param func: function or flags
        :return: security flags
        """

        if isinstance(func, int):
            config = func
        else:
            # Return masks there so user don't need to reboot
            # every time he changes permissions. It doesn't
            # decrease security at all, bc user anyway can
            # access this attribute
            config = self._db.get(__name__, "masks", {}).get(
                f"{func.__module__}.{func.__name__}",
                getattr(func, "security", self._default),
            )

        if config & ~ALL and not config & EVERYONE:
            logger.error("Security config contains unknown bits")
            return False

        return config & self._db.get(__name__, "bounding_mask", DEFAULT_PERMISSIONS)

    def _check_tsec_inline(self, user_id: int, command: str) -> bool:
        """
        Checks if user is permitted to execute certain inline command

        :param user_id: user ID
        :param command: command name
        :return: True if permitted, False otherwise
        """

        return command and any(
            (
                rule["target"] == user_id
                and rule["rule_type"] == "inline"
                and rule["rule"] == command
            )
            for rule in self._tsec_user
        )

    def check_tsec(self, user_id: int, command: str) -> bool:
        for info in self._sgroups.copy().values():
            if user_id in info.users:
                for permission in info.permissions:
                    if (
                        permission["rule_type"] == "command"
                        and permission["rule"] == command
                        or permission["rule_type"] == "module"
                        and permission["rule"] == command
                    ):
                        return True

        for info in self._tsec_user.copy():
            if info["target"] == user_id and (
                info["rule_type"] == "command"
                and info["rule"] == command
                or info["rule_type"] == "module"
                and command in self._client.loader.commands
                and info["rule"]
                == self._client.loader.commands[command].__qualname__.split(".")[0]
            ):
                return True

        return False

    async def check(
        self,
        message: Message | None,
        func: Command | int,
        user_id: int | None = None,
        inline_cmd: str | None = None,
        *,
        usernames: set[str] | None = None,
    ) -> bool:
        """
        Checks if message sender is permitted to execute certain function

        :param message: Message to check or None if you manually pass user_id
        :param func: function or flags
        :param user_id: user ID
        :param inline_cmd: Inline command name if it's inline query
        :return: True if permitted, False otherwise
        """

        self._reload_rights()

        if not (config := self.get_flags(func)):
            return False

        if not user_id:
            user_id = message.sender_id

        if not user_id:
            user_id = message.peer_id

        is_channel = False

        if (
            message
            and message.is_channel
            and not message.is_group
            and message.edit_date
        ):
            async for event in self._client.iter_admin_log(
                utils.get_chat_id(message),
                limit=10,
                edit=True,
            ):
                if event.action.prev_message.id == message.id:
                    user_id = event.user_id
                    is_channel = True

        if (
            user_id == self._client.tg_id
            or getattr(message, "out", False)
            and not is_channel
        ):
            return True

        logger.debug("Checking security match for %s", config)

        if config & SUDO or config & SUPPORT:
            if not self._last_warning or time.time() - self._last_warning > 60 * 60:
                import warnings

                warnings.warn(
                    (
                        "You are using module containing SUDO or SUPPORT security"
                        " groups, which are deprecated. It might behave strangely"
                    ),
                    DeprecationWarning,
                )
                self._last_warning = time.time()

        f_group_owner = config & GROUP_OWNER
        f_group_admin_add_admins = config & GROUP_ADMIN_ADD_ADMINS
        f_group_admin_change_info = config & GROUP_ADMIN_CHANGE_INFO
        f_group_admin_ban_users = config & GROUP_ADMIN_BAN_USERS
        f_group_admin_delete_messages = config & GROUP_ADMIN_DELETE_MESSAGES
        f_group_admin_pin_messages = config & GROUP_ADMIN_PIN_MESSAGES
        f_group_admin_invite_users = config & GROUP_ADMIN_INVITE_USERS
        f_group_admin = config & GROUP_ADMIN
        f_group_member = config & GROUP_MEMBER
        f_pm = config & PM

        f_group_admin_any = (
            f_group_admin_add_admins
            or f_group_admin_change_info
            or f_group_admin_ban_users
            or f_group_admin_delete_messages
            or f_group_admin_pin_messages
            or f_group_admin_invite_users
            or f_group_admin
        )

        if user_id in self._owner:
            return True

        if user_id in self._db.get(main.__name__, "blacklist_users", []):
            return False

        if message is None:  # In case of checking inline query security map
            return self._check_tsec_inline(user_id, inline_cmd) or bool(
                config & EVERYONE
            )

        try:
            chat = utils.get_chat_id(message)
        except Exception:
            chat = None

        try:
            cmd = message.raw_text[1:].split()[0].strip()
            if usernames:
                for username in usernames:
                    cmd = cmd.replace(f"@{username}", "")
        except Exception:
            cmd = None

        if callable(func):
            command = self._client.loader.find_alias(cmd, include_legacy=True) or cmd

            for info in self._sgroups.copy().values():
                if user_id in info.users:
                    for permission in info.permissions:
                        if (
                            permission["rule_type"] == "command"
                            and permission["rule"] == command
                        ):
                            logger.debug("sgroup match for %s", command)
                            return True

                        if (
                            permission["rule_type"] == "module"
                            and permission["rule"] == func.__self__.__class__.__name__
                        ):
                            logger.debug(
                                "sgroup match for %s", func.__self__.__class__.__name__
                            )
                            return True

            for info in self._tsec_user.copy():
                if info["target"] == user_id:
                    if info["rule_type"] == "command" and info["rule"] == command:
                        logger.debug("tsec match for user %s", command)
                        return True

                    if (
                        info["rule_type"] == "module"
                        and info["rule"] == func.__self__.__class__.__name__
                    ):
                        logger.debug(
                            "tsec match for user %s",
                            func.__self__.__class__.__name__,
                        )
                        return True

            if chat:
                for info in self._tsec_chat.copy():
                    if info["target"] == chat:
                        if info["rule_type"] == "command" and info["rule"] == command:
                            logger.debug("tsec match for %s", command)
                            return True

                        if (
                            info["rule_type"] == "module"
                            and info["rule"] == func.__self__.__class__.__name__
                        ):
                            logger.debug(
                                "tsec match for %s",
                                func.__self__.__class__.__name__,
                            )
                            return True

        if f_group_member and message.is_group or f_pm and message.is_private:
            return True

        if message.is_channel:
            if not message.is_group:
                chat_id = utils.get_chat_id(message)
                if (
                    chat_id in self._cache
                    and self._cache[chat_id]["exp"] >= time.time()
                ):
                    chat = self._cache[chat_id]["chat"]
                else:
                    chat = await message.get_chat()
                    self._cache[chat_id] = {"chat": chat, "exp": time.time() + 5 * 60}

                if (
                    not chat.creator
                    and not chat.admin_rights
                    or not chat.creator
                    and not chat.admin_rights.post_messages
                ):
                    return False

                if self._any_admin and f_group_admin_any or f_group_admin:
                    return True
            elif f_group_admin_any or f_group_owner:
                chat_id = utils.get_chat_id(message)
                cache_obj = f"{chat_id}/{user_id}"
                if (
                    cache_obj in self._cache
                    and self._cache[cache_obj]["exp"] >= time.time()
                ):
                    participant = self._cache[cache_obj]["user"]
                else:
                    participant = await message.client.get_permissions(
                        message.peer_id,
                        user_id,
                    )
                    self._cache[cache_obj] = {
                        "user": participant,
                        "exp": time.time() + 5 * 60,
                    }

                if (
                    participant.is_creator
                    or participant.is_admin
                    and (
                        self._any_admin
                        and f_group_admin_any
                        or f_group_admin
                        or f_group_admin_add_admins
                        and participant.add_admins
                        or f_group_admin_change_info
                        and participant.change_info
                        or f_group_admin_ban_users
                        and participant.ban_users
                        or f_group_admin_delete_messages
                        and participant.delete_messages
                        or f_group_admin_pin_messages
                        and participant.pin_messages
                        or f_group_admin_invite_users
                        and participant.invite_users
                    )
                ):
                    return True
            return False

        if message.is_group and (f_group_admin_any or f_group_owner):
            chat_id = utils.get_chat_id(message)
            cache_obj = f"{chat_id}/{user_id}"

            if (
                cache_obj in self._cache
                and self._cache[cache_obj]["exp"] >= time.time()
            ):
                participant = self._cache[cache_obj]["user"]
            else:
                full_chat = await message.client(GetFullChatRequest(message.chat_id))
                participants = full_chat.full_chat.participants.participants
                participant = next(
                    (
                        possible_participant
                        for possible_participant in participants
                        if possible_participant.user_id == message.sender_id
                    ),
                    None,
                )
                self._cache[cache_obj] = {
                    "user": participant,
                    "exp": time.time() + 5 * 60,
                }

            if not participant:
                return

            if (
                isinstance(participant, ChatParticipantCreator)
                or isinstance(participant, ChatParticipantAdmin)
                and f_group_admin_any
            ):
                return True

        return False

    _check = check  # Legacy
