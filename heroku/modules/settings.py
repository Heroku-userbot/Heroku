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
import getpass
import herokutl
from herokutl.tl.types import Message, User

from .. import loader, main, utils, version
from ..inline.types import InlineCall


@loader.tds
class CoreMod(loader.Module):
    """Control core userbot settings"""

    strings = {"name": "Settings"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "allow_nonstandart_prefixes",
                False,
                lambda: self.strings["_cfg_nonstandart_prefixes"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "alias_emoji",
                "<tg-emoji emoji-id=4974259868996207180>▪️</tg-emoji>",
                lambda: self.strings["_cfg_alias_emoji"],
            ),
            loader.ConfigValue(
                "rich_mode",
                False,
                lambda: self.strings["_cfg_rich_mode"],
                validator=loader.validators.Boolean(),
            ),
            loader.ConfigValue(
                "keep_message_state",
                True,
                lambda: self.strings["_cfg_keep_message_state"],
                validator=loader.validators.Boolean(),
            ),
        )

    async def client_ready(self):
        self._markup = lambda: utils.chunks(
            [
                {
                    "text": self.strings[platform],
                    "callback": self._inline__choose__installation,
                    "args": (platform,),
                }
                for platform in [
                    "vds",
                    "wsl",
                    "userland",
                    "hikkahost",
                    "universal",
                ]
            ],
            2,
        )

    async def blacklistcommon(self, message: Message):
        args = utils.get_args(message)

        if len(args) > 2:
            await utils.answer(message, self.strings["too_many_args"])
            return

        chatid = None
        module = None

        if args:
            try:
                chatid = int(args[0])
            except ValueError:
                module = args[0]

        if len(args) == 2:
            module = args[1]

        if chatid is None:
            chatid = utils.get_chat_id(message)

        module = self.allmodules.get_classname(module)
        return f"{str(chatid)}.{module}" if module else chatid

    @loader.command(
        ru_doc="Информация о Хероку",
        en_doc="Information of Heroku",
        ua_doc="Інформація про Хероку",
        de_doc="Informationen über Heroku",
    )
    async def herokucmd(self, message: Message):

        branch_text = ""
        if version.branch == "master":
            branch_text = ""
        elif version.branch == "beta" or self.tg_id in [
            1714120111,
            1226061708,
            5717135725,
        ]:
            branch_text = self.strings["happy_beta"].format(version.branch)
        else:
            branch_text = self.strings["unstable"].format(version.branch)

        if self.config["rich_mode"]:
            rich_message = self.strings["rich_heroku_message"].format(
                platform=utils.get_platform_emoji(),
                version=".".join(map(str, version.__version__)),
                build=utils.get_commit_url(),
                htl_version=herokutl.__version__,
                layer=herokutl.tl.alltlobjects.LAYER,
                current_user=getpass.getuser(),
                banner_url="https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/heroku_cmd.jpg",
            )
            if branch_text:
                rich_message += f"<footer>{branch_text.strip()}</footer>"
            await utils.answer(
                message,
                rich_message=rich_message,
                reply_to=getattr(message, "reply_to_msg_id", None),
            )
            return

        await utils.answer(
            message,
            self.strings["heroku"].format(
                (
                    utils.get_platform_emoji()
                    if self._client.heroku_me.premium
                    else "🪐 <b>Heroku userbot</b>"
                ),
                *version.__version__,
                utils.get_commit_url(),
                f"{herokutl.__version__} #{herokutl.tl.alltlobjects.LAYER}",
            )
            + (branch_text),
            file="https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/heroku_cmd.jpg",
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

    @loader.command()
    async def blacklist(self, message: Message):
        chatid = await self.blacklistcommon(message)
        chatid_str = str(chatid)

        if chatid_str.startswith("-100"):
            chatid = chatid_str[4:]

        self._db.set(
            main.__name__,
            "blacklist_chats",
            self._db.get(main.__name__, "blacklist_chats", []) + [chatid],
        )

        await utils.answer(message, self.strings["blacklisted"].format(chatid))

    @loader.command()
    async def unblacklist(self, message: Message):
        chatid = await self.blacklistcommon(message)
        chatid_str = str(chatid)

        if chatid_str.startswith("-100"):
            chatid = chatid_str[4:]

        self._db.set(
            main.__name__,
            "blacklist_chats",
            list(set(self._db.get(main.__name__, "blacklist_chats", [])) - {chatid}),
        )

        await utils.answer(message, self.strings["unblacklisted"].format(chatid))

    async def getuser(self, message: Message):
        try:
            return int(utils.get_args(message)[0])
        except (ValueError, IndexError):
            if reply := await message.get_reply_message():
                return reply.sender_id

            return message.to_id.user_id if message.is_private else False

    @loader.command()
    async def blacklistuser(self, message: Message):
        if not (user := await self.getuser(message)):
            await utils.answer(message, self.strings["who_to_blacklist"])
            return

        self._db.set(
            main.__name__,
            "blacklist_users",
            self._db.get(main.__name__, "blacklist_users", []) + [user],
        )

        await utils.answer(message, self.strings["user_blacklisted"].format(user))

    @loader.command()
    async def unblacklistuser(self, message: Message):
        if not (user := await self.getuser(message)):
            await utils.answer(message, self.strings["who_to_unblacklist"])
            return

        self._db.set(
            main.__name__,
            "blacklist_users",
            list(set(self._db.get(main.__name__, "blacklist_users", [])) - {user}),
        )

        await utils.answer(
            message,
            self.strings["user_unblacklisted"].format(user),
        )

    @loader.command()
    async def setprefix(self, message: Message):
        """<prefix ...> [@owner] or --user <ID> <prefix ...> — Set personal prefixes."""
        args = utils.get_args(message)
        if not isinstance(args, list):
            return await utils.answer(message, self.strings["what_prefix"])
        target = getattr(message, "sender_id", None) or self.tg_id
        if "--user" in args:
            index = args.index("--user")
            if index + 1 >= len(args):
                return await utils.answer(message, self.strings["what_prefix"])
            target = args[index + 1]
            del args[index:index + 2]
        elif len(args) > 1 and (
            (args[-1].startswith("@") and len(args[-1]) > 1)
            or (args[-1].isdigit() and len(args[-1]) >= 5)
        ):
            target = args.pop()
        if not args:
            return await utils.answer(message, self.strings["what_prefix"])
        if any(
            not p or p == "s" or any(c.isspace() for c in p)
            or (len(p) != 1 and not self.config.get("allow_nonstandart_prefixes"))
            for p in args
        ):
            return await utils.answer(message, self.strings["prefix_incorrect"])
        prefixes = utils.normalize_prefixes(args)
        target = int(target) if str(target).isdigit() else target
        try:
            entity = await self.client.get_entity(target)
        except Exception:
            return await utils.answer(message, self.strings["invalid_id_or_username"])
        if not isinstance(entity, User):
            return await utils.answer(message, self.strings["not_a_user"].format(target))
        oldprefixes = utils.user_prefixes(
            self._db, main.__name__, entity.id, self.tg_id
        )
        if entity.id != self.tg_id:
            security = self._client.dispatcher.security
            allowed = set(security.owner)
            allowed.update(u for g in security._sgroups.values() for u in g.users)
            allowed.update(rule["target"] for rule in security._tsec_user)
            if entity.id not in allowed:
                return await utils.answer(message, self.strings["id_not_found_scgroup"])
            personal = dict(self._db.get(main.__name__, "command_prefixes", {}))
            personal[str(entity.id)] = prefixes[0] if len(prefixes) == 1 else prefixes
            self._db.set(main.__name__, "command_prefixes", personal)
        else:
            self._db.set(main.__name__, "command_prefix", prefixes[0])
            self._db.set(main.__name__, "command_prefix_aliases", prefixes[1:])
        await utils.answer(
            message,
            self.strings[
                "prefix_set" if entity.id == self.tg_id else "entity_prefix_set"
            ].format(
                "<tg-emoji emoji-id=5197474765387864959>👍</tg-emoji>",
                entity_name=utils.escape_html(entity.first_name),
                entity_id=entity.id,
                newprefix=utils.escape_html(utils.format_prefixes(prefixes)),
                oldprefix=utils.escape_html(" ".join(oldprefixes)),
            ),
        )

    @loader.command()
    async def aliases(self, message: Message):
        await utils.answer(
            message,
            self.strings["aliases"]
            + "<blockquote expandable>"
            + "\n".join(
                [
                    (self.config["alias_emoji"] + f" <code>{i}</code> &lt;- {y}")
                    for i, y in self.allmodules.aliases.items()
                ]
            )
            + "</blockquote>",
        )

    @loader.command()
    async def addalias(self, message: Message):

        args_raw = utils.get_args_raw(message)
        if not args_raw:
            await utils.answer(message, self.strings["alias_args"])
            return

        import keyword

        def parse_alias_line(line: str) -> tuple[list[str], str] | None:
            line = line.strip()
            if not line:
                return None

            if "&&" in line:
                parts = line.split("&&", 1)
                alias_part, command_part = parts[0].strip(), parts[1].strip()
                aliases = [a.strip().lower() for a in alias_part.split(",") if a.strip()]
                return aliases, command_part
            elif "," in line:
                parts = [part.strip() for part in line.split(",")]
                if parts:
                    last = parts[-1].split(maxsplit=1)
                    if len(last) >= 2:
                        aliases = [part.lower() for part in parts[:-1] if part]
                        aliases.append(last[0].lower())
                        return aliases, last[1]
            else:
                args = line.split(maxsplit=1)
                if len(args) >= 2:
                    return [args[0].lower()], args[1]
            return None

        alias_lines = []
        lines = args_raw.splitlines()

        for line_idx, line in enumerate(lines):
            is_new_alias = False
            parsed_aliases = None
            parsed_cmd = None
            parsed_rest = None

            stripped_line = line.strip()
            if stripped_line:
                parsed = parse_alias_line(line)
                if parsed:
                    aliases, command = parsed
                    command_parts = command.split(maxsplit=1)
                    cmd = command_parts[0]
                    rest = command_parts[1] if len(command_parts) > 1 else None

                    first_word = stripped_line.split()[0] if stripped_line else ""
                    is_valid_candidate = (
                        not line.startswith(" ")
                        and not line.startswith("\t")
                        and not keyword.iskeyword(first_word)
                        and all(c.isalnum() or c in "_-" for c in first_word)
                    )

                    if is_valid_candidate and cmd in self.allmodules.commands:
                        is_new_alias = True
                        parsed_aliases = aliases
                        parsed_cmd = cmd
                        parsed_rest = rest

            if line_idx == 0:
                parsed = parse_alias_line(line)
                if not parsed:
                    await utils.answer(message, self.strings["alias_args"])
                    return
                aliases, command = parsed
                command_parts = command.split(maxsplit=1)
                cmd = command_parts[0]
                rest = command_parts[1] if len(command_parts) > 1 else None

                if cmd not in self.allmodules.commands:
                    await utils.answer(
                        message,
                        self.strings["no_command"].format(utils.escape_html(cmd)),
                    )
                    return

                alias_lines.append((aliases, cmd, rest))
            else:
                if is_new_alias:
                    alias_lines.append((parsed_aliases, parsed_cmd, parsed_rest))
                else:
                    if alias_lines:
                        aliases, cmd, rest = alias_lines[-1]
                        if rest is None:
                            new_rest = line
                        else:
                            new_rest = rest + "\n" + line
                        alias_lines[-1] = (aliases, cmd, new_rest)

        if not alias_lines:
            await utils.answer(message, self.strings["alias_args"])
            return

        added_lines = []
        skipped_lines = []
        planned_aliases = {}
        stored_aliases = {**self.get("aliases", {})}

        for aliases, cmd, rest in alias_lines:
            target = f"{cmd} {rest}" if rest else cmd
            added_aliases = []

            for alias in aliases:
                if alias in self.allmodules.aliases:
                    skipped_lines.append(
                        self.strings["alias_exists"].format(
                            alias=utils.escape_html(alias),
                            command=utils.escape_html(self.allmodules.aliases[alias]),
                        )
                    )
                    continue

                if alias in planned_aliases:
                    skipped_lines.append(
                        self.strings["alias_exists"].format(
                            alias=utils.escape_html(alias),
                            command=utils.escape_html(planned_aliases[alias]),
                        )
                    )
                    continue

                if not self.allmodules.add_alias(alias, cmd, rest):
                    await utils.answer(
                        message,
                        self.strings["no_command"].format(utils.escape_html(cmd)),
                    )
                    return

                stored_aliases[alias] = target
                planned_aliases[alias] = target
                added_aliases.append(alias)

            if added_aliases:
                added_lines.append((added_aliases, target))

        if added_lines:
            self.set("aliases", stored_aliases)

        if len(added_lines) == 1 and len(added_lines[0][0]) == 1 and not skipped_lines:
            await utils.answer(
                message,
                self.strings["alias_created"].format(
                    utils.escape_html(added_lines[0][0][0])
                ),
            )
            return

        added_count = sum(len(aliases) for aliases, _ in added_lines)
        response = []

        if added_lines:
            response.append(
                self.strings["aliases_created"].format(
                    count=added_count,
                    aliases="\n".join(
                        self.strings["aliases_created_line"].format(
                            aliases=utils.escape_html(", ".join(aliases)),
                            command=utils.escape_html(target),
                        )
                        for aliases, target in added_lines
                    ),
                )
            )

        response.extend(skipped_lines)

        await utils.answer(message, "\n\n".join(response))

    @loader.command()
    async def delalias(self, message: Message):
        args_raw = utils.get_args_raw(message)

        if not args_raw:
            await utils.answer(message, self.strings["delalias_args"])
            return

        if args_raw.strip() in {"-c", "--clear"}:
            self.allmodules.aliases.clear()
            self.set("aliases", {})
            await utils.answer(message, self.strings["aliases_cleared"])
            return

        aliases = []
        seen_aliases = set()
        for line in args_raw.splitlines():
            for alias in line.split(","):
                alias = alias.lower().strip()
                if alias and alias not in seen_aliases:
                    aliases.append(alias)
                    seen_aliases.add(alias)

        if not aliases:
            await utils.answer(message, self.strings["delalias_args"])
            return

        current = self.get("aliases", {})
        removed_aliases = []
        missed_aliases = []

        for alias in aliases:
            if not self.allmodules.remove_alias(alias):
                missed_aliases.append(alias)
                continue

            current.pop(alias, None)
            removed_aliases.append(alias)

        if removed_aliases:
            self.set("aliases", current)

        if len(removed_aliases) == 1 and not missed_aliases:
            await utils.answer(
                message,
                self.strings["alias_removed"].format(
                    utils.escape_html(removed_aliases[0])
                ),
            )
            return

        response = []
        if removed_aliases:
            response.append(
                self.strings["aliases_removed"].format(
                    count=len(removed_aliases),
                    aliases=utils.escape_html(", ".join(removed_aliases)),
                )
            )

        response.extend(
            self.strings["no_alias"].format(utils.escape_html(alias))
            for alias in missed_aliases
        )

        await utils.answer(
            message,
            "\n\n".join(response),
        )

    @loader.command()
    async def cleardb(self, message: Message):
        await self.inline.form(
            self.strings["confirm_cleardb"],
            message,
            reply_markup=[
                {
                    "text": self.strings["cleardb_confirm"],
                    "callback": self._inline__cleardb,
                },
                {
                    "text": self.strings["cancel"],
                    "action": "close",
                },
            ],
        )

    async def _inline__cleardb(self, call: InlineCall):
        self._db.clear()
        self._db.save()
        await utils.answer(call, self.strings["db_cleared"])

    @loader.command()
    async def togglecmdcmd(self, message: Message):
        """Toggle disable specific command of a module: togglecmd <module> <command> or togglecmd <command>"""
        args = utils.get_args(message)
        if not args:
            await utils.answer(message, self.strings["wrong_usage_tcc"])

        if args and len(args) >= 2:
            mod_arg, cmd = args[0], args[1]
            mod_inst = self.allmodules.lookup(mod_arg)
            if not mod_inst:
                await utils.answer(message, self.strings["mod404"].format(mod_arg))

        module_key = mod_inst.__class__.__name__

        disabled_commands = self._db.get(main.__name__, "disabled_commands", {})
        current = [x for x in disabled_commands.get(module_key, [])]

        if cmd.lower() not in [c.lower() for c in mod_inst.heroku_commands.keys()]:
            await utils.answer(message, self.strings["cmd404"])

        if any(c.lower() == cmd.lower() for c in current):
            current = [c for c in current if c.lower() != cmd.lower()]
            if current:
                disabled_commands[module_key] = current
            else:
                disabled_commands.pop(module_key, None)

            self._db.set(main.__name__, "disabled_commands", disabled_commands)
            try:
                self.allmodules.register_commands(mod_inst)
            except Exception:
                pass

            await utils.answer(
                message, self.strings["cmd_enabled"].format(cmd, module_key)
            )
        else:
            current.append(cmd)
            disabled_commands[module_key] = current
            self._db.set(main.__name__, "disabled_commands", disabled_commands)

            try:
                self.allmodules.commands.pop(cmd.lower(), None)
            except Exception:
                pass

            for alias, target in list(self.allmodules.aliases.items()):
                if target.split()[0].lower() == cmd.lower():
                    self.allmodules.aliases.pop(alias, None)

            await utils.answer(
                message, self.strings["cmd_disabled"].format(cmd, module_key)
            )

    @loader.command()
    async def togglemod(self, message: Message):
        """Toggle disable entire module: togglemod <module>"""
        args = utils.get_args(message)
        if not args:
            await utils.answer(message, self.strings["wrong_usage_tmc"])

        mod_arg = args[0]
        mod_inst = self.allmodules.lookup(mod_arg)
        if not mod_inst:
            await utils.answer(message, self.strings["mod404"].format(mod_arg))

        module_key = mod_inst.__class__.__name__
        disabled = self._db.get(main.__name__, "disabled_modules", [])

        if module_key in disabled:
            disabled = [m for m in disabled if m != module_key]
            self._db.set(main.__name__, "disabled_modules", disabled)
            try:
                self.allmodules.register_commands(mod_inst)
                self.allmodules.register_watchers(mod_inst)
                self.allmodules.register_raw_handlers(mod_inst)
                self.allmodules.register_inline_stuff(mod_inst)
            except Exception:
                pass
            await utils.answer(message, self.strings["mod_enabled"].format(module_key))
        else:
            disabled += [module_key]
            self._db.set(main.__name__, "disabled_modules", disabled)
            try:
                self.allmodules.unregister_commands(mod_inst, "disable")
                self.allmodules.unregister_watchers(mod_inst, "disable")
                self.allmodules.unregister_raw_handlers(mod_inst, "disable")
                self.allmodules.unregister_inline_stuff(mod_inst, "disable")
            except Exception:
                pass
            await utils.answer(message, self.strings["mod_disabled"].format(module_key))

    @loader.command()
    async def clearmodule(self, message: Message):
        """Clear all DB entries for module: clearmodule <module>"""
        args = utils.get_args(message)
        if not args:
            return await utils.answer(message, self.strings["wrong_usage_cmc"])

        mod_arg = args[0]
        mod_inst = self.allmodules.lookup(mod_arg)
        if mod_inst:
            module_key = mod_inst.__class__.__name__
        else:
            module_key = mod_arg

        if module_key in self._db:
            try:
                del self._db[module_key]
                self._db.save()
            except Exception:
                pass

        disabled_commands = self._db.get(main.__name__, "disabled_commands", {})
        disabled_commands.pop(module_key, None)
        self._db.set(main.__name__, "disabled_commands", disabled_commands)

        disabled_modules = self._db.get(main.__name__, "disabled_modules", [])
        if module_key in disabled_modules:
            disabled_modules = [m for m in disabled_modules if m != module_key]
            self._db.set(main.__name__, "disabled_modules", disabled_modules)

        await utils.answer(message, self.strings["cmc_done"].format(mod_arg))

    async def installationcmd(self, message: Message):
        """| Guide of installation"""

        args = utils.get_args_raw(message)

        if (
            not args or args not in {"-vds", "-wsl", "-ul", "-jh", "-hh", "-lh", "-uni"}
        ) and not (
            await self.inline.form(
                self.strings["choose_installation"],
                message,
                reply_markup=self._markup(),
                photo="https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/heroku_installation.jpg",
            )
        ):

            await self.client.send_file(
                message.peer_id,
                "https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/heroku_installation.jpg",
                caption=self.strings["vds_install"],
                reply_to=getattr(message, "reply_to_msg_id", None),
            )
        match True:
            case _ if "-vds" in args:
                await utils.answer(message, self.strings["vds_install"])
            case _ if "-wsl" in args:
                await utils.answer(message, self.strings["wsl_install"])
            case _ if "-ul" in args:
                await utils.answer(message, self.strings["userland_install"])
            case _ if "-hh" in args:
                await utils.answer(message, self.strings["hikkahost_install"])
            case _ if "-uni" in args:
                await utils.answer(message, self.strings["universal_install"])

    async def _inline__choose__installation(self, call: InlineCall, platform: str):
        with contextlib.suppress(Exception):
            await utils.answer(
                call,
                self.strings[f"{platform}_install"],
                reply_markup=self._markup(),
            )
