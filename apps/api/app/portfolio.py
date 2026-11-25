import ipaddress
import json
import re
import socket
import time
from dataclasses import dataclass
from urllib import robotparser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.parsing import clean_text

USER_AGENT = "CareerFitBot/0.1"
MAX_URL_LENGTH = 2048
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_ROBOTS_BYTES = 512 * 1024
MAX_REDIRECTS = 3
MAX_TEXT_CHARS = 100_000
TIMEOUT_SECONDS = 10
# The whole fetch, redirects included. TIMEOUT_SECONDS only bounds each wait, so a site sending a byte
# every few seconds could otherwise hold a worker for hours.
MAX_FETCH_SECONDS = 30

_TEXT_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_NOISE_TAGS = ("script", "style", "noscript", "nav", "footer", "aside", "form", "svg")
_DEFAULT_PORTS = {"http": 80, "https": 443}
_GITHUB_USERNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")

# Redirects are followed by hand so that every hop passes the address check.
_client = httpx.Client(
    timeout=TIMEOUT_SECONDS,
    follow_redirects=False,
    trust_env=False,
    headers={"User-Agent": USER_AGENT},
)


class RejectedLink(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message


class LinkFetchFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FetchedPage:
    status_code: int
    content_type: str
    body: bytes


_INVALID_LINK = RejectedLink("invalid_link", "Enter a full public web address starting with https://.")


def normalize_link(url: str) -> str:
    """Checks the shape of the address. Where it resolves to is checked again at fetch time."""
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise _INVALID_LINK
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise _INVALID_LINK from exc
    if (
        parts.scheme not in _DEFAULT_PORTS
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or (port is not None and port != _DEFAULT_PORTS[parts.scheme])
    ):
        raise _INVALID_LINK
    try:
        literal = ipaddress.ip_address(parts.hostname)
    except ValueError:
        if "." not in parts.hostname or parts.hostname.endswith((".local", ".internal", ".localhost")):
            raise _INVALID_LINK from None
    else:
        if not _is_public(literal):
            raise _INVALID_LINK
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def is_linkedin(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def read_link(url: str) -> str:
    username = _github_username(url)
    if username:
        return _read_github(username)
    return _read_page(url)


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    target = mapped if mapped is not None else ip
    return target.is_global and not target.is_multicast


def _resolve_public_ip(host: str) -> str:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise LinkFetchFailed("link_unreachable") from exc
    addresses = {str(info[4][0]) for info in infos}
    if not addresses:
        raise LinkFetchFailed("link_unreachable")
    # Any private answer blocks the host, so a mixed DNS response can't reach internal services.
    if not all(_is_public(ipaddress.ip_address(address)) for address in addresses):
        raise LinkFetchFailed("link_blocked")
    return sorted(addresses)[0]


def _fetch(
    url: str,
    max_bytes: int = MAX_PAGE_BYTES,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> FetchedPage:
    current = url
    deadline = time.monotonic() + MAX_FETCH_SECONDS
    for _ in range(MAX_REDIRECTS + 1):
        try:
            current = normalize_link(current)
        except RejectedLink as exc:
            raise LinkFetchFailed("link_blocked") from exc
        parts = urlsplit(current)
        host = parts.hostname or ""
        ip = _resolve_public_ip(host)
        # Connecting to the checked address stops DNS changing between the check and the request.
        ip_host = f"[{ip}]" if ":" in ip else ip
        target = urlunsplit((parts.scheme, ip_host, parts.path or "/", parts.query, ""))
        request_headers = {"Host": parts.netloc, **(headers or {})}
        try:
            with _client.stream(
                "GET",
                target,
                headers=request_headers,
                extensions={"sni_hostname": host},
            ) as response:
                if response.is_redirect and follow_redirects:
                    location = response.headers.get("location")
                    if not location:
                        raise LinkFetchFailed("link_unreachable")
                    current = urljoin(current, location)
                    continue
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise LinkFetchFailed("link_too_large")
                    if time.monotonic() > deadline:
                        raise LinkFetchFailed("link_unreachable")
                return FetchedPage(
                    response.status_code,
                    response.headers.get("content-type", "").split(";")[0].strip().lower(),
                    bytes(body),
                )
        except httpx.HTTPError as exc:
            raise LinkFetchFailed("link_unreachable") from exc
    raise LinkFetchFailed("link_unreachable")


def _robots_allow(url: str) -> bool:
    parts = urlsplit(url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    try:
        page = _fetch(robots_url, max_bytes=MAX_ROBOTS_BYTES)
    except LinkFetchFailed:
        return False
    if 400 <= page.status_code < 500:
        return True
    if page.status_code != 200:
        return False
    parser = robotparser.RobotFileParser()
    parser.parse(page.body.decode("utf-8", errors="replace").splitlines())
    return parser.can_fetch(USER_AGENT, url)


def _read_page(url: str) -> str:
    if not _robots_allow(url):
        raise LinkFetchFailed("link_disallowed")
    page = _fetch(url)
    if page.status_code != 200:
        raise LinkFetchFailed("link_unreachable")
    if page.content_type not in _TEXT_CONTENT_TYPES:
        raise LinkFetchFailed("link_unsupported")
    if page.content_type == "text/plain":
        return clean_text(page.body.decode("utf-8", errors="replace"), MAX_TEXT_CHARS)

    soup = BeautifulSoup(page.body, "html.parser")
    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    return clean_text(root.get_text("\n", strip=True), MAX_TEXT_CHARS)


def _github_username(url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in ("github.com", "www.github.com"):
        return None
    segments = [segment for segment in parts.path.split("/") if segment]
    if segments and _GITHUB_USERNAME.match(segments[0]):
        return segments[0]
    raise LinkFetchFailed("github_not_found")


def _read_github(username: str) -> str:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    # No redirects: following one could send the token to another host.
    page = _fetch(
        f"https://api.github.com/users/{username}/repos?per_page=100&sort=pushed&type=owner",
        headers=headers,
        follow_redirects=False,
    )
    if page.status_code == 404:
        raise LinkFetchFailed("github_not_found")
    if page.status_code != 200:
        raise LinkFetchFailed("github_unavailable")

    lines = [f"GitHub profile: {username}"]
    for repo in json.loads(page.body):
        if repo.get("fork"):
            continue
        language = f" ({repo['language']})" if repo.get("language") else ""
        description = f": {repo['description']}" if repo.get("description") else ""
        lines.append(f"{repo['name']}{language}{description}")
    return clean_text("\n".join(lines), MAX_TEXT_CHARS) if len(lines) > 1 else ""
