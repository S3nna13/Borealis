"""Borealis Configuration Management — YAML-based config with validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModelConfig:
    """Model selection configuration."""
    preferred_model: str = "core"  # spark, core, apex
    default_context_size: int = 32768
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9


@dataclass
class BackendConfig:
    """Backend runtime configuration."""
    preferred_backend: str = "auto"  # auto, mlx, vllm, llama_cpp_gguf, onnx_runtime, tensorrt_llm, remote_borealis
    remote_endpoint: str = ""
    remote_api_key: str = ""
    fallback_enabled: bool = True


@dataclass
class MemoryConfig:
    """Memory management configuration."""
    memory_policy: str = "balanced"  # conservative, balanced, performance, frontier
    kv_cache_gb: float = 4.0
    weights_offload_threshold: float = 0.8  # RAM usage threshold for offloading
    enable_kv_quantization: bool = True
    kv_quant_bits: int = 4  # 2, 4, or 8


@dataclass
class CUAConfig:
    """Computer Use configuration."""
    cua_mode: str = "local_basic"  # verifier_only, remote_driver, browser_only, local_basic, local_full, multimodal_full
    screenshot_interval: float = 1.0
    action_timeout: int = 30
    enable_audit_log: bool = True
    audit_log_path: str = ""


@dataclass
class SafetyConfig:
    """Safety and governance configuration."""
    safety_mode: str = "balanced"  # strict, balanced, permissive
    approval_mode: str = "inline"  # inline, always_ask, auto_approve_safe
    require_polaris_gates: bool = True
    max_skill_runtime: int = 300
    block_destructive_ops: bool = True


@dataclass
class TelemetryConfig:
    """Telemetry and observability configuration."""
    enabled: bool = True
    anonymize: bool = True
    export_format: str = "json"  # json, otel, langfuse
    export_endpoint: str = ""
    log_level: str = "INFO"


@dataclass
class MCPConfig:
    """MCP server configuration."""
    enabled: bool = True
    transport: str = "streamable-http"  # stdio, streamable-http, sse
    host: str = "127.0.0.1"
    port: int = 8000
    mount_path: str = "/mcp"
    allow_external_servers: bool = True
    trusted_servers: list[str] = field(default_factory=list)


@dataclass
class BorealisConfig:
    """Top-level Borealis configuration."""
    version: str = "2.0.0"
    model: ModelConfig = field(default_factory=ModelConfig)
    backend: BackendConfig = field(default_factory=BackendConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    cua: CUAConfig = field(default_factory=CUAConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serialisable dict."""
        return asdict(self)

    def to_yaml(self) -> str:
        """Convert to YAML string."""
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BorealisConfig":
        """Create config from dict, handling nested structures."""
        config = cls()
        if "model" in data:
            config.model = ModelConfig(**{k: v for k, v in data["model"].items() if k in ModelConfig.__dataclass_fields__})
        if "backend" in data:
            config.backend = BackendConfig(**{k: v for k, v in data["backend"].items() if k in BackendConfig.__dataclass_fields__})
        if "memory" in data:
            config.memory = MemoryConfig(**{k: v for k, v in data["memory"].items() if k in MemoryConfig.__dataclass_fields__})
        if "cua" in data:
            config.cua = CUAConfig(**{k: v for k, v in data["cua"].items() if k in CUAConfig.__dataclass_fields__})
        if "safety" in data:
            config.safety = SafetyConfig(**{k: v for k, v in data["safety"].items() if k in SafetyConfig.__dataclass_fields__})
        if "telemetry" in data:
            config.telemetry = TelemetryConfig(**{k: v for k, v in data["telemetry"].items() if k in TelemetryConfig.__dataclass_fields__})
        if "mcp" in data:
            config.mcp = MCPConfig(**{k: v for k, v in data["mcp"].items() if k in MCPConfig.__dataclass_fields__})
        return config

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "BorealisConfig":
        """Create config from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data or {})


class ConfigManager:
    """Manages Borealis configuration lifecycle."""

    DEFAULT_CONFIG_DIR = os.path.expanduser("~/.borealis")
    DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_CONFIG_DIR, "config.yaml")

    def __init__(self, config_path: str | None = None) -> None:
        self._config_path = config_path or self.DEFAULT_CONFIG_FILE
        self._config = BorealisConfig()

    @property
    def config(self) -> BorealisConfig:
        """Get current configuration."""
        return self._config

    @property
    def config_path(self) -> str:
        """Get configuration file path."""
        return self._config_path

    def load(self) -> BorealisConfig:
        """Load configuration from file."""
        path = Path(self._config_path)
        if not path.exists():
            return self._config

        try:
            yaml_str = path.read_text()
            self._config = BorealisConfig.from_yaml(yaml_str)
        except Exception:
            # If config is malformed, use defaults
            self._config = BorealisConfig()

        return self._config

    def save(self) -> None:
        """Save configuration to file."""
        path = Path(self._config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._config.to_yaml())

    def get(self, key_path: str) -> Any:
        """Get a config value by dot-path (e.g. 'model.preferred_model')."""
        parts = key_path.split(".")
        obj: Any = self._config
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                raise KeyError(f"Config key not found: {key_path}")
        return obj

    def set(self, key_path: str, value: Any) -> None:
        """Set a config value by dot-path."""
        parts = key_path.split(".")
        obj: Any = self._config
        for part in parts[:-1]:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                raise KeyError(f"Config key not found: {key_path}")

        final_key = parts[-1]
        if hasattr(obj, final_key):
            setattr(obj, final_key, value)
        elif isinstance(obj, dict):
            obj[final_key] = value
        else:
            raise KeyError(f"Config key not found: {key_path}")

    def reset(self) -> None:
        """Reset to default configuration."""
        self._config = BorealisConfig()

    def diff(self, other: "BorealisConfig") -> dict[str, Any]:
        """Show differences between two configs."""
        diffs: dict[str, Any] = {}
        self_dict = self._config.to_dict()
        other_dict = other.to_dict()
        self._compare_dicts(self_dict, other_dict, "", diffs)
        return diffs

    def _compare_dicts(
        self, a: dict, b: dict, prefix: str, diffs: dict
    ) -> None:
        """Recursively compare two dicts."""
        all_keys = set(a.keys()) | set(b.keys())
        for key in all_keys:
            path = f"{prefix}.{key}" if prefix else key
            if key not in a:
                diffs[path] = {"old": None, "new": b[key]}
            elif key not in b:
                diffs[path] = {"old": a[key], "new": None}
            elif isinstance(a[key], dict) and isinstance(b[key], dict):
                self._compare_dicts(a[key], b[key], path, diffs)
            elif a[key] != b[key]:
                diffs[path] = {"old": a[key], "new": b[key]}
