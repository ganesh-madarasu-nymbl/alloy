import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _path(var: str, default: str) -> Path:
    path = Path(os.getenv(var, default))
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class Settings:
    model: str = field(default_factory=lambda: os.getenv("ALLOY_MODEL", "openai/gpt-oss-120b"))
    # Any OpenAI-compatible endpoint serves non-Claude models; Groq has a no-card free tier.
    llm_base_url: str = field(default_factory=lambda: os.getenv("ALLOY_LLM_BASE_URL", "https://api.groq.com/openai/v1"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    # Free tiers cap tokens per minute, and a request counts its output allowance against that cap.
    max_tokens: int = field(default_factory=lambda: int(os.getenv("ALLOY_MAX_TOKENS", "2048")))
    valency_mcp_url: str = field(default_factory=lambda: os.getenv("VALENCY_MCP_URL", ""))
    valency_token: str = field(default_factory=lambda: os.getenv("VALENCY_TOKEN", ""))
    bond_backend: str = field(default_factory=lambda: os.getenv("ALLOY_BOND_BACKEND", "http"))
    cache_dir: Path = field(default_factory=lambda: _path("ALLOY_CACHE_DIR", "cache"))
    run_dir: Path = field(default_factory=lambda: _path("ALLOY_RUN_DIR", "runs"))
    memory_dir: Path = field(default_factory=lambda: _path("ALLOY_MEMORY_DIR", "memory"))
    # A public deployment shares one model key with every visitor: smaller budgets, an optional
    # passcode for live literature, and a daily cap on live runs across all sessions.
    public: bool = field(default_factory=lambda: os.getenv("ALLOY_PUBLIC", "").lower() in {"1", "true", "yes"})
    live_passcode: str = field(default_factory=lambda: os.getenv("ALLOY_LIVE_PASSCODE", ""))
    live_runs_per_day: int = field(default_factory=lambda: int(os.getenv("ALLOY_LIVE_RUNS_PER_DAY", "40")))

    @property
    def max_runs(self) -> int:
        return 120 if self.public else 500

    @property
    def max_minutes(self) -> float:
        return 10.0 if self.public else 60.0

    @property
    def bond_configured(self) -> bool:
        if self.bond_backend == "codex":
            return shutil.which("codex") is not None
        if self.bond_backend == "http":
            return bool(self.valency_mcp_url and (self.valency_token or os.getenv("VALENCY_REFRESH_TOKEN")))
        return bool(self.valency_mcp_url)


settings = Settings()
