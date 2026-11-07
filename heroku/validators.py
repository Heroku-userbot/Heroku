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

import functools
import re
import typing
from collections.abc import Callable

import grapheme
import emoji

from . import utils
from .translations import SUPPORTED_LANGUAGES, fmt, translator

ConfigAllowedTypes = typing.Union[tuple, list, str, int, bool, None]

ALLOWED_EMOJIS = set(emoji.EMOJI_DATA.keys())


class ValidationError(Exception):
    """
    Is being raised when config value passed can't be converted properly
    Must be raised with string, describing why value is incorrect
    It will be shown in .config, if user tries to set incorrect value
    """


class LocalizedText(str):
    """English text, which also carries its translations in `translations`"""

    translations: dict


def _tr(key: str, **kwargs) -> dict:
    """Same as `translator.getdict`, but falls back to english text"""
    key = f"validators.{key}"
    default = translator.data.get("en", {}).get(key) or key
    return {
        lang: fmt(pack.get(key) or default, kwargs)
        for lang, pack in translator.data.items()
    }


def _error(key: str, localized: dict | None = None, **kwargs) -> ValidationError:
    """
    Builds translated `ValidationError` from `validators.err_<key>`
    :param localized: Placeholders, which have different values for each language
    """
    texts = {
        lang: fmt(
            text,
            {
                **kwargs,
                **{
                    name: values.get(lang, values.get("en", ""))
                    for name, values in (localized or {}).items()
                },
            },
        )
        for lang, text in _tr(f"err_{key}").items()
    }
    text = LocalizedText(texts.get("en", key))
    text.translations = texts
    return ValidationError(text)


class Validator:
    """
    Class used as validator of config value
    :param validator: Sync function, which raises `ValidationError` if passed
                      value is incorrect (with explanation) and returns converted
                      value if it is semantically correct.
                      ⚠️ If validator returns `None`, value will always be set to `None`
    :param doc: Docstrings for this validator as string, or dict in format:
                {
                    "en": "docstring",
                    "ru": "докстрингом",
                    "ua": "докстрінгом",
                    "de": "Dokumentation",
                }
                Use instrumental case with lowercase
    :param _internal_id: Do not pass anything here, or things will break
    """

    def __init__(
        self,
        validator: Callable,
        doc: str | dict | None = None,
        _internal_id: int | None = None,
    ):
        self.validate = validator

        if isinstance(doc, str):
            doc = {lang: doc for lang in SUPPORTED_LANGUAGES}

        self.doc = doc
        self.internal_id = _internal_id


