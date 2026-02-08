#!/usr/bin/env python3
"""
Nexus CLI Quality Gate Module

Provides configurable quality gates with:
- Build verification
- Lint/Type checking
- Code review triggers
- Configurable gate policies

Gate policies:
- per_batch: Run gates after each batch
- on_complete: Run gates only after all batches complete
- manual: Only run when explicitly requested
"""

import subprocess
import os
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from enum import Enum
from pathlib import Path
from datetime import datetime


class GatePolicy(str, Enum):
    """When to run quality gates"""
    PER_BATCH = "per_batch"       # After each batch completes
    ON_COMPLETE = "on_complete"   # After all batches complete (default)
    MANUAL = "manual"             # Only when user requests


class GateType(str, Enum):
    """Types of quality gates"""
    BUILD = "build"
    LINT = "lint"
    TYPECHECK = "typecheck"
    TEST = "test"
    REVIEW = "review"


class GateStatus(str, Enum):
    """Gate execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"  # Passed with warnings


@dataclass
class GateResult:
    """Result of a single gate check"""
    gate_type: GateType
    status: GateStatus
    message: str = ""
    details: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    exit_code: int = 0


@dataclass
class GateConfig:
    """Configuration for a single gate"""
    enabled: bool = True
    command: Optional[str] = None  # Custom command override
    working_dir: str = "."
    timeout_seconds: int = 300
    fail_on_error: bool = True  # Block if gate fails
    allow_warnings: bool = True


@dataclass
class QualityGateConfig:
    """Complete quality gate configuration"""
    policy: GatePolicy = GatePolicy.ON_COMPLETE
    ask_before_run: bool = True  # Ask user before running gates
    gates: Dict[str, GateConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> "QualityGateConfig":
        """Create config from dictionary"""
        policy = GatePolicy(data.get("policy", "on_complete"))
        ask_before_run = data.get("ask_before_run", True)

        gates = {}
        for gate_name, gate_data in data.get("gates", {}).items():
            gates[gate_name] = GateConfig(
                enabled=gate_data.get("enabled", True),
                command=gate_data.get("command"),
                working_dir=gate_data.get("working_dir", "."),
                timeout_seconds=gate_data.get("timeout_seconds", 300),
                fail_on_error=gate_data.get("fail_on_error", True),
                allow_warnings=gate_data.get("allow_warnings", True)
            )

        return cls(policy=policy, ask_before_run=ask_before_run, gates=gates)

    @classmethod
    def default(cls) -> "QualityGateConfig":
        """Create default configuration"""
        return cls(
            policy=GatePolicy.ON_COMPLETE,
            ask_before_run=True,
            gates={
                "build": GateConfig(enabled=True, fail_on_error=True),
                "lint": GateConfig(enabled=True, fail_on_error=False),
                "typecheck": GateConfig(enabled=True, fail_on_error=False),
                "review": GateConfig(enabled=True, fail_on_error=False),
            }
        )


class QualityGate:
    """
    Quality Gate Manager for Nexus CLI

    Handles build verification, linting, type checking, and code review gates.
    """

    # Default commands for different project types
    DEFAULT_COMMANDS = {
        "build": {
            "node": "npm run build",
            "python": "python -m py_compile",
            "go": "go build ./...",
            "rust": "cargo build",
            "default": "echo 'No build command configured'"
        },
        "lint": {
            "node": "npm run lint",
            "python": "ruff check . || pylint **/*.py",
            "go": "golangci-lint run",
            "rust": "cargo clippy",
            "default": "echo 'No lint command configured'"
        },
        "typecheck": {
            "node": "npm run typecheck || npx tsc --noEmit",
            "python": "mypy . || pyright",
            "go": "go vet ./...",
            "rust": "cargo check",
            "default": "echo 'No typecheck command configured'"
        },
        "test": {
            "node": "npm test",
            "python": "pytest",
            "go": "go test ./...",
            "rust": "cargo test",
            "default": "echo 'No test command configured'"
        }
    }

    def __init__(
        self,
        config: Optional[QualityGateConfig] = None,
        project_root: str = ".",
        on_status_update: Optional[Callable[[GateType, GateStatus, str], None]] = None
    ):
        self.config = config or QualityGateConfig.default()
        self.project_root = Path(project_root).resolve()
        self.on_status_update = on_status_update
        self._project_type = self._detect_project_type()
        self._results: List[GateResult] = []

    def _detect_project_type(self) -> str:
        """Detect project type based on files present"""
        if (self.project_root / "package.json").exists():
            return "node"
        elif (self.project_root / "pyproject.toml").exists() or \
             (self.project_root / "setup.py").exists() or \
             (self.project_root / "requirements.txt").exists():
            return "python"
        elif (self.project_root / "go.mod").exists():
            return "go"
        elif (self.project_root / "Cargo.toml").exists():
            return "rust"
        return "default"

    def _get_command(self, gate_type: str) -> str:
        """Get command for gate type"""
        gate_config = self.config.gates.get(gate_type, GateConfig())

        # Use custom command if specified
        if gate_config.command:
            return gate_config.command

        # Use default command for project type
        commands = self.DEFAULT_COMMANDS.get(gate_type, {})
        return commands.get(self._project_type, commands.get("default", ""))

    def _notify(self, gate_type: GateType, status: GateStatus, message: str = ""):
        """Notify status update (safe against callback errors)"""
        if self.on_status_update:
            try:
                self.on_status_update(gate_type, status, message)
            except Exception:
                pass

    def _run_command(
        self,
        command: str,
        timeout: int = 300,
        working_dir: str = "."
    ) -> tuple:
        """Run a shell command and capture output"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_root / working_dir),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return -1, "", str(e)

    # ─────────────────────────────────────────────────────────────────────────
    # Individual Gate Checks
    # ─────────────────────────────────────────────────────────────────────────

    def run_build_check(self) -> GateResult:
        """Run build verification"""
        gate_config = self.config.gates.get("build", GateConfig())
        if not gate_config.enabled:
            return GateResult(
                gate_type=GateType.BUILD,
                status=GateStatus.SKIPPED,
                message="Build check disabled"
            )

        self._notify(GateType.BUILD, GateStatus.RUNNING, "Running build...")

        import time
        start_time = time.time()

        command = self._get_command("build")
        exit_code, stdout, stderr = self._run_command(
            command,
            timeout=gate_config.timeout_seconds,
            working_dir=gate_config.working_dir
        )

        duration = time.time() - start_time

        if exit_code == 0:
            result = GateResult(
                gate_type=GateType.BUILD,
                status=GateStatus.PASSED,
                message="Build successful",
                duration_seconds=duration,
                exit_code=exit_code
            )
        else:
            result = GateResult(
                gate_type=GateType.BUILD,
                status=GateStatus.FAILED,
                message=f"Build failed with exit code {exit_code}",
                details=[stderr] if stderr else [stdout],
                duration_seconds=duration,
                exit_code=exit_code
            )

        self._notify(GateType.BUILD, result.status, result.message)
        return result

    def run_lint_check(self) -> GateResult:
        """Run lint check"""
        gate_config = self.config.gates.get("lint", GateConfig())
        if not gate_config.enabled:
            return GateResult(
                gate_type=GateType.LINT,
                status=GateStatus.SKIPPED,
                message="Lint check disabled"
            )

        self._notify(GateType.LINT, GateStatus.RUNNING, "Running lint...")

        import time
        start_time = time.time()

        command = self._get_command("lint")
        exit_code, stdout, stderr = self._run_command(
            command,
            timeout=gate_config.timeout_seconds,
            working_dir=gate_config.working_dir
        )

        duration = time.time() - start_time

        # Parse lint output for issues
        output = stdout + stderr
        issues = self._parse_lint_output(output)

        if exit_code == 0:
            if issues:
                result = GateResult(
                    gate_type=GateType.LINT,
                    status=GateStatus.WARNING if gate_config.allow_warnings else GateStatus.FAILED,
                    message=f"Lint passed with {len(issues)} warnings",
                    details=issues[:10],  # Limit to first 10 issues
                    duration_seconds=duration,
                    exit_code=exit_code
                )
            else:
                result = GateResult(
                    gate_type=GateType.LINT,
                    status=GateStatus.PASSED,
                    message="Lint check passed",
                    duration_seconds=duration,
                    exit_code=exit_code
                )
        else:
            result = GateResult(
                gate_type=GateType.LINT,
                status=GateStatus.FAILED,
                message=f"Lint failed with {len(issues)} issues",
                details=issues[:10],
                duration_seconds=duration,
                exit_code=exit_code
            )

        self._notify(GateType.LINT, result.status, result.message)
        return result

    def run_typecheck(self) -> GateResult:
        """Run type check"""
        gate_config = self.config.gates.get("typecheck", GateConfig())
        if not gate_config.enabled:
            return GateResult(
                gate_type=GateType.TYPECHECK,
                status=GateStatus.SKIPPED,
                message="Type check disabled"
            )

        self._notify(GateType.TYPECHECK, GateStatus.RUNNING, "Running type check...")

        import time
        start_time = time.time()

        command = self._get_command("typecheck")
        exit_code, stdout, stderr = self._run_command(
            command,
            timeout=gate_config.timeout_seconds,
            working_dir=gate_config.working_dir
        )

        duration = time.time() - start_time

        output = stdout + stderr
        errors = self._parse_type_errors(output)

        if exit_code == 0:
            result = GateResult(
                gate_type=GateType.TYPECHECK,
                status=GateStatus.PASSED,
                message="Type check passed",
                duration_seconds=duration,
                exit_code=exit_code
            )
        else:
            result = GateResult(
                gate_type=GateType.TYPECHECK,
                status=GateStatus.FAILED,
                message=f"Type check failed with {len(errors)} errors",
                details=errors[:10],
                duration_seconds=duration,
                exit_code=exit_code
            )

        self._notify(GateType.TYPECHECK, result.status, result.message)
        return result

    def run_test_check(self) -> GateResult:
        """Run test suite"""
        gate_config = self.config.gates.get("test", GateConfig())
        if not gate_config.enabled:
            return GateResult(
                gate_type=GateType.TEST,
                status=GateStatus.SKIPPED,
                message="Test check disabled"
            )

        self._notify(GateType.TEST, GateStatus.RUNNING, "Running tests...")

        import time
        start_time = time.time()

        command = self._get_command("test")
        exit_code, stdout, stderr = self._run_command(
            command,
            timeout=gate_config.timeout_seconds,
            working_dir=gate_config.working_dir
        )

        duration = time.time() - start_time

        if exit_code == 0:
            result = GateResult(
                gate_type=GateType.TEST,
                status=GateStatus.PASSED,
                message="All tests passed",
                duration_seconds=duration,
                exit_code=exit_code
            )
        else:
            result = GateResult(
                gate_type=GateType.TEST,
                status=GateStatus.FAILED,
                message="Tests failed",
                details=[stderr] if stderr else [stdout],
                duration_seconds=duration,
                exit_code=exit_code
            )

        self._notify(GateType.TEST, result.status, result.message)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Output Parsing Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_lint_output(self, output: str) -> List[str]:
        """Parse lint output into issues list"""
        issues = []
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Common lint output patterns
            if any(keyword in line.lower() for keyword in ["error", "warning", "issue", ":"]):
                if len(line) < 200:  # Skip very long lines
                    issues.append(line)
        return issues

    def _parse_type_errors(self, output: str) -> List[str]:
        """Parse type check output into errors list"""
        errors = []
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            if any(keyword in line.lower() for keyword in ["error", "type", ":"]):
                if len(line) < 200:
                    errors.append(line)
        return errors

    # ─────────────────────────────────────────────────────────────────────────
    # Gate Orchestration
    # ─────────────────────────────────────────────────────────────────────────

    def run_all_gates(
        self,
        gates: Optional[List[str]] = None
    ) -> Dict[str, GateResult]:
        """
        Run all enabled gates

        Args:
            gates: Specific gates to run (default: all enabled)

        Returns:
            Dict mapping gate name to result
        """
        results = {}

        # Determine which gates to run
        gates_to_run = gates or ["build", "lint", "typecheck"]

        # Run gates in order
        gate_runners = {
            "build": self.run_build_check,
            "lint": self.run_lint_check,
            "typecheck": self.run_typecheck,
            "test": self.run_test_check,
        }

        for gate_name in gates_to_run:
            if gate_name in gate_runners:
                gate_config = self.config.gates.get(gate_name, GateConfig())
                if gate_config.enabled:
                    result = gate_runners[gate_name]()
                    results[gate_name] = result
                    self._results.append(result)

                    # Check if should block on failure
                    if result.status == GateStatus.FAILED and gate_config.fail_on_error:
                        break  # Stop running further gates

        return results

    def should_run_gates(self, context: str) -> bool:
        """
        Determine if gates should run based on policy and context

        Args:
            context: "batch_complete" or "all_complete"

        Returns:
            True if gates should run
        """
        if self.config.policy == GatePolicy.PER_BATCH:
            return context == "batch_complete"
        elif self.config.policy == GatePolicy.ON_COMPLETE:
            return context == "all_complete"
        elif self.config.policy == GatePolicy.MANUAL:
            return False
        return False

    def get_summary(self) -> Dict:
        """Get summary of all gate results"""
        passed = sum(1 for r in self._results if r.status == GateStatus.PASSED)
        failed = sum(1 for r in self._results if r.status == GateStatus.FAILED)
        warnings = sum(1 for r in self._results if r.status == GateStatus.WARNING)
        skipped = sum(1 for r in self._results if r.status == GateStatus.SKIPPED)

        return {
            "total": len(self._results),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "skipped": skipped,
            "all_passed": failed == 0,
            "results": [
                {
                    "gate": r.gate_type.value,
                    "status": r.status.value,
                    "message": r.message,
                    "duration": r.duration_seconds
                }
                for r in self._results
            ]
        }

    def format_results(self) -> str:
        """Format results for display"""
        lines = []
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║                    Quality Gate Results                      ║")
        lines.append("╠══════════════════════════════════════════════════════════════╣")

        status_icons = {
            GateStatus.PASSED: "✅",
            GateStatus.FAILED: "❌",
            GateStatus.WARNING: "⚠️",
            GateStatus.SKIPPED: "⏭️",
            GateStatus.RUNNING: "🔄",
            GateStatus.PENDING: "⏳"
        }

        for result in self._results:
            icon = status_icons.get(result.status, "•")
            duration = f"({result.duration_seconds:.1f}s)" if result.duration_seconds > 0 else ""
            lines.append(f"║  {icon} {result.gate_type.value.upper():12} {result.message:30} {duration:8} ║")

            # Show details for failures
            if result.status == GateStatus.FAILED and result.details:
                for detail in result.details[:3]:
                    truncated = detail[:55] + "..." if len(detail) > 55 else detail
                    lines.append(f"║     └─ {truncated:55} ║")

        lines.append("╚══════════════════════════════════════════════════════════════╝")

        summary = self.get_summary()
        if summary["all_passed"]:
            lines.append("\n✅ All quality gates passed!")
        else:
            lines.append(f"\n⚠️ {summary['failed']} gate(s) failed, {summary['warnings']} warning(s)")

        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt Templates for User Interaction
