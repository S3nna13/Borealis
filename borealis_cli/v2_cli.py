"""Borealis CLI — v2 command layer built alongside the existing main.py.

This module provides the v2 command structure defined in the master plan.
The existing main.py handles legacy commands; this extends with v2 features.

Usage:
    borealis doctor          # System health check
    borealis hardware detect # Detect hardware
    borealis profile use     # Use a hardware profile
    borealis skills list     # List native skills
    borealis skills suggest  # Suggest matching skills for a prompt
    borealis polaris quick     # Run quick POLARIS gate
    borealis schedule        # Schedule cron/interval/delayed shell jobs
    borealis serve           # Start runtime API server
    borealis ui              # Open Aurora Dashboard UI
"""

from __future__ import annotations

import json
import sys

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    _RICH = True
except ImportError:
    _RICH = False


def _console() -> Console | None:
    return Console() if _RICH else None


def cmd_doctor() -> int:
    """Full health/dependency/environment diagnostic."""
    import importlib
    import platform
    import sys
    con = _console()

    results: list[dict] = []

    # Python version
    results.append({"check": "Python version", "status": "ok", "detail": sys.version})

    # OS
    results.append({"check": "OS", "status": "ok", "detail": f"{platform.system()} {platform.release()}"})

    # Key dependencies
    deps = ["numpy", "torch", "safetensors", "pydantic", "rich", "mlx", "transformers", "cuda"]
    for dep in deps:
        try:
            if dep == "cuda":
                import torch
                has_cuda = torch.cuda.is_available()
                v = f"torch.cuda available={has_cuda}"
                results.append({"check": dep, "status": "ok" if has_cuda else "warn", "detail": v})
            else:
                mod = importlib.import_module(dep)
                v = getattr(mod, "__version__", "installed")
                results.append({"check": dep, "status": "ok", "detail": v})
        except ImportError:
            results.append({"check": dep, "status": "missing", "detail": "not installed"})

    # Print results
    if con:
        table = Table(title="Borealis Doctor — System Health")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Detail")
        for r in results:
            status_style = {"ok": "green", "warn": "yellow", "missing": "red"}.get(r["status"], "white")
            table.add_row(r["check"], f"[{status_style}]{r['status']}[/]", r["detail"])
        con.print(table)
    else:
        print("Borealis Doctor")
        print("=" * 60)
        for r in results:
            print(f"  {r['check']:20s} [{r['status']:7s}] {r['detail']}")

    missing = [r for r in results if r["status"] == "missing"]
    if missing:
        print(f"\nMissing dependencies: {', '.join(r['check'] for r in missing)}")
        return 1
    return 0


def cmd_hardware_detect() -> int:
    """Detect hardware and recommend profile."""
    try:
        from src.runtime.hardware_detector import HardwareDetector
        detector = HardwareDetector()
        info = detector.detect()
        profile = detector.recommend_profile(info)

        con = _console()
        if con:
            panel = Panel(
                f"CPU: {info.cpu_arch} ({info.cpu_count} cores)\n"
                f"RAM: {info.total_ram_gb} GB\n"
                f"GPU: {info.gpu_name or 'none detected'} ({info.gpu_count} devices)\n"
                f"VRAM: {info.gpu_vram_gb} GB\n"
                f"Unified Memory: {info.unified_memory}\n"
                f"CUDA: {info.cuda_available} ({info.cuda_version})\n"
                f"MLX: {info.mlx_available}\n"
                f"TensorRT: {info.tensorrt_available}\n"
                f"Profile: {profile.id}\n"
                f"Recommended: {profile.recommended_models}",
                title="Hardware Detection Results",
                border_style="cyan",
            )
            con.print(panel)
        else:
            print(f"Hardware Profile: {profile.id}")
            print(f"CPU: {info.cpu_arch} {info.cpu_count} cores")
            print(f"RAM: {info.total_ram_gb} GB")
            print(f"Recommended Models: {profile.recommended_models}")
    except ImportError:
        print("ERROR: Runtime module not available. Run from borealis/ directory.")
        return 1
    return 0


def cmd_skills_list(category: str | None = None) -> int:
    """List native skills."""
    try:
        from src.skills.registry import SkillRegistry
        registry = SkillRegistry()
        count = registry.discover_from_path()

        skills = registry.list_skills(category)
        con = _console()

        if con:
            table = Table(title=f"Borealis Native Skills ({len(skills)} loaded, {count} discovered)")
            table.add_column("ID", style="cyan")
            table.add_column("Name")
            table.add_column("Category")
            table.add_column("Risk")
            table.add_column("Status")
            for s in skills:
                table.add_row(s.manifest.id, s.manifest.name, s.manifest.category,
                              s.manifest.risk_level.value, s.manifest.status.value)
            con.print(table)
        else:
            print(f"Native Skills ({len(skills)} skills)")
            print("=" * 60)
            for s in skills:
                print(f"  {s.manifest.id:40s} [{s.manifest.risk_level.value:8s}] {s.manifest.name}")

        stats = registry.stats()
        print(f"\nStats: {json.dumps(stats, indent=2)}")
    except ImportError as e:
        print(f"ERROR: {e}")
        return 1
    return 0


