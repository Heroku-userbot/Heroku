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

import re
import string
import random

from herokutl.tl.types import Message

from .. import loader, utils
from ..inline.types import BotInlineMessage, InlineCall


@loader.tds
class InlineStuff(loader.Module):
    """Provides support for inline stuff"""

    strings = {"name": "InlineStuff"}

    @loader.watcher(
        "out",
        "only_inline",
        contains="This message will be deleted automatically",
    )
    async def watcher(self, message: Message):
        if message.via_bot_id == self.inline.bot_id:
            await message.delete()

    @loader.watcher("out", "only_inline", contains="Opening gallery...")
    async def gallery_watcher(self, message: Message):
        if message.via_bot_id != self.inline.bot_id:
            return

        id_ = re.search(r"#id: ([a-zA-Z0-9]+)", message.raw_text)[1]

        await message.delete()

        m = await message.respond("🪐", reply_to=utils.get_topic(message))

        await self.inline.gallery(
            message=m,
            next_handler=self.inline._custom_map[id_]["handler"],
            caption=self.inline._custom_map[id_].get("caption", ""),
            force_me=self.inline._custom_map[id_].get("force_me", False),
            disable_security=self.inline._custom_map[id_].get(
                "disable_security", False
            ),
            silent=True,
        )

    async def _check_bot(self, username: str) -> bool:
        if await self.inline._check_bot(username):
            return True

        try:
            await self._client.get_entity(username)
            return False
        except Exception:
            return True

    @loader.command()
    async def ch_heroku_bot(self, message: Message):
        args = utils.get_args_raw(message).strip("@")

        if not args:
            from .. import main

            uid = utils.rand(7)
            genran = "".join(random.choice(main.LATIN_MOCK))
            args = f"{genran}_{uid}_bot"

        if (
            not args.lower().endswith("bot")
            or len(args) <= 4
            or any(
                litera not in (string.ascii_letters + string.digits + "_")
                for litera in args
            )
        ):
            await utils.answer(message, self.strings["bot_username_invalid"])
            return

        try:
            await self._client.get_entity(f"@{args}")
        except ValueError:
            pass
        else:
            if not await self._check_bot(args):
                await utils.answer(message, self.strings["bot_username_occupied"])
                return

        self._db.set("heroku.inline", "custom_bot", args)
        self._db.set("heroku.inline", "bot_token", None)
        await utils.answer(message, self.strings["bot_updated"])

    @loader.command()
    async def ch_bot_token(self, message: Message):
        args = utils.get_args_raw(message)
        if not args or not re.match(r"[0-9]{8,10}:[a-zA-Z0-9_-]{34,36}", args):
            await utils.answer(message, self.strings["token_invalid"])
            return
        self._db.set("heroku.inline", "bot_token", args)
        self._db.set("heroku.inline", "needs_inline_setup", True)
        await utils.answer(message, self.strings["bot_updated"])

    async def bot_watcher(self, message: BotInlineMessage):
        match message.text:
            case "/start":
                await message.answer_photo(
                    "https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/start_cmd.jpg",
                    caption=self.strings["this_is_heroku"].format(
                        (
                            "<tg-emoji emoji-id=5463379725441341739>🪐</tg-emoji>"
                            if self._client.heroku_me.premium is True
                            else "🪐"
                        ),
                        utils.get_platform_emoji() if self._client.heroku_me.premium is True else "Heroku",
                    ),
                    reply_markup=self.inline.generate_markup(
                        markup_obj=[
                            [
                                {
                                    "text": "GitHub",
                                    "url": "https://github.com/Heroku-userbot/Heroku",
                                    "emoji_id": "5231065262228250587",
                                }
                            ],
                            [
                                {
                                    "text": self.strings["support_chat_caption"],
                                    "url": "https://t.me/heroku_talks",
                                    "emoji_id": "5363805650327450240",
                                }
                            ],
                        ]
                    ),
                )
            case "/profile":
                if message.from_user.id != self.client.tg_id:
                    pass
                else:
                    await message.answer_photo(
                        "https://raw.githubusercontent.com/Heroku-userbot/assets/refs/heads/main/start_cmd.jpg",
                        caption=self.strings["profile_cmd"].format(
                            prefix=self.get_prefix(),
                            ram_usage=utils.get_ram_usage(),
                            cpu_usage=utils.get_cpu_usage(),
                            host=utils.get_named_platform(),
                        ),
                        reply_markup=self.inline.generate_markup(
                            markup_obj=[
                                [
                                    {
                                        "text": "Restart",
                                        "callback": self.restart,
                                        "style": "primary",
                                        "args": (message,),
                                        "emoji_id": "5873204392429096339",
                                    }
                                ],
                                [
                                    {
                                        "text": "Reset prefix",
                                        "callback": self.reset_prefix,
                                        "style": "primary",
                                        "args": (message,),
                                        "emoji_id": "5870903672937911120",
                                    }
                                ],
                            ]
                        ),
                    )
            case _:
                return

    async def restart(self, call: InlineCall, message):
        await call.edit(self.strings["restart"])
        await self.invoke("restart", "-f", message=message, peer=self.inline.bot_id)

    async def reset_prefix(self, call: InlineCall, message):
        await message.answer(self.strings["prefix_reset"])
        self.db.set("heroku.main", "command_prefix", ".")
        self.db.set("heroku.main", "command_prefix_aliases", [])