# ─────────────────────────────────────────────────────────────────────────────

GATE_PROMPTS = {
    "ask_before_gates": {
        "header": "质量检查",
        "question": "是否运行质量门控检查？",
        "options": [
            {"label": "是，运行检查", "description": "运行构建、Lint 和类型检查"},
            {"label": "否，跳过", "description": "跳过质量检查，直接继续"},
            {"label": "仅运行部分", "description": "选择要运行的检查项"}
        ]
    },
    "select_gates": {
        "header": "选择检查项",
        "question": "选择要运行的质量检查：",
        "options": [
            {"label": "构建检查 (Build)", "description": "验证项目能够成功构建"},
            {"label": "Lint 检查", "description": "检查代码风格和潜在问题"},
            {"label": "类型检查", "description": "运行 TypeScript/MyPy 等类型检查"},
            {"label": "代码审查", "description": "启动 AI 代码审查"}
        ]
    },
    "gate_failed": {
        "header": "质量检查失败",
        "question": "部分质量检查未通过，如何处理？",
        "options": [
            {"label": "查看详情并修复", "description": "显示失败详情，暂停执行"},
            {"label": "忽略并继续", "description": "跳过失败的检查，继续执行"},
            {"label": "终止执行", "description": "停止后续任务执行"}
        ]
    }
}


# ─────────────────────────────────────────────────────────────────────────────
# CLI Interface
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nexus CLI Quality Gate")
    parser.add_argument("--gates", nargs="+", choices=["build", "lint", "typecheck", "test"],
                       help="Specific gates to run")
    parser.add_argument("--project", default=".", help="Project root directory")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--test", action="store_true", help="Run self-test")

    args = parser.parse_args()

    if args.test:
        print("Running Quality Gate self-test...")
        print("")

        # Create test gate
        gate = QualityGate(project_root=args.project)

        print(f"Detected project type: {gate._project_type}")
        print("")

        # Run all gates
        results = gate.run_all_gates(args.gates)

        # Print results
        print(gate.format_results())

    else:
        # Normal execution
        gate = QualityGate(project_root=args.project)
        results = gate.run_all_gates(args.gates)
        print(gate.format_results())
