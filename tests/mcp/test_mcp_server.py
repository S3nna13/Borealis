"""Tests for Borealis MCP server."""

from __future__ import annotations

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_create_mcp_server():
    """Test that MCP server can be created."""
    from src.mcp.server import create_mcp_server
    server = create_mcp_server()
    assert server is not None
    assert server.name == "Borealis"


def test_mcp_server_has_meta_tools():
    """Test that meta-tools are registered."""
    from src.mcp.server import create_mcp_server
    server = create_mcp_server()
    # The server should have tools registered
    # FastMCP stores tools internally
    assert hasattr(server, "_tool_manager") or hasattr(server, "tools")


def test_skill_registry_integration():
    """Test that skill registry is properly integrated."""
    from src.skills.registry import SkillRegistry
    import os
    registry = SkillRegistry()
    # Point to the actual builtin skills directory
    skills_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "skills")
    count = registry.discover_from_path(skills_path)
    assert count > 0, f"Should discover at least some skills (got {count})"
    stats = registry.stats()
    assert stats["total_skills"] > 0
    assert len(stats["categories"]) > 0


def test_skill_manifest_to_dict():
    """Test skill manifest serialization."""
    from src.skills.manifest import SkillManifest, RiskLevel, SkillStatus
    manifest = SkillManifest(
        id="test.example",
        name="Test Skill",
        version="1.0.0",
        category="test",
        summary="A test skill",
        risk_level=RiskLevel.LOW,
        status=SkillStatus.STABLE,
    )
    d = manifest.to_dict()
    assert d["id"] == "test.example"
    assert d["name"] == "Test Skill"
    assert d["risk_level"] == "low"
    assert d["status"] == "stable"


def test_mcp_server_exposes_non_deprecated_skills():
    """Test that deprecated/unsafe skills are not exposed."""
    from src.skills.manifest import SkillManifest, RiskLevel, SkillStatus
    from src.skills.registry import SkillRegistry
    import os

    registry = SkillRegistry()
    skills_path = os.path.join(os.path.dirname(__file__), "..", "..", "src", "skills")
    count = registry.discover_from_path(skills_path)
    assert count > 0

    # All discovered skills should be either stable or experimental
    for entry in registry.list_skills():
        assert entry.manifest.status not in (
            SkillStatus.DEPRECATED,
            SkillStatus.UNSAFE,
        ), f"Skill {entry.manifest.id} should not be deprecated/unsafe"
