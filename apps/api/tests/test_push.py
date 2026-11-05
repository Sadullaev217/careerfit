import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app import push
from app.config import settings
from tests.helpers import OTHER_USER_ID, USER_ID, FakeStore, auth_headers

TOKEN = "ExponentPushToken[abcDEF123_-xyz]"
OTHER_TOKEN = "ExpoPushToken[zyx987]"
ANALYSIS_ID = "33333333-3333-3333-3333-333333333333"


# --- Registering a phone ---


def test_a_phone_registers_its_token(client: TestClient, fake_store: FakeStore) -> None:
    response = client.put(
        "/push-tokens",
        json={"token": TOKEN, "platform": "android", "language": "ru"},
        headers=auth_headers(),
    )
    assert response.status_code == 204
    assert fake_store.push_tokens[TOKEN] == {"user_id": USER_ID, "platform": "android", "language": "ru"}


def test_language_defaults_to_english(client: TestClient, fake_store: FakeStore) -> None:
    client.put("/push-tokens", json={"token": TOKEN, "platform": "ios"}, headers=auth_headers())
    assert fake_store.push_tokens[TOKEN]["language"] == "en"


@pytest.mark.parametrize(
    "body",
    [
        {"token": "not-a-token", "platform": "android"},
        {"token": "ExponentPushToken[]", "platform": "android"},
        {"token": "ExponentPushToken[has space]", "platform": "android"},
        {"token": f"ExponentPushToken[{'a' * 300}]", "platform": "android"},
        {"token": TOKEN, "platform": "windows"},
        {"token": TOKEN, "platform": "android", "language": "de"},
    ],
)
def test_anything_but_an_expo_token_is_refused(
    client: TestClient, fake_store: FakeStore, body: dict[str, Any]
) -> None:
    assert client.put("/push-tokens", json=body, headers=auth_headers()).status_code == 422
    assert fake_store.push_tokens == {}


def test_registering_needs_a_signed_in_person(client: TestClient, fake_store: FakeStore) -> None:
    response = client.put("/push-tokens", json={"token": TOKEN, "platform": "android"})
    assert response.status_code == 401
    assert fake_store.push_tokens == {}


def test_a_phone_that_switches_account_takes_its_token_along(
    client: TestClient, fake_store: FakeStore
) -> None:
    client.put("/push-tokens", json={"token": TOKEN, "platform": "android"}, headers=auth_headers())
    client.put(
        "/push-tokens",
        json={"token": TOKEN, "platform": "android"},
        headers=auth_headers(OTHER_USER_ID),
    )
    assert fake_store.list_push_tokens(USER_ID) == []
    assert [row["token"] for row in fake_store.list_push_tokens(OTHER_USER_ID)] == [TOKEN]


def test_signing_out_removes_the_token(client: TestClient, fake_store: FakeStore) -> None:
    fake_store.save_push_token(USER_ID, TOKEN, "android", "en")
    response = client.delete(f"/push-tokens/{TOKEN}", headers=auth_headers())
    assert response.status_code == 204
    assert fake_store.push_tokens == {}


def test_one_account_cannot_remove_another_accounts_token(
    client: TestClient, fake_store: FakeStore
) -> None:
    fake_store.save_push_token(USER_ID, TOKEN, "android", "en")
    client.delete(f"/push-tokens/{TOKEN}", headers=auth_headers(OTHER_USER_ID))
    assert TOKEN in fake_store.push_tokens


# --- Sending ---


class Recorder:
    def __init__(self, reply: dict[str, Any] | None = None, status: int = 200, error: bool = False):
        self.requests: list[httpx.Request] = []
        self.reply = reply if reply is not None else {"data": []}
        self.status = status
        self.error = error

    def client(self) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            if self.error:
                raise httpx.ConnectError("refused")
            return httpx.Response(self.status, json=self.reply)

        return httpx.Client(transport=httpx.MockTransport(handler))

    @property
    def messages(self) -> list[dict[str, Any]]:
        return [message for request in self.requests for message in json.loads(request.content)]


