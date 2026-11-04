import json
import socket
from collections.abc import Callable

import httpx
import pytest

from app import portfolio
from app.config import settings
from app.portfolio import LinkFetchFailed, RejectedLink, normalize_link, read_link

PUBLIC_IP = "93.184.216.34"
Handler = Callable[[httpx.Request], httpx.Response]


def use_transport(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": portfolio.USER_AGENT},
        follow_redirects=False,
    )
    monkeypatch.setattr(portfolio, "_client", client)


def use_dns(monkeypatch: pytest.MonkeyPatch, answers: dict[str, list[str]]) -> None:
    def fake(host: str, *_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        addresses = answers.get(host, [PUBLIC_IP])
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 0)) for a in addresses]

    monkeypatch.setattr(portfolio.socket, "getaddrinfo", fake)


def site(pages: dict[str, httpx.Response]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return pages.get(request.url.path, httpx.Response(404))

    return handler


def failure(url: str) -> str:
    with pytest.raises(LinkFetchFailed) as caught:
        read_link(url)
    return caught.value.code


HTML = httpx.Response(
    200,
    headers={"content-type": "text/html; charset=utf-8"},
    text="""<html><head><script>steal()</script><style>a{}</style></head><body>
    <nav>Menu</nav><main><h1>Case study</h1><p>Rebuilt the billing system</p></main>
    <footer>Copyright</footer></body></html>""",
)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "javascript:alert(1)",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://[::1]/",
        "http://localhost/",
        "http://printer.local/",
        "https://user:pass@example.com/",
        "https://example.com:8443/",
        "not a url",
        "https://example.com/" + "a" * 2100,
    ],
)
def test_rejects_unsafe_addresses(url: str) -> None:
    with pytest.raises(RejectedLink):
        normalize_link(url)


def test_accepts_normal_address_and_drops_fragment() -> None:
    assert normalize_link(" https://example.com/work?x=1#top ") == "https://example.com/work?x=1"


def test_reads_main_text_only(monkeypatch: pytest.MonkeyPatch) -> None:
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, site({"/robots.txt": httpx.Response(404), "/work": HTML}))
    text = read_link("https://example.com/work")
    assert "Rebuilt the billing system" in text
    assert "steal" not in text
    assert "Menu" not in text
    assert "Copyright" not in text


def test_connects_to_the_checked_address_not_the_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return HTML if request.url.path == "/work" else httpx.Response(404)

    use_dns(monkeypatch, {})
    use_transport(monkeypatch, handler)
    read_link("https://example.com/work")
    assert all(request.url.host == PUBLIC_IP for request in seen)
    assert all(request.headers["host"] == "example.com" for request in seen)
    assert seen[-1].extensions["sni_hostname"] == "example.com"
    assert seen[-1].headers["user-agent"] == portfolio.USER_AGENT


@pytest.mark.parametrize(
    "addresses",
    [["10.0.0.5"], ["127.0.0.1"], ["169.254.169.254"], ["::1"], ["::ffff:127.0.0.1"], [PUBLIC_IP, "10.0.0.5"]],
)
def test_blocks_names_that_resolve_to_internal_addresses(
    monkeypatch: pytest.MonkeyPatch, addresses: list[str]
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    use_dns(monkeypatch, {"sneaky.example.com": addresses})
    use_transport(monkeypatch, handler)
    # Robots can't be read from a blocked host, which reports as disallowed before any request.
    assert failure("https://sneaky.example.com/") == "link_disallowed"
    assert requests == []


@pytest.mark.parametrize(
    "location",
    ["http://169.254.169.254/latest/meta-data/", "http://127.0.0.1/", "https://internal.example.com/"],
)
def test_blocks_redirects_to_internal_addresses(
    monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    requested_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_hosts.append(request.headers["host"])
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": location})

    use_dns(monkeypatch, {"internal.example.com": ["10.1.2.3"]})
    use_transport(monkeypatch, handler)
    assert failure("https://example.com/go") in ("link_blocked",)
    assert set(requested_hosts) == {"example.com"}


def test_stops_after_too_many_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(302, headers={"location": "/loop"})

    use_dns(monkeypatch, {})
    use_transport(monkeypatch, handler)
    assert failure("https://example.com/loop") == "link_unreachable"


def test_respects_robots_disallow(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {
        "/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /private"),
        "/private": HTML,
    }
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, site(pages))
    assert failure("https://example.com/private") == "link_disallowed"


def test_robots_server_error_means_do_not_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, site({"/robots.txt": httpx.Response(500), "/work": HTML}))
    assert failure("https://example.com/work") == "link_disallowed"


def test_rejects_oversized_page(monkeypatch: pytest.MonkeyPatch) -> None:
    big = httpx.Response(
        200, headers={"content-type": "text/html"}, content=b"x" * (portfolio.MAX_PAGE_BYTES + 1)
    )
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, site({"/robots.txt": httpx.Response(404), "/big": big}))
    assert failure("https://example.com/big") == "link_too_large"


def test_rejects_non_text_content(monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-")
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, site({"/robots.txt": httpx.Response(404), "/cv.pdf": pdf}))
    assert failure("https://example.com/cv.pdf") == "link_unsupported"


def test_network_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    use_dns(monkeypatch, {})
    use_transport(monkeypatch, handler)
    with pytest.raises(LinkFetchFailed):
        portfolio._fetch("https://example.com/")


REPOS = [
    {"name": "ledger", "language": "Python", "description": "Double-entry ledger", "fork": False},
    {"name": "forked", "language": "C", "description": "Not mine", "fork": True},
    {"name": "notes", "language": None, "description": None, "fork": False},
]


def github(status: int = 200, body: object = REPOS) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["host"] == "api.github.com"
        assert request.url.path == "/users/octocat/repos"
        return httpx.Response(status, content=json.dumps(body))

    return handler


def test_github_uses_official_api_and_skips_forks(monkeypatch: pytest.MonkeyPatch) -> None:
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, github())
    text = read_link("https://github.com/octocat")
    assert "ledger (Python): Double-entry ledger" in text
    assert "notes" in text
    assert "forked" not in text


def test_github_repo_url_reads_the_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, github())
    assert "ledger" in read_link("https://github.com/octocat/ledger")


def test_github_token_is_sent_only_to_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"location": "https://evil.example.com/"})

    monkeypatch.setattr(settings, "github_token", "test-token")
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, handler)
    assert failure("https://github.com/octocat") == "github_unavailable"
    assert [request.headers["host"] for request in seen] == ["api.github.com"]


def test_github_missing_user(monkeypatch: pytest.MonkeyPatch) -> None:
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, github(status=404, body={}))
    assert failure("https://github.com/octocat") == "github_not_found"


def test_github_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, github(status=403, body={}))
    assert failure("https://github.com/octocat") == "github_unavailable"


def test_github_profile_with_no_repos_has_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    use_dns(monkeypatch, {})
    use_transport(monkeypatch, github(body=[]))
    assert read_link("https://github.com/octocat") == ""


def test_linkedin_detection() -> None:
    assert portfolio.is_linkedin("https://www.linkedin.com/in/someone")
    assert portfolio.is_linkedin("https://linkedin.com/in/someone")
    assert not portfolio.is_linkedin("https://notlinkedin.com/in/someone")
    assert not portfolio.is_linkedin("https://linkedin.com.evil.example/in/someone")