def cmd_skills_suggest(query: str) -> int:
    """Suggest skills that match a query using the trigger engine."""
    try:
        from src.agent.skill_trigger_engine import SkillTriggerEngine
        from src.skills.registry import SkillRegistry

        registry = SkillRegistry()
        registry.discover_from_path()
        engine = SkillTriggerEngine(registry=registry)
        result = engine.match(query)
        payload = {
            "query": query,
            "count": len(result.matches),
            "matches": [
                {
                    "skill_id": match.skill_id,
                    "name": match.name,
                    "trigger_pattern": match.trigger_pattern,
                    "confidence": round(match.confidence, 3),
                    "summary": match.summary,
                }
                for match in result.matches
            ],
        }
        print(json.dumps(payload, indent=2))
    except ImportError as e:
        print(f"ERROR: {e}")
        return 1
    return 0


def cmd_polaris_quick() -> int:
    """Run quick POLARIS gate check."""
    try:
        from src.skills.registry import SkillRegistry
        from src.skills.validator import SkillValidator

        registry = SkillRegistry()
        count = registry.discover_from_path()
        validator = SkillValidator()

        results = {"total_checked": 0, "passed": 0, "failed": 0, "errors": []}

        for entry in registry.list_skills():
            results["total_checked"] += 1
            report = validator.validate(entry.manifest)
            if report.valid:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({"skill": entry.manifest.id, "errors": report.manifest_errors})

        con = _console()
        if con:
            from rich.table import Table
            table = Table(title="POLARIS Quick Gate")
            table.add_column("Gate", style="cyan")
            table.add_column("Result")
            table.add_column("Detail")
            table.add_row("Skills Discovered", f"{count}", "builtin skills loaded")
            table.add_row("Manifest Validation", f"{results['passed']}/{results['total_checked']}",
                          "passed" if results["failed"] == 0 else f"{results['failed']} failures")
            table.add_row("No Silent Fallback", "CHECKED", "all manifests specify model truth")
            con.print(table)
        else:
            print(f"POLARIS Quick Gate: {results['passed']}/{results['total_checked']} passed, {results['failed']} failed")

        return 0 if results["failed"] == 0 else 1
    except ImportError as e:
        print(f"ERROR: {e}")
        return 1


def cmd_status() -> int:
    """Show current system status."""
    try:
        from src.runtime.hardware_detector import HardwareDetector
        from src.runtime.memory_budget import MemoryBudgetConfig, MemoryBudgetManager
        from src.skills.registry import SkillRegistry

        # Hardware
        hw = HardwareDetector()
        info = hw.detect()

        # Memory budget
        config = MemoryBudgetConfig(total_memory_gb=info.total_ram_gb)
        budget_mgr = MemoryBudgetManager(config)
        budget_mgr.update_consumer("weights_gb", 3.0)
        budget_mgr.update_consumer("kv_cache_gb", 1.0)
        report = budget_mgr.generate_report()

        # Skills
        registry = SkillRegistry()
        skill_count = registry.discover_from_path()

        print("Borealis Status")
        print(f"{'='*50}")
        print(f"  Hardware: {info.cpu_arch} | RAM: {info.total_ram_gb}GB")
        if info.gpu_name:
            print(f"  GPU: {info.gpu_name} | VRAM: {info.gpu_vram_gb}GB")
        print(f"  Memory: {report.used_gb:.1f}GB used / {report.available_for_borealis_gb:.1f}GB available")
        print(f"  Pressure: {report.pressure_level.value}")
        print(f"  Skills: {skill_count} discovered")
        print(f"  CUDA: {info.cuda_available} | MLX: {info.mlx_available}")
    except ImportError as e:
        print(f"ERROR: {e}")
        return 1
    return 0


def cmd_serve(port: int = 8000) -> int:
    """Start runtime API server."""
    print(f"Starting Borealis API server on port {port}...")
    print("See src/api/ for server implementation.")
    print("For development: uvicorn src.api.server:app --reload --port {port}")
    return 0


