"""Sponsor clients against a fake urlopen: request shapes and response parsing, no network."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

import pytest

from ledger import config
from sponsors import bfl, liquid, nimble


class FakeResponse:
    def __init__(self, body: bytes | str | dict):
        if isinstance(body, dict):
            body = json.dumps(body)
        self.body = body.encode() if isinstance(body, str) else body

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc_info) -> None:
        return None


class FakeNetwork:
    """Replays queued responses in order and records every request it was handed."""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request, timeout=None):
        if isinstance(request, str):
            request = urllib.request.Request(request)
        self.requests.append(request)
        if not self.responses:
            raise AssertionError(f"unexpected request to {request.full_url}")
        return FakeResponse(self.responses.pop(0))

    def body(self, index: int) -> dict:
        return json.loads(self.requests[index].data.decode())


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(config, "_loaded", True)  # a real .env must never leak into these tests
    for name in ("NIMBLE_API_KEY", "LIQUID_API_KEY", "LIQUID_BASE_URL", "LIQUID_MODEL", "BFL_API_KEY",
                 "RAWTREE_API_KEY", "RAWTREE_DATABASE"):
        monkeypatch.delenv(name, raising=False)


def install(monkeypatch, responses: list) -> FakeNetwork:
    network = FakeNetwork(responses)
    monkeypatch.setattr(urllib.request, "urlopen", network)
    return network


# ---- nimble -----------------------------------------------------------------------


def test_nimble_search_body_and_results(monkeypatch):
    monkeypatch.setenv("NIMBLE_API_KEY", "nk-test")
    results = [{"title": "One", "url": "https://a.example", "description": "d", "content": "c"}]
    network = install(monkeypatch, [{"results": results}])
    assert nimble.search("agents", max_results=2, full_content=False, depth="lite") == results
    request = network.requests[0]
    assert request.full_url == f"{nimble.BASE}/search" and request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer nk-test"
    assert network.body(0) == {"query": "agents", "max_results": 2, "search_depth": "lite", "full_content": False}


def test_nimble_search_missing_results_is_empty(monkeypatch):
    monkeypatch.setenv("NIMBLE_API_KEY", "nk-test")
    install(monkeypatch, [{}])
    assert nimble.search("agents") == []


def test_nimble_extract_synchronous_shape(monkeypatch):
    monkeypatch.setenv("NIMBLE_API_KEY", "nk-test")
    network = install(monkeypatch, [{"data": {"markdown": "# Page"}}])
    assert nimble.extract("https://a.example") == {"data": {"markdown": "# Page"}}
    assert len(network.requests) == 1
    assert network.body(0) == {"url": "https://a.example", "render": True}


def test_nimble_extract_task_and_poll_shape(monkeypatch):
    monkeypatch.setenv("NIMBLE_API_KEY", "nk-test")
    monkeypatch.setattr(nimble.time, "sleep", lambda seconds: None)
    network = install(monkeypatch, [
        {"task_id": "t-1"},
        {"status": "running"},
        {"status": "Completed"},
        {"markdown": "polled page"},
    ])
    assert nimble.extract("https://a.example") == {"markdown": "polled page"}
    urls = [request.full_url for request in network.requests]
    assert urls == [f"{nimble.BASE}/extract", f"{nimble.BASE}/tasks/t-1", f"{nimble.BASE}/tasks/t-1",
                    f"{nimble.BASE}/tasks/t-1/results"]
    assert [request.get_method() for request in network.requests[1:]] == ["GET", "GET", "GET"]


def test_nimble_extract_failed_task_raises(monkeypatch):
    monkeypatch.setenv("NIMBLE_API_KEY", "nk-test")
    install(monkeypatch, [{"task_id": "t-2"}, {"status": "failed"}])
    with pytest.raises(RuntimeError, match="t-2"):
        nimble.extract("https://a.example")


def test_nimble_observe_search_and_extract(monkeypatch):
    monkeypatch.setenv("NIMBLE_API_KEY", "nk-test")
    install(monkeypatch, [{"results": [
        {"title": "First", "url": "https://one.example", "description": "about one", "content": "body one"},
        {"title": "Second", "url": "https://two.example", "description": "about two", "content": "body two"},
    ]}])
    text, source = nimble.observe("agents")
    assert source == "nimble search 'agents' (2 results)"
    assert text == ("# First\nhttps://one.example\nabout one\nbody one\n\n"
                    "# Second\nhttps://two.example\nabout two\nbody two")

    install(monkeypatch, [{"data": {"parsing": {"markdown": "extracted text"}}}])
    text, source = nimble.observe("agents", url="https://one.example")
    assert (text, source) == ("extracted text", "nimble extract https://one.example")


def test_nimble_without_key_raises(monkeypatch):
    install(monkeypatch, [])
    with pytest.raises(RuntimeError, match="NIMBLE_API_KEY"):
        nimble.search("agents")


# ---- liquid -----------------------------------------------------------------------


def completion(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 50, "completion_tokens": 9}}


def test_liquid_distill_clips_to_three_lines(monkeypatch):
    network = install(monkeypatch, [completion("- one\n* two\nthree\n\n- four\n- five")])
    delta, usage = liquid.distill("raw page " * 10, "- old fact", "agents")
    assert delta == "- one\n- two\n- three"
    assert usage == {"prompt_tokens": 50, "completion_tokens": 9}
    body = network.body(0)
    assert network.requests[0].full_url == f"{liquid.DEFAULT_BASE}/chat/completions"
    assert body["model"] == liquid.DEFAULT_MODEL and body["messages"][0]["content"] == liquid.SYSTEM
    assert "- old fact" in body["messages"][1]["content"]
    assert network.requests[0].get_header("Authorization") is None  # local Ollama: no key header


def test_liquid_distill_empty_reply_is_no_change(monkeypatch):
    install(monkeypatch, [completion("  \n\n")])
    delta, _usage = liquid.distill("raw", "", "agents")
    assert delta == "- no change"


def test_liquid_distill_clips_raw_page(monkeypatch):
    network = install(monkeypatch, [completion("- x")])
    liquid.distill("a" * 500, "", "agents", max_chars=100)
    user = network.body(0)["messages"][1]["content"]
    assert "(500 bytes, clipped to 100)" in user and "a" * 101 not in user


def test_liquid_hosted_key_sets_bearer(monkeypatch):
    monkeypatch.setenv("LIQUID_API_KEY", "lq-test")
    monkeypatch.setenv("LIQUID_BASE_URL", "https://liquid.example/v1/")
    network = install(monkeypatch, [completion("- y")])
    liquid.chat([{"role": "user", "content": "hi"}], max_tokens=1)
    assert network.requests[0].full_url == "https://liquid.example/v1/chat/completions"
    assert network.requests[0].get_header("Authorization") == "Bearer lq-test"
    assert liquid.configured() is True


# ---- black forest labs ------------------------------------------------------------


@dataclass
class FakeEntry:
    title: str
    paused: bool = False


def test_bfl_generate_submit_poll_download(monkeypatch):
    monkeypatch.setenv("BFL_API_KEY", "bfl-test")
    monkeypatch.setattr(bfl.time, "sleep", lambda seconds: None)
    network = install(monkeypatch, [
        {"id": "job-1", "polling_url": "https://api.bfl.ai/v1/get_result?id=job-1"},
        {"status": "Pending"},
        {"status": "Ready", "result": {"sample": "https://cdn.bfl.example/sample.jpg"}},
        b"\xff\xd8JPEGBYTES",
    ])
    assert bfl.generate("a ledger on a desk", width=512, height=384) == b"\xff\xd8JPEGBYTES"
    submit, first_poll, second_poll, download = network.requests
    assert submit.full_url == bfl.ENDPOINT and submit.get_method() == "POST"
    assert submit.get_header("X-key") == "bfl-test"
    assert network.body(0) == {"prompt": "a ledger on a desk", "width": 512, "height": 384}
    assert first_poll.full_url == second_poll.full_url == "https://api.bfl.ai/v1/get_result?id=job-1"
    assert first_poll.get_header("X-key") == "bfl-test"
    assert download.full_url == "https://cdn.bfl.example/sample.jpg"


def test_bfl_generate_error_raises(monkeypatch):
    monkeypatch.setenv("BFL_API_KEY", "bfl-test")
    monkeypatch.setattr(bfl.time, "sleep", lambda seconds: None)
    install(monkeypatch, [{"polling_url": "https://api.bfl.ai/poll"}, {"status": "Error"}])
    with pytest.raises(RuntimeError, match="flux failed"):
        bfl.generate("x")


def test_bfl_prompt_from_digest():
    entries = [FakeEntry(f"entry {index}") for index in range(10)]
    entries.append(FakeEntry("resume here", paused=True))
    entries.append(FakeEntry("gate `H1` **PASS** # done"))
    prompt = bfl.prompt_from_digest(entries, topic_hint="Hackathon day.")
    assert prompt.startswith("Editorial illustration")
    assert "no text or letters" in prompt
    # paused entries are dropped first, then the last 8 headlines are taken
    assert "work: entry 3; entry 4; entry 5; entry 6; entry 7; entry 8; entry 9; gate H1 PASS  done." in prompt
    assert "entry 2" not in prompt and "resume here" not in prompt
    assert prompt.endswith("Hackathon day.")


def test_bfl_without_key_makes_no_request(monkeypatch):
    install(monkeypatch, [])
    assert bfl.configured() is False
    with pytest.raises(RuntimeError, match="BFL_API_KEY"):
        bfl.generate("x")
