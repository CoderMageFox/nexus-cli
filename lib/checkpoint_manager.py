#!/usr/bin/env python3
"""
Nexus CLI Checkpoint Manager

Provides task execution state persistence for:
- Saving execution progress at batch boundaries
- Resuming interrupted executions
- Recovery from failures

Storage location: .nexus-temp/checkpoints/
"""

import json
import os
import time
import hashlib
import threading
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
from pathlib import Path


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BatchStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"  # Some tasks completed, some failed
    FAILED = "failed"


@dataclass
class TaskState:
    """State of a single task"""
    task_id: str
    name: str
    executor: str
    status: TaskStatus
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    retry_count: int = 0
    result: Optional[str] = None


@dataclass
class BatchState:
    """State of a batch of tasks"""
    batch_id: int
    name: str
    batch_type: str  # "serial" or "parallel"
    status: BatchStatus
    tasks: List[TaskState] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@dataclass
class ExecutionCheckpoint:
    """Complete execution checkpoint state"""
    feature_name: str
    version: str = "1.0.0"
    spec_completed: bool = False
    current_batch: int = 0
    total_batches: int = 0
    batches: List[BatchState] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    execution_id: str = field(default_factory=lambda: hashlib.md5(
        f"{time.time()}".encode()).hexdigest()[:8])
    config: Dict[str, Any] = field(default_factory=dict)
    error_log: List[Dict] = field(default_factory=list)


