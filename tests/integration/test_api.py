from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from aikit.serving.api import create_app


@pytest.fixture
def client(index_path: str) -> Iterator[TestClient]:
    app = create_app(
        "project/app.yaml", overrides={"components.vector_store.path": index_path}, offline=True
    )
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        data = next(line for line in block.splitlines() if line.startswith("data: "))
        events.append(json.loads(data[len("data: ") :]))
    return events


def test_health_and_components(client: TestClient) -> None:
    assert client.get("/health").json()["flow"] == "AgentFlow"
    assert "hybrid" in client.get("/components").json()["retriever"]


def test_ingest_then_query(client: TestClient) -> None:
    assert client.post("/ingest").json()["documents"] == 4
    body = client.post("/query", json={"input": "How long is the warranty on electronics?"}).json()
    assert body["status"] == "completed"
    assert body["citations"]


def test_sse_stream(client: TestClient) -> None:
    client.post("/ingest")
    response = client.post("/runs", json={"input": "How long does express shipping take?"})
    assert response.headers["content-type"].startswith("text/event-stream")
    types = [e["type"] for e in parse_sse(response.text)]
    assert types[0] == "start" and types[-1] == "done" and "tool_call" in types


def test_principal_groups_drive_acl(client: TestClient) -> None:
    client.post("/ingest")
    question = {"input": "What goodwill credit can support leads grant?", "stream": False}
    public = client.post("/runs", json=question).json()
    lead = client.post("/runs", json=question, headers={"X-User-Groups": "support_leads"}).json()
    assert not any(c["source"].endswith("internal_escalation.md") for c in public["citations"])
    assert any(c["source"].endswith("internal_escalation.md") for c in lead["citations"])


def test_approval_round_trip(client: TestClient) -> None:
    paused = client.post(
        "/runs",
        json={"input": "Please issue a refund for order A-1001, amount 80.", "stream": False},
    ).json()
    assert paused["status"] == "awaiting_approval"
    assert client.post("/runs/unknown/approve", json={"approved": True}).status_code == 404

    done = client.post(f"/runs/{paused['run_id']}/approve", json={"approved": True}).json()
    assert done["status"] == "completed"
    assert [c["name"] for c in done["tool_calls"]] == ["issue_refund"]


def test_validation_error(client: TestClient) -> None:
    assert client.post("/query", json={"input": ""}).status_code == 422
