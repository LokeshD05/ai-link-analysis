import asyncio
import ipaddress
import socket

import httpx


class UnsafeURL(ValueError):
    pass


def public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            address = address.ipv4_mapped
        elif (address.is_site_local or address.sixtofour or address.teredo
              or address in ipaddress.ip_network("64:ff9b::/96")):
            return False
    return address.is_global and not (address.is_multicast or address.is_reserved)


def validate_url(url: httpx.URL) -> None:
    port = url.port or (443 if url.scheme == "https" else 80)
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.userinfo
        or port != (443 if url.scheme == "https" else 80)
        or "%" in url.host
    ):
        raise UnsafeURL("Use a public HTTP or HTTPS URL on its standard port.")

    try:
        ipaddress.ip_address(url.host)
    except ValueError:
        if "." not in url.host.rstrip("."):
            raise UnsafeURL("Use a public website hostname.")
    else:
        if not public_ip(url.host):
            raise UnsafeURL("The URL must resolve to public addresses.")


async def resolve_public(url: httpx.URL) -> list[str]:
    validate_url(url)
    port = url.port or (443 if url.scheme == "https" else 80)
    records = await asyncio.get_running_loop().getaddrinfo(
        url.raw_host.decode("ascii"), port, type=socket.SOCK_STREAM
    )
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or not all(public_ip(address) for address in addresses):
        raise UnsafeURL("The URL must resolve to public addresses.")
    return addresses
