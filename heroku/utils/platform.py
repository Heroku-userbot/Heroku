# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import contextlib
import logging
import os
import time
from datetime import timedelta

import herokutl

parser = herokutl.utils.sanitize_parse_mode("html")
logger = logging.getLogger(__name__)

IS_DOCKER = "DOCKER" in os.environ
IS_HIKKAHOST = "HIKKAHOST" in os.environ
IS_MACOS = "com.apple" in os.environ.get("PATH", "")
IS_USERLAND = "userland" in os.environ.get("USER", "")
IS_WSL = False
IS_WINDOWS = False
with contextlib.suppress(Exception):
    from platform import uname

    if "microsoft-standard" in uname().release:
        IS_WSL = True
    elif uname().system == "Windows":
        IS_WINDOWS = True


def get_named_platform() -> str:
    """
    Returns formatted platform name
    :return: Platform name
    """

    with contextlib.suppress(Exception):
        if os.path.isfile("/proc/device-tree/model"):
            with open("/proc/device-tree/model") as f:
                model = f.read().strip()
                if any(board in model for board in ("Orange", "Raspberry")):
                    return model

    match True:

        case _ if IS_WSL:
            return "WSL"

        case _ if IS_WINDOWS:
            return "Windows"

        case _ if IS_MACOS:
            return "MacOS"

        case _ if IS_USERLAND:
            return "UserLand"

        case _ if IS_HIKKAHOST:
            return "HikkaHost"

        case _ if IS_DOCKER:
            return "Docker"

        case _:
            return "VDS"


def get_named_platform_emoji() -> str:
    """
    Returns emoji for current platform
    """

    with contextlib.suppress(Exception):
        if os.path.isfile("/proc/device-tree/model"):
            with open("/proc/device-tree/model") as f:
                model = f.read()
                if "Orange" in model:
                    return "🍊 "

                if "Raspberry" in model:
                    return "🍇 "
                else:
                    return "?"

    match True:

        case _ if IS_WSL:
            return "🍀 "

        case _ if IS_WINDOWS:
            return "💻 "

        case _ if IS_MACOS:
            return "🍏 "

        case _ if IS_USERLAND:
            return "🐧 "

        case _ if IS_HIKKAHOST:
            return "🌼 "

        case _ if IS_DOCKER:
            return "🐳 "

        case _:
            return "💎 "


def get_platform_emoji() -> str:
    """
    Returns custom emoji for current platform
    :return: Emoji entity in string
    """

    BASE = "".join(
        (
            "<tg-emoji emoji-id={}>🪐</tg-emoji>",
            "<tg-emoji emoji-id=5352934134618549768>🪐</tg-emoji>",
            "<tg-emoji emoji-id=5352663371290271790>🪐</tg-emoji>",
            "<tg-emoji emoji-id=5350822883314655367>🪐</tg-emoji>",
        )
    )

    match True:

        case _ if IS_HIKKAHOST:
            return BASE.format(5395745114494624362)

        case _ if IS_USERLAND:
            return BASE.format(5458877818031077824)

        case _ if IS_DOCKER:
            return BASE.format(5352678227582152630)

        case _:
            return BASE.format(5393588431026674882)


def uptime() -> int:
    """
    Returns userbot uptime in seconds
    """
    current_uptime = round(time.perf_counter() - init_ts)
    return current_uptime


def formatted_uptime() -> str:
    """
    Returns formatted uptime including days if applicable.
    :return: Formatted uptime
    """
    total_seconds = uptime()
    days, remainder = divmod(total_seconds, 86400)
    time_formatted = str(timedelta(seconds=remainder))
    if days > 0:
        return f"{days} day(s), {time_formatted}"
    return time_formatted


def get_ram_usage() -> float:
    """Returns current process tree memory usage in MB"""
    try:
        import psutil

        current_process = psutil.Process(os.getpid())
        mem = current_process.memory_info()[0] / 2.0**20
        for child in current_process.children(recursive=True):
            mem += child.memory_info()[0] / 2.0**20
        return round(mem, 1)
    except Exception:
        return 0


def get_ram_usage_system() -> dict:
    """
    Get system-wide RAM usage information
    :return: Dictionary with used, total in MB and percent
    """
    try:
        import psutil

        vm = psutil.virtual_memory()
        return {
            "percent": round(vm.percent, 1),
            "used": round(vm.used / 1024 / 1024),
            "total": round(vm.total / 1024 / 1024),
        }
    except Exception:
        return {"error": "Failed to get RAM usage"}


def get_swap_usage() -> dict:
    """
    Get swap usage information
    :return: Dictionary with used, total in MB and percent, or error string
    """
    try:
        import psutil

        swap = psutil.swap_memory()
        if swap.total == 0:
            return {"error": "Swap is not configured on this system"}
        return {
            "percent": round(swap.percent, 1),
            "used": round(swap.used / 1024 / 1024),
            "total": round(swap.total / 1024 / 1024),
        }
    except Exception:
        return {"error": "Failed to get swap usage"}


def get_cpu_usage():
    """
    Get CPU usage percentage using system-wide metrics
    Falls back to psutil.cpu_percent() to avoid /proc/stat permission issues
    """
    import psutil

    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        return f"{cpu_percent:.2f}"
    except PermissionError:
        try:
            cpu_percent = psutil.cpu_percent(interval=0)
            return f"{cpu_percent:.2f}" if cpu_percent != 0 else "0.00"
        except Exception:
            return "0.00"
    except Exception:
        return "0.00"


init_ts = time.perf_counter()

get_platform_name = get_named_platform


def get_ip_address() -> str:
    """
    Get the public IP address
    :return: IP address string
    """
    try:
        import requests

        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        return response.json()["ip"]
    except Exception:
        return "Unknown"


def get_disk_usage() -> dict:
    """
    Get disk usage information
    :return: Dictionary with total, used, free in GB
    """
    try:
        import psutil

        disk = psutil.disk_usage("/")
        return {
            "total": round(disk.total / (1024**3), 2),
            "used": round(disk.used / (1024**3), 2),
            "free": round(disk.free / (1024**3), 2),
            "percent": disk.percent,
        }
    except Exception:
        return {"total": 0, "used": 0, "free": 0, "percent": 0}