def test_each_phone_gets_a_message_in_its_own_language() -> None:
    store = FakeStore()
    store.save_push_token(USER_ID, TOKEN, "android", "en")
    store.save_push_token(USER_ID, OTHER_TOKEN, "ios", "ru")
    store.save_push_token(OTHER_USER_ID, "ExponentPushToken[someoneelse]", "ios", "en")
    recorder = Recorder()
    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=store, http=recorder.client())
    assert len(recorder.requests) == 1
    assert str(recorder.requests[0].url) == settings.expo_push_url
    by_token = {message["to"]: message for message in recorder.messages}
    assert set(by_token) == {TOKEN, OTHER_TOKEN}
    assert by_token[TOKEN]["title"] == "Your CareerFit report is ready"
    assert by_token[OTHER_TOKEN]["title"] == "Ваш отчёт CareerFit готов"
    assert by_token[TOKEN]["data"] == {"analysisId": ANALYSIS_ID}
    assert by_token[TOKEN]["channelId"] == push.ANDROID_CHANNEL


def test_the_message_carries_nothing_but_fixed_text_and_the_id() -> None:
    store = FakeStore()
    store.save_push_token(USER_ID, TOKEN, "android", "en")
    recorder = Recorder()
    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=store, http=recorder.client())
    message = recorder.messages[0]
    assert set(message) == {"to", "title", "body", "data", "sound", "channelId"}
    assert set(message["data"]) == {"analysisId"}


def test_no_phones_means_no_request() -> None:
    recorder = Recorder()
    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=FakeStore(), http=recorder.client())
    assert recorder.requests == []


def test_a_phone_that_uninstalled_the_app_is_forgotten() -> None:
    store = FakeStore()
    store.save_push_token(USER_ID, TOKEN, "android", "en")
    store.save_push_token(USER_ID, OTHER_TOKEN, "ios", "en")
    reply = {
        "data": [
            {"status": "error", "message": "gone", "details": {"error": "DeviceNotRegistered"}},
            {"status": "ok", "id": "ticket"},
        ]
    }
    recorder = Recorder(reply)
    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=store, http=recorder.client())
    sent_first = recorder.messages[0]["to"]
    assert sent_first not in store.push_tokens
    assert len(store.push_tokens) == 1


def test_other_ticket_errors_keep_the_token() -> None:
    store = FakeStore()
    store.save_push_token(USER_ID, TOKEN, "android", "en")
    reply = {"data": [{"status": "error", "details": {"error": "MessageRateExceeded"}}]}
    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=store, http=Recorder(reply).client())
    assert TOKEN in store.push_tokens


@pytest.mark.parametrize("failure", ["network", "server"])
def test_a_failed_send_never_raises(failure: str) -> None:
    store = FakeStore()
    store.save_push_token(USER_ID, TOKEN, "android", "en")
    recorder = Recorder(status=500) if failure == "server" else Recorder(error=True)
    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=store, http=recorder.client())
    assert TOKEN in store.push_tokens


def test_a_broken_store_never_raises() -> None:
    class BrokenStore(FakeStore):
        def list_push_tokens(self, user_id: str) -> list[dict[str, Any]]:
            raise httpx.ConnectError("database down")

    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=BrokenStore(), http=Recorder().client())


def test_the_access_token_is_sent_only_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore()
    store.save_push_token(USER_ID, TOKEN, "android", "en")
    recorder = Recorder()
    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=store, http=recorder.client())
    assert "authorization" not in recorder.requests[0].headers
    monkeypatch.setattr(settings, "expo_access_token", "expo-test-value")
    push.send_report_ready(USER_ID, ANALYSIS_ID, push_store=store, http=recorder.client())
    assert recorder.requests[1].headers["authorization"] == "Bearer expo-test-value"
