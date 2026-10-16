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
import datetime
import time
import typing
from collections.abc import Callable

from herokutl.custom import Message
from herokutl.hints import EntityLike
from herokutl.tl.types import PeerUser, User
from herokutl.utils import get_display_name

from .. import loader, main, security, utils
from ..inline.types import InlineCall, InlineMessage
from ..security import (
    DEFAULT_PERMISSIONS,
    EVERYONE,
    GROUP_ADMIN,
    GROUP_ADMIN_ADD_ADMINS,
    GROUP_ADMIN_BAN_USERS,
    GROUP_ADMIN_CHANGE_INFO,
    GROUP_ADMIN_DELETE_MESSAGES,
    GROUP_ADMIN_INVITE_USERS,
    GROUP_ADMIN_PIN_MESSAGES,
    GROUP_MEMBER,
    GROUP_OWNER,
    PM,
    SecurityGroup,
)


@loader.tds
class HerokuSecurityMod(loader.Module):
    """Control security settings"""

    strings = {"name": "HerokuSecurity"}

    async def client_ready(self):
        self._sgroups: typing.Iterable[str, SecurityGroup] = self.pointer(
            "sgroups", {}, item_type=SecurityGroup
        )
        self._reload_sgroups()

    def _reload_sgroups(self):
        self._client.dispatcher.security.apply_sgroups(self._sgroups.todict())

    async def inline__switch_perm(
        self,
        call: InlineCall,
        command: str,
        group: str,
        level: bool,
        is_inline: bool,
    ):
        cmd = (
            self.allmodules.inline_handlers[command]
            if is_inline
            else self.allmodules.commands[command]
        )

        mask = self._db.get(security.__name__, "masks", {}).get(
            f"{cmd.__module__}.{cmd.__name__}",
            getattr(cmd, "security", security.DEFAULT_PERMISSIONS),
        )

        bit = security.BITMAP[group.upper()]

        if level:
            mask |= bit
        else:
            mask &= ~bit

        masks = self._db.get(security.__name__, "masks", {})
        masks[f"{cmd.__module__}.{cmd.__name__}"] = mask
        self._db.set(security.__name__, "masks", masks)

        if (
            not self._db.get(security.__name__, "bounding_mask", DEFAULT_PERMISSIONS)
            & bit
            and level
        ):
            await call.answer(
                (
                    "Security value set but not applied. Consider enabling this value"
                    f" in .{'inlinesec' if is_inline else 'security'}"
                ),
                show_alert=True,
            )
        else:
            await call.answer("Security value set!")

        await call.edit(
            self.strings["permissions"].format(
                utils.escape_html(
                    f"@{self.inline.bot_username} " if is_inline else self.get_prefix()
                ),
                command,
            ),
            reply_markup=self._build_markup(cmd, is_inline),
        )

    async def inline__switch_perm_bm(
        self,
        call: InlineCall,
        group: str,
        level: bool,
        is_inline: bool,
    ):
        mask = self._db.get(security.__name__, "bounding_mask", DEFAULT_PERMISSIONS)
        bit = security.BITMAP[group.upper()]

        if level:
            mask |= bit
        else:
            mask &= ~bit

        self._db.set(security.__name__, "bounding_mask", mask)

        await call.answer("Bounding mask value set!")
        await call.edit(
            self.strings["global"],
            reply_markup=self._build_markup_global(is_inline),
        )

    async def inline__switch_perm_inline_query(self, call: InlineCall):
        query = self._db.get(security.__name__, "allow_inline_query", False)
        self._db.set(security.__name__, "allow_inline_query", not query)

        await call.answer("Inline query permission set!")
        await call.edit(
            self.strings["querysec_info"],
            reply_markup={
                "text": "❌" if query else "✅",
                "callback": self.inline__switch_perm_inline_query,
            },
        )

    def _build_markup(
        self,
        command: Callable,
        is_inline: bool = False,
    ) -> list[list[dict]]:
        perms = self._get_current_perms(command, is_inline)
        return (
            utils.chunks(
                [
                    {
                        "text": f"{'✅' if level else '🚫'} {self.strings[group]}",
                        "callback": self.inline__switch_perm,
                        "args": (
                            command.__name__.rsplit("_inline_handler", maxsplit=1)[0],
                            group,
                            not level,
                            is_inline,
                        ),
                    }
                    for group, level in perms.items()
                ],
                2,
            )
            + [[{"text": self.strings["close_menu"], "action": "close"}]]
            if is_inline
            else utils.chunks(
                [
                    {
                        "text": f"{'✅' if level else '🚫'} {self.strings[group]}",
                        "callback": self.inline__switch_perm,
                        "args": (
                            command.__name__.rsplit("cmd", maxsplit=1)[0],
                            group,
                            not level,
                            is_inline,
                        ),
                    }
                    for group, level in perms.items()
                ],
                2,
            )
            + [
                [
                    {
                        "text": self.strings["close_menu"],
                        "action": "close",
                    }
                ]
            ]
        )

    def _build_markup_global(
        self,
        is_inline: bool = False,
    ) -> list[list[dict]]:
        return utils.chunks(
            [
                {
                    "text": f"{'✅' if level else '🚫'} {self.strings[group]}",
                    "callback": self.inline__switch_perm_bm,
                    "args": (group, not level, is_inline),
                }
                for group, level in self._get_current_bm(is_inline).items()
            ],
            2,
        ) + [[{"text": self.strings["close_menu"], "action": "close"}]]

    def _get_current_bm(self, is_inline: bool = False) -> dict:
        return self._perms_map(
            self._db.get(security.__name__, "bounding_mask", DEFAULT_PERMISSIONS),
            is_inline,
        )

    @staticmethod
    def _perms_map(perms: int, is_inline: bool) -> dict:
        return (
            {"everyone": bool(perms & EVERYONE)}
            if is_inline
            else {
                "group_owner": bool(perms & GROUP_OWNER),
                "group_admin_add_admins": bool(perms & GROUP_ADMIN_ADD_ADMINS),
                "group_admin_change_info": bool(perms & GROUP_ADMIN_CHANGE_INFO),
                "group_admin_ban_users": bool(perms & GROUP_ADMIN_BAN_USERS),
                "group_admin_delete_messages": bool(
                    perms & GROUP_ADMIN_DELETE_MESSAGES
                ),
                "group_admin_pin_messages": bool(perms & GROUP_ADMIN_PIN_MESSAGES),
                "group_admin_invite_users": bool(perms & GROUP_ADMIN_INVITE_USERS),
                "group_admin": bool(perms & GROUP_ADMIN),
                "group_member": bool(perms & GROUP_MEMBER),
                "pm": bool(perms & PM),
                "everyone": bool(perms & EVERYONE),
            }
        )

    def _get_current_perms(
        self,
        command: Callable,
        is_inline: bool = False,
    ) -> dict:
        return self._perms_map(
            self._db.get(security.__name__, "masks", {}).get(
                f"{command.__module__}.{command.__name__}",
                getattr(command, "security", self._client.dispatcher.security.default),
            ),
            is_inline,
        )

    @loader.command()
    async def newsgroup(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_args"])
            return

        if not all([i.isalnum() for i in args]):
            await utils.answer(message, self.strings["invalid_name"])
            return

        if args in self._sgroups:
            await utils.answer(
                message, self.strings["sgroup_already_exists"].format(args)
            )
            return

        self._sgroups[args] = SecurityGroup(args, [], [])
        self._reload_sgroups()

        await utils.answer(message, self.strings["created_sgroup"].format(args))

    @loader.command()
    async def sgroups(self, message: Message):
        await utils.answer(
            message,
            self.strings["sgroups_list"].format(
                "\n".join(
                    self.strings["sgroup_li"].format(
                        group.name, len(group.users), len(group.permissions)
                    )
                    for group in self._sgroups.values()
                )
            ),
        )

    @loader.command()
    async def sgroup(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_args"])
            return

        if not (group := self._sgroups.get(args)):
            await utils.answer(message, self.strings["sgroup_not_found"].format(args))
            return

        await utils.answer(
            message,
            self.strings["sgroup_info"].format(
                group.name,
                (
                    self.strings["users_list"].format(
                        "\n".join(
                            [
                                self.strings["li"].format(
                                    utils.get_entity_url(
                                        await self._client.get_entity(user, exp=0)
                                    ),
                                    utils.escape_html(
                                        get_display_name(
                                            await self._client.get_entity(user, exp=0)
                                        )
                                    ),
                                )
                                for user in group.users
                            ]
                        )
                    )
                    if group.users
                    else self.strings["no_users"]
                ),
                (
                    self.strings["permissions_list"].format(
                        "\n".join(
                            "<tg-emoji emoji-id=4974307891025543730>▫️</tg-emoji>"
                            " <b>{}</b> <code>{}</code> <b>{}</b>".format(
                                self.strings[rule["rule_type"]],
                                rule["rule"],
                                (
                                    (
                                        self.strings["until"]
                                        + " "
                                        + self._convert_time_abs(rule["expires"])
                                    )
                                    if rule["expires"]
                                    else self.strings["forever"]
                                ),
                            )
                            for rule in group.permissions
                        )
                    )
                    if group.permissions
                    else self.strings["no_permissions"]
                ),
            ),
        )

    @loader.command()
    async def delsgroup(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_args"])
            return

        if not self._sgroups.get(args):
            await utils.answer(message, self.strings["sgroup_not_found"].format(args))
            return

        del self._sgroups[args]
        self._reload_sgroups()

        await utils.answer(message, self.strings["deleted_sgroup"].format(args))

    @loader.command()
    async def sgroupadd(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_args"])
            return

        if len(args.split()) >= 2:
            group, user = args.split()

            if user.isdigit():
                user = int(user)

            try:
                user = await self._client.get_entity(user, exp=0)
            except ValueError:
                await utils.answer(message, self.strings["no_args"])
                return
        else:
            if not message.is_reply:
                await utils.answer(message, self.strings["no_args"])
                return

            group, user = args, await (await message.get_reply_message()).get_sender()

        if not (group := self._sgroups.get(group)):
            await utils.answer(message, self.strings["sgroup_not_found"].format(group))
            return

        if user.id in group.users:
            await utils.answer(
                message,
                self.strings["user_already_in_sgroup"].format(
                    utils.escape_html(get_display_name(user)),
                    group.name,
                ),
            )
            return

        group.users.append(user.id)
        self._sgroups[group.name] = group
        self._reload_sgroups()

        await utils.answer(
            message,
            self.strings["user_added_to_sgroup"].format(
                utils.escape_html(get_display_name(user)),
                group.name,
            ),
        )

    @loader.command()
    async def sgroupdel(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_args"])
            return

        if len(args.split()) >= 2:
            group, user = args.split()

            if user.isdigit():
                user = int(user)

            try:
                user = await self._client.get_entity(user, exp=0)
            except ValueError:
                await utils.answer(message, self.strings["no_args"])
                return
        else:
            if not message.is_reply:
                await utils.answer(message, self.strings["no_args"])
                return

            group, user = args, await (await message.get_reply_message()).get_sender()

        if not (group := self._sgroups.get(group)):
            await utils.answer(message, self.strings["sgroup_not_found"].format(group))
            return

        if user.id not in group.users:
            await utils.answer(
                message,
                self.strings["user_not_in_sgroup"].format(
                    utils.escape_html(get_display_name(user)),
                    group.name,
                ),
            )
            return

        group.users.remove(user.id)
        self._sgroups[group.name] = group
        self._reload_sgroups()

        await utils.answer(
            message,
            self.strings["user_removed_from_sgroup"].format(
                utils.escape_html(get_display_name(user)),
                group.name,
            ),
        )

    @loader.command()
    async def security(self, message: Message):
        if (
            args := utils.get_args_raw(message).lower().strip()
        ) and args not in self.allmodules.commands:
            await utils.answer(message, self.strings["no_command"].format(args))
            return

        if not args:
            await self.inline.form(
                self.strings["global"],
                reply_markup=self._build_markup_global(),
                message=message,
                ttl=5 * 60,
            )
            return

        await self.inline.form(
            self.strings["permissions"].format(self.get_prefix(), args),
            reply_markup=self._build_markup(self.allmodules.commands[args]),
            message=message,
            ttl=5 * 60,
        )

    @loader.command()
    async def inlinesec(self, message: Message):
        if not (args := utils.get_args_raw(message).lower().strip()):
            await self.inline.form(
                self.strings["global"],
                reply_markup=self._build_markup_global(True),
                message=message,
                ttl=5 * 60,
            )
            return

        if args not in self.allmodules.inline_handlers:
            await utils.answer(message, self.strings["no_command"].format(args))
            return

        await self.inline.form(
            self.strings["permissions"].format(f"@{self.inline.bot_username} ", args),
            reply_markup=self._build_markup(
                self.allmodules.inline_handlers[args],
                True,
            ),
            message=message,
            ttl=5 * 60,
        )

    @loader.command()
    async def querysec(self, message: Message):
        query = self._db.get(security.__name__, "allow_inline_query", False)
        await self.inline.form(
            self.strings["querysec_info"],
            reply_markup={
                "text": "✅" if query else "❌",
                "callback": self.inline__switch_perm_inline_query,
            },
            message=message,
            ttl=5 * 60,
        )

    async def _resolve_user(self, message: Message, args_raw: str = None):
        args = (utils.get_args_raw(message) if args_raw is None else args_raw).replace(
            "@", ""
        )
        reply = None

        if not args and not (reply := await message.get_reply_message()):
            await utils.answer(message, self.strings["no_user"])
            return

        user = None

        if args:
            with contextlib.suppress(Exception):
                if str(args).isdigit():
                    args = int(args)

                user = await self._client.get_entity(args, exp=0)

        if user is None:
            if reply is None:
                reply = await message.get_reply_message()

            if reply is not None:
                try:
                    user = await self._client.get_entity(reply.sender_id, exp=0)
                except ValueError:
                    user = await reply.get_sender()

        if user is None:
            await utils.answer(message, self.strings["no_user"])
            return

        if not isinstance(user, (User, PeerUser)):
            await utils.answer(message, self.strings["not_a_user"])
            return

        if user.id == self.tg_id:
            await utils.answer(message, self.strings["self"])
            return

        return user

    async def _add_to_group(
        self,
        message: Message | InlineCall,
        group: str,
        confirmed: bool = False,
        user: int = None,
        enable_nonick: bool = False,
        force: bool = False,
        prefix: str | list[str] = None,
    ):
        if user is None and not (user := await self._resolve_user(message)):
            return

        if isinstance(user, int):
            user = await self._client.get_entity(user, exp=0)

        if user.id in getattr(self._client.dispatcher.security, group):
            return await utils.answer(
                message,
                self.strings["owner_exists"].format(
                    user.id, utils.escape_html(get_display_name(user))
                ),
            )

        if not confirmed and not force:
            await self.inline.form(
                self.strings["warning"].format(
                    user.id,
                    utils.escape_html(get_display_name(user)),
                    group,
                ) + (
                    "\n\n" + self.strings["owner_prefix"].format(utils.escape_html(utils.format_prefixes(prefix)))
                    if prefix is not None else ""
                ),
                message=message,
                ttl=10 * 60,
                reply_markup=[
                    {
                        "text": self.strings["cancel"],
                        "action": "close",
                    },
                    {
                        "text": self.strings["confirm"],
                        "callback": self._add_to_group,
                        "args": (group, True, user.id, enable_nonick, False, prefix),
                    },
                ],
            )
            return

        if user.id not in getattr(self._client.dispatcher.security, group):
            getattr(self._client.dispatcher.security, group).append(user.id)
            self._client.dispatcher.security._reload_rights(force=True)

        prefix_text = ""
        if prefix is not None:
            prefixes = dict(self._db.get(main.__name__, "command_prefixes", {}))
            prefixes[str(user.id)] = prefix
            self._db.set(main.__name__, "command_prefixes", prefixes)
            prefix_text = "\n\n" + self.strings["owner_prefix"].format(
                utils.escape_html(utils.format_prefixes(prefix))
            )

        if enable_nonick:
            self._db.set(
                main.__name__,
                "nonickusers",
                list(set(self._db.get(main.__name__, "nonickusers", []) + [user.id])),
            )

            await utils.answer(
                message,
                self.strings[f"{group}_added"].format(
                    user.id,
                    utils.escape_html(get_display_name(user)),
                )
                + prefix_text
                + "\n\n"
                + self.strings["user_nn"].format(
                    user.id,
                    utils.escape_html(get_display_name(user)),
                ),
            )
            return

        await utils.answer(
            message,
            (
                self.strings[f"{group}_added"].format(
                    user.id,
                    utils.escape_html(get_display_name(user)),
                )
                + prefix_text
                + "\n\n"
                + self.strings["suggest_nonick"]
            ),
            reply_markup=[
                {
                    "text": self.strings["cancel"],
                    "action": "close",
                },
                {
                    "text": self.strings["enable_nonick_btn"],
                    "callback": self._enable_nonick,
                    "args": (user,),
                },
            ],
        )

    async def _enable_nonick(self, call: InlineCall, user: User):
        self._db.set(
            main.__name__,
            "nonickusers",
            list(set(self._db.get(main.__name__, "nonickusers", []) + [user.id])),
        )

        await call.edit(
            self.strings["user_nn"].format(
                user.id,
                utils.escape_html(get_display_name(user)),
            )
        )

        await call.unload()

    @loader.command()
    async def owneradd(self, message: Message):
        """[-f|--force] [-n|--nonick] [-p <prefix>]... <user or reply> — Add owner."""
        args = utils.get_args(message)
        if not isinstance(args, list):
            return await utils.answer(message, self.strings["owneradd_usage"])
        force = enable_nonick = False
        prefix = None
        targets = []
        options = {"-f", "--force", "-n", "--nonick", "-p", "--prefix"}
        tokens = iter(args)
        for arg in tokens:
            if arg in {"-f", "--force"}:
                force = True
            elif arg in {"-n", "--nonick"}:
                enable_nonick = True
            elif arg in {"-p", "--prefix"}:
                value = next(tokens, None)
                if not value or value in options:
                    return await utils.answer(message, self.strings["owneradd_usage"])
                prefix = utils.normalize_prefixes(utils.normalize_prefixes(prefix) + [value])
            else:
                targets.append(arg)
        if len(targets) > 1:
            return await utils.answer(message, self.strings["owneradd_usage"])
        if prefix is not None:
            settings = self.lookup("CoreMod")
            allow_long = settings and settings.config.get("allow_nonstandart_prefixes")
            if any(p == "s" or any(c.isspace() for c in p) or (
                len(p) != 1 and not allow_long
            ) for p in prefix):
                return await utils.answer(message, self.strings["owner_prefix_invalid"])
        user_args = " ".join(targets)
        user = await self._resolve_user(message, user_args)

        if not user:
            return

        await self._add_to_group(
            message,
            "owner",
            user=user.id,
            enable_nonick=enable_nonick,
            force=force,
            prefix=prefix[0] if prefix and len(prefix) == 1 else prefix,
        )

    @loader.command()
    async def ownerrm(self, message: Message):
        if not (user := await self._resolve_user(message)):
            return

        if user.id in self._client.dispatcher.security.owner:
            self._client.dispatcher.security.owner.remove(user.id)
            self._client.dispatcher.security._reload_rights(force=True)

        await utils.answer(
            message,
            self.strings["owner_removed"].format(
                user.id,
                utils.escape_html(get_display_name(user)),
            ),
        )

    @loader.command()
    async def ownerlist(self, message: Message):
        _resolved_users = []
        _and_prefixes = []
        for user in set(self._client.dispatcher.security.owner + [self.tg_id]):
            with contextlib.suppress(Exception):
                _resolved_users += [await self._client.get_entity(user, exp=0)]

        if not _resolved_users:
            await utils.answer(message, self.strings["no_owner"])
            return

        for user in _resolved_users:
            _and_prefixes.append(utils.format_prefixes(utils.user_prefixes(
                self._db, main.__name__, user.id, self.tg_id
            )))

        await utils.answer(
            message,
            self.strings["owner_list"].format(
                "\n".join(
                    [
                        self.strings["li"].format(
                            utils.get_entity_url(i), utils.escape_html(get_display_name(i))
                        )
                        + (f" (<code>{utils.escape_html(p)}</code>)" if p else "")
                        for i, p in zip(_resolved_users, _and_prefixes)
                    ]
                )
            ),
        )

    def _lookup(self, needle: str) -> str:
        # TODO: to not removing ALL prefixes from needle using message author's id
        command = needle
        for prefix in self.get_prefixes():
            command = command.lower().removeprefix(prefix)

        return (
            (
                []
                if needle.lower().startswith(tuple(self.get_prefixes()))
                else (
                    [f"module/{self.lookup(needle).__class__.__name__}"]
                    if self.lookup(needle)
                    else []
                )
            )
            + ([f"command/{command}"] if command in self.allmodules.commands else [])
            + (
                [f"inline/{needle.lower().removeprefix('@')}"]
                if needle.lower().removeprefix("@") in self.allmodules.inline_handlers
                else []
            )
        )

    @staticmethod
    def _extract_time(args: list) -> int:
        for suffix, quantifier in [
            ("d", 24 * 60 * 60),
            ("h", 60 * 60),
            ("m", 60),
            ("s", 1),
        ]:
            duration = next(
                (
                    int(arg.rsplit(suffix, maxsplit=1)[0])
                    for arg in args
                    if arg.endswith(suffix)
                    and arg.rsplit(suffix, maxsplit=1)[0].isdigit()
                ),
                None,
            )
            if duration is not None:
                return duration * quantifier

        return 0

    def _convert_time_abs(self, timestamp: int) -> str:
        return (
            self.strings["forever"]
            if not timestamp
            else datetime.datetime.fromtimestamp(timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

    def _convert_time(self, duration: int) -> str:
        return (
            self.strings["forever"]
            if not duration or duration < 0
            else (
                (
                    f"{duration // (24 * 60 * 60)} "
                    + self.strings[
                        f"day{'s' if duration // (24 * 60 * 60) > 1 else ''}"
                    ]
                )
                if duration >= 24 * 60 * 60
                else (
                    (
                        f"{duration // (60 * 60)} "
                        + self.strings[
                            f"hour{'s' if duration // (60 * 60) > 1 else ''}"
                        ]
                    )
                    if duration >= 60 * 60
                    else (
                        (
                            f"{duration // 60} "
                            + self.strings[f"minute{'s' if duration // 60 > 1 else ''}"]
                        )
                        if duration >= 60
                        else (
                            f"{duration} "
                            + self.strings[f"second{'s' if duration > 1 else ''}"]
                        )
                    )
                )
            )
        )

    async def _add_rule(
        self,
        call: InlineCall,
        target_type: str,
        target: EntityLike | str,
        rule: str,
        duration: int,
    ):
        if rule.startswith("inline") and target_type == "chat":
            await call.edit(self.strings["chat_inline"])
            return

        if target_type == "sgroup":
            group = self._sgroups[target]
            group.permissions.append(
                {
                    "target": target,
                    "rule_type": rule.split("/")[0],
                    "rule": rule.split("/", maxsplit=1)[1],
                    "expires": int(time.time() + duration) if duration else 0,
                    "entity_name": group.name,
                    "entity_url": "",
                }
            )
            self._reload_sgroups()
        else:
            self._client.dispatcher.security.add_rule(
                target_type,
                target,
                rule,
                duration,
            )

        await call.edit(
            self.strings["rule_added"].format(
                self.strings[target_type],
                utils.get_entity_url(target) if not isinstance(target, str) else "",
                utils.escape_html(
                    get_display_name(target) if not isinstance(target, str) else target
                ),
                self.strings[rule.split("/", maxsplit=1)[0]],
                (
                    (
                        f"@{self.inline.bot_username} "
                        if rule.split("/", maxsplit=1)[0] == "inline"
                        else ""
                    )
                    + rule.split("/", maxsplit=1)[1]
                ),
                (
                    (self.strings["for"] + " " + self._convert_time(duration))
                    if duration
                    else self.strings["forever"]
                ),
            )
        )

    async def _confirm(
        self,
        obj: Message | InlineMessage,
        target_type: str,
        target: EntityLike | str,
        rule: str,
        duration: int,
    ):
        await utils.answer(
            obj,
            self.strings["confirm_rule"].format(
                self.strings[target_type],
                utils.get_entity_url(target) if not isinstance(target, str) else "",
                utils.escape_html(
                    get_display_name(target) if not isinstance(target, str) else target
                ),
                self.strings[rule.split("/", maxsplit=1)[0]],
                (
                    (
                        f"@{self.inline.bot_username} "
                        if rule.split("/", maxsplit=1)[0] == "inline"
                        else ""
                    )
                    + rule.split("/", maxsplit=1)[1]
                ),
                (
                    (self.strings["for"] + " " + self._convert_time(duration))
                    if duration
                    else self.strings["forever"]
                ),
            ),
            reply_markup=[
                {
                    "text": self.strings["confirm_btn"],
                    "callback": self._add_rule,
                    "args": (target_type, target, rule, duration),
                },
                {"text": self.strings["cancel_btn"], "action": "close"},
            ],
        )

    async def _tsec_chat(self, message: Message, args: list):
        if len(args) == 1 and message.is_private:
            await utils.answer(message, self.strings["no_target"])
            return

        if len(args) >= 2:
            try:
                if not args[1].isdigit() and not args[1].startswith("@"):
                    raise ValueError

                target = await self._client.get_entity(
                    int(args[1]) if args[1].isdigit() else args[1],
                    exp=0,
                )
            except (ValueError, TypeError):
                if not message.is_private:
                    target = await self._client.get_entity(message.peer_id, exp=0)
                else:
                    await utils.answer(message, self.strings["no_target"])
                    return

        if not (
            possible_rules := utils.array_sum([self._lookup(arg) for arg in args[1:]])
        ):
            await utils.answer(message, self.strings["no_rule"])
            return

        duration = self._extract_time(args)

        if len(possible_rules) > 1:
            await self.inline.form(
                message=message,
                text=self.strings["multiple_rules"].format(
                    "\n".join(
                        "🛡 <b>{}</b> <code>{}</code>".format(
                            self.strings[rule.split("/")[0]].capitalize(),
                            rule.split("/", maxsplit=1)[1],
                        )
                        for rule in possible_rules
                    )
                ),
                reply_markup=utils.chunks(
                    [
                        {
                            "text": "🛡 {} {}".format(
                                self.strings[rule.split("/")[0]].capitalize(),
                                rule.split("/", maxsplit=1)[1],
                            ),
                            "callback": self._confirm,
                            "args": ("chat", target, rule, duration),
                        }
                        for rule in possible_rules
                    ],
                    3,
                ),
            )
            return

        await self._confirm(message, "chat", target, possible_rules[0], duration)

    async def _tsec_sgroup(self, message: Message, args: list):
        if len(args) <= 1:
            await utils.answer(message, self.strings["no_target"])
            return

        if (target := args[1]) not in self._sgroups:
            await utils.answer(message, self.strings["sgroup_not_found"].format(target))
            return

        if not (
            possible_rules := utils.array_sum([self._lookup(arg) for arg in args[1:]])
        ):
            await utils.answer(message, self.strings["no_rule"])
            return

        duration = self._extract_time(args)

        if len(possible_rules) > 1:
            await self.inline.form(
                message=message,
                text=self.strings["multiple_rules"].format(
                    "\n".join(
                        "🛡 <b>{}</b> <code>{}</code>".format(
                            self.strings[rule.split("/")[0]].capitalize(),
                            rule.split("/", maxsplit=1)[1],
                        )
                        for rule in possible_rules
                    )
                ),
                reply_markup=utils.chunks(
                    [
                        {
                            "text": "🛡 {} {}".format(
                                self.strings[rule.split("/")[0]].capitalize(),
                                rule.split("/", maxsplit=1)[1],
                            ),
                            "callback": self._confirm,
                            "args": ("sgroup", target, rule, duration),
                        }
                        for rule in possible_rules
                    ],
                    3,
                ),
            )
            return

        await self._confirm(message, "sgroup", target, possible_rules[0], duration)

    async def _tsec_user(self, message: Message, args: list):

        match args:
            case [_]:
                if not message.is_private and not message.is_reply:
                    await utils.answer(message, self.strings["no_target"])
                    return
                await utils.answer(message, self.strings["no_rule"])
                return
            case _ if len(args) >= 2:
                try:
                    if not args[1].isdigit() and not args[1].startswith("@"):
                        raise ValueError

                    target = await self._client.get_entity(
                        int(args[1]) if args[1].isdigit() else args[1],
                        exp=0,
                    )
                except (ValueError, TypeError):
                    if message.is_private:
                        target = await self._client.get_entity(message.peer_id, exp=0)
                    elif message.is_reply:
                        target = await self._client.get_entity(
                            (await message.get_reply_message()).sender_id,
                            exp=0,
                        )
                    else:
                        await utils.answer(message, self.strings["no_target"])
                        return

        if target.id in self._client.dispatcher.security.owner:
            await utils.answer(message, self.strings["owner_target"])
            return

        duration = self._extract_time(args)

        if not (
            possible_rules := utils.array_sum([self._lookup(arg) for arg in args[1:]])
        ):
            await utils.answer(message, self.strings["no_rule"])
            return

        if len(possible_rules) > 1:
            await self.inline.form(
                message=message,
                text=self.strings["multiple_rules"].format(
                    "\n".join(
                        "🛡 <b>{}</b> <code>{}</code>".format(
                            self.strings[rule.split("/")[0]].capitalize(),
                            rule.split("/", maxsplit=1)[1],
                        )
                        for rule in possible_rules
                    )
                ),
                reply_markup=utils.chunks(
                    [
                        {
                            "text": "🛡 {} {}".format(
                                self.strings[rule.split("/")[0]].capitalize(),
                                rule.split("/", maxsplit=1)[1],
                            ),
                            "callback": self._confirm,
                            "args": ("user", target, rule, duration),
                        }
                        for rule in possible_rules
                    ],
                    3,
                ),
            )
            return

        await self._confirm(message, "user", target, possible_rules[0], duration)

    @loader.command()
    async def tsecrm(self, message: Message):

        if not (args := utils.get_args(message)) or args[0] not in [
            "user",
            "chat",
            "sgroup",
        ]:
            await utils.answer(message, self.strings["no_target"])
            return

        if args[0] == "user":
            if not message.is_private and not message.is_reply and len(args) < 3:
                await utils.answer(message, self.strings["no_target"])
                return

            if message.is_private:
                target = await self._client.get_entity(message.peer_id, exp=0)
            elif message.is_reply:
                target = await self._client.get_entity(
                    (await message.get_reply_message()).sender_id,
                    exp=0,
                )
            elif len(args) == 3:
                _ent = int(args[1]) if args[1].isdigit() else args[1]
                try:
                    target = await self._client.get_entity(_ent, exp=0)
                except ValueError:
                    await utils.answer(message, self.strings["no_target"])
                    return

            if not self._client.dispatcher.security.remove_rule(
                "user",
                target.id,
                args[-1],
            ):
                await utils.answer(message, self.strings["no_rules"])
                return

            await utils.answer(
                message,
                self.strings["rule_removed"].format(
                    utils.get_entity_url(target),
                    utils.escape_html(get_display_name(target)),
                    utils.escape_html(args[-1]),
                ),
            )
            return

        if args[0] == "sgroup":
            if len(args) < 3 or args[1] not in self._sgroups:
                await utils.answer(message, self.strings["no_target"])
                return

            group = self._sgroups[args[1]]
            permissions = group.permissions
            _any = False
            for rule in permissions:
                if rule["rule"] == args[2]:
                    permissions.remove(rule)
                    _any = True

            if not _any:
                await utils.answer(message, self.strings["no_rules"])
                return

            self._reload_sgroups()

            await utils.answer(
                message,
                self.strings["rule_removed"].format(
                    "",
                    utils.escape_html(group.name),
                    utils.escape_html(args[2]),
                ),
            )
            return

        if message.is_private:
            await utils.answer(message, self.strings["no_target"])
            return

        target = await self._client.get_entity(message.peer_id, exp=0)

        if not self._client.dispatcher.security.remove_rule("chat", target.id, args[1]):
            await utils.answer(message, self.strings["no_rules"])
            return

        await utils.answer(
            message,
            self.strings["rule_removed"].format(
                utils.get_entity_url(target),
                utils.escape_html(get_display_name(target)),
                utils.escape_html(args[1]),
            ),
        )

    @loader.command()
    async def tsecclr(self, message: Message):

        if (
            not (args := utils.get_args(message))
            or not (args := args[0])
            or args not in {"user", "chat", "sgroup"}
        ):
            await utils.answer(message, self.strings["no_target"])
            return

        if args == "user":
            if not message.is_private and not message.is_reply and len(args) < 2:
                await utils.answer(message, self.strings["no_target"])
                return

            if message.is_private:
                target = await self._client.get_entity(message.peer_id, exp=0)
            elif message.is_reply:
                target = await self._client.get_entity(
                    (await message.get_reply_message()).sender_id,
                    exp=0,
                )
            elif len(args) == 2:
                _ent = int(args[1]) if args[1].isdigit() else args[1]
                try:
                    target = await self._client.get_entity(_ent, exp=0)
                except ValueError:
                    await utils.answer(message, self.strings["no_target"])
                    return

            if not self._client.dispatcher.security.remove_rules("user", target.id):
                await utils.answer(message, self.strings["no_rules"])
                return

            await utils.answer(
                message,
                self.strings["rules_removed"].format(
                    utils.get_entity_url(target),
                    utils.escape_html(get_display_name(target)),
                ),
            )
            return

        if args == "sgroup":
            group = utils.get_args(message)[1]
            if not (group := self._sgroups.get(group)):
                await utils.answer(message, self.strings["no_target"])
                return

            group.permissions.clear()
            self._sgroups[group.name] = group
            self._reload_sgroups()

            await utils.answer(
                message,
                self.strings["rules_removed"].format(
                    "",
                    utils.escape_html(group.name),
                ),
            )
            return

        if message.is_private:
            await utils.answer(message, self.strings["no_target"])
            return

        target = await self._client.get_entity(message.peer_id, exp=0)

        if not self._client.dispatcher.security.remove_rules("chat", target.id):
            await utils.answer(message, self.strings["no_rules"])
            return

        await utils.answer(
            message,
            self.strings["rules_removed"].format(
                utils.get_entity_url(target),
                utils.escape_html(get_display_name(target)),
            ),
        )

    @loader.command()
    async def tsec(self, message: Message):
        if not (args := utils.get_args(message)):

            await utils.answer(
                message,
                self.strings["rules"].format(
                    "\n".join(
                        [
                            "<tg-emoji emoji-id=6037355667365300960>👥</tg-emoji> <b><a"
                            " href='{}'>{}</a> {} {} {}</b> <code>{}</code>".format(
                                rule["entity_url"],
                                utils.escape_html(rule["entity_name"]),
                                self._convert_time(int(rule["expires"] - time.time())),
                                self.strings["for"],
                                self.strings[rule["rule_type"]],
                                rule["rule"],
                            )
                            for rule in self._client.dispatcher.security.tsec_chat
                        ]
                        + [
                            "<tg-emoji emoji-id=6037122016849432064>👤</tg-emoji> <b><a"
                            " href='{}'>{}</a> {} {} {}</b> <code>{}</code>".format(
                                rule["entity_url"],
                                utils.escape_html(rule["entity_name"]),
                                self._convert_time(int(rule["expires"] - time.time())),
                                self.strings["for"],
                                self.strings[rule["rule_type"]],
                                rule["rule"],
                            )
                            for rule in self._client.dispatcher.security.tsec_user
                        ]
                        + [
                            "\n".join(
                                [
                                    "<tg-emoji emoji-id=5870704313440932932>🔒</tg-emoji>"
                                    " <code>{}</code> <b>{} {} {}</b> <code>{}</code>".format(
                                        utils.escape_html(group.name),
                                        self._convert_time(
                                            int(rule["expires"] - time.time())
                                        ),
                                        self.strings["for"],
                                        self.strings[rule["rule_type"]],
                                        rule["rule"],
                                    )
                                    for rule in group.permissions
                                ]
                            )
                            for group in self._sgroups.values()
                        ]
                    )
                ),
            )
            return

        if args[0] not in {"user", "chat", "sgroup"}:
            await utils.answer(message, self.strings["what"])
            return

        await getattr(self, f"_tsec_{args[0]}")(message, args)
