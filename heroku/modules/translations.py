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

from .. import loader, translations, utils
from ..inline.types import InlineCall

logger = logging.getLogger(__name__)


@loader.tds
class Translations(loader.Module):
    """Processes internal translations"""

    strings = {"name": "Translations"}

    async def _change_language(self, call: InlineCall, lang: str):
        lang = translations.normalize_language(lang)
        self._db.set(translations.__name__, "lang", lang)
        await self.allmodules.reload_translations()

        await call.edit(self.strings["lang_saved"].format(self._get_flag(lang)))

    def _get_downloaded_langs(self) -> list:
        langs = self._db.get(translations.__name__, "lang", None)
        if not langs:
            return []
        return [lang for lang in langs.split() if utils.check_url(lang)]

    def _get_non_downloaded_langs(self) -> str:
        langs = self._db.get(translations.__name__, "lang", None)
        if not langs:
            return None
        result = " ".join(
            translations.normalize_language(lang)
            for lang in langs.split()
            if not utils.check_url(lang)
        )
        return result if result else None

    async def _choose_language(
        self, message: Message | InlineCall, is_meme: bool = False
    ):
        reply_markup = utils.chunks(
            [
                {
                    "text": text,
                    "callback": self._change_language,
                    "args": (lang,),
                }
                for lang, text in (
                    translations.SUPPORTED_LANGUAGES.items()
                    if not is_meme
                    else translations.MEME_LANGUAGES.items()
                )
            ],
            2,
        )

        back_btn = {
            "text": (
                self.strings["off_langs"] if is_meme else self.strings["meme_langs"]
            ),
            "callback": self._choose_language,
            "args": (not is_meme,),
        }

        downloaded_btn = {
            "text": self.strings["downloaded_langs"],
            "callback": self._show_downloaded,
        }

        reply_markup.append([back_btn])
        reply_markup.append([downloaded_btn])

        await utils.answer(
            message=message,
            response=self.strings["choose_language"],
            reply_markup=reply_markup,
        )

    async def _show_downloaded(self, call: InlineCall):
        downloaded = self._get_downloaded_langs()

        if not downloaded:
            await call.edit(self.strings["no_downloaded"])
            return

        reply_markup = [
            [
                {
                    "text": url.split("/")[-1],
                    "callback": self._confirm_downloaded,
                    "args": (url,),
                }
            ]
            for url in downloaded
        ]

        reply_markup.append(
            [
                {
                    "text": self.strings["btn_back"],
                    "callback": self._choose_language,
                    "args": (False,),
                }
            ]
        )

        await call.edit(
            self.strings["choose_downloaded"],
            reply_markup=reply_markup,
        )

    async def _confirm_downloaded(self, call: InlineCall, url: str):
        reply_markup = [
            [
                {
                    "text": self.strings["btn_yes"],
                    "callback": self._set_downloaded,
                    "args": (url,),
                },
            ],
            [
                {
                    "text": self.strings["btn_cancel"],
                    "callback": self._cancel_action,
                },
            ],
            [
                {
                    "text": self.strings["btn_delete"],
                    "callback": self._delete_downloaded,
                    "args": (url,),
                },
            ],
        ]

        await call.edit(
            self.strings["confirm_lang"].format(url),
            reply_markup=reply_markup,
        )

    async def _set_downloaded(self, call: InlineCall, url: str):
        non_downloaded = self._get_non_downloaded_langs()
        new_lang = f"{non_downloaded} {url}" if non_downloaded else url
        self._db.set(translations.__name__, "lang", new_lang)
        await self.allmodules.reload_translations()
        await call.edit(self.strings["lang_saved"].format(url.split("/")[-1]))

    async def _cancel_action(self, call: InlineCall):
        await call.edit(self.strings["action_cancelled"])

    async def _delete_downloaded(self, call: InlineCall, url: str):
        downloaded = self._get_downloaded_langs()
        downloaded = [lang for lang in downloaded if lang != url]
        non_downloaded = self._get_non_downloaded_langs()

        parts = []
        if non_downloaded:
            parts.append(non_downloaded)
        parts.extend(downloaded)

        new_lang = " ".join(parts) if parts else None
        self._db.set(translations.__name__, "lang", new_lang)
        await self.allmodules.reload_translations()
        await call.edit(self.strings["lang_deleted"])

    def _get_flag(self, lang: str) -> str:
        lang = translations.normalize_language(lang)
        emoji_flags = {
            "🇬🇧": "<tg-emoji emoji-id=6323589145717376403>🇬🇧</tg-emoji>",
            "🇺🇿": "<tg-emoji emoji-id=6323430017179059570>🇺🇿</tg-emoji>",
            "🇷🇺": "<tg-emoji emoji-id=6323139226418284334>🇷🇺</tg-emoji>",
            "🇺🇦": "<tg-emoji emoji-id=5276140694891666474>🇺🇦</tg-emoji>",
            "🇮🇹": "<tg-emoji emoji-id=6323471399188957082>🇮🇹</tg-emoji>",
            "🇩🇪": "<tg-emoji emoji-id=6320817337033295141>🇩🇪</tg-emoji>",
            "🇪🇸": "<tg-emoji emoji-id=6323315062379382237>🇪🇸</tg-emoji>",
            "🇹🇷": "<tg-emoji emoji-id=6321003171678259486>🇹🇷</tg-emoji>",
            "🇰🇿": "<tg-emoji emoji-id=5228718354658769982>🇰🇿</tg-emoji>",
            "🥟": "<tg-emoji emoji-id=5382337996123020810>🥟</tg-emoji>",
            "🇯🇵": "<tg-emoji emoji-id=5456261908069885892>🇯🇵</tg-emoji>",
            "🇫🇷": "<tg-emoji emoji-id=5202132623060640759>🇫🇷</tg-emoji>",
            "🏴‍☠️": "<tg-emoji emoji-id=5386372293263892965>🏴‍☠️</tg-emoji>",
        }

        lang2country = {
            "en": "🇬🇧",
            "tt": "🥟",
            "kz": "🇰🇿",
            "uk": "🇺🇦",
            "ua": "🇺🇦",
            "de": "🇩🇪",
            "ja": "🇯🇵",
            "jp": "🇯🇵",
            "fr": "🇫🇷",
            "uz": "🇺🇿",
        }

        for meme in translations.MEME_LANGUAGES.keys():
            lang2country[meme] = "🏴‍☠️"

        lang = lang2country.get(lang) or utils.get_lang_flag(lang)
        return emoji_flags.get(lang, lang)

    @loader.command()
    async def setlang(self, message: Message):
        if not (args := utils.get_args_raw(message).lower()):
            await self._choose_language(message=message)
            return

        known_langs = set(translations.SUPPORTED_LANGUAGES) | set(translations.MEME_LANGUAGES)
        if any(i not in known_langs and not utils.check_url(i) for i in args.split()):
            await utils.answer(message, self.strings["incorrect_language"])
            return

        args = " ".join(translations.normalize_language_token(x) for x in args.split())

        seen = set()
        seen_add = seen.add
        args = " ".join(x for x in args.split() if not (x in seen or seen_add(x)))

        self._db.set(translations.__name__, "lang", args)
        await self.allmodules.reload_translations()

        await utils.answer(
            message,
            self.strings["lang_saved"].format(
                "".join(
                    [
                        (
                            self._get_flag(lang)
                            if not utils.check_url(lang)
                            else "<tg-emoji emoji-id=5433653135799228968>📁</tg-emoji>"
                        )
                        for lang in args.split()
                    ]
                )
            )
            + (
                ("\n\n" + self.strings["not_official"])
                if any(
                    lang not in translations.SUPPORTED_LANGUAGES
                    and lang not in translations.MEME_LANGUAGES
                    for lang in args.split()
                )
                else ""
            ),
        )

    @loader.command()
    async def dllangpackcmd(self, message: Message):
        if not (args := utils.get_args_raw(message)) or not utils.check_url(args):
            await utils.answer(message, self.strings["check_url"])
            return

        current_lang = (
            " ".join(
                lang
                for lang in self._db.get(translations.__name__, "lang", None).split()
                if not utils.check_url(lang)
            )
            if self._db.get(translations.__name__, "lang", None)
            else None
        )

        self._db.set(
            translations.__name__,
            "lang",
            f"{current_lang} {args}" if current_lang else args,
        )

        await utils.answer(
            message,
            self.strings[
                (
                    "pack_saved"
                    if await self.allmodules.reload_translations()
                    else "check_pack"
                )
            ],
        )
