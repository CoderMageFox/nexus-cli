"""
Nexus CLI Library Module

This package provides core functionality for Nexus CLI:
- checkpoint_manager: Task execution state persistence
- config_manager: Configuration management
- execution_engine: Task execution with parallel control
- execution_logger: Logging and audit trail
- progress_display: Rich progress visualization
- i18n: Internationalization support
- quality_gate: Quality gates for build, lint, type checking, and code review
"""

from lib.checkpoint_manager import (
    CheckpointManager,
    TaskStatus,
    BatchStatus,
    TaskState,
    BatchState,
    ExecutionCheckpoint,
)

from lib.config_manager import (
    ConfigManager,
    NexusConfig,
    RoutingRule,
    ExecutorConfig,
    ErrorStrategy,
)

from lib.execution_engine import (
    ExecutionEngine,
    ExecutionResult,
    TaskResult,
    BatchResult,
)

from lib.execution_logger import (
    ExecutionLogger,
    EventType,
)

from lib.progress_display import (
    ProgressDisplay,
    DisplayMode,
    print_progress_line,
    print_task_result,
    print_batch_summary,
)

from lib.i18n import (
    I18n,
    Language,
    get_i18n,
    set_language,
    t,
)

from lib.quality_gate import (
    QualityGate,
    GateType,
    GatePolicy,
    GateResult,
    GateStatus,
    GATE_PROMPTS,
)

__version__ = "1.1.0"
__all__ = [
    # Checkpoint
    "CheckpointManager",
    "TaskStatus",
    "BatchStatus",
    "TaskState",
    "BatchState",
    "ExecutionCheckpoint",
    # Config
    "ConfigManager",
    "NexusConfig",
    "RoutingRule",
    "ExecutorConfig",
    "ErrorStrategy",
    # Engine
    "ExecutionEngine",
    "ExecutionResult",
    "TaskResult",
    "BatchResult",
    # Logger
    "ExecutionLogger",
    "EventType",
    # Progress
    "ProgressDisplay",
    "DisplayMode",
    "print_progress_line",
    "print_task_result",
    "print_batch_summary",
    # i18n
    "I18n",
    "Language",
    "get_i18n",
    "set_language",
    "t",
    # Quality Gates
    "QualityGate",
    "GateType",
    "GatePolicy",
    "GateResult",
    "GateStatus",
    "GATE_PROMPTS",
]
