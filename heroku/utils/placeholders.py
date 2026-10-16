# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import logging as _logging
import typing

custom_placeholders = {}


class LazyPlaceholderData(dict):
    def __init__(self, providers):
        super().__init__()
        self._providers = providers

    def __missing__(self, name):
        if name not in self._providers:
            raise KeyError(name)
        try:
            value = self._providers[name]()
            self[name] = value if value is not None else ""
        except OSError:
            self[name] = ""
        except Exception:
            _logging.getLogger(__name__).exception("Unavailable placeholder: %s", name)
            self[name] = ""
        return self[name]

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default


def register_placeholder(
    placeholder: str,
    callback: typing.Callable,
    description: str | None = None,
):
    """
    Register placeholder
    """
    module_name = callback.__self__.__class__.__name__
    module_instance = callback.__self__
    custom_placeholders[placeholder] = {
        "module_name": module_name,
        "module_instance": module_instance,
        "callback": callback,
        "description": description,
        "placeholder_name": placeholder,
    }
    return True


async def get_placeholder(placeholder: str, data: dict | None = None):
    """
    Returns placeholder data
    """
    callback = custom_placeholders[placeholder]["callback"]
    try:
        callback_data = str(await callback(data))
    except Exception:
        callback_data = str(await callback())
    return callback_data


async def get_placeholders(data, custom_message):
    """
    Returns placeholders if it is in custom_message
    """
    if custom_message is None:
        return data
    for placeholder in custom_placeholders.values():
        if f"{{{placeholder['placeholder_name']}}}" in custom_message:
            data[placeholder["placeholder_name"]] = await get_placeholder(
                placeholder["placeholder_name"], data
            )
    return data


def unregister_placeholders(module_name: str) -> int:
    """
    Removes placeholders by module_name
    """
    placeholders_to_remove = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if placeholder_data.get("module_name") == module_name:
            placeholders_to_remove.append(placeholder_name)
    for placeholder_name in placeholders_to_remove:
        del custom_placeholders[placeholder_name]
    return True


def config_placeholders():
    """
    Return placeholders list for config
    """
    result = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        result.append(
            f"{{{placeholder_name}}} - {placeholder_data.get('description') if placeholder_data.get('description') is not None else 'No docs'}"
        )
    if result == []:
        return None
    else:
        return "\n".join(result)


def module_placeholders(module_name: str) -> list[str]:
    """
    Return placeholder names registered by module
    """
    result = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if placeholder_data.get("module_name") == module_name:
            result.append(placeholder_name)
    return result


def help_placeholders(module_name, self):
    """
    Return placeholders list for help
    """
    result = []
    for placeholder_name, placeholder_data in custom_placeholders.items():
        if placeholder_data.get("module_name") == module_name:
            if placeholder_data.get("description") is not None:
                result.append(
                    self.db.get("Help", "__config__", None).get("command_emoji")
                    + f" {{{placeholder_name}}} - {placeholder_data.get('description')}"
                )
            else:
                result.append(
                    self.db.get("Help", "__config__", None).get("command_emoji")
                    + f" {{{placeholder_name}}} - No docs"
                )
    return result


def debug_placeholders():
    """
    Just for debug purposes
    """
    return custom_placeholders
