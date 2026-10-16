# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/Heroku-userbot/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import logging
import socket

logger = logging.getLogger(__name__)


def get_hostname() -> str:
    """
    Get the hostname of the machine
    :return: Hostname
    """
    try:
        return socket.gethostname()
    except Exception:
        return "Unknown"


def resolve_domain(domain: str) -> str:
    """
    Resolve domain to IP address
    :param domain: Domain name
    :return: IP address or error message
    """
    try:
        return socket.gethostbyname(domain)
    except socket.gaierror:
        return "Unable to resolve"


def is_port_open(host: str, port: int) -> bool:
    """
    Check if a port is open on a host
    :param host: Hostname or IP
    :param port: Port number
    :return: True if open, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_network_interfaces() -> dict[str, str]:
    """
    Get network interfaces and their IP addresses
    :return: Dictionary of interface: IP
    """
    import psutil

    try:
        interfaces = {}
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interfaces[name] = addr.address
                    break
        return interfaces
    except Exception:
        return {}
