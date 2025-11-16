from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, conint, field_validator

from ..config.settings import AppConfig
from ..prompts.compliance import SYSTEM_PROMPT, build_user_prompt
from .analysis_base import AnalysisClient
from .context_builder import ContextBundle

logger = logging.getLogger(__name__)


class CitationBlock(BaseModel):
    manual_section: str | None = None
    regulation_sections: list[str] = Field(default_factory=list)

    @field_validator("regulation_sections", mode="after")
    @classmethod
    def _strip_reg_refs(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value]


class ChunkAnalysis(BaseModel):
    flag: str
    severity_score: conint(ge=0, le=100) = 0  # type: ignore[assignment]
    regulation_references: list[str] = Field(default_factory=list)
    findings: str = Field(min_length=1)
    gaps: list[str] = Field(default_factory=list)
    citations: CitationBlock
    recommendations: list[str] = Field(default_factory=list)
    needs_additional_context: bool = False
    context_query: str | None = None

    @field_validator("gaps", mode="before")
    @classmethod
    def _normalize_gaps(cls, value: list[Any] | None) -> list[str]:
        """Normalize gaps to list of strings, handling both string and object formats.
        
        The LLM should return gaps as an array of strings, but sometimes returns objects.
        This validator handles both formats gracefully.
        """
        if not value:
            return []
        normalized = []
        for item in value:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, dict):
                # Extract gap description from various possible field names
                gap_text = (
                    item.get("gap_name") or
                    item.get("gap_item") or
                    item.get("gap_description") or
                    item.get("description") or
                    str(item)  # Fallback to string representation
                )
                if gap_text:
                    normalized.append(str(gap_text))
                    # Log when we normalize from object format to help track LLM compliance
                    logger.debug(
                        "Normalized gap from object format: %s -> %s",
                        item,
                        gap_text
                    )
            else:
                # Fallback: convert to string
                normalized.append(str(item))
        return normalized

    @field_validator("regulation_references", "gaps", "recommendations", mode="after")
    @classmethod
    def _strip_entries(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value]

    @field_validator("flag", mode="before")
    @classmethod
    def _normalize_flag(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"RED", "YELLOW", "GREEN"}:
            raise ValueError("flag must be RED, YELLOW, or GREEN")
        return normalized

    def normalize(self) -> dict[str, Any]:
        data = self.model_dump()
        data["regulation_references"] = [ref for ref in data["regulation_references"] if ref]
        data["gaps"] = [gap for gap in data["gaps"] if gap]
        data["recommendations"] = [rec for rec in data["recommendations"] if rec]
        return data


class OpenRouterError(RuntimeError):
    """Raised when the LLM API client cannot satisfy a request."""


@dataclass
class LLMConfig:
    """Configuration for LLM API (supports OpenRouter, Featherless, and other OpenAI-compatible APIs)."""
    api_key: str
    model: str
    api_base_url: str
    max_retries: int = 2
    timeout: float = 60.0
    
    @property
    def api_url(self) -> str:
        """Construct the full API URL for chat completions."""
        base = self.api_base_url.rstrip("/")
        if "/chat/completions" not in base:
            return f"{base}/chat/completions"
        return base