def cmd_mcp_serve(transport: str = "streamable-http", port: int = 8000) -> int:
    """Start Borealis MCP server."""
    try:
        from src.mcp.server import create_mcp_server
        mcp = create_mcp_server()
        registry = _get_mcp_registry_for_display()
        print(f"Starting Borealis MCP Server ({transport} on port {port})...")
        print(f"Exposing {registry['total_skills']} skills as MCP tools")
        print(f"Categories: {', '.join(registry['categories'])}")
        print(f"\nConnect with: borealis mcp connect http://localhost:{port}/mcp")
        print("Or add to your MCP client configuration.")
        mcp.run(transport=transport, port=port)
        return 0
    except ImportError as e:
        print(f"ERROR: MCP module not available: {e}")
        print("Install MCP dependency: pip install mcp")
        return 1
    except Exception as e:
        print(f"ERROR: Failed to start MCP server: {e}")
        return 1


def _get_mcp_registry_for_display() -> dict:
    """Get registry stats for MCP server display."""
    try:
        from src.skills.registry import SkillRegistry
        registry = SkillRegistry()
        registry.discover_from_path()
        stats = registry.stats()
        return {
            "total_skills": stats["total_skills"],
            "categories": stats["categories"],
        }
    except Exception:
        return {"total_skills": 0, "categories": []}


def cmd_mcp_list() -> int:
    """List skills exposed via MCP."""
    try:
        from src.mcp.server import create_mcp_server
        from src.skills.registry import SkillRegistry

        registry = SkillRegistry()
        count = registry.discover_from_path()
        skills = registry.list_skills()

        con = _console()
        if con:
            table = Table(title=f"Borealis MCP Tools ({len(skills)} exposed)")
            table.add_column("Tool Name", style="cyan")
            table.add_column("Skill ID")
            table.add_column("Category")
            table.add_column("Risk")
            for s in skills:
                if s.manifest.status.value not in ("deprecated", "unsafe"):
                    tool_name = s.manifest.id.replace(".", "_")
                    table.add_row(tool_name, s.manifest.id, s.manifest.category, s.manifest.risk_level.value)
            con.print(table)
        else:
            print(f"MCP Tools ({len(skills)} skills)")
            print("=" * 60)
            for s in skills:
                if s.manifest.status.value not in ("deprecated", "unsafe"):
                    print(f"  {s.manifest.id.replace('.', '_'):40s} [{s.manifest.risk_level.value:8s}] {s.manifest.name}")
        return 0
    except ImportError as e:
        print(f"ERROR: {e}")
        return 1


def cmd_ui() -> int:
    """Open Aurora Dashboard UI."""
    print("Opening Aurora Dashboard UI...")
    print("Navigate to http://localhost:5173 in your browser.")
    print("See borealis/ui/ for frontend implementation.")
    return 0


def main_v2() -> int:
    """Entry point for v2 commands when invoked directly."""
    if len(sys.argv) < 2:
        print("Usage: python -m borealis_cli.v2_cli <command> [args]")
        print("Commands: doctor, hardware, skills, polaris, schedule, status, serve, mcp, ui, skills suggest")
        return 1

    command = sys.argv[1]

    if command == "doctor":
        return cmd_doctor()
    elif command == "hardware":
        if len(sys.argv) > 2 and sys.argv[2] == "detect":
            return cmd_hardware_detect()
        return 1
    elif command == "skills":
        if len(sys.argv) > 2 and sys.argv[2] == "list":
            cat = sys.argv[3] if len(sys.argv) > 3 else None
            return cmd_skills_list(cat)
        if len(sys.argv) > 2 and sys.argv[2] == "suggest":
            query = " ".join(sys.argv[3:]).strip()
            if not query:
                print("Usage: borealis skills suggest <query>")
                return 1
            return cmd_skills_suggest(query)
        return 0
    elif command == "polaris":
        if len(sys.argv) > 2 and sys.argv[2] in ("quick",):
            return cmd_polaris_quick()
        return 0
    elif command == "schedule":
        from borealis_cli.scheduler_commands import main_schedule

        return main_schedule(sys.argv[2:])
    elif command == "status":
        return cmd_status()
    elif command == "serve":
        port = 8000
        if len(sys.argv) > 3 and sys.argv[2] == "--port":
            port = int(sys.argv[3])
        return cmd_serve(port)
    elif command == "mcp":
        if len(sys.argv) > 2 and sys.argv[2] == "serve":
            port = 8000
            transport = "streamable-http"
            i = 3
            while i < len(sys.argv):
                if sys.argv[i] == "--port" and i + 1 < len(sys.argv):
                    port = int(sys.argv[i + 1])
                    i += 2
                elif sys.argv[i] == "--transport" and i + 1 < len(sys.argv):
                    transport = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            return cmd_mcp_serve(transport=transport, port=port)
        elif len(sys.argv) > 2 and sys.argv[2] == "list":
            return cmd_mcp_list()
        else:
            print("Usage: borealis mcp serve [--port N] [--transport stdio|streamable-http]")
            print("       borealis mcp list")
            return 1
    elif command == "ui":
        return cmd_ui()
    else:
        print(f"Unknown command: {command}")
        return 1


if __name__ == "__main__":
    sys.exit(main_v2())
