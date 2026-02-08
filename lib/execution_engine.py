#!/usr/bin/env python3
"""
Nexus CLI Execution Engine

Provides task execution with:
- Configurable parallel execution control
- Error recovery strategies (retry, skip, fail_fast, ask)
- Integration with checkpoint, config, and logging systems

Storage location: .nexus-temp/
"""

import time
import signal
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from enum import Enum
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed

# Import local modules
from lib.checkpoint_manager import (
    CheckpointManager, TaskStatus, BatchStatus
)
from lib.config_manager import ConfigManager, NexusConfig, ErrorStrategy
from lib.execution_logger import ExecutionLogger


class ExecutionResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class TaskResult:
    """Result of a single task execution"""
    task_id: str
    task_name: str
    executor: str
    result: ExecutionResult
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    retry_count: int = 0


@dataclass
class BatchResult:
    """Result of a batch execution"""
    batch_id: int
    batch_name: str
    batch_type: str
    task_results: List[TaskResult] = field(default_factory=list)
    status: BatchStatus = BatchStatus.PENDING
    duration_seconds: float = 0.0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.task_results if r.result == ExecutionResult.SUCCESS)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.task_results if r.result == ExecutionResult.FAILED)

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.task_results if r.result == ExecutionResult.SKIPPED)


