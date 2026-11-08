# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import io
import logging

import orjson

from .. import loader, utils
from ..types import Message

logger = logging.getLogger(__name__)


@loader.tds
class Aliases(loader.Module):
    """Load and save command aliases"""

    strings = {
        "name": "Aliases"
    }

    @loader.command(alias="la")
    async def loadaliases(self, message: Message):
        """Load aliases from file. Send a file with the command or reply to a file."""
        msg = message if message.file else (await message.get_reply_message())
        if not msg or not msg.file:
            await message.edit(self.strings["no_file"])
            return
        try:
            data = orjson.loads(await msg.download_media(bytes))
        except Exception:
            await message.edit(self.strings["load_failed"])
            logger.exception("Failed to load aliases from file")
            return
        if not isinstance(data, list) or not all(
            isinstance(item, dict) and "alias" in item and "command" in item
            for item in data
        ):
            await message.edit(self.strings["load_failed"])
            logger.error("Invalid aliases format")
            return

        loaded = []
        for item in data:
            alias = item["alias"]
            cmd_str = item["command"]
            parts = cmd_str.split(maxsplit=1)
            cmd = parts[0]
            rest = parts[1] if len(parts) > 1 else None
            if self.allmodules.add_alias(alias, cmd, rest):
                self.set(
                    "aliases",
                    {
                        **self.get("aliases", {}),
                        alias: f"{cmd} {rest}" if rest else cmd,
                    },
                )
                loaded.append(alias)
            else:
                logger.error("Falied to load alias %s", alias)

        await utils.answer(
            message,
            self.strings["aliases_list"].format(
                "\n".join(f"{alias}" for alias in loaded)
            ),
            reply_to=getattr(message, "reply_to_msg_id", None),
        )

    @loader.command(alias="al")
    async def aliasload(self, message: Message):
        """send aliases via file"""
        aliases = self.allmodules.aliases.items()
        if not aliases:
            await message.edit(self.strings["no_aliases"])
            return
        file = io.BytesIO(
            orjson.dumps([{"alias": alias, "command": cmd} for alias, cmd in aliases])
        )
        file.name = "aliases.json"
        await utils.answer(
            message,
            self.strings["aliases_file"].format(prefix=self.get_prefix()),
            file=file,
            reply_to=getattr(message, "reply_to_msg_id", None),
        )
