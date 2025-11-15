from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from backend.app.config.settings import AppConfig
from backend.app.services.analysis import (
    ChunkAnalysis,
    ComplianceLLMClient,
    OpenRouterConfig,
    OpenRouterError,
)
from backend.app.services.context_builder import ContextBundle, ContextSlice


def test_chunk_analysis_normalizes_lists():
    payload = {
        "flag": "red",
        "severity_score": 80,
        "regulation_references": [" Part-145.A.30(c) ", ""],
        "findings": "Details",
        "gaps": [" Gap A ", ""],
        "citations": {"manual_section": "4.2", "regulation_sections": [" AMC 145.A.30 "]},
        "recommendations": [" Fix it ", ""],
        "needs_additional_context": False,
    }
    analysis = ChunkAnalysis(**payload)
    normalized = analysis.normalize()

    assert normalized["flag"] == "RED"
    assert normalized["severity_score"] == 80
    assert normalized["regulation_references"] == ["Part-145.A.30(c)"]
    assert normalized["gaps"] == ["Gap A"]
    assert normalized["recommendations"] == ["Fix it"]
    assert normalized["citations"]["regulation_sections"] == ["AMC 145.A.30"]


class DummyHTTPClient:
    def __init__(self, response: httpx.Response):
        self.response = response
        self.closed = False

    def post(self, *args, **kwargs):
        return self.response

    def close(self):
        self.closed = True


def _build_bundle() -> ContextBundle:
    focus = ContextSlice(
        label="Focus",
        source="manual",
        content="Manual focus text",
        token_count=10,
        metadata={"section_path": ["Manual", "Section 1"]},
    )
    return ContextBundle(focus=focus)


class StubChunk(SimpleNamespace):
    pass


def test_compliance_llm_client_parses_response(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL_COMPLIANCE", "test-model")

    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "flag": "GREEN",
                            "severity_score": 15,
                            "regulation_references": ["Part-145.A.30"],
                            "findings": "Looks good.",
                            "gaps": [],
                            "citations": {
                                "manual_section": "4.2",
                                "regulation_sections": ["Part-145.A.30"],
                            },
                            "recommendations": ["None"],
                            "needs_additional_context": False,
                        }
                    )
                }
            }
        ]
    }

    response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://example.com"),
        json=payload,
    )
    client = ComplianceLLMClient(
        AppConfig(),
        http_client=DummyHTTPClient(response),
        router_config=OpenRouterConfig(api_key="test", model="mock"),
    )

    result = client.analyze(
        StubChunk(chunk_id="chunk-1", chunk_index=0),
        _build_bundle(),
    )
    assert result["flag"] == "GREEN"
    assert result["regulation_references"] == ["Part-145.A.30"]


def test_compliance_llm_client_raises_on_invalid_json(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    bad_payload = {"choices": [{"message": {"content": "not-json"}}]}
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "https://example.com"),
        json=bad_payload,
    )
    client = ComplianceLLMClient(
        AppConfig(),
        http_client=DummyHTTPClient(response),
        router_config=OpenRouterConfig(api_key="test", model="mock", max_retries=1),
    )

    with pytest.raises(OpenRouterError):
        client.analyze(StubChunk(chunk_id="id", chunk_index=0), _build_bundle())

