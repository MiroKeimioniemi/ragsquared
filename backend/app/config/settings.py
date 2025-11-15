from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration payload for the semantic chunker."""

    size: int
    overlap: int
    tokenizer: str
    max_section_tokens: int


@dataclass(frozen=True)
class ContextBuilderConfig:
    """Configuration payload controlling contextual retrieval budgets."""

    manual_neighbor_window: int
    manual_token_budget: int
    regulation_top_k: int
    regulation_token_budget: int
    guidance_top_k: int
    guidance_token_budget: int
    evidence_top_k: int
    evidence_token_budget: int
    total_token_budget: int
    tokenizer: str


@dataclass
class AppConfig:
    """Centralized configuration loader."""

    flask_env: str = field(default_factory=lambda: os.getenv("FLASK_ENV", "development"))
    flask_debug: bool = field(default_factory=lambda: os.getenv("FLASK_DEBUG", "1") == "1")
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/app.db")
    )
    data_root: str = field(default_factory=lambda: os.getenv("DATA_ROOT", "./data"))
    # LLM API Configuration (supports OpenRouter and Featherless)
    llm_api_key: str = field(
        default_factory=lambda: os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("FEATHERLESS_API_KEY", "")
    )
    llm_api_base_url: str = field(
        default_factory=lambda: os.getenv("LLM_API_BASE_URL") or os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")
    )
    llm_model_compliance: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL_COMPLIANCE") or os.getenv("OPENROUTER_MODEL_COMPLIANCE", "openrouter/horizon-beta")
    )
    # Backward compatibility
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model_compliance: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL_COMPLIANCE", "openrouter/horizon-beta")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    )
    embedding_api_base_url: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_API_BASE_URL") or os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")
    )
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "800")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "80")))
    chunk_tokenizer: str = field(
        default_factory=lambda: os.getenv("CHUNK_TOKENIZER", "cl100k_base")
    )
    chunk_max_section_tokens: int = field(
        default_factory=lambda: int(os.getenv("CHUNK_MAX_SECTION_TOKENS", "4000"))
    )
    context_manual_window: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_MANUAL_WINDOW", "1"))
    )
    context_manual_token_limit: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_MANUAL_TOKEN_LIMIT", "1200"))
    )
    context_regulation_top_k: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_REGULATION_TOP_K", "10"))
    )
    context_regulation_token_limit: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_REGULATION_TOKEN_LIMIT", "2000"))
    )
    context_guidance_top_k: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_GUIDANCE_TOP_K", "5"))
    )
    context_guidance_token_limit: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_GUIDANCE_TOKEN_LIMIT", "1500"))
    )
    context_evidence_top_k: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_EVIDENCE_TOP_K", "2"))
    )
    context_evidence_token_limit: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_EVIDENCE_TOKEN_LIMIT", "1000"))
    )
    context_total_token_limit: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_TOTAL_TOKEN_LIMIT", "6000"))
    )
    context_tokenizer: str = field(
        default_factory=lambda: os.getenv("CONTEXT_TOKENIZER", "cl100k_base")
    )
    refinement_max_attempts: int = field(
        default_factory=lambda: int(os.getenv("REFINEMENT_MAX_ATTEMPTS", "1"))
    )
    refinement_manual_window: int = field(
        default_factory=lambda: int(os.getenv("REFINEMENT_MANUAL_WINDOW", "2"))
    )
    refinement_token_multiplier: float = field(
        default_factory=lambda: float(os.getenv("REFINEMENT_TOKEN_MULTIPLIER", "1.5"))
    )
    refinement_include_evidence: bool = field(
        default_factory=lambda: os.getenv("REFINEMENT_INCLUDE_EVIDENCE", "1") == "1"
    )
    # Rate limiting configuration
    chunk_processing_delay: float = field(
        default_factory=lambda: float(os.getenv("CHUNK_PROCESSING_DELAY", "5.0"))
    )
    rate_limit_backoff_base: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_BACKOFF_BASE", "10.0"))
    )
    rate_limit_max_wait: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_MAX_WAIT", "120.0"))
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    secret_key: str = field(
        default_factory=lambda: os.getenv("FLASK_SECRET_KEY", "hackathon-secret")
    )
    config_version: str = "1.0"
    extra: dict[str, str] = field(default_factory=dict)

    def to_flask_dict(self) -> dict[str, object]:
        base = asdict(self)
        base.update(
            {
                "SQLALCHEMY_DATABASE_URI": self.database_url,
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            }
        )
        return base

    @property
    def sqlite_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.replace("sqlite:///", ""))
        return Path("data/app.db")

    @property
    def chunking(self) -> ChunkingConfig:
        """Return the semantic chunker configuration block."""

        return ChunkingConfig(
            size=self.chunk_size,
            overlap=self.chunk_overlap,
            tokenizer=self.chunk_tokenizer,
            max_section_tokens=self.chunk_max_section_tokens,
        )

    @property
    def context_builder(self) -> ContextBuilderConfig:
        """Return the context builder configuration block."""

        return ContextBuilderConfig(
            manual_neighbor_window=self.context_manual_window,
            manual_token_budget=self.context_manual_token_limit,
            regulation_top_k=self.context_regulation_top_k,
            regulation_token_budget=self.context_regulation_token_limit,
            guidance_top_k=self.context_guidance_top_k,
            guidance_token_budget=self.context_guidance_token_limit,
            evidence_top_k=self.context_evidence_top_k,
            evidence_token_budget=self.context_evidence_token_limit,
            total_token_budget=self.context_total_token_limit,
            tokenizer=self.context_tokenizer or self.chunk_tokenizer,
        )

