import asyncio
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.utils.validators import UnsafeURL, resolve_public

MAX_BYTES = 1_000_000
PAGE_HINT = re.compile(r"service|product|solution|about|industr|what-we-do|pricing", re.I)


class WebsiteUnavailable(Exception):
    pass


@dataclass
class Page:
    url: str
    text: str
    links: list[httpx.URL]


async def fetch(url: httpx.URL) -> tuple[httpx.URL, bytes]:
    async with asyncio.timeout(10):
        for _ in range(5):
            addresses = await resolve_public(url)
            for address in addresses:
                target = url.copy_with(host=address)
                try:
                    async with httpx.AsyncClient(trust_env=False, timeout=4) as client:
                        async with client.stream(
                            "GET", target,
                            headers={
                                "Host": url.netloc.decode("ascii"),
                                "Accept": "text/html,application/xhtml+xml",
                                "Accept-Encoding": "identity",
                                "User-Agent": "WebsiteLinkAnalysis/1.0",
                            },
                            extensions={"sni_hostname": url.raw_host.decode("ascii").rstrip(".")},
                        ) as response:
                            if response.status_code in {301, 302, 303, 307, 308}:
                                location = response.headers.get("location")
                                if not location:
                                    raise WebsiteUnavailable("The website sent an invalid redirect.")
                                url = url.join(location).copy_with(fragment=None)
                                break
                            response.raise_for_status()
                            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                            if content_type not in {"text/html", "application/xhtml+xml"}:
                                raise WebsiteUnavailable("The URL must serve an HTML page.")
                            if response.headers.get("content-encoding", "identity").lower() != "identity":
                                raise WebsiteUnavailable("The website requires unsupported content encoding.")
                            body = bytearray()
                            async for chunk in response.aiter_raw():
                                body.extend(chunk)
                                if len(body) > MAX_BYTES:
                                    raise WebsiteUnavailable("The website page exceeds the size limit.")
                            return url, bytes(body)
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    if address == addresses[-1]:
                        raise
    raise WebsiteUnavailable("The website exceeded the redirect limit.")


def parse_page(url: httpx.URL, html: bytes, limit: int) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    metadata = []
    for name in ("description", "og:site_name", "og:description"):
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", property=name)
        if tag and tag.get("content"):
            metadata.append(tag["content"])

    links = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        try:
            link = url.join(href).copy_with(query=None, fragment=None)
        except (httpx.InvalidURL, ValueError):
            continue
        if (
            link.scheme == url.scheme and link.netloc == url.netloc and not link.userinfo
            and link.path != url.path and PAGE_HINT.search(link.path) and link not in links
        ):
            links.append(link)
            if len(links) == 2:
                break

    for tag in soup(["head", "script", "style", "noscript", "svg", "nav", "footer", "iframe", "template"]):
        tag.decompose()
    content = soup.find("main") or soup.body or soup
    lines = [title, *metadata, *content.stripped_strings]
    normalized = dict.fromkeys(" ".join(line.split()) for line in lines if line.strip())
    return Page(str(url), "\n".join(normalized)[:limit], links)


async def load_page(url: httpx.URL, limit: int) -> Page:
    try:
        resolved, html = await fetch(url)
    except (httpx.HTTPError, httpx.InvalidURL, OSError, TimeoutError) as exc:
        raise WebsiteUnavailable("The website could not be reached or denied access.") from exc
    return await asyncio.to_thread(parse_page, resolved, html, limit)


async def extract_website(url: str) -> list[Page]:
    home = await load_page(httpx.URL(url).copy_with(fragment=None), 10_000)
    extras = await asyncio.gather(
        *(load_page(link, 4_000) for link in home.links), return_exceptions=True
    )
    pages = []
    seen = set()
    for page in [home, *extras]:
        if isinstance(page, (WebsiteUnavailable, UnsafeURL)):
            continue
        if isinstance(page, BaseException):
            raise page
        if len(page.text) >= 40 and page.text not in seen:
            pages.append(page)
            seen.add(page.text)
    if not pages:
        raise WebsiteUnavailable("The website did not provide enough readable content.")
    return pages