class ExecutionEngine:
    """
    Execution engine for Nexus CLI tasks

    Features:
    - Parallel execution with configurable concurrency
    - Error recovery strategies
    - Checkpoint integration for resume capability
    - Comprehensive logging and audit trail
    """

    def __init__(
        self,
        config: Optional[NexusConfig] = None,
        project_root: str = ".",
        feature_name: str = "unnamed"
    ):
        self.project_root = Path(project_root).resolve()
        self.feature_name = feature_name

        # Load configuration
        if config:
            self.config = config
        else:
            config_manager = ConfigManager(str(self.project_root))
            self.config = config_manager.load_config()

        # Initialize managers
        self.checkpoint_manager = CheckpointManager(str(self.project_root))
        self.logger = ExecutionLogger(str(self.project_root))

        # Execution state
        self._cancelled = False
        self._pause_requested = False
        self._current_batch: Optional[int] = None
        self._executor_pool: Optional[ThreadPoolExecutor] = None

        # Callbacks
        self._on_task_start: Optional[Callable[[str, str], None]] = None
        self._on_task_complete: Optional[Callable[[TaskResult], None]] = None
        self._on_batch_complete: Optional[Callable[[BatchResult], None]] = None
        self._on_progress_update: Optional[Callable[[Dict], None]] = None
        self._on_error_decision: Optional[Callable[[str, str, str], str]] = None

        # Setup signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown, preserving existing handlers"""
        self._prev_sigint = signal.getsignal(signal.SIGINT)
        self._prev_sigterm = signal.getsignal(signal.SIGTERM)

        def handle_interrupt(signum, frame):
            print("\n⚠️  Interrupt received, saving checkpoint...")
            self._cancelled = True
            # Force-save checkpoint on interrupt
            try:
                self.checkpoint_manager.save_checkpoint_if_loaded(self.feature_name)
            except Exception:
                pass
            # Call previous handler if it was a callable
            prev = self._prev_sigint if signum == signal.SIGINT else self._prev_sigterm
            if callable(prev) and prev not in (signal.SIG_DFL, signal.SIG_IGN):
                prev(signum, frame)

        signal.signal(signal.SIGINT, handle_interrupt)
        signal.signal(signal.SIGTERM, handle_interrupt)

    # ─────────────────────────────────────────────────────────────────────────
    # Callback Registration
    # ─────────────────────────────────────────────────────────────────────────

    def on_task_start(self, callback: Callable[[str, str], None]):
        """Register callback for task start events"""
        self._on_task_start = callback

    def on_task_complete(self, callback: Callable[[TaskResult], None]):
        """Register callback for task completion events"""
        self._on_task_complete = callback

    def on_batch_complete(self, callback: Callable[[BatchResult], None]):
        """Register callback for batch completion events"""
        self._on_batch_complete = callback

    def on_progress_update(self, callback: Callable[[Dict], None]):
        """Register callback for progress updates"""
        self._on_progress_update = callback

    def on_error_decision(self, callback: Callable[[str, str, str], str]):
        """
        Register callback for error decision (when strategy is 'ask')

        Callback receives: (task_id, task_name, error_message)
        Should return: 'retry', 'skip', or 'abort'
        """
        self._on_error_decision = callback

    # ─────────────────────────────────────────────────────────────────────────
    # Task Execution
    # ─────────────────────────────────────────────────────────────────────────

    def execute_task(
        self,
        task_id: str,
        task_name: str,
        executor: str,
        task_func: Callable[[], Any],
        timeout_seconds: Optional[int] = None
    ) -> TaskResult:
        """
        Execute a single task with retry and timeout support

        Args:
            task_id: Unique task identifier
            task_name: Human-readable task name
            executor: Executor name (claude, gemini, codex)
            task_func: Function to execute
            timeout_seconds: Optional timeout override

        Returns:
            TaskResult with execution outcome
        """
        if timeout_seconds is None:
            timeout_seconds = self.config.execution.task_timeout_minutes * 60

        max_retries = self.config.execution.max_retries
        retry_delay = self.config.execution.retry_delay_seconds
        retry_count = 0

        # Notify task start
        if self._on_task_start:
            try:
                self._on_task_start(task_id, task_name)
            except Exception:
                pass

        self.logger.log_task_start(task_id, task_name, executor)
        self.checkpoint_manager.update_task_status(
            self.feature_name, task_id, TaskStatus.IN_PROGRESS
        )

        start_time = time.time()
        last_error = None

        while retry_count <= max_retries:
            if self._cancelled:
                return TaskResult(
                    task_id=task_id,
                    task_name=task_name,
                    executor=executor,
                    result=ExecutionResult.CANCELLED,
                    error="Execution cancelled by user",
                    duration_seconds=time.time() - start_time,
                    retry_count=retry_count
                )

            try:
                # Execute with timeout
                result = self._execute_with_timeout(task_func, timeout_seconds)

                # Success
                duration = time.time() - start_time
                task_result = TaskResult(
                    task_id=task_id,
                    task_name=task_name,
                    executor=executor,
                    result=ExecutionResult.SUCCESS,
                    output=str(result) if result else None,
                    duration_seconds=duration,
                    retry_count=retry_count
                )

                self.logger.log_task_end(
                    task_id, task_name, executor, status="completed"
                )
                self.checkpoint_manager.update_task_status(
                    self.feature_name, task_id, TaskStatus.COMPLETED,
                    result=str(result) if result else None
                )

                if self._on_task_complete:
                    try:
                        self._on_task_complete(task_result)
                    except Exception:
                        pass

                return task_result

            except TimeoutError:
                last_error = f"Task timed out after {timeout_seconds} seconds"
                self.logger.log_error(last_error, task_id=task_id, error_type="timeout")

            except Exception as e:
                last_error = str(e)
                self.logger.log_error(last_error, task_id=task_id, error_type="execution_error")

            # Handle error based on strategy
            decision = self._handle_error(task_id, task_name, last_error, retry_count)

            if decision == "retry":
                retry_count += 1
                if retry_count <= max_retries:
                    self.logger.log_task_retry(task_id, task_name, retry_count, last_error)
                    time.sleep(retry_delay)
                    continue

            elif decision == "skip":
                duration = time.time() - start_time
                task_result = TaskResult(
                    task_id=task_id,
                    task_name=task_name,
                    executor=executor,
                    result=ExecutionResult.SKIPPED,
                    error=last_error,
                    duration_seconds=duration,
                    retry_count=retry_count
                )

                self.checkpoint_manager.update_task_status(
                    self.feature_name, task_id, TaskStatus.SKIPPED,
                    error_message=last_error
                )

                if self._on_task_complete:
                    try:
                        self._on_task_complete(task_result)
                    except Exception:
                        pass

                return task_result

            elif decision == "abort":
                self._cancelled = True
                break

        # Failed after all retries
        duration = time.time() - start_time
        task_result = TaskResult(
            task_id=task_id,
            task_name=task_name,
            executor=executor,
            result=ExecutionResult.FAILED,
            error=last_error,
            duration_seconds=duration,
            retry_count=retry_count
        )

        self.checkpoint_manager.update_task_status(
            self.feature_name, task_id, TaskStatus.FAILED,
            error_message=last_error
        )

        if self._on_task_complete:
            try:
                self._on_task_complete(task_result)
            except Exception:
                pass

        return task_result

    def _execute_with_timeout(self, func: Callable, timeout: int) -> Any:
        """Execute a function with timeout using ThreadPoolExecutor"""
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(func)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError:
                future.cancel()
                raise TimeoutError(f"Execution timed out after {timeout} seconds")

    def _handle_error(
        self,
        task_id: str,
        task_name: str,
        error: str,
        retry_count: int
    ) -> str:
        """
        Handle task error based on configured strategy

        Returns: 'retry', 'skip', or 'abort'
        """
        strategy = self.config.execution.error_strategy
        max_retries = self.config.execution.max_retries

        if strategy == ErrorStrategy.RETRY:
            if retry_count < max_retries:
                return "retry"
            return "skip"  # Give up after max retries

        elif strategy == ErrorStrategy.SKIP:
            return "skip"

        elif strategy == ErrorStrategy.FAIL_FAST:
            return "abort"

        elif strategy == ErrorStrategy.ASK:
            if self._on_error_decision:
                return self._on_error_decision(task_id, task_name, error)
            # Default to retry if no callback
            if retry_count < max_retries:
                return "retry"
            return "skip"

        return "skip"

    # ─────────────────────────────────────────────────────────────────────────
    # Batch Execution
    # ─────────────────────────────────────────────────────────────────────────

    def execute_batch_serial(
        self,
        batch_id: int,
        batch_name: str,
        tasks: List[Dict],
        task_executor: Callable[[Dict], Any]
    ) -> BatchResult:
        """
        Execute tasks in a batch sequentially

        Args:
            batch_id: Batch identifier
            batch_name: Human-readable batch name
            tasks: List of task dictionaries with id, name, executor
            task_executor: Function to execute each task

        Returns:
            BatchResult with all task outcomes
        """
        self.logger.log_batch_start(batch_id, batch_name, len(tasks))
        self.checkpoint_manager.update_batch_status(
            self.feature_name, batch_id, BatchStatus.IN_PROGRESS
        )

        start_time = time.time()
        batch_result = BatchResult(
            batch_id=batch_id,
            batch_name=batch_name,
            batch_type="serial"
        )

        for task in tasks:
            if self._cancelled:
                break

            task_result = self.execute_task(
                task_id=task["id"],
                task_name=task["name"],
                executor=task["executor"],
                task_func=lambda t=task: task_executor(t)
            )
            batch_result.task_results.append(task_result)

            # Update progress
            if self._on_progress_update:
                try:
                    self._on_progress_update({
                        "batch_id": batch_id,
                        "completed": len(batch_result.task_results),
                        "total": len(tasks),
                        "success": batch_result.success_count,
                        "failed": batch_result.failed_count
                    })
                except Exception:
                    pass

            # Check for fail-fast
            if (task_result.result == ExecutionResult.FAILED and
                self.config.execution.error_strategy == ErrorStrategy.FAIL_FAST):
                break

        # Determine batch status
        batch_result.duration_seconds = time.time() - start_time

        if self._cancelled:
            batch_result.status = BatchStatus.PARTIAL
        elif batch_result.failed_count == 0:
            batch_result.status = BatchStatus.COMPLETED
        elif batch_result.success_count == 0:
            batch_result.status = BatchStatus.FAILED
        else:
            batch_result.status = BatchStatus.PARTIAL

        self.logger.log_batch_end(batch_id, batch_name, batch_result.status.value)
        self.checkpoint_manager.update_batch_status(
            self.feature_name, batch_id, batch_result.status
        )

        if self._on_batch_complete:
            try:
                self._on_batch_complete(batch_result)
            except Exception:
                pass

        return batch_result

    def execute_batch_parallel(
        self,
        batch_id: int,
        batch_name: str,
        tasks: List[Dict],
        task_executor: Callable[[Dict], Any]
    ) -> BatchResult:
        """
        Execute tasks in a batch in parallel with controlled concurrency

        Args:
            batch_id: Batch identifier
            batch_name: Human-readable batch name
            tasks: List of task dictionaries with id, name, executor
            task_executor: Function to execute each task

        Returns:
            BatchResult with all task outcomes
        """
        max_parallel = self.config.execution.max_parallel_tasks
        self.logger.log_batch_start(batch_id, batch_name, len(tasks))
        self.checkpoint_manager.update_batch_status(
            self.feature_name, batch_id, BatchStatus.IN_PROGRESS
        )

        start_time = time.time()
        batch_result = BatchResult(
            batch_id=batch_id,
            batch_name=batch_name,
            batch_type="parallel"
        )

        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            self._executor_pool = executor

            # Submit all tasks
            future_to_task = {}
            for task in tasks:
                if self._cancelled:
                    break

                future = executor.submit(
                    self.execute_task,
                    task_id=task["id"],
                    task_name=task["name"],
                    executor=task["executor"],
                    task_func=lambda t=task: task_executor(t)
                )
                future_to_task[future] = task

            # Collect results as they complete
            for future in as_completed(future_to_task):
                if self._cancelled:
                    # Cancel remaining futures
                    for f in future_to_task:
                        f.cancel()
                    break

                try:
                    task_result = future.result()
                    batch_result.task_results.append(task_result)
                except Exception as e:
                    task = future_to_task[future]
                    batch_result.task_results.append(TaskResult(
                        task_id=task["id"],
                        task_name=task["name"],
                        executor=task["executor"],
                        result=ExecutionResult.FAILED,
                        error=str(e)
                    ))

                # Update progress
                if self._on_progress_update:
                    try:
                        self._on_progress_update({
                            "batch_id": batch_id,
                            "completed": len(batch_result.task_results),
                            "total": len(tasks),
                            "success": batch_result.success_count,
                            "failed": batch_result.failed_count
                        })
                    except Exception:
                        pass

            self._executor_pool = None

        # Determine batch status
        batch_result.duration_seconds = time.time() - start_time

        if self._cancelled:
            batch_result.status = BatchStatus.PARTIAL
        elif batch_result.failed_count == 0:
            batch_result.status = BatchStatus.COMPLETED
        elif batch_result.success_count == 0:
            batch_result.status = BatchStatus.FAILED
        else:
            batch_result.status = BatchStatus.PARTIAL

        self.logger.log_batch_end(batch_id, batch_name, batch_result.status.value)
        self.checkpoint_manager.update_batch_status(
            self.feature_name, batch_id, batch_result.status
        )

        if self._on_batch_complete:
            try:
                self._on_batch_complete(batch_result)
            except Exception:
                pass

        return batch_result

    # ─────────────────────────────────────────────────────────────────────────
    # Full Execution Pipeline
    # ─────────────────────────────────────────────────────────────────────────

    def execute_all_batches(
        self,
        batches: List[Dict],
        task_executor: Callable[[Dict], Any],
        resume: bool = True
    ) -> List[BatchResult]:
        """
        Execute all batches with checkpoint support

        Args:
            batches: List of batch configurations
            task_executor: Function to execute individual tasks
            resume: Whether to resume from checkpoint if available

        Returns:
            List of BatchResult for all batches
        """
        # Initialize or load checkpoint
        checkpoint = None
        if resume:
            checkpoint = self.checkpoint_manager.load_checkpoint(self.feature_name)

        if not checkpoint:
            checkpoint = self.checkpoint_manager.create_checkpoint(
                self.feature_name, batches
            )

        self.logger.log_execution_start(
            self.feature_name,
            len(batches),
            sum(len(b.get("tasks", [])) for b in batches)
        )

        results = []
        start_batch = 0

        # Find resume point if resuming
        if resume and checkpoint:
            resume_point = self.checkpoint_manager.get_resume_point(self.feature_name)
            if resume_point:
                start_batch = resume_point["batch_id"] - 1
                print(f"📍 Resuming from batch {resume_point['batch_id']}: {resume_point['batch_name']}")

        # Execute batches
        for i, batch in enumerate(batches):
            if i < start_batch:
                continue

            if self._cancelled:
                break

            self._current_batch = batch["id"]

            # Choose execution method based on batch type
            if batch.get("type", "serial") == "parallel":
                result = self.execute_batch_parallel(
                    batch_id=batch["id"],
                    batch_name=batch["name"],
                    tasks=batch.get("tasks", []),
                    task_executor=task_executor
                )
            else:
                result = self.execute_batch_serial(
                    batch_id=batch["id"],
                    batch_name=batch["name"],
                    tasks=batch.get("tasks", []),
                    task_executor=task_executor
                )

            results.append(result)

            # Check for batch failure with fail-fast
            if (result.status == BatchStatus.FAILED and
                self.config.execution.error_strategy == ErrorStrategy.FAIL_FAST):
                break

        # Log execution complete
        total_success = sum(r.success_count for r in results)
        total_failed = sum(r.failed_count for r in results)
        total_duration = sum(r.duration_seconds for r in results)

        status = "completed" if total_failed == 0 else "partial"
        self.logger.log_execution_end(status)

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Control Methods
    # ─────────────────────────────────────────────────────────────────────────

    def cancel(self):
        """Cancel the current execution"""
        self._cancelled = True
        if self._executor_pool:
            self._executor_pool.shutdown(wait=False)

    def pause(self):
        """Pause execution (checkpoint is automatically saved)"""
        self._pause_requested = True

    def resume(self):
        """Resume paused execution"""
        self._pause_requested = False

    def get_status(self) -> Dict:
        """Get current execution status"""
        summary = self.checkpoint_manager.get_execution_summary(self.feature_name)
        return {
            "feature_name": self.feature_name,
            "cancelled": self._cancelled,
            "paused": self._pause_requested,
            "current_batch": self._current_batch,
            "checkpoint_summary": summary
        }