class ComplianceLLMClient(AnalysisClient):
    """Analysis client that calls LLM APIs (OpenRouter, Featherless, or other OpenAI-compatible) for structured JSON responses."""

    def __init__(
        self,
        app_config: AppConfig,
        *,
        http_client: httpx.Client | None = None,
        llm_config: LLMConfig | None = None,
    ):
        # Determine API key and base URL
        api_key = app_config.llm_api_key or app_config.openrouter_api_key
        api_base_url = app_config.llm_api_base_url
        
        # Auto-detect Featherless API (keys start with 'rc_')
        if api_key.startswith("rc_"):
            api_base_url = "https://api.featherless.ai/v1"
            logger.info("Detected Featherless API key, using Featherless base URL")
        elif not api_base_url or api_base_url == "https://openrouter.ai/api/v1":
            # Default to OpenRouter
            api_base_url = "https://openrouter.ai/api/v1"
        
        self.config = llm_config or LLMConfig(
            api_key=api_key,
            model=app_config.llm_model_compliance or app_config.openrouter_model_compliance,
            api_base_url=api_base_url,
        )
        if not self.config.api_key:
            raise ValueError("LLM API key is required for ComplianceLLMClient.")
        self._client = http_client or httpx.Client(timeout=self.config.timeout)

    def analyze(self, chunk, context: ContextBundle) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(context)},
        ]
        payload = {
            "model": self.config.model,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        import time
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                api_url = self.config.api_url
                logger.debug(f"Calling LLM API: {api_url} with model: {self.config.model}")
                response = self._client.post(api_url, headers=headers, json=payload)
                
                # Handle rate limits (429) with exponential backoff
                if response.status_code == 429:
                    # Try to get Retry-After header, otherwise use exponential backoff
                    retry_after_header = response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            retry_after = int(retry_after_header)
                        except ValueError:
                            retry_after = None
                    else:
                        retry_after = None
                    
                    # Calculate wait time: use Retry-After if available, otherwise exponential backoff
                    if retry_after:
                        wait_time = min(retry_after, 120)  # Respect Retry-After, max 120s
                    else:
                        # Exponential backoff: 10s, 20s, 40s, etc., capped at 120s
                        backoff_base = 10.0
                        wait_time = min(backoff_base * (2 ** (attempt - 1)), 120)
                    
                    logger.warning(
                        "Rate limit hit (429), waiting %s seconds before retry %s/%s",
                        wait_time,
                        attempt,
                        self.config.max_retries,
                    )
                    if attempt < self.config.max_retries:
                        time.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()
                
                # Check for 404 errors which often indicate model not found
                if response.status_code == 404:
                    error_body = response.text
                    try:
                        error_json = response.json()
                        error_message = error_json.get("error", {}).get("message", error_body)
                    except Exception:
                        error_message = error_body
                    logger.error(
                        f"404 Not Found from OpenRouter API. This usually means the model '{self.config.model}' "
                        f"does not exist or is not available. Error: {error_message}. "
                        f"Please check: 1) Model name is correct, 2) Model is available on OpenRouter, "
                        f"3) Your API key has access to this model."
                    )
                    response.raise_for_status()
                
                response.raise_for_status()
                content = self._extract_content(response.json())
                # Log the raw content for debugging
                logger.debug(f"LLM raw response (first 500 chars): {content[:500]}")
                try:
                    analysis = ChunkAnalysis.model_validate_json(content)
                    return analysis.normalize()
                except ValidationError as ve:
                    # Log the full content when validation fails - this is critical for debugging
                    logger.error(
                        "Validation failed. LLM returned invalid JSON structure.\n"
                        f"Full response: {content}\n"
                        f"Validation error: {ve}"
                    )
                    raise
            except (httpx.HTTPError, ValidationError, ValueError) as exc:
                last_error = exc
                # For rate limits, add exponential backoff before retry
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                    if attempt < self.config.max_retries:
                        # Exponential backoff: 10s, 20s, 40s, etc., capped at 120s
                        backoff_base = 10.0
                        wait_time = min(backoff_base * (2 ** (attempt - 1)), 120)
                        logger.warning("Rate limit error, waiting %s seconds before retry %s/%s", 
                                     wait_time, attempt + 1, self.config.max_retries)
                        time.sleep(wait_time)
                logger.warning(
                    "Compliance LLM attempt %s/%s failed: %s",
                    attempt,
                    self.config.max_retries,
                    exc,
                )
        raise OpenRouterError(f"Unable to obtain valid analysis: {last_error}") from last_error

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("LLM API response missing choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise ValueError("LLM API response missing message content.")
        
        # Strip markdown code blocks if present (some LLMs wrap JSON in ```json ... ```)
        content = content.strip()
        if content.startswith("```"):
            # Remove opening ```json or ```
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        
        return content

    def close(self) -> None:
        self._client.close()

