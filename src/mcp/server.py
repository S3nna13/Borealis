"""Borealis MCP Server — exposes all native skills as MCP tools."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.skills.executor import SkillExecutor
from src.skills.manifest import SkillExecutionMode, SkillStatus
from src.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

# Global registry and executor — initialised once at startup
_registry: SkillRegistry | None = None
_executor: SkillExecutor | None = None


def _get_registry() -> SkillRegistry:
    """Lazy-initialise and return the skill registry."""
    global _registry, _executor
    if _registry is None:
        _registry = SkillRegistry()
        builtin_path = os.path.join(os.path.dirname(__file__), "..", "skills")
        _registry.discover_from_path(builtin_path)
        _executor = SkillExecutor()
    return _registry


def _get_executor() -> SkillExecutor:
    """Lazy-initialise and return the skill executor."""
    _get_registry()  # ensures _executor is set
    return _executor  # type: ignore[return-value]


def create_mcp_server() -> FastMCP:
    """Create and configure the Borealis MCP server."""
    mcp = FastMCP(
        "Borealis",
        instructions=(
            "Borealis AI runtime — 150+ native skills for coding, "
            "security, devops, testing, ML, CUA, and more."
        ),
    )

    registry = _get_registry()

    # Register each skill as an MCP tool
    for entry in registry.list_skills():
        manifest = entry.manifest
        if manifest.status in (SkillStatus.DEPRECATED, SkillStatus.UNSAFE):
            continue

        _register_skill_tool(mcp, manifest)

    # Register meta-tools for discovery and management
    _register_meta_tools(mcp, registry)

    return mcp


def _register_skill_tool(mcp: FastMCP, manifest: Any) -> None:
    """Register a single Borealis skill as an MCP tool."""

    async def skill_tool(**inputs: Any) -> dict[str, Any]:
        """Dynamically generated tool for skill: {manifest.id}"""
        registry = _get_registry()
        executor = _get_executor()
        entry = registry.get(manifest.id)

        if entry is None:
            return {
                "success": False,
                "error": f"Skill {manifest.id} not found",
            }

        # Check permissions
        checks = registry.check_permissions(manifest.id)
        denials = [c for c in checks if c.grant == "denied"]
        if denials:
            return {
                "success": False,
                "error": f"Permissions denied: {', '.join(d.reason for d in denials)}",
            }

        # Execute in dry_run mode by default for safety
        mode = SkillExecutionMode.DRY_RUN
        if inputs.get("mode") == "execute":
            mode = SkillExecutionMode.EXECUTE
        elif inputs.get("mode") == "plan":
            mode = SkillExecutionMode.PLAN
        elif inputs.get("mode") == "verify":
            mode = SkillExecutionMode.VERIFY

        # Remove mode from inputs before passing to skill
        skill_inputs = {k: v for k, v in inputs.items() if k != "mode"}

        result = executor.execute(
            manifest=manifest,
            mode=mode,
            skill_callable=entry.module if entry.loaded else None,
            inputs=skill_inputs,
        )

        # Record telemetry
        registry.record_use(
            manifest.id,
            success=result.success,
            runtime_ms=result.runtime_ms,
        )

        return {
            "skill_id": manifest.id,
            "skill_name": manifest.name,
            "mode": mode.value,
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "runtime_ms": result.runtime_ms,
            "dry_run_details": result.dry_run_details,
        }

    # Build tool description
    description = (
        f"{manifest.summary}\n\n"
        f"Category: {manifest.category}\n"
        f"Risk: {manifest.risk_level.value}\n"
        f"Tags: {', '.join(manifest.tags)}\n\n"
        f"Supported modes: {', '.join(m.value for m in manifest.supported_modes)}\n"
        f"Pass mode='execute' to actually run (default: dry_run)."
    )

    # Register with FastMCP
    tool_name = manifest.id.replace(".", "_")
    mcp.tool(name=tool_name, description=description)(skill_tool)


def _register_meta_tools(mcp: FastMCP, registry: SkillRegistry) -> None:
    """Register meta-tools for skill discovery and management."""

    @mcp.tool(
        name="borealis_list_skills",
        description="List all available Borealis skills. Optionally filter by category.",
    )
    async def list_skills(category: str = "") -> dict[str, Any]:
        """List Borealis skills."""
        reg = _get_registry()
        skills = reg.list_skills(category=category if category else None)
        return {
            "total": len(skills),
            "skills": [
                {
                    "id": s.manifest.id,
                    "name": s.manifest.name,
                    "category": s.manifest.category,
                    "summary": s.manifest.summary,
                    "risk_level": s.manifest.risk_level.value,
                    "status": s.manifest.status.value,
                    "tags": s.manifest.tags,
                }
                for s in skills
            ],
        }

    @mcp.tool(
        name="borealis_search_skills",
        description="Search Borealis skills by query (matches name, summary, tags, id).",
    )
    async def search_skills(query: str) -> dict[str, Any]:
        """Search Borealis skills."""
        reg = _get_registry()
        results = reg.search(query)
        return {
            "query": query,
            "total": len(results),
            "skills": [
                {
                    "id": s.manifest.id,
                    "name": s.manifest.name,
                    "category": s.manifest.category,
                    "summary": s.manifest.summary,
                    "risk_level": s.manifest.risk_level.value,
                    "tags": s.manifest.tags,
                }
                for s in results
            ],
        }

    @mcp.tool(
        name="borealis_skill_detail",
        description="Get full details for a specific Borealis skill by ID.",
    )
    async def skill_detail(skill_id: str) -> dict[str, Any]:
        """Get skill details."""
        reg = _get_registry()
        entry = reg.get(skill_id)
        if entry is None:
            return {"success": False, "error": f"Skill {skill_id} not found"}
        return {
            "success": True,
            "skill": entry.manifest.to_dict(),
        }

    @mcp.tool(
        name="borealis_skill_stats",
        description="Get statistics about the Borealis skill registry.",
    )
    async def skill_stats() -> dict[str, Any]:
        """Get registry statistics."""
        reg = _get_registry()
        return reg.stats()

    @mcp.tool(
        name="borealis_categories",
        description="List all skill categories.",
    )
    async def categories() -> dict[str, Any]:
        """List categories."""
        reg = _get_registry()
        return {"categories": reg.categories()}
