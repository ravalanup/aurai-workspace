import asyncio
import json
from pathlib import Path

import httpx
import yaml
from jsonschema import Draft202012Validator

from functions.knowledge_search import Tools, format_results

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "contracts" / "knowledge-service.openapi.yaml").read_text()
)
TOKEN = {"access_token": "user-token"}

PASSAGE = {
    "chunk_id": "c1",
    "text": "Gates open at 8:00.",
    "score": 0.91,
    "source": {
        "title": "Opening procedures",
        "collection": "ops-reports",
        "classification": "internal",
        "freshness": "2026-11-01",
    },
}


def response_validator(name):
    schema = {"$ref": f"#/components/schemas/{name}", "components": CONTRACT["components"]}
    return Draft202012Validator(schema)


def fake_service(seen, status=200, results=None):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        payload = {"results": [PASSAGE] if results is None else results}
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


def tool(transport=None, url="http://knowledge.test"):
    t = Tools(transport=transport)
    t.valves.knowledge_service_url = url
    return t


def run(coro):
    return asyncio.run(coro)


def test_contract_parses_and_declares_search():
    assert CONTRACT["openapi"].startswith("3.1")
    assert "/v1/search" in CONTRACT["paths"]
    assert CONTRACT["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"


def test_example_passage_matches_contract():
    response_validator("SearchResponse").validate({"results": [PASSAGE]})


def test_request_matches_contract_and_carries_user_token():
    seen = []
    out = run(tool(fake_service(seen)).search_knowledge("opening time", __oauth_token__=TOKEN))
    request = seen[0]
    body = json.loads(request.content)
    response_validator("SearchRequest").validate(body)
    assert request.headers["authorization"] == "Bearer user-token"
    assert "[1] Opening procedures (ops-reports, internal, ingested 2026-11-01)" in out
    assert "Gates open at 8:00." in out


def test_collections_are_forwarded():
    seen = []
    run(tool(fake_service(seen)).search_knowledge("x", collections=["ops-reports"], __oauth_token__=TOKEN))
    assert json.loads(seen[0].content)["collections"] == ["ops-reports"]


def test_not_configured_is_clearly_unavailable():
    out = run(Tools().search_knowledge("x", __oauth_token__=TOKEN))
    assert "not available yet" in out


def test_missing_session_token():
    seen = []
    out = run(tool(fake_service(seen)).search_knowledge("x"))
    assert "sign in" in out and seen == []


def test_forbidden_and_errors_do_not_leak_or_guess():
    assert "do not have access" in run(tool(fake_service([], status=403)).search_knowledge("x", __oauth_token__=TOKEN))
    assert "do not guess" in run(tool(fake_service([], status=503)).search_knowledge("x", __oauth_token__=TOKEN))


def test_unreachable_service():
    def boom(request):
        raise httpx.ConnectError("down")

    out = run(tool(httpx.MockTransport(boom)).search_knowledge("x", __oauth_token__=TOKEN))
    assert "could not be reached" in out


def test_empty_results_tell_the_model_not_to_answer_from_memory():
    assert "nothing was found" in format_results([])
