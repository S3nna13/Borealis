"""Tests for Borealis CLI commands."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_cmd_models_list():
    """Test models list command runs without error."""
    from borealis_cli.v2_cli import cmd_models_list
    result = cmd_models_list()
    assert result == 0


def test_cmd_models_info():
    """Test models info for each model variant."""
    from borealis_cli.v2_cli import cmd_models_info

    for model in ("spark", "core", "apex"):
        result = cmd_models_info(model)
        assert result == 0, f"models info {model} failed"


def test_cmd_models_info_invalid():
    """Test models info with invalid model name returns error."""
    from borealis_cli.v2_cli import cmd_models_info
    result = cmd_models_info("nonexistent")
    assert result == 1


def test_cmd_run_empty():
    """Test run with empty prompt returns error."""
    from borealis_cli.v2_cli import cmd_run
    result = cmd_run("")
    assert result == 1


def test_cmd_run_with_prompt():
    """Test run with valid prompt returns success."""
    from borealis_cli.v2_cli import cmd_run
    result = cmd_run("list files")
    assert result == 0


def test_cmd_config_path():
    """Test config path command."""
    from borealis_cli.v2_cli import cmd_config_path
    result = cmd_config_path()
    assert result == 0


def test_cmd_mcp_list():
    """Test MCP list command."""
    from borealis_cli.v2_cli import cmd_mcp_list
    result = cmd_mcp_list()
    assert result == 0
