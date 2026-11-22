"""Smoke test: the agent answers GET /, and POST /ask runs the agent loop with no API key and no
network - the tool really executes and the no-key answer says so."""

import os

from fastapi.testclient import TestClient

from main import NO_KEY_MESSAGE, app

client = TestClient(app)


def test_root_answers_200():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_calls_the_tool_and_returns_the_labelled_stub():
    body = client.post("/ask", json={"question": "how long is this sentence"}).json()
    assert body["mode"] == "stub"
    # The stub model asked for word_count, the SDK ran it for real, and the stub answered from that real result.
    assert body["answer"] == NO_KEY_MESSAGE.format(tool_output="5 words, 25 characters")


def test_rejects_an_empty_or_oversized_question():
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={"question": "x" * 501}).status_code == 422


def test_works_without_any_api_key():
    assert "OPENAI_API_KEY" not in os.environ
