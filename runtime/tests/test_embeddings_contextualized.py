"""CO-13 — voyage-context-3 contextualized-embeddings routing (DL-74).

Mocked (no network): is_contextualized; query routes to the contextualized endpoint
with input_type='query'; voyage-3-large stays on /v1/embeddings; embed_grouped
preserves order + sends input_type='document'; the shared retry/backoff fires on a
429 for the contextualized endpoint; the stub (no-key) path returns correctly shaped
nested + flat vectors. Live (env-gated): a real contextualized call returns 1024-dim
float vectors.
"""

from __future__ import annotations

import os

import pytest

from app.config import get_settings
from app.knowledge import embeddings


def _ctx_response(payload: dict, dim: int = 1024) -> dict:
    """A contextualized-endpoint response mirroring the input grouping/order, with
    each chunk's first component encoding its text (so order is verifiable)."""
    return {
        "data": [
            {
                "index": gi,
                "data": [
                    {
                        "index": ci,
                        "embedding": [float(ord(chunk[0])) if chunk else 0.0] + [0.0] * (dim - 1),
                    }
                    for ci, chunk in enumerate(group)
                ],
            }
            for gi, group in enumerate(payload["inputs"])
        ]
    }


def test_is_contextualized():
    assert embeddings.is_contextualized("voyage-context-3")
    assert embeddings.is_contextualized("voyage-context-4")
    assert not embeddings.is_contextualized("voyage-3-large")
    assert not embeddings.is_contextualized("voyage-3")


@pytest.mark.asyncio
async def test_query_routes_to_contextualized_endpoint_as_query(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")
    calls: list[tuple[str, dict]] = []

    async def fake_post(url, payload):
        calls.append((url, payload))
        return _ctx_response(payload)

    monkeypatch.setattr(embeddings, "_post_voyage", fake_post)
    vec = await embeddings.embed("my query", "voyage-context-3")
    url, payload = calls[0]
    assert url == embeddings.VOYAGE_CONTEXT_EMBED_URL
    assert payload["input_type"] == "query"
    assert payload["inputs"] == [["my query"]]
    assert len(vec) == 1024


@pytest.mark.asyncio
async def test_voyage3large_stays_on_flat_endpoint(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")
    calls: list[tuple[str, dict]] = []

    async def fake_post(url, payload):
        calls.append((url, payload))
        return {"data": [{"embedding": [0.2] * 1024} for _ in payload["input"]]}

    monkeypatch.setattr(embeddings, "_post_voyage", fake_post)
    vecs = await embeddings.embed_batch(["a", "b"], "voyage-3-large")
    url, payload = calls[0]
    assert url == embeddings.VOYAGE_EMBED_URL
    assert "input" in payload and "inputs" not in payload  # flat shape unchanged
    assert len(vecs) == 2


@pytest.mark.asyncio
async def test_embed_grouped_preserves_order_as_document(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")
    calls: list[tuple[str, dict]] = []

    async def fake_post(url, payload):
        calls.append((url, payload))
        return _ctx_response(payload)

    monkeypatch.setattr(embeddings, "_post_voyage", fake_post)
    nested = await embeddings.embed_grouped(
        [["alpha", "beta"], ["gamma"]], "voyage-context-3", input_type="document"
    )
    assert calls[0][1]["input_type"] == "document"
    assert [len(g) for g in nested] == [2, 1]
    assert nested[0][0][0] == float(ord("a"))  # alpha
    assert nested[0][1][0] == float(ord("b"))  # beta
    assert nested[1][0][0] == float(ord("g"))  # gamma


@pytest.mark.asyncio
async def test_retry_on_429_contextualized(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", "test-key")

    async def _no_sleep(*_a, **_k):
        return None

    monkeypatch.setattr(embeddings.asyncio, "sleep", _no_sleep)

    class _Resp:
        def __init__(self, status, data=None, headers=None):
            self.status_code = status
            self._data = data or {}
            self.headers = headers or {}

        def json(self):
            return self._data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"http {self.status_code}")

    ok = {"data": [{"index": 0, "data": [{"index": 0, "embedding": [0.1] * 1024}]}]}
    seq = [_Resp(429, headers={"retry-after": "0"}), _Resp(200, ok)]

    class _Client:
        calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def post(self, _url, json=None, headers=None):
            r = seq[min(_Client.calls, len(seq) - 1)]
            _Client.calls += 1
            return r

    monkeypatch.setattr(embeddings.httpx, "AsyncClient", lambda *a, **k: _Client())
    nested = await embeddings.embed_contextualized([["x"]], "voyage-context-3")
    assert _Client.calls == 2  # retried once after the 429
    assert len(nested[0][0]) == 1024


@pytest.mark.asyncio
async def test_stub_nested_and_flat_shapes(monkeypatch):
    monkeypatch.setattr(get_settings(), "voyage_api_key", None)  # no key -> deterministic stub
    nested = await embeddings.embed_contextualized([["a", "b"], ["c"]], "voyage-context-3")
    assert [len(g) for g in nested] == [2, 1]
    assert all(len(v) == 1024 for g in nested for v in g)
    flat = await embeddings.embed_batch(["a", "b"], "voyage-context-3")  # flat batch stays flat
    assert len(flat) == 2 and all(len(v) == 1024 for v in flat)
    single = await embeddings.embed("q", "voyage-context-3")  # query path, stubbed
    assert len(single) == 1024


@pytest.mark.skipif(not os.environ.get("VOYAGE_API_KEY"), reason="needs a real VOYAGE_API_KEY")
@pytest.mark.asyncio
async def test_live_contextualized_returns_1024_float():
    nested = await embeddings.embed_contextualized(
        [["the appeal window is 180 days", "urgent claims decided in 72 hours"]],
        "voyage-context-3",
        input_type="document",
    )
    assert len(nested[0]) == 2
    assert all(len(v) == 1024 and isinstance(v[0], float) for v in nested[0])