# ─────────────────────────────────────────────────────────────────────────────
# CLI Interface
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nexus CLI Execution Engine")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run self-test")
    test_parser.add_argument("--parallel", action="store_true", help="Test parallel execution")

    args = parser.parse_args()

    if args.command == "test":
        print("Running execution engine self-test...")
        print("")

        # Create test engine
        engine = ExecutionEngine(feature_name="test-feature")

        # Setup callbacks
        engine.on_task_start(lambda tid, name: print(f"  ▶ Starting: {name}"))
        engine.on_task_complete(lambda r: print(f"  {'✅' if r.result == ExecutionResult.SUCCESS else '❌'} {r.task_name}: {r.result.value}"))
        engine.on_progress_update(lambda p: print(f"  📊 Progress: {p['completed']}/{p['total']}"))

        # Test tasks
        test_tasks = [
            {"id": "1", "name": "Task 1", "executor": "test"},
            {"id": "2", "name": "Task 2", "executor": "test"},
            {"id": "3", "name": "Task 3", "executor": "test"},
        ]

        def mock_executor(task):
            time.sleep(0.5)  # Simulate work
            return f"Result for {task['name']}"

        # Test serial execution
        print("Testing serial execution:")
        result = engine.execute_batch_serial(
            batch_id=1,
            batch_name="Test Serial Batch",
            tasks=test_tasks,
            task_executor=mock_executor
        )
        print(f"  Batch result: {result.status.value}")
        print(f"  Success: {result.success_count}, Failed: {result.failed_count}")
        print("")

        if args.parallel:
            # Test parallel execution
            print("Testing parallel execution:")
            engine2 = ExecutionEngine(feature_name="test-feature-parallel")
            engine2.on_task_start(lambda tid, name: print(f"  ▶ Starting: {name}"))
            engine2.on_task_complete(lambda r: print(f"  {'✅' if r.result == ExecutionResult.SUCCESS else '❌'} {r.task_name}: {r.result.value}"))

            result = engine2.execute_batch_parallel(
                batch_id=1,
                batch_name="Test Parallel Batch",
                tasks=test_tasks,
                task_executor=mock_executor
            )
            print(f"  Batch result: {result.status.value}")
            print(f"  Duration: {result.duration_seconds:.2f}s")
            print("")

        # Cleanup test checkpoints
        engine.checkpoint_manager.delete_checkpoint("test-feature")
        if args.parallel:
            engine2.checkpoint_manager.delete_checkpoint("test-feature-parallel")

        print("🎉 Self-test complete!")

    else:
        parser.print_help()
