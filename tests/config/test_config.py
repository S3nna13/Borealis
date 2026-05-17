"""Tests for Borealis configuration management."""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.config.manager import (
    BorealisConfig,
    ConfigManager,
    ModelConfig,
    BackendConfig,
    MemoryConfig,
    CUAConfig,
    SafetyConfig,
    TelemetryConfig,
    MCPConfig,
)


def test_default_config():
    """Test that default config has expected values."""
    config = BorealisConfig()
    assert config.model.preferred_model == "core"
    assert config.backend.preferred_backend == "auto"
    assert config.memory.memory_policy == "balanced"
    assert config.cua.cua_mode == "local_basic"
    assert config.safety.safety_mode == "balanced"
    assert config.telemetry.enabled is True
    assert config.mcp.enabled is True


def test_config_to_yaml():
    """Test YAML serialization."""
    config = BorealisConfig()
    yaml_str = config.to_yaml()
    assert "preferred_model: core" in yaml_str
    assert "memory_policy: balanced" in yaml_str


def test_config_from_yaml():
    """Test YAML deserialization."""
    yaml_str = """
model:
  preferred_model: apex
  max_tokens: 8192
memory:
  memory_policy: performance
mcp:
  port: 9000
"""
    config = BorealisConfig.from_yaml(yaml_str)
    assert config.model.preferred_model == "apex"
    assert config.model.max_tokens == 8192
    assert config.memory.memory_policy == "performance"
    assert config.mcp.port == 9000
    # Defaults for unspecified values
    assert config.backend.preferred_backend == "auto"


def test_config_manager_load_save():
    """Test config manager load and save."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.yaml")
        mgr = ConfigManager(config_path=config_path)

        # Modify and save
        mgr.config.model.preferred_model = "spark"
        mgr.save()

        # Load in new manager
        mgr2 = ConfigManager(config_path=config_path)
        mgr2.load()
        assert mgr2.config.model.preferred_model == "spark"


def test_config_manager_get_set():
    """Test config manager get/set by dot-path."""
    mgr = ConfigManager()
    mgr.load()

    # Get
    assert mgr.get("model.preferred_model") == "core"
    assert mgr.get("mcp.port") == 8000

    # Set
    mgr.set("model.preferred_model", "apex")
    assert mgr.get("model.preferred_model") == "apex"

    mgr.set("mcp.port", 9000)
    assert mgr.get("mcp.port") == 9000


def test_config_manager_reset():
    """Test config manager reset."""
    mgr = ConfigManager()
    mgr.load()
    mgr.set("model.preferred_model", "apex")
    mgr.reset()
    assert mgr.get("model.preferred_model") == "core"


def test_config_manager_get_missing_key():
    """Test getting a non-existent key raises KeyError."""
    mgr = ConfigManager()
    try:
        mgr.get("nonexistent.key")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_config_diff():
    """Test config diff functionality."""
    config1 = BorealisConfig()
    config2 = BorealisConfig()
    config2.model.preferred_model = "apex"
    config2.mcp.port = 9000

    mgr = ConfigManager()
    mgr._config = config1
    diffs = mgr.diff(config2)

    assert "model.preferred_model" in diffs
    assert diffs["model.preferred_model"]["old"] == "core"
    assert diffs["model.preferred_model"]["new"] == "apex"
    assert "mcp.port" in diffs


def test_config_yaml_roundtrip():
    """Test that YAML roundtrip preserves all values."""
    original = BorealisConfig()
    original.model.preferred_model = "spark"
    original.memory.memory_policy = "frontier"
    original.mcp.port = 7000

    yaml_str = original.to_yaml()
    restored = BorealisConfig.from_yaml(yaml_str)

    assert restored.model.preferred_model == original.model.preferred_model
    assert restored.memory.memory_policy == original.memory.memory_policy
    assert restored.mcp.port == original.mcp.port