class Boolean(Validator):
    """
    Any logical value to be passed
    `1`, `"1"` etc. will be automatically converted to bool
    """

    _TRUE_VALUES = frozenset(
        ("True", "true", "1", 1, True, "yes", "Yes", "on", "On", "y", "Y")
    )
    _FALSE_VALUES = frozenset(
        ("False", "false", "0", 0, False, "no", "No", "off", "Off", "n", "N")
    )
    _ALL_VALUES = _TRUE_VALUES | _FALSE_VALUES

    def __init__(self):
        super().__init__(
            self._validate,
            translator.getdict("validators.boolean"),
            _internal_id="Boolean",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> bool:
        if value not in Boolean._ALL_VALUES:
            raise _error("boolean", value=value)

        return value in Boolean._TRUE_VALUES


class Integer(Validator):
    """
    Checks whether passed argument is an integer value
    :param digits: Digits quantity, which must be passed
    :param minimum: Minimal number to be passed
    :param maximum: Maximum number to be passed
    """

    def __init__(
        self,
        *,
        digits: int | None = None,
        minimum: int | None = None,
        maximum: int | None = None,
    ):
        _signs = (
            translator.getdict("validators.positive")
            if minimum is not None and minimum == 0
            else (_tr("negative") if maximum is not None and maximum == 0 else {})
        )
        _digits = (
            translator.getdict("validators.digits", digits=digits)
            if digits is not None
            else {}
        )

        match True:
            case _ if minimum is not None and minimum != 0:
                doc = (
                    {
                        lang: text.format(
                            sign=_signs.get(lang, ""),
                            digits=_digits.get(lang, ""),
                            minimum=minimum,
                        )
                        for lang, text in translator.getdict(
                            "validators.integer_min"
                        ).items()
                    }
                    if maximum is None and maximum != 0
                    else {
                        lang: text.format(
                            sign=_signs.get(lang, ""),
                            digits=_digits.get(lang, ""),
                            minimum=minimum,
                            maximum=maximum,
                        )
                        for lang, text in translator.getdict(
                            "validators.integer_range"
                        ).items()
                    }
                )
            case _ if maximum is None and maximum != 0:
                doc = {
                    lang: text.format(
                        sign=_signs.get(lang, ""), digits=_digits.get(lang, "")
                    )
                    for lang, text in translator.getdict("validators.integer").items()
                }
            case _:
                doc = {
                    lang: text.format(
                        sign=_signs.get(lang, ""),
                        digits=_digits.get(lang, ""),
                        maximum=maximum,
                    )
                    for lang, text in translator.getdict(
                        "validators.integer_max"
                    ).items()
                }

        super().__init__(
            functools.partial(
                self._validate,
                digits=digits,
                minimum=minimum,
                maximum=maximum,
            ),
            doc,
            _internal_id="Integer",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        digits: int,
        minimum: int,
        maximum: int,
    ) -> int | None:
        try:
            value = int(str(value).strip())
        except ValueError:
            raise _error("integer", value=value)

        if minimum is not None and value < minimum:
            raise _error("minimum", value=value, minimum=minimum)

        if maximum is not None and value > maximum:
            raise _error("maximum", value=value, maximum=maximum)

        if digits is not None and len(str(value)) != digits:
            raise _error("digits", value=value, digits=digits)

        return value


class Choice(Validator):
    """
    Check whether entered value is in the allowed list
    :param possible_values: Allowed values to be passed to config param
    """

    def __init__(
        self,
        possible_values: list[ConfigAllowedTypes],
        /,
    ):
        super().__init__(
            functools.partial(self._validate, possible_values=possible_values),
            translator.getdict(
                "validators.choice",
                possible=" / ".join(list(map(str, possible_values))),
            ),
            _internal_id="Choice",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        possible_values: list[ConfigAllowedTypes],
    ) -> ConfigAllowedTypes:
        if value not in possible_values:
            # "1" may come as int after `ast.literal_eval`, compare as strings too
            for possible in possible_values:
                if str(possible) == str(value):
                    return possible

            raise _error(
                "choice",
                value=value,
                possible=" / ".join(list(map(str, possible_values))),
            )

        return value


class MultiChoice(Validator):
    """
    Check whether every entered value is in the allowed list
    :param possible_values: Allowed values to be passed to config param
    """

    def __init__(
        self,
        possible_values: list[ConfigAllowedTypes],
        /,
    ):
        possible = " / ".join(list(map(str, possible_values)))
        super().__init__(
            functools.partial(self._validate, possible_values=possible_values),
            translator.getdict("validators.multichoice", possible=possible),
            _internal_id="MultiChoice",
        )

    @staticmethod
    def _validate(
        value: list[ConfigAllowedTypes],
        /,
        *,
        possible_values: list[ConfigAllowedTypes],
    ) -> list[ConfigAllowedTypes]:
        if not isinstance(value, (list, tuple)):
            value = [value]

        value = list(value)
        for i, item in enumerate(value):
            if item not in possible_values:
                matches = [
                    possible
                    for possible in possible_values
                    if str(possible) == str(item)
                ]
                if not matches:
                    raise _error(
                        "choice",
                        value=item,
                        possible=" / ".join(list(map(str, possible_values))),
                    )

                value[i] = matches[0]

        return list(set(value))


class Series(Validator):
    """
    Represents the series of value (simply `list`)
    :param separator: With which separator values must be separated
    :param validator: Internal validator for each sequence value
    :param min_len: Minimal number of series items to be passed
    :param max_len: Maximum number of series items to be passed
    :param fixed_len: Fixed number of series items to be passed
    """

    def __init__(
        self,
        validator: Validator | None = None,
        min_len: int | None = None,
        max_len: int | None = None,
        fixed_len: int | None = None,
    ):
        def trans(lang: str) -> str:
            return validator.doc.get(lang, validator.doc["en"])

        _each = (
            {
                lang: text.format(each=trans(lang))
                for lang, text in translator.getdict("validators.each").items()
            }
            if validator is not None
            else {}
        )

        match True:
            case _ if fixed_len is not None:
                _len = translator.getdict("validators.fixed_len", fixed_len=fixed_len)
            case _ if min_len is None:
                if max_len is None:
                    _len = {}
                else:
                    _len = translator.getdict("validators.max_len", max_len=max_len)
            case _ if max_len is not None:
                _len = translator.getdict(
                    "validators.len_range", min_len=min_len, max_len=max_len
                )
            case _:
                _len = translator.getdict("validators.min_len", min_len=min_len)

        super().__init__(
            functools.partial(
                self._validate,
                validator=validator,
                min_len=min_len,
                max_len=max_len,
                fixed_len=fixed_len,
            ),
            {
                lang: text.format(each=_each.get(lang, ""), len=_len.get(lang, ""))
                for lang, text in translator.getdict("validators.series").items()
            },
            _internal_id="Series",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        validator: Validator | None = None,
        min_len: int | None = None,
        max_len: int | None = None,
        fixed_len: int | None = None,
    ) -> list[ConfigAllowedTypes]:
        if not isinstance(value, (list, tuple, set)):
            value = str(value).split(",")

        if isinstance(value, (tuple, set)):
            value = list(value)

        if min_len is not None and len(value) < min_len:
            raise _error("series_min_len", value=value, min_len=min_len)

        if max_len is not None and len(value) > max_len:
            raise _error("series_max_len", value=value, max_len=max_len)

        if fixed_len is not None and len(value) != fixed_len:
            raise _error("series_fixed_len", value=value, fixed_len=fixed_len)

        value = [item.strip() if isinstance(item, str) else item for item in value]

        if isinstance(validator, Validator):
            for i, item in enumerate(value):
                try:
                    value[i] = validator.validate(item)
                except ValidationError:
                    raise _error(
                        "series_item",
                        localized={"each": validator.doc or {}},
                        value=value,
                        item=str(item).strip(),
                    )

        value = list(filter(lambda x: x, value))

        return value


class Link(Validator):
    """Valid url must be specified"""

    def __init__(self):
        super().__init__(
            lambda value: self._validate(value),
            translator.getdict("validators.link"),
            _internal_id="Link",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> str:
        try:
            if not utils.check_url(value):
                raise Exception("Invalid URL")
        except Exception:
            raise _error("link", value=value)

        return value


class String(Validator):
    """
    Checks for length of passed value and automatically converts it to string
    :param length: Exact length of string
    :param min_len: Minimal length of string
    :param max_len: Maximum length of string
    """

    def __init__(
        self,
        length: int | None = None,
        min_len: int | None = None,
        max_len: int | None = None,
    ):
        if length is not None:
            doc = translator.getdict("validators.string_fixed_len", length=length)
        else:
            match True:
                case _ if min_len is None:
                    if max_len is None:
                        doc = translator.getdict("validators.string")
                    else:
                        doc = translator.getdict(
                            "validators.string_max_len", max_len=max_len
                        )
                case _ if max_len is not None:
                    doc = translator.getdict(
                        "validators.string_len_range", min_len=min_len, max_len=max_len
                    )
                case _:
                    doc = translator.getdict(
                        "validators.string_min_len", min_len=min_len
                    )

        super().__init__(
            functools.partial(
                self._validate,
                length=length,
                min_len=min_len,
                max_len=max_len,
            ),
            doc,
            _internal_id="String",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        length: int | None,
        min_len: int | None,
        max_len: int | None,
    ) -> str:
        if (
            isinstance(length, int)
            and len(list(grapheme.graphemes(str(value)))) != length
        ):
            raise _error("string_fixed_len", value=value, length=length)

        if (
            isinstance(min_len, int)
            and len(list(grapheme.graphemes(str(value)))) < min_len
        ):
            raise _error("string_min_len", value=value, min_len=min_len)

        if (
            isinstance(max_len, int)
            and len(list(grapheme.graphemes(str(value)))) > max_len
        ):
            raise _error("string_max_len", value=value, max_len=max_len)

        return str(value)


class RegExp(Validator):
    """
    Checks if value matches the regex
    :param regex: Regex to match
    :param flags: Flags to pass to re.compile
    :param description: Description of regex
    """

    def __init__(
        self,
        regex: str,
        flags: re.RegexFlag | None = None,
        description: dict | str | None = None,
    ):
        if not flags:
            flags = 0

        try:
            re.compile(regex, flags=flags)
        except re.error as e:
            raise Exception(f"{regex} is not a valid regex") from e

        if description is None:
            doc = translator.getdict("validators.regex", regex=regex)
        else:
            if isinstance(description, str):
                doc = {"en": description}
            else:
                doc = description

        super().__init__(
            functools.partial(self._validate, regex=regex, flags=flags),
            doc,
            _internal_id="RegExp",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        regex: str,
        flags: re.RegexFlag | None,
    ) -> str:
        if not re.match(regex, str(value), flags=flags):
            raise _error("regex", value=value, regex=regex)

        return str(value)


class Float(Validator):
    """
    Checks whether passed argument is a float value
    :param minimum: Minimal number to be passed
    :param maximum: Maximum number to be passed
    """

    def __init__(
        self,
        minimum: float | None = None,
        maximum: float | None = None,
    ):
        _signs = (
            translator.getdict("validators.positive")
            if minimum is not None and minimum == 0
            else (_tr("negative") if maximum is not None and maximum == 0 else {})
        )

        if minimum is not None and minimum != 0:
            doc = (
                {
                    lang: text.format(sign=_signs.get(lang, ""), minimum=minimum)
                    for lang, text in translator.getdict("validators.float_min").items()
                }
                if maximum is None and maximum != 0
                else {
                    lang: text.format(
                        sign=_signs.get(lang, ""), minimum=minimum, maximum=maximum
                    )
                    for lang, text in translator.getdict(
                        "validators.float_range"
                    ).items()
                }
            )

        elif maximum is None and maximum != 0:
            doc = {
                lang: text.format(sign=_signs.get(lang, ""))
                for lang, text in translator.getdict("validators.float").items()
            }
        else:
            doc = {
                lang: text.format(sign=_signs.get(lang, ""), maximum=maximum)
                for lang, text in translator.getdict("validators.float_max").items()
            }

        super().__init__(
            functools.partial(
                self._validate,
                minimum=minimum,
                maximum=maximum,
            ),
            doc,
            _internal_id="Float",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        try:
            value = float(str(value).strip().replace(",", "."))
        except ValueError:
            raise _error("float", value=value)

        if minimum is not None and value < minimum:
            raise _error("minimum", value=value, minimum=minimum)

        if maximum is not None and value > maximum:
            raise _error("maximum", value=value, maximum=maximum)

        return value


class TelegramID(Validator):
    def __init__(self):
        super().__init__(
            self._validate,
            "Telegram ID",
            _internal_id="TelegramID",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> int:
        e = _error("telegram_id", value=value)

        try:
            value = int(str(value).strip())
        except Exception:
            raise e

        if str(value).startswith("-100"):
            value = int(str(value)[4:])

        if value > 2**64 - 1 or value < 0:
            raise e

        return value


class Union(Validator):
    def __init__(self, *validators):
        doc = translator.getdict("validators.union")

        def case(x: str) -> str:
            return x[0].upper() + x[1:]

        for validator in validators:
            for key in doc:
                doc[key] += f"- {case(validator.doc.get(key, validator.doc['en']))}\n"

        for key, value in doc.items():
            doc[key] = value.strip()

        super().__init__(
            functools.partial(self._validate, validators=validators),
            doc,
            _internal_id="Union",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        validators: list,
    ) -> ConfigAllowedTypes:
        for validator in validators:
            try:
                return validator.validate(value)
            except ValidationError:
                pass

        raise _error("union", value=value)


class NoneType(Validator):
    def __init__(self):
        super().__init__(
            self._validate,
            translator.getdict("validators.empty"),
            _internal_id="NoneType",
        )

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /) -> None:
        if value:
            raise _error("empty", value=value)

        return None


class Hidden(Validator):
    def __init__(self, validator: Validator | None = None):
        if not validator:
            validator = String()

        super().__init__(
            functools.partial(self._validate, validator=validator),
            validator.doc,
            _internal_id="Hidden",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        validator: Validator,
    ) -> ConfigAllowedTypes:
        return validator.validate(value)


class Emoji(Validator):
    """
    Checks whether passed argument is a valid emoji
    :param quantity: Number of emojis to be passed
    :param min_len: Minimum number of emojis
    :param max_len: Maximum number of emojis
    """

    def __init__(
        self,
        length: int | None = None,
        min_len: int | None = None,
        max_len: int | None = None,
    ):
        match True:
            case _ if length is not None:
                doc = translator.getdict("validators.emoji_fixed_len", length=length)
            case _ if min_len is not None and max_len is not None:
                doc = translator.getdict(
                    "validators.emoji_len_range", min_len=min_len, max_len=max_len
                )
            case _ if min_len is not None:
                doc = translator.getdict("validators.emoji_min_len", min_len=min_len)
            case _ if max_len is not None:
                doc = translator.getdict("validators.emoji_max_len", max_len=max_len)
            case _:
                doc = translator.getdict("validators.emoji")

        super().__init__(
            functools.partial(
                self._validate,
                length=length,
                min_len=min_len,
                max_len=max_len,
            ),
            doc,
            _internal_id="Emoji",
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        length: int | None,
        min_len: int | None,
        max_len: int | None,
    ) -> str:
        value = str(value)
        passed_length = len(list(grapheme.graphemes(value)))

        if length is not None and passed_length != length:
            raise _error("emoji_fixed_len", value=value, length=length)

        if (
            min_len is not None
            and max_len is not None
            and (passed_length < min_len or passed_length > max_len)
        ):
            raise _error(
                "emoji_len_range", value=value, min_len=min_len, max_len=max_len
            )

        if min_len is not None and passed_length < min_len:
            raise _error("emoji_min_len", value=value, min_len=min_len)

        if max_len is not None and passed_length > max_len:
            raise _error("emoji_max_len", value=value, max_len=max_len)

        if any(emoji not in ALLOWED_EMOJIS for emoji in grapheme.graphemes(value)):
            raise _error("emoji", value=value)

        return value


class EntityLike(RegExp):
    def __init__(self):
        super().__init__(
            regex=r"^(?:-?\d+|(?:@|https?://t\.me/)?(?:[a-zA-Z0-9_]{5,32}|[a-zA-Z0-9_]{1,32}\?[a-zA-Z0-9_]{1,32}))$",
            description=translator.getdict("validators.entity_like"),
        )

    @staticmethod
    def _validate(
        value: ConfigAllowedTypes,
        /,
        *,
        regex: str,
        flags: re.RegexFlag | None,
    ) -> str | int:
        value = RegExp._validate(value, regex=regex, flags=flags)

        if value.lstrip("-").isdigit():
            if value.startswith("-100"):
                value = value[4:]

            return int(value)

        value = re.sub(r"^https?://t\.me/", "", value)

        if not value.startswith("@"):
            value = f"@{value}"

        return value


class RandomLinkList(list):
    def __str__(self):
        import random

        if not self:
            return ""
        return str(random.choice(self))

    def __bytes__(self):
        return str(self).encode("utf-8")

    def __repr__(self):
        return super().__repr__()


class RandomLink(Series):
    def __init__(self):
        super().__init__(validator=Link(), min_len=1)
        self.internal_id = "Series"
        self.doc = {
            "en": "list of links, one of which will be chosen randomly",
            "ru": "списком ссылок, из которых будет выбрана случайная",
        }

    @staticmethod
    def _validate(value: ConfigAllowedTypes, /, **kwargs) -> RandomLinkList:
        val_args = kwargs.copy()
        if "validator" not in val_args:
            val_args["validator"] = Link()
        if "min_len" not in val_args:
            val_args["min_len"] = 1

        clean_list = Series._validate(value, **val_args)
        return RandomLinkList(clean_list)
