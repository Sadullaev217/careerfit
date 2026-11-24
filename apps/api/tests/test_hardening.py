"""Strict CORS, security headers, request limits and the settings deployed servers refuse."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import rate_limit
from app.config import Settings
from app.routers import account, analyses, billing, documents, market, notifications
from tests.helpers import auth_headers

WEB = "http://localhost:3000"


def test_cors_allows_only_the_listed_web_addresses(client: TestClient) -> None:
    allowed = client.options(
        "/me",
        headers={
            "Origin": WEB,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == WEB
    # Bearer tokens, never cookies: browsers are told not to send credentials.
    assert "access-control-allow-credentials" not in allowed.headers

    other = client.options(
        "/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}
    )
    assert other.status_code == 400
    assert "access-control-allow-origin" not in other.headers


def test_cors_refuses_unlisted_methods_and_headers(client: TestClient) -> None:
    for extra in (
        {"Access-Control-Request-Method": "TRACE"},
        {"Access-Control-Request-Headers": "x-anything"},
    ):
        response = client.options(
            "/me", headers={"Origin": WEB, "Access-Control-Request-Method": "GET", **extra}
        )
        assert response.status_code == 400


def test_responses_carry_security_headers(client: TestClient) -> None:
    for response in (
        client.get("/health"),
        client.get("/me"),
        client.get("/me", headers=auth_headers()),
    ):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert (
            response.headers["content-security-policy"]
            == "default-src 'none'; frame-ancestors 'none'"
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        # Only deployed servers, which are always behind https, send HSTS.
        assert "strict-transport-security" not in response.headers


def test_an_account_is_limited(client: TestClient) -> None:
    small = FastAPI()

    @small.get("/costly", dependencies=[Depends(rate_limit.per_user("costly", "2/minute"))])
    def costly() -> dict[str, bool]:
        return {"ok": True}

    test = TestClient(small)
    assert [test.get("/costly", headers=auth_headers()).status_code for _ in range(2)] == [200, 200]
    refused = test.get("/costly", headers=auth_headers())
    assert refused.status_code == 429
    assert refused.json()["detail"]["code"] == "rate_limited"
    assert int(refused.headers["retry-after"]) > 0
    # Another account has its own allowance.
    assert test.get("/costly", headers=auth_headers("other-user")).status_code == 200


COSTLY_ROUTES = {
    ("POST", "/documents"),
    ("POST", "/documents/portfolio"),
    ("POST", "/analyses"),
    ("POST", "/analyses/{analysis_id}/tailored-rewrites"),
    ("GET", "/analyses/{analysis_id}/report.pdf"),
    ("POST", "/billing/checkout"),
    ("POST", "/billing/portal"),
    ("POST", "/billing/app-store/sync"),
    ("POST", "/billing/app-store/report"),
    ("DELETE", "/account"),
    ("GET", "/market/roles"),
    ("GET", "/market/requirements"),
    ("PUT", "/push-tokens"),
    ("DELETE", "/push-tokens/{token}"),
}


ROUTERS = [
    module.router for module in (account, analyses, billing, documents, market, notifications)
]


def test_costly_routes_count_per_account() -> None:
    limited = {
        (method, route.path)
        for router in ROUTERS
        for route in router.routes
        if isinstance(route, APIRoute)
        and any(
            d.call.__qualname__ == "per_user.<locals>.dependency"
            for d in route.dependant.dependencies
        )
        for method in route.methods
    }
    assert limited >= COSTLY_ROUTES


def test_an_address_is_limited_across_routes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rate_limit, "PER_ADDRESS", rate_limit.parse("3/minute"))
    assert [client.get("/me").status_code for _ in range(3)] == [401, 401, 401]
    response = client.get("/me", headers={"Origin": WEB})
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "rate_limited"
    # The web app can read the refusal and the wait.
    assert response.headers["access-control-allow-origin"] == WEB
    assert "retry-after" in response.headers["access-control-expose-headers"].lower()
    # Uptime checks and Stripe's webhook are never counted.
    assert client.get("/health").status_code == 200


def test_a_broken_counter_store_lets_requests_through(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object) -> bool:
        raise ConnectionError("redis is down")

    monkeypatch.setattr(rate_limit._limiter, "hit", broken)
    assert client.get("/me", headers=auth_headers()).status_code == 200


def test_limits_can_be_turned_off_for_local_work(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rate_limit, "PER_ADDRESS", rate_limit.parse("1/minute"))
    monkeypatch.setattr(rate_limit.settings, "rate_limits_enabled", False)
    assert [
        client.get("/health").status_code,
        client.get("/me").status_code,
        client.get("/me").status_code,
    ] == [200, 401, 401]


DEPLOYED_OK = {
    "environment": "production",
    "supabase_url": "https://project.supabase.co",
    "supabase_secret_key": "server-key",
    "web_url": "https://careerfit.example",
    "allowed_origins": ["https://careerfit.example"],
    "rate_limit_storage": "rediss://cache.example:6380/0",
    "malware_scanner": "clamav",
}


def settings_with(**changes: object) -> Settings:
    return Settings(_env_file=None, **{**DEPLOYED_OK, **changes})  # type: ignore[arg-type]


def test_safe_deployed_settings_are_accepted() -> None:
    assert settings_with().deployed
    assert settings_with(environment="staging").deployed


@pytest.mark.parametrize(
    ("changes", "named"),
    [
        ({"debug": True}, "DEBUG"),
        ({"supabase_url": "http://project.supabase.co"}, "SUPABASE_URL"),
        ({"supabase_secret_key": ""}, "SUPABASE_SECRET_KEY"),
        ({"web_url": "http://careerfit.example"}, "WEB_URL"),
        ({"allowed_origins": ["http://careerfit.example"]}, "ALLOWED_ORIGINS"),
        ({"rate_limit_storage": "memory://"}, "RATE_LIMIT_STORAGE"),
        ({"rate_limits_enabled": False}, "RATE_LIMITS_ENABLED"),
        ({"malware_scanner": "off"}, "MALWARE_SCANNER"),
        ({"llm_provider": "openrouter", "openrouter_api_key": ""}, "OPENROUTER_API_KEY"),
        ({"llm_provider": "demo"}, "LLM_PROVIDER=demo"),
    ],
)
def test_deployed_servers_refuse_unsafe_settings(changes: dict[str, object], named: str) -> None:
    with pytest.raises(ValueError, match=named):
        settings_with(**changes)


def test_a_single_instance_may_keep_rate_limits_in_memory() -> None:
    assert settings_with(rate_limit_storage="memory://", single_instance=True).deployed


def test_only_the_demo_may_skip_virus_scanning() -> None:
    assert settings_with(malware_scanner="off", demo_mode=True).deployed
    with pytest.raises(ValueError, match="MALWARE_SCANNER"):
        settings_with(malware_scanner="off", single_instance=True)


def test_unsafe_settings_are_fine_on_a_laptop() -> None:
    local = Settings(
        _env_file=None, environment="development", debug=True, rate_limit_storage="memory://"
    )  # type: ignore[call-arg]
    assert not local.deployed


def test_any_origin_is_refused_everywhere() -> None:
    with pytest.raises(ValueError, match="exact addresses"):
        Settings(_env_file=None, allowed_origins=["*"])  # type: ignore[call-arg]
