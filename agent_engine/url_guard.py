import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_PORTS = {None, 80, 443}


class UnsafeUrl(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


async def resolve(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [info[4][0].split("%")[0] for info in infos]


def is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


def is_official_host(host: str | None, official_domain: str | None) -> bool:
    if not host or not official_domain:
        return False
    host = host.lower().rstrip(".").removeprefix("www.")
    official = official_domain.lower().rstrip(".").removeprefix("www.")
    return host == official or host.endswith("." + official)


async def check_url(url: str, resolver=resolve) -> str:
    """Return the lowercase host if the URL is safe to request, otherwise raise UnsafeUrl.

    Run it for every hop. DNS errors are not hidden: they surface as OSError so the caller
    can treat them like any other network failure.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeUrl("bad_scheme")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrl("userinfo")
    try:
        port = parts.port
    except ValueError:
        raise UnsafeUrl("bad_port") from None
    if port not in ALLOWED_PORTS:
        raise UnsafeUrl("bad_port")
    host = parts.hostname
    if not host:
        raise UnsafeUrl("no_host")

    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        addresses = await resolver(host)
    if not addresses or not all(is_public(address) for address in addresses):
        raise UnsafeUrl("private_address")
    return host.lower()
