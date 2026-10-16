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

from herokutl.tl.types import Message
from herokutl.utils import get_display_name

from .. import loader, main, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)

ALL_INVOKES = [
    "flush_entity_cache",
    "flush_fulluser_cache",
    "flush_fullchannel_cache",
    "flush_perms_cache",
    "flush_loader_cache",
    "flush_cache",
    "reload_core",
    "inspect_cache",
    "inspect_modules",
]


@loader.tds
class HerokuSettingsMod(loader.Module):
    """Advanced settings for Heroku Userbot"""

    strings = {"name": "HerokuSettings"}

    def get_watchers(self) -> tuple:
        return [
            str(watcher.__self__.__class__.strings["name"])
            for watcher in self.allmodules.watchers
            if watcher.__self__.__class__.strings is not None
        ], self._db.get(main.__name__, "disabled_watchers", {})

    @loader.command()
    async def watchers(self, message: Message):
        watchers, disabled_watchers = self.get_watchers()
        watchers = [
            f"♻️ {watcher}"
            for watcher in watchers
            if watcher not in list(disabled_watchers.keys())
        ]
        watchers += [f"💢 {k} {v}" for k, v in disabled_watchers.items()]
        await utils.answer(
            message, self.strings["watchers"].format("\n".join(watchers))
        )

    @loader.command()
    async def watcherbl(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["args"])
            return

        watchers, disabled_watchers = self.get_watchers()

        if args.lower() not in map(lambda x: x.lower(), watchers):
            await utils.answer(message, self.strings["mod404"].format(args))
            return

        args = next((x for x in watchers if x.lower() == args.lower()), args)

        current_bl = [
            v for k, v in disabled_watchers.items() if k.lower() == args.lower()
        ]
        current_bl = current_bl[0] if current_bl else []

        chat = utils.get_chat_id(message)
        if chat not in current_bl:
            if args in disabled_watchers:
                for k in disabled_watchers:
                    if k.lower() == args.lower():
                        disabled_watchers[k].append(chat)
                        break
            else:
                disabled_watchers[args] = [chat]

            await utils.answer(
                message,
                self.strings["disabled"].format(args) + " <b>in current chat</b>",
            )
        else:
            for k in disabled_watchers.copy():
                if k.lower() == args.lower():
                    disabled_watchers[k].remove(chat)
                    if not disabled_watchers[k]:
                        del disabled_watchers[k]
                    break

            await utils.answer(
                message,
                self.strings["enabled"].format(args) + " <b>in current chat</b>",
            )

        self._db.set(main.__name__, "disabled_watchers", disabled_watchers)

    @loader.command()
    async def watchercmd(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            return await utils.answer(message, self.strings["args"])

        chats, pm, out, incoming = False, False, False, False

        if "-c" in args:
            args = args.replace("-c", "").replace("  ", " ").strip()
            chats = True

        if "-p" in args:
            args = args.replace("-p", "").replace("  ", " ").strip()
            pm = True

        if "-o" in args:
            args = args.replace("-o", "").replace("  ", " ").strip()
            out = True

        if "-i" in args:
            args = args.replace("-i", "").replace("  ", " ").strip()
            incoming = True

        if chats and pm:
            pm = False
        if out and incoming:
            incoming = False

        watchers, disabled_watchers = self.get_watchers()

        if args.lower() not in [watcher.lower() for watcher in watchers]:
            return await utils.answer(message, self.strings["mod404"].format(args))

        args = [watcher for watcher in watchers if watcher.lower() == args.lower()][0]

        if chats or pm or out or incoming:
            disabled_watchers[args] = [
                *(["only_chats"] if chats else []),
                *(["only_pm"] if pm else []),
                *(["out"] if out else []),
                *(["in"] if incoming else []),
            ]
            self._db.set(main.__name__, "disabled_watchers", disabled_watchers)
            await utils.answer(
                message,
                self.strings["enabled"].format(args)
                + f" (<code>{disabled_watchers[args]}</code>)",
            )
            return

        if args in disabled_watchers and "*" in disabled_watchers[args]:
            await utils.answer(message, self.strings["enabled"].format(args))
            del disabled_watchers[args]
            self._db.set(main.__name__, "disabled_watchers", disabled_watchers)
            return

        disabled_watchers[args] = ["*"]
        self._db.set(main.__name__, "disabled_watchers", disabled_watchers)
        await utils.answer(message, self.strings["disabled"].format(args))

    @loader.command()
    async def nonickuser(self, message: Message):
        if not (reply := await message.get_reply_message()):
            await utils.answer(message, self.strings["reply_required"])
            return

        u = reply.sender_id
        if not isinstance(u, int):
            u = u.user_id

        nn = self._db.get(main.__name__, "nonickusers", [])
        if u not in nn:
            nn += [u]
            nn = list(set(nn))  # skipcq: PTC-W0018
            await utils.answer(message, self.strings["user_nn"].format("on"))
        else:
            nn = list(set(nn) - {u})
            await utils.answer(message, self.strings["user_nn"].format("off"))

        self._db.set(main.__name__, "nonickusers", nn)

    @loader.command()
    async def nonickchat(self, message: Message):
        if message.is_private:
            await utils.answer(message, self.strings["private_not_allowed"])
            return

        chat = utils.get_chat_id(message)

        nn = self._db.get(main.__name__, "nonickchats", [])
        if chat not in nn:
            nn += [chat]
            nn = list(set(nn))  # skipcq: PTC-W0018
            await utils.answer(
                message,
                self.strings["cmd_nn"].format(
                    utils.escape_html((await message.get_chat()).title),
                    "on",
                ),
            )
        else:
            nn = list(set(nn) - {chat})
            await utils.answer(
                message,
                self.strings["cmd_nn"].format(
                    utils.escape_html((await message.get_chat()).title),
                    "off",
                ),
            )

        self._db.set(main.__name__, "nonickchats", nn)

    @loader.command()
    async def nonickcmdcmd(self, message: Message):
        if not (args := utils.get_args_raw(message)):
            await utils.answer(message, self.strings["no_cmd"])
            return

        if args not in self.allmodules.commands:
            await utils.answer(message, self.strings["cmd404"])
            return

        nn = self._db.get(main.__name__, "nonickcmds", [])
        if args not in nn:
            nn += [args]
            nn = list(set(nn))
            await utils.answer(
                message,
                self.strings["cmd_nn"].format(
                    utils.escape_html(self.get_prefix() + args),
                    "on",
                ),
            )
        else:
            nn = list(set(nn) - {args})
            await utils.answer(
                message,
                self.strings["cmd_nn"].format(
                    utils.escape_html(self.get_prefix() + args),
                    "off",
                ),
            )

        self._db.set(main.__name__, "nonickcmds", nn)

    @loader.command()
    async def nonickcmds(self, message: Message):
        if not self._db.get(main.__name__, "nonickcmds", []):
            await utils.answer(message, self.strings["nothing"])
            return

        await utils.answer(
            message,
            self.strings["cmd_nn_list"].format(
                "\n".join(
                    [
                        f"▫️ <code>{utils.escape_html(self.get_prefix() + cmd)}</code>"
                        for cmd in self._db.get(main.__name__, "nonickcmds", [])
                    ]
                )
            ),
        )

    @loader.command()
    async def nonickusers(self, message: Message):
        users = []
        for user_id in self._db.get(main.__name__, "nonickusers", []).copy():
            try:
                user = await self._client.get_entity(user_id)
            except Exception:
                self._db.set(
                    main.__name__,
                    "nonickusers",
                    list(
                        set(self._db.get(main.__name__, "nonickusers", [])) - {user_id}
                    ),
                )

                logger.warning("User %s removed from nonickusers list", user_id)
                continue

            users += [
                '▫️ <b><a href="tg://user?id={}">{}</a></b>'.format(
                    user_id,
                    utils.escape_html(get_display_name(user)),
                )
            ]

        if not users:
            await utils.answer(message, self.strings["nothing"])
            return

        await utils.answer(
            message,
            self.strings["user_nn_list"].format("\n".join(users)),
        )

    @loader.command()
    async def nonickchats(self, message: Message):
        chats = []
        for chat in self._db.get(main.__name__, "nonickchats", []):
            try:
                chat_entity = await self._client.get_entity(int(chat))
            except Exception:
                self._db.set(
                    main.__name__,
                    "nonickchats",
                    list(set(self._db.get(main.__name__, "nonickchats", [])) - {chat}),
                )

                logger.warning("Chat %s removed from nonickchats list", chat)
                continue

            chats += [
                '▫️ <b><a href="{}">{}</a></b>'.format(
                    utils.get_entity_url(chat_entity),
                    utils.escape_html(get_display_name(chat_entity)),
                )
            ]

        if not chats:
            await utils.answer(message, self.strings["nothing"])
            return

        await utils.answer(
            message,
            self.strings["user_nn_list"].format("\n".join(chats)),
        )

    async def inline__setting(self, call: InlineCall, key: str, state: bool = False):

        self.db.set(main.__name__, key, state)

        if key == "no_nickname" and state and self.get_prefix() == ".":
            await call.answer(
                self.strings["nonick_warning"],
                show_alert=True,
            )
        else:
            await call.answer("Configuration value saved!")

        await call.edit(
            self.strings["inline_settings"],
            reply_markup=self._get_settings_markup(),
        )

    async def inline__update(
        self,
        call: InlineCall,
        confirm_required: bool = False,
    ):
        if confirm_required:
            await call.edit(
                self.strings["confirm_update"],
                reply_markup=[
                    {
                        "text": "🪂 Update",
                        "callback": self.inline__update,
                        "style": "primary",
                    },
                    {
                        "text": "🚫 Cancel",
                        "action": "close",
                        "style": "danger",
                    },
                ],
            )
            return

        await call.answer("You userbot is being updated...", show_alert=True)
        await call.delete()
        await self.invoke("update", "-f", peer="me")

    async def inline__restart(
        self,
        call: InlineCall,
        confirm_required: bool = False,
    ):
        if confirm_required:
            await call.edit(
                self.strings["confirm_restart"],
                reply_markup=[
                    {
                        "text": "🔄 Restart",
                        "callback": self.inline__restart,
                        "style": "primary",
                    },
                    {"text": "🚫 Cancel", "action": "close", "style": "danger"},
                ],
            )
            return

        await call.answer("You userbot is being restarted...", show_alert=True)
        await call.delete()
        await self.invoke("restart", "-f", peer="me")

    def _get_settings_markup(self) -> list:
        return [
            [
                (
                    {
                        "text": "✅ NoNick",
                        "callback": self.inline__setting,
                        "args": (
                            "no_nickname",
                            False,
                        ),
                    }
                    if self._db.get(main.__name__, "no_nickname", False)
                    else {
                        "text": "🚫 NoNick",
                        "callback": self.inline__setting,
                        "args": (
                            "no_nickname",
                            True,
                        ),
                    }
                ),
                (
                    {
                        "text": "✅ Grep",
                        "callback": self.inline__setting,
                        "args": (
                            "grep",
                            False,
                        ),
                    }
                    if self._db.get(main.__name__, "grep", False)
                    else {
                        "text": "🚫 Grep",
                        "callback": self.inline__setting,
                        "args": (
                            "grep",
                            True,
                        ),
                    }
                ),
                (
                    {
                        "text": "✅ InlineLogs",
                        "callback": self.inline__setting,
                        "args": (
                            "inlinelogs",
                            False,
                        ),
                    }
                    if self._db.get(main.__name__, "inlinelogs", True)
                    else {
                        "text": "🚫 InlineLogs",
                        "callback": self.inline__setting,
                        "args": (
                            "inlinelogs",
                            True,
                        ),
                    }
                ),
            ],
            [
                (
                    {
                        "text": self.strings["suggest_subscribe"],
                        "callback": self.inline__setting,
                        "args": (
                            "suggest_subscribe",
                            False,
                        ),
                    }
                    if self._db.get(main.__name__, "suggest_subscribe", True)
                    else {
                        "text": self.strings["do_not_suggest_subscribe"],
                        "callback": self.inline__setting,
                        "args": (
                            "suggest_subscribe",
                            True,
                        ),
                    }
                ),
            ],
            [
                {
                    "text": self.strings["btn_restart"],
                    "callback": self.inline__restart,
                    "style": "primary",
                    "args": (True,),
                },
                {
                    "text": self.strings["btn_update"],
                    "callback": self.inline__update,
                    "style": "primary",
                    "args": (True,),
                },
            ],
            [
                {
                    "text": self.strings["close_menu"],
                    "action": "close",
                    "style": "danger",
                }
            ],
        ]

    @loader.command()
    async def settings(self, message: Message):
        await self.inline.form(
            self.strings["inline_settings"],
            message=message,
            reply_markup=self._get_settings_markup(),
        )

    def _get_all_IDM(self, module: str):
        return {
            getattr(getattr(self.lookup(module), name), "name", name): getattr(
                self.lookup(module), name
            )
            for name in dir(self.lookup(module))
            if getattr(getattr(self.lookup(module), name), "is_debug_method", False)
        }
