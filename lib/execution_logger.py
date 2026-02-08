#!/usr/bin/env python3
"""
Nexus CLI Execution Logger

Provides comprehensive logging and audit trail for:
- Task execution events
- Batch progress tracking
- Executor performance metrics
- Error diagnostics

Storage location: .nexus-temp/logs/
"""

import json
import os
import time
import logging
import sys
import threading
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
from pathlib import Path
from logging.handlers import RotatingFileHandler


class EventType(str, Enum):
    """Types of logged events"""
    # Execution lifecycle
    EXECUTION_START = "execution_start"
    EXECUTION_END = "execution_end"

    # Batch events
    BATCH_START = "batch_start"
    BATCH_END = "batch_end"
    BATCH_RETRY = "batch_retry"

    # Task events
    TASK_START = "task_start"
    TASK_END = "task_end"
    TASK_RETRY = "task_retry"
    TASK_SKIP = "task_skip"

    # Executor events
    EXECUTOR_CALL = "executor_call"
    EXECUTOR_RESPONSE = "executor_response"
    EXECUTOR_ERROR = "executor_error"
    EXECUTOR_TIMEOUT = "executor_timeout"

    # Checkpoint events
    CHECKPOINT_SAVE = "checkpoint_save"
    CHECKPOINT_LOAD = "checkpoint_load"
    CHECKPOINT_RESUME = "checkpoint_resume"

    # User interaction
    USER_CONFIRM = "user_confirm"
    USER_CANCEL = "user_cancel"

    # System events
    CONFIG_LOAD = "config_load"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class LogEvent:
    """A single log event"""
    timestamp: str
    event_type: EventType
    message: str
    feature_name: Optional[str] = None
    batch_id: Optional[int] = None
    task_id: Optional[str] = None
    executor: Optional[str] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionLogger:
    """Logger for Nexus CLI execution events"""

    LOG_DIR = ".nexus-temp/logs"
    EXECUTION_LOG = "execution.log"
    AUDIT_LOG = "audit.jsonl"

    def __init__(self, project_root: str = ".", feature_name: Optional[str] = None):
        self.project_root = Path(project_root).resolve()
        self.log_dir = self.project_root / self.LOG_DIR
        self.feature_name = feature_name
        self.execution_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._ensure_dir()
        self._setup_loggers()

        # Thread safety lock for stats and audit file
        self._lock = threading.Lock()

        # Performance tracking
        self._task_starts: Dict[str, float] = {}
        self._batch_starts: Dict[int, float] = {}
        self._execution_start: Optional[float] = None

        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "skipped_tasks": 0,
            "retried_tasks": 0,
            "executor_calls": {"claude": 0, "gemini": 0, "codex": 0},
            "executor_errors": {"claude": 0, "gemini": 0, "codex": 0},
            "total_duration_ms": 0
        }

    def _ensure_dir(self):
        """Ensure log directory exists"""
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create feature-specific directory if needed
        if self.feature_name:
            feature_dir = self.log_dir / self._safe_name(self.feature_name)
            feature_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, name: str) -> str:
        """Convert name to filesystem-safe format"""
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    def _setup_loggers(self):
        """Set up logging handlers"""
        # Main execution logger (human-readable)
        self.logger = logging.getLogger(f"nexus.execution.{self.execution_id}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []

        # Determine log file path
        if self.feature_name:
            log_file = self.log_dir / self._safe_name(self.feature_name) / f"{self.execution_id}.log"
        else:
            log_file = self.log_dir / f"execution_{self.execution_id}.log"

        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler (info and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        # Don't add console handler by default - control output separately

        # Audit logger (JSON lines format)
        if self.feature_name:
            self.audit_file = self.log_dir / self._safe_name(self.feature_name) / f"{self.execution_id}_audit.jsonl"
        else:
            self.audit_file = self.log_dir / f"audit_{self.execution_id}.jsonl"

    def _log_event(self, event: LogEvent):
        """Log an event to both human-readable and audit logs"""
        # Human-readable log
        level = logging.INFO
        if event.event_type == EventType.ERROR:
            level = logging.ERROR
        elif event.event_type == EventType.WARNING:
            level = logging.WARNING
        elif event.event_type in [EventType.TASK_START, EventType.BATCH_START]:
            level = logging.DEBUG

        log_msg = self._format_event(event)
        self.logger.log(level, log_msg)

        # Audit log (JSON lines) — thread-safe write
        audit_entry = {
            "timestamp": event.timestamp,
            "event_type": event.event_type.value,
            "message": event.message,
            "feature_name": event.feature_name or self.feature_name,
            "batch_id": event.batch_id,
            "task_id": event.task_id,
            "executor": event.executor,
            "duration_ms": event.duration_ms,
            "status": event.status,
            "metadata": event.metadata
        }

        with self._lock:
            with open(self.audit_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + '\n')

    def _format_event(self, event: LogEvent) -> str:
        """Format event for human-readable log"""
        parts = []

        if event.batch_id is not None:
            parts.append(f"[Batch {event.batch_id}]")

        if event.task_id:
            parts.append(f"[Task {event.task_id}]")

        if event.executor:
            emoji = {"claude": "🧠", "gemini": "💎", "codex": "🔷"}.get(event.executor, "")
            parts.append(f"[{emoji} {event.executor}]")

        parts.append(event.message)

        if event.duration_ms is not None:
            duration_str = self._format_duration(event.duration_ms)
            parts.append(f"({duration_str})")

        if event.status:
            status_emoji = {"completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(event.status, "")
            parts.append(f"{status_emoji}")

        return " ".join(parts)

    def _format_duration(self, ms: int) -> str:
        """Format duration for display"""
        if ms < 1000:
            return f"{ms}ms"
        elif ms < 60000:
            return f"{ms / 1000:.1f}s"
        else:
            minutes = ms // 60000
            seconds = (ms % 60000) / 1000
            return f"{minutes}m{seconds:.0f}s"

    # ─────────────────────────────────────────────────────────────────────
    # Execution Lifecycle
    # ─────────────────────────────────────────────────────────────────────

    def log_execution_start(self, feature_name: str, total_batches: int, total_tasks: int):
        """Log start of execution"""
        self.feature_name = feature_name
        self._execution_start = time.time()
        with self._lock:
            self.stats["total_tasks"] = total_tasks

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.EXECUTION_START,
            message=f"Starting execution: {feature_name}",
            feature_name=feature_name,
            metadata={
                "total_batches": total_batches,
                "total_tasks": total_tasks,
                "execution_id": self.execution_id
            }
        ))

    def log_execution_end(self, status: str):
        """Log end of execution"""
        duration_ms = None
        if self._execution_start:
            duration_ms = int((time.time() - self._execution_start) * 1000)
            with self._lock:
                self.stats["total_duration_ms"] = duration_ms

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.EXECUTION_END,
            message=f"Execution completed: {status}",
            feature_name=self.feature_name,
            duration_ms=duration_ms,
            status=status,
            metadata=self.stats.copy()
        ))

    # ─────────────────────────────────────────────────────────────────────
    # Batch Events
    # ─────────────────────────────────────────────────────────────────────

    def log_batch_start(self, batch_id: int, batch_name: str, task_count: int):
        """Log start of batch execution"""
        with self._lock:
            self._batch_starts[batch_id] = time.time()

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.BATCH_START,
            message=f"Starting batch: {batch_name}",
            batch_id=batch_id,
            metadata={"task_count": task_count}
        ))

    def log_batch_end(self, batch_id: int, batch_name: str, status: str):
        """Log end of batch execution"""
        duration_ms = None
        with self._lock:
            if batch_id in self._batch_starts:
                duration_ms = int((time.time() - self._batch_starts[batch_id]) * 1000)
                del self._batch_starts[batch_id]

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.BATCH_END,
            message=f"Batch completed: {batch_name}",
            batch_id=batch_id,
            duration_ms=duration_ms,
            status=status
        ))

    # ─────────────────────────────────────────────────────────────────────
    # Task Events
    # ─────────────────────────────────────────────────────────────────────

    def log_task_start(self, task_id: str, task_name: str, executor: str, batch_id: Optional[int] = None):
        """Log start of task execution"""
        with self._lock:
            self._task_starts[task_id] = time.time()

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.TASK_START,
            message=f"Starting task: {task_name}",
            task_id=task_id,
            batch_id=batch_id,
            executor=executor
        ))

    def log_task_end(
        self,
        task_id: str,
        task_name: str,
        executor: str,
        status: str,
        batch_id: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """Log end of task execution"""
        duration_ms = None
        with self._lock:
            if task_id in self._task_starts:
                duration_ms = int((time.time() - self._task_starts[task_id]) * 1000)
                del self._task_starts[task_id]

        # Update statistics (thread-safe)
        with self._lock:
            if status == "completed":
                self.stats["completed_tasks"] += 1
            elif status == "failed":
                self.stats["failed_tasks"] += 1
            elif status == "skipped":
                self.stats["skipped_tasks"] += 1

        metadata = {}
        if error_message:
            metadata["error"] = error_message

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.TASK_END,
            message=f"Task completed: {task_name}",
            task_id=task_id,
            batch_id=batch_id,
            executor=executor,
            duration_ms=duration_ms,
            status=status,
            metadata=metadata
        ))

    def log_task_retry(self, task_id: str, task_name: str, attempt: int, reason: str):
        """Log task retry attempt"""
        with self._lock:
            self.stats["retried_tasks"] += 1

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.TASK_RETRY,
            message=f"Retrying task: {task_name} (attempt {attempt})",
            task_id=task_id,
            metadata={"attempt": attempt, "reason": reason}
        ))

    # ─────────────────────────────────────────────────────────────────────
    # Executor Events
    # ─────────────────────────────────────────────────────────────────────

    def log_executor_call(self, executor: str, task_id: str, prompt_preview: str):
        """Log call to executor"""
        with self._lock:
            self.stats["executor_calls"][executor] = self.stats["executor_calls"].get(executor, 0) + 1

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.EXECUTOR_CALL,
            message=f"Calling {executor}",
            task_id=task_id,
            executor=executor,
            metadata={"prompt_preview": prompt_preview[:100] + "..." if len(prompt_preview) > 100 else prompt_preview}
        ))

    def log_executor_response(self, executor: str, task_id: str, response_preview: str, duration_ms: int):
        """Log response from executor"""
        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.EXECUTOR_RESPONSE,
            message=f"Response from {executor}",
            task_id=task_id,
            executor=executor,
            duration_ms=duration_ms,
            status="success",
            metadata={"response_preview": response_preview[:100] + "..." if len(response_preview) > 100 else response_preview}
        ))

    def log_executor_error(self, executor: str, task_id: str, error: str):
        """Log executor error"""
        with self._lock:
            self.stats["executor_errors"][executor] = self.stats["executor_errors"].get(executor, 0) + 1

        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.EXECUTOR_ERROR,
            message=f"Error from {executor}: {error}",
            task_id=task_id,
            executor=executor,
            status="error",
            metadata={"error": error}
        ))

    # ─────────────────────────────────────────────────────────────────────
    # Checkpoint Events
    # ─────────────────────────────────────────────────────────────────────

    def log_checkpoint_save(self, feature_name: str, current_batch: int):
        """Log checkpoint save"""
        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.CHECKPOINT_SAVE,
            message=f"Checkpoint saved",
            feature_name=feature_name,
            batch_id=current_batch
        ))

    def log_checkpoint_resume(self, feature_name: str, batch_id: int, incomplete_tasks: int):
        """Log checkpoint resume"""
        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.CHECKPOINT_RESUME,
            message=f"Resuming from checkpoint",
            feature_name=feature_name,
            batch_id=batch_id,
            metadata={"incomplete_tasks": incomplete_tasks}
        ))

    # ─────────────────────────────────────────────────────────────────────
    # User Interaction Events
    # ─────────────────────────────────────────────────────────────────────

    def log_user_confirm(self, action: str, choice: str):
        """Log user confirmation"""
        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.USER_CONFIRM,
            message=f"User confirmed: {action}",
            metadata={"action": action, "choice": choice}
        ))

    def log_user_cancel(self, action: str, reason: Optional[str] = None):
        """Log user cancellation"""
        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.USER_CANCEL,
            message=f"User cancelled: {action}",
            metadata={"action": action, "reason": reason}
        ))

    # ─────────────────────────────────────────────────────────────────────
    # General Events
    # ─────────────────────────────────────────────────────────────────────

    def log_info(self, message: str, **metadata):
        """Log informational message"""
        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.INFO,
            message=message,
            metadata=metadata
        ))

    def log_warning(self, message: str, **metadata):
        """Log warning message"""
        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.WARNING,
            message=message,
            metadata=metadata
        ))

    def log_error(self, message: str, **metadata):
        """Log error message"""
        self._log_event(LogEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.ERROR,
            message=message,
            metadata=metadata
        ))

    # ─────────────────────────────────────────────────────────────────────
    # Reports
    # ─────────────────────────────────────────────────────────────────────

    def get_execution_report(self) -> Dict:
        """Get execution report"""
        return {
            "execution_id": self.execution_id,
            "feature_name": self.feature_name,
            "statistics": self.stats,
            "log_file": str(self.audit_file)
        }

    def generate_summary_report(self) -> str:
        """Generate human-readable summary report"""
        lines = [
            "═" * 60,
            "           Nexus CLI Execution Report",
            "═" * 60,
            "",
            f"Execution ID: {self.execution_id}",
            f"Feature: {self.feature_name}",
            "",
            "─" * 60,
            "                    Statistics",
            "─" * 60,
            "",
            f"Total Tasks:     {self.stats['total_tasks']}",
            f"  ✅ Completed:  {self.stats['completed_tasks']}",
            f"  ❌ Failed:     {self.stats['failed_tasks']}",
            f"  ⏭️  Skipped:    {self.stats['skipped_tasks']}",
            f"  🔄 Retried:    {self.stats['retried_tasks']}",
            "",
            "─" * 60,
            "                  Executor Usage",
            "─" * 60,
            "",
        ]

        for executor, count in self.stats["executor_calls"].items():
            errors = self.stats["executor_errors"].get(executor, 0)
            emoji = {"claude": "🧠", "gemini": "💎", "codex": "🔷"}.get(executor, "")
            lines.append(f"  {emoji} {executor}: {count} calls, {errors} errors")

        lines.extend([
            "",
            "─" * 60,
            f"Total Duration: {self._format_duration(self.stats.get('total_duration_ms', 0))}",
            f"Log File: {self.audit_file}",
            "═" * 60,
        ])

        return "\n".join(lines)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nexus CLI Execution Logger")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # View command
    view_parser = subparsers.add_parser("view", help="View execution log")
    view_parser.add_argument("log_file", help="Path to audit log file")
    view_parser.add_argument("--filter", help="Filter by event type")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show log statistics")
    stats_parser.add_argument("log_file", help="Path to audit log file")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run self-test")

    args = parser.parse_args()

    if args.command == "view":
        log_path = Path(args.log_file)
        if not log_path.exists():
            print(f"Log file not found: {log_path}")
            sys.exit(1)

        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                event = json.loads(line)
                if args.filter and event["event_type"] != args.filter:
                    continue
                ts = event["timestamp"][:19]
                msg = event["message"]
                print(f"[{ts}] {event['event_type']}: {msg}")

    elif args.command == "stats":
        log_path = Path(args.log_file)
        if not log_path.exists():
            print(f"Log file not found: {log_path}")
            sys.exit(1)

        events = []
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                events.append(json.loads(line))

        print(f"Total events: {len(events)}")
        print("\nEvent types:")
        event_counts = {}
        for e in events:
            et = e["event_type"]
            event_counts[et] = event_counts.get(et, 0) + 1
        for et, count in sorted(event_counts.items(), key=lambda x: -x[1]):
            print(f"  {et}: {count}")

    elif args.command == "test":
        print("Running execution logger self-test...")

        logger = ExecutionLogger(feature_name="test-feature")
        logger.log_execution_start("test-feature", 3, 7)

        # Simulate batch 1
        logger.log_batch_start(1, "数据层", 2)
        logger.log_task_start("1.1", "Create User Model", "codex", 1)
        time.sleep(0.1)
        logger.log_executor_call("codex", "1.1", "Create User model...")
        time.sleep(0.1)
        logger.log_executor_response("codex", "1.1", "Model created", 100)
        logger.log_task_end("1.1", "Create User Model", "codex", "completed", 1)
        logger.log_batch_end(1, "数据层", "completed")

        logger.log_execution_end("completed")

        print(logger.generate_summary_report())
        print("\n🎉 Self-test complete!")

    else:
        parser.print_help()
