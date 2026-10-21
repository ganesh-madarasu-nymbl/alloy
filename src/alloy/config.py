import os
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
    model: str = field(default_factory=lambda: os.getenv("ALLOY_MODEL", "claude-opus-5-5"))
    valency_mcp_url: str = field(default_factory=lambda: os.getenv("VALENCY_MCP_URL", ""))
    valency_token: str = field(default_factory=lambda: os.getenv("VALENCY_TOKEN", ""))
    cache_dir: Path = field(default_factory=lambda: _path("ALLOY_CACHE_DIR", "cache"))
    run_dir: Path = field(default_factory=lambda: _path("ALLOY_RUN_DIR", "runs"))
    memory_dir: Path = field(default_factory=lambda: _path("ALLOY_MEMORY_DIR", "memory"))

    @property
    def bond_configured(self) -> bool:
        return bool(self.valency_mcp_url)


settings = Settings()