class CheckpointManager:
    """Manager for execution checkpoints"""

    CHECKPOINT_DIR = ".nexus-temp/checkpoints"
    CHECKPOINT_FILE = "checkpoint.json"

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.checkpoint_dir = self.project_root / self.CHECKPOINT_DIR
        self._lock = threading.Lock()

    def _ensure_dir(self):
        """Ensure checkpoint directory exists"""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, feature_name: str) -> Path:
        """Get checkpoint file path for a feature"""
        # Sanitize feature name for filesystem
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in feature_name)
        return self.checkpoint_dir / safe_name / self.CHECKPOINT_FILE

    def create_checkpoint(self, feature_name: str, batches_config: List[Dict]) -> ExecutionCheckpoint:
        """Create a new checkpoint for a feature execution"""
        self._ensure_dir()

        # Convert batches config to BatchState objects
        batch_states = []
        for batch in batches_config:
            tasks = [
                TaskState(
                    task_id=t["id"],
                    name=t["name"],
                    executor=t["executor"],
                    status=TaskStatus.PENDING,
                    output_file=t.get("output_file")
                )
                for t in batch.get("tasks", [])
            ]
            batch_state = BatchState(
                batch_id=batch["id"],
                name=batch["name"],
                batch_type=batch.get("type", "serial"),
                status=BatchStatus.PENDING,
                tasks=tasks
            )
            batch_states.append(batch_state)

        checkpoint = ExecutionCheckpoint(
            feature_name=feature_name,
            total_batches=len(batch_states),
            batches=batch_states
        )

        self.save_checkpoint(checkpoint)
        return checkpoint

    def save_checkpoint(self, checkpoint: ExecutionCheckpoint) -> bool:
        """Save checkpoint to disk"""
        self._ensure_dir()
        checkpoint_path = self._get_checkpoint_path(checkpoint.feature_name)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        checkpoint.updated_at = datetime.now().isoformat()

        # Convert to dict for JSON serialization
        def to_dict(obj):
            if isinstance(obj, Enum):
                return obj.value
            elif hasattr(obj, '__dataclass_fields__'):
                return {k: to_dict(v) for k, v in asdict(obj).items()}
            elif isinstance(obj, list):
                return [to_dict(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            return obj

        data = to_dict(checkpoint)

        temp_path = checkpoint_path.with_suffix('.tmp')
        try:
            # Write atomically using temp file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.rename(checkpoint_path)
            return True
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
            # Clean up temp file on failure
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            return False

    def load_checkpoint(self, feature_name: str) -> Optional[ExecutionCheckpoint]:
        """Load checkpoint from disk"""
        checkpoint_path = self._get_checkpoint_path(feature_name)

        if not checkpoint_path.exists():
            return None

        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Reconstruct checkpoint from dict
            batches = []
            for b in data.get("batches", []):
                tasks = [
                    TaskState(
                        task_id=t["task_id"],
                        name=t["name"],
                        executor=t["executor"],
                        status=TaskStatus(t["status"]),
                        output_file=t.get("output_file"),
                        error_message=t.get("error_message"),
                        start_time=t.get("start_time"),
                        end_time=t.get("end_time"),
                        retry_count=t.get("retry_count", 0),
                        result=t.get("result")
                    )
                    for t in b.get("tasks", [])
                ]
                batch = BatchState(
                    batch_id=b["batch_id"],
                    name=b["name"],
                    batch_type=b["batch_type"],
                    status=BatchStatus(b["status"]),
                    tasks=tasks,
                    start_time=b.get("start_time"),
                    end_time=b.get("end_time")
                )
                batches.append(batch)

            checkpoint = ExecutionCheckpoint(
                feature_name=data["feature_name"],
                version=data.get("version", "1.0.0"),
                spec_completed=data.get("spec_completed", False),
                current_batch=data.get("current_batch", 0),
                total_batches=data.get("total_batches", 0),
                batches=batches,
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                execution_id=data.get("execution_id", ""),
                config=data.get("config", {}),
                error_log=data.get("error_log", [])
            )

            return checkpoint

        except Exception as e:
            print(f"Error loading checkpoint: {e}")
            return None

    def update_task_status(
        self,
        feature_name: str,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
        result: Optional[str] = None
    ) -> bool:
        """Update status of a specific task (thread-safe)"""
        with self._lock:
            checkpoint = self.load_checkpoint(feature_name)
            if not checkpoint:
                return False

            for batch in checkpoint.batches:
                for task in batch.tasks:
                    if task.task_id == task_id:
                        task.status = status
                        if status == TaskStatus.IN_PROGRESS:
                            task.start_time = datetime.now().isoformat()
                        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                            task.end_time = datetime.now().isoformat()
                        if error_message:
                            task.error_message = error_message
                            checkpoint.error_log.append({
                                "task_id": task_id,
                                "error": error_message,
                                "timestamp": datetime.now().isoformat()
                            })
                        if result:
                            task.result = result

                        return self.save_checkpoint(checkpoint)

            return False

    def update_batch_status(
        self,
        feature_name: str,
        batch_id: int,
        status: BatchStatus
    ) -> bool:
        """Update status of a batch (thread-safe)"""
        with self._lock:
            checkpoint = self.load_checkpoint(feature_name)
            if not checkpoint:
                return False

            for batch in checkpoint.batches:
                if batch.batch_id == batch_id:
                    batch.status = status
                    if status == BatchStatus.IN_PROGRESS:
                        batch.start_time = datetime.now().isoformat()
                        checkpoint.current_batch = batch_id
                    elif status in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.PARTIAL]:
                        batch.end_time = datetime.now().isoformat()

                    return self.save_checkpoint(checkpoint)

            return False

    def get_resume_point(self, feature_name: str) -> Optional[Dict]:
        """Get the point from which execution should resume"""
        checkpoint = self.load_checkpoint(feature_name)
        if not checkpoint:
            return None

        # Find first incomplete batch
        for batch in checkpoint.batches:
            if batch.status in [BatchStatus.PENDING, BatchStatus.IN_PROGRESS, BatchStatus.PARTIAL]:
                # Find incomplete tasks in this batch
                incomplete_tasks = [
                    task for task in batch.tasks
                    if task.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.FAILED]
                ]
                return {
                    "batch_id": batch.batch_id,
                    "batch_name": batch.name,
                    "incomplete_tasks": [
                        {"id": t.task_id, "name": t.name, "executor": t.executor}
                        for t in incomplete_tasks
                    ],
                    "completed_tasks": [
                        t.task_id for t in batch.tasks
                        if t.status == TaskStatus.COMPLETED
                    ]
                }

        return None  # All batches completed

    def get_execution_summary(self, feature_name: str) -> Optional[Dict]:
        """Get summary of execution progress"""
        checkpoint = self.load_checkpoint(feature_name)
        if not checkpoint:
            return None

        total_tasks = sum(len(b.tasks) for b in checkpoint.batches)
        completed_tasks = sum(
            1 for b in checkpoint.batches for t in b.tasks
            if t.status == TaskStatus.COMPLETED
        )
        failed_tasks = sum(
            1 for b in checkpoint.batches for t in b.tasks
            if t.status == TaskStatus.FAILED
        )
        pending_tasks = sum(
            1 for b in checkpoint.batches for t in b.tasks
            if t.status == TaskStatus.PENDING
        )

        completed_batches = sum(
            1 for b in checkpoint.batches
            if b.status == BatchStatus.COMPLETED
        )

        return {
            "feature_name": checkpoint.feature_name,
            "execution_id": checkpoint.execution_id,
            "progress": {
                "batches": f"{completed_batches}/{checkpoint.total_batches}",
                "tasks": f"{completed_tasks}/{total_tasks}",
                "percentage": round(completed_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0
            },
            "status": {
                "completed": completed_tasks,
                "failed": failed_tasks,
                "pending": pending_tasks,
                "in_progress": total_tasks - completed_tasks - failed_tasks - pending_tasks
            },
            "created_at": checkpoint.created_at,
            "updated_at": checkpoint.updated_at,
            "has_errors": len(checkpoint.error_log) > 0,
            "error_count": len(checkpoint.error_log)
        }

    def save_checkpoint_if_loaded(self, feature_name: str) -> bool:
        """Force-save the current checkpoint state (for signal handlers).
        Re-loads and saves to ensure updated_at is refreshed."""
        checkpoint = self.load_checkpoint(feature_name)
        if checkpoint:
            return self.save_checkpoint(checkpoint)
        return False

    def delete_checkpoint(self, feature_name: str) -> bool:
        """Delete checkpoint for a feature"""
        checkpoint_path = self._get_checkpoint_path(feature_name)
        try:
            if checkpoint_path.exists():
                checkpoint_path.unlink()
                # Also remove parent directory if empty
                if checkpoint_path.parent.exists() and not any(checkpoint_path.parent.iterdir()):
                    checkpoint_path.parent.rmdir()
            return True
        except Exception as e:
            print(f"Error deleting checkpoint: {e}")
            return False

    def list_checkpoints(self) -> List[Dict]:
        """List all available checkpoints"""
        if not self.checkpoint_dir.exists():
            return []

        checkpoints = []
        for feature_dir in self.checkpoint_dir.iterdir():
            if feature_dir.is_dir():
                checkpoint_file = feature_dir / self.CHECKPOINT_FILE
                if checkpoint_file.exists():
                    summary = self.get_execution_summary(feature_dir.name)
                    if summary:
                        checkpoints.append(summary)

        return checkpoints


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nexus CLI Checkpoint Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List all checkpoints")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show checkpoint details")
    show_parser.add_argument("feature", help="Feature name")

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Get resume point")
    resume_parser.add_argument("feature", help="Feature name")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete checkpoint")
    delete_parser.add_argument("feature", help="Feature name")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run self-test")

    args = parser.parse_args()

    manager = CheckpointManager()

    if args.command == "list":
        checkpoints = manager.list_checkpoints()
        if checkpoints:
            print("Available checkpoints:")
            for cp in checkpoints:
                print(f"  - {cp['feature_name']}: {cp['progress']['percentage']}% "
                      f"({cp['progress']['tasks']} tasks)")
        else:
            print("No checkpoints found")

    elif args.command == "show":
        summary = manager.get_execution_summary(args.feature)
        if summary:
            print(json.dumps(summary, indent=2))
        else:
            print(f"No checkpoint found for '{args.feature}'")

    elif args.command == "resume":
        resume_point = manager.get_resume_point(args.feature)
        if resume_point:
            print(f"Resume from batch {resume_point['batch_id']}: {resume_point['batch_name']}")
            print(f"Incomplete tasks: {len(resume_point['incomplete_tasks'])}")
            for task in resume_point['incomplete_tasks']:
                print(f"  - {task['id']}: {task['name']} ({task['executor']})")
        else:
            print("No resume point found (execution may be complete)")

    elif args.command == "delete":
        if manager.delete_checkpoint(args.feature):
            print(f"Checkpoint for '{args.feature}' deleted")
        else:
            print(f"Failed to delete checkpoint for '{args.feature}'")

    elif args.command == "test":
        print("Running checkpoint manager self-test...")

        # Create test checkpoint
        test_batches = [
            {
                "id": 1,
                "name": "Test Batch 1",
                "type": "serial",
                "tasks": [
                    {"id": "1.1", "name": "Task 1", "executor": "Codex"},
                    {"id": "1.2", "name": "Task 2", "executor": "Gemini"}
                ]
            },
            {
                "id": 2,
                "name": "Test Batch 2",
                "type": "parallel",
                "tasks": [
                    {"id": "2.1", "name": "Task 3", "executor": "Claude"},
                    {"id": "2.2", "name": "Task 4", "executor": "Codex"}
                ]
            }
        ]

        checkpoint = manager.create_checkpoint("test-feature", test_batches)
        print(f"✅ Created checkpoint: {checkpoint.execution_id}")

        # Update task status
        manager.update_task_status("test-feature", "1.1", TaskStatus.COMPLETED)
        print("✅ Updated task status")

        # Get summary
        summary = manager.get_execution_summary("test-feature")
        print(f"✅ Summary: {summary['progress']['percentage']}% complete")

        # Get resume point
        resume = manager.get_resume_point("test-feature")
        print(f"✅ Resume point: batch {resume['batch_id']}")

        # Cleanup
        manager.delete_checkpoint("test-feature")
        print("✅ Deleted test checkpoint")

        print("\n🎉 Self-test complete!")

    else:
        parser.print_help()
