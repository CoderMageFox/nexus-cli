#!/usr/bin/env python3
"""
Nexus CLI Configuration Manager

Provides flexible configuration for:
- Executor routing rules
- Parallel execution settings
- Error handling strategies
- Logging and monitoring

Configuration sources (priority order):
1. Environment variables (NEXUS_*)
2. Project config (.nexus-config.yaml)
3. User config (~/.nexus/config.yaml)
4. Default config
"""

import os
import yaml
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
from enum import Enum


class ErrorStrategy(str, Enum):
    """Error handling strategies"""
    RETRY = "retry"           # Retry failed tasks
    SKIP = "skip"             # Skip failed tasks
    FAIL_FAST = "fail_fast"   # Stop on first failure
    ASK = "ask"               # Ask user how to handle


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class RoutingRule:
    """Executor routing rule"""
    pattern: str           # Glob pattern or keyword
    executor: str          # "claude", "gemini", "codex"
    priority: int = 0      # Higher = more priority
    description: str = ""


@dataclass
class ExecutorConfig:
    """Configuration for a specific executor"""
    enabled: bool = True
    timeout_minutes: int = 10
    max_retries: int = 3
    role: str = "default"  # PAL clink role
    preferred_model: str = ""  # Preferred PAL model for this executor


@dataclass
class RoutingConfig:
    """Executor routing configuration"""
    default_executor: str = "claude"
    rules: List[RoutingRule] = field(default_factory=list)
    executors: Dict[str, ExecutorConfig] = field(default_factory=dict)


@dataclass
class ExecutionConfig:
    """Execution behavior configuration"""
    max_parallel_tasks: int = 5
    task_timeout_minutes: int = 10
    batch_timeout_minutes: int = 30
    error_strategy: ErrorStrategy = ErrorStrategy.ASK
    max_retries: int = 3
    retry_delay_seconds: int = 5


@dataclass
class LoggingConfig:
    """Logging configuration"""
    enabled: bool = True
    level: LogLevel = LogLevel.INFO
    log_to_file: bool = True
    log_dir: str = ".nexus-temp/logs"
    max_log_files: int = 10
    max_log_size_mb: int = 10


@dataclass
class ProgressConfig:
    """Progress display configuration"""
    show_task_progress: bool = True
    show_batch_progress: bool = True
    show_time_estimates: bool = True
    show_executor_stats: bool = True
    update_interval_seconds: float = 1.0


@dataclass
class NexusConfig:
    """Complete Nexus CLI configuration"""
    version: str = "1.0.0"
    language: str = "auto"  # "auto", "zh-CN", "en-US"
    spec_dir: str = ".nexus-temp/specs"
    checkpoint_dir: str = ".nexus-temp/checkpoints"

    routing: RoutingConfig = field(default_factory=RoutingConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    progress: ProgressConfig = field(default_factory=ProgressConfig)

    # Feature flags
    skip_code_review: bool = False
    skip_documentation: bool = False
    auto_checkpoint: bool = True


class ConfigManager:
    """Manager for Nexus CLI configuration"""

    DEFAULT_PROJECT_CONFIG = ".nexus-config.yaml"
    DEFAULT_USER_CONFIG = "~/.nexus/config.yaml"
    ENV_PREFIX = "NEXUS_"

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self._config: Optional[NexusConfig] = None

    def _get_default_config(self) -> NexusConfig:
        """Get default configuration"""
        return NexusConfig(
            routing=RoutingConfig(
                default_executor="claude",
                rules=[
                    # Frontend rules
                    RoutingRule(
                        pattern="**/components/**",
                        executor="gemini",
                        priority=10,
                        description="React/Vue components"
                    ),
                    RoutingRule(
                        pattern="*.tsx",
                        executor="gemini",
                        priority=5,
                        description="TypeScript React files"
                    ),
                    RoutingRule(
                        pattern="*.vue",
                        executor="gemini",
                        priority=5,
                        description="Vue components"
                    ),
                    RoutingRule(
                        pattern="**/ui/**",
                        executor="gemini",
                        priority=8,
                        description="UI related files"
                    ),
                    RoutingRule(
                        pattern="**/styles/**",
                        executor="gemini",
                        priority=8,
                        description="Styling files"
                    ),
                    # Backend rules
                    RoutingRule(
                        pattern="**/api/**",
                        executor="codex",
                        priority=10,
                        description="API endpoints"
                    ),
                    RoutingRule(
                        pattern="**/models/**",
                        executor="codex",
                        priority=8,
                        description="Data models"
                    ),
                    RoutingRule(
                        pattern="**/services/**",
                        executor="codex",
                        priority=8,
                        description="Service layer"
                    ),
                    RoutingRule(
                        pattern="**/db/**",
                        executor="codex",
                        priority=10,
                        description="Database related"
                    ),
                    RoutingRule(
                        pattern="*.sql",
                        executor="codex",
                        priority=10,
                        description="SQL files"
                    ),
                    # Architecture rules (Claude)
                    RoutingRule(
                        pattern="**/architecture/**",
                        executor="claude",
                        priority=15,
                        description="Architecture docs"
                    ),
                    RoutingRule(
                        pattern="**/design/**",
                        executor="claude",
                        priority=12,
                        description="Design documents"
                    ),
                ],
                executors={
                    "claude": ExecutorConfig(
                        enabled=True,
                        timeout_minutes=15,
                        max_retries=2,
                        preferred_model="anthropic/claude-opus-4-6"
                    ),
                    "gemini": ExecutorConfig(
                        enabled=True,
                        timeout_minutes=10,
                        max_retries=3,
                        role="default",
                        preferred_model="gemini-3-pro-preview"
                    ),
                    "codex": ExecutorConfig(
                        enabled=True,
                        timeout_minutes=10,
                        max_retries=3,
                        role="default",
                        preferred_model="openai/gpt-5.3-codex"
                    )
                }
            ),
            execution=ExecutionConfig(
                max_parallel_tasks=5,
                task_timeout_minutes=10,
                error_strategy=ErrorStrategy.ASK
            ),
            logging=LoggingConfig(
                enabled=True,
                level=LogLevel.INFO
            ),
            progress=ProgressConfig(
                show_task_progress=True,
                show_batch_progress=True
            )
        )

    def _load_yaml_config(self, path: Path) -> Optional[Dict]:
        """Load configuration from YAML file"""
        if not path.exists():
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            return None

    def _apply_env_overrides(self, config: NexusConfig) -> NexusConfig:
        """Apply environment variable overrides"""
        # Example: NEXUS_MAX_PARALLEL_TASKS=10
        env_mappings = {
            "NEXUS_MAX_PARALLEL_TASKS": ("execution", "max_parallel_tasks", int),
            "NEXUS_TASK_TIMEOUT": ("execution", "task_timeout_minutes", int),
            "NEXUS_BATCH_TIMEOUT": ("execution", "batch_timeout_minutes", int),
            "NEXUS_ERROR_STRATEGY": ("execution", "error_strategy", ErrorStrategy),
            "NEXUS_MAX_RETRIES": ("execution", "max_retries", int),
            "NEXUS_LOG_LEVEL": ("logging", "level", LogLevel),
            "NEXUS_LANGUAGE": (None, "language", str),
            "NEXUS_DEFAULT_EXECUTOR": ("routing", "default_executor", str),
            "NEXUS_SPEC_DIR": (None, "spec_dir", str),
            "NEXUS_CHECKPOINT_DIR": (None, "checkpoint_dir", str),
        }

        for env_var, (section, field, type_fn) in env_mappings.items():
            value = os.environ.get(env_var)
            if value:
                try:
                    typed_value = type_fn(value)
                    if section:
                        section_obj = getattr(config, section)
                        setattr(section_obj, field, typed_value)
                    else:
                        setattr(config, field, typed_value)
                except Exception as e:
                    print(f"Warning: Failed to apply {env_var}={value}: {e}")

        return config

    def _merge_dict_config(self, config: NexusConfig, data: Dict) -> NexusConfig:
        """Merge dictionary config into NexusConfig"""
        if not data:
            return config

        # Routing section
        if "routing" in data:
            routing_data = data["routing"]
            if "default_executor" in routing_data:
                config.routing.default_executor = routing_data["default_executor"]

            if "rules" in routing_data:
                # Add custom rules with higher priority
                for rule_data in routing_data["rules"]:
                    rule = RoutingRule(
                        pattern=rule_data.get("pattern", "*"),
                        executor=rule_data.get("executor", "claude"),
                        priority=rule_data.get("priority", 100),  # Custom rules get high priority
                        description=rule_data.get("description", "")
                    )
                    config.routing.rules.append(rule)

            if "executors" in routing_data:
                for name, exec_data in routing_data["executors"].items():
                    if name in config.routing.executors:
                        exec_config = config.routing.executors[name]
                        if "enabled" in exec_data:
                            exec_config.enabled = exec_data["enabled"]
                        if "timeout_minutes" in exec_data:
                            exec_config.timeout_minutes = exec_data["timeout_minutes"]
                        if "max_retries" in exec_data:
                            exec_config.max_retries = exec_data["max_retries"]
                        if "role" in exec_data:
                            exec_config.role = exec_data["role"]
                        if "preferred_model" in exec_data:
                            exec_config.preferred_model = exec_data["preferred_model"]

        # Execution section
        if "execution" in data:
            exec_data = data["execution"]
            if "max_parallel_tasks" in exec_data:
                config.execution.max_parallel_tasks = exec_data["max_parallel_tasks"]
            if "task_timeout_minutes" in exec_data:
                config.execution.task_timeout_minutes = exec_data["task_timeout_minutes"]
            if "error_strategy" in exec_data:
                config.execution.error_strategy = ErrorStrategy(exec_data["error_strategy"])
            if "max_retries" in exec_data:
                config.execution.max_retries = exec_data["max_retries"]

        # Logging section
        if "logging" in data:
            log_data = data["logging"]
            if "enabled" in log_data:
                config.logging.enabled = log_data["enabled"]
            if "level" in log_data:
                config.logging.level = LogLevel(log_data["level"])
            if "log_to_file" in log_data:
                config.logging.log_to_file = log_data["log_to_file"]

        # Progress section
        if "progress" in data:
            progress_data = data["progress"]
            if "show_task_progress" in progress_data:
                config.progress.show_task_progress = progress_data["show_task_progress"]
            if "show_batch_progress" in progress_data:
                config.progress.show_batch_progress = progress_data["show_batch_progress"]

        # Top-level options
        if "language" in data:
            config.language = data["language"]
        if "skip_code_review" in data:
            config.skip_code_review = data["skip_code_review"]
        if "skip_documentation" in data:
            config.skip_documentation = data["skip_documentation"]

        return config

    def load_config(self, force_reload: bool = False) -> NexusConfig:
        """Load configuration from all sources"""
        if self._config and not force_reload:
            return self._config

        # Start with defaults
        config = self._get_default_config()

        # Load user config
        user_config_path = Path(self.DEFAULT_USER_CONFIG).expanduser()
        user_data = self._load_yaml_config(user_config_path)
        if user_data:
            config = self._merge_dict_config(config, user_data)

        # Load project config (overrides user config)
        project_config_path = self.project_root / self.DEFAULT_PROJECT_CONFIG
        project_data = self._load_yaml_config(project_config_path)
        if project_data:
            config = self._merge_dict_config(config, project_data)

        # Apply environment overrides (highest priority)
        config = self._apply_env_overrides(config)

        # Sort routing rules by priority
        config.routing.rules.sort(key=lambda r: r.priority, reverse=True)

        self._config = config
        return config

    def get_executor_for_task(self, task_description: str, output_file: Optional[str] = None) -> str:
        """Determine the best executor for a task"""
        config = self.load_config()

        # Check file pattern rules first
        if output_file:
            for rule in config.routing.rules:
                if self._match_pattern(output_file, rule.pattern):
                    executor = rule.executor
                    if config.routing.executors.get(executor, ExecutorConfig()).enabled:
                        return executor

        # Check task description keywords
        description_lower = task_description.lower()

        # Architecture/analysis keywords (check first - highest priority)
        architecture_keywords = [
            "architecture", "design", "analyze", "review", "audit",
            "security", "performance", "optimize", "refactor"
        ]
        if any(kw in description_lower for kw in architecture_keywords):
            return "claude"

        # Frontend keywords
        frontend_keywords = [
            "component", "ui", "frontend", "react", "vue", "angular",
            "css", "style", "layout", "form", "button", "modal",
            "interface", "animation", "responsive"
        ]
        if any(kw in description_lower for kw in frontend_keywords):
            if config.routing.executors.get("gemini", ExecutorConfig()).enabled:
                return "gemini"

        # Backend keywords
        backend_keywords = [
            "api", "endpoint", "database", "db", "sql", "model",
            "service", "server", "backend", "rest", "graphql",
            "authentication", "auth", "middleware", "controller"
        ]
        if any(kw in description_lower for kw in backend_keywords):
            if config.routing.executors.get("codex", ExecutorConfig()).enabled:
                return "codex"

        return config.routing.default_executor

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Match a path against a glob pattern"""
        from pathlib import PurePosixPath
        import fnmatch

        # Normalize path separators
        path = path.replace("\\", "/")
        pattern = pattern.replace("\\", "/")

        # Use PurePosixPath.match for ** support
        try:
            return PurePosixPath(path).match(pattern)
        except (ValueError, TypeError):
            return fnmatch.fnmatch(path, pattern)

    def save_project_config(self, config: NexusConfig) -> bool:
        """Save configuration to project config file"""
        project_config_path = self.project_root / self.DEFAULT_PROJECT_CONFIG

        try:
            # Convert to dict
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

            data = to_dict(config)

            with open(project_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def generate_default_config_file(self, path: Optional[str] = None) -> str:
        """Generate a default configuration file"""
        config = self._get_default_config()

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

        data = to_dict(config)

        yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True)

        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write("# Nexus CLI Configuration\n")
                f.write("# Generated by nexus-cli\n")
                f.write("# See documentation for all options\n\n")
                f.write(yaml_content)

        return yaml_content


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nexus CLI Config Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show current config")

    # Init command
    init_parser = subparsers.add_parser("init", help="Generate default config file")
    init_parser.add_argument("--path", default=".nexus-config.yaml", help="Output path")

    # Route command
    route_parser = subparsers.add_parser("route", help="Get executor for task")
    route_parser.add_argument("task", help="Task description")
    route_parser.add_argument("--file", help="Output file path")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run self-test")

    args = parser.parse_args()

    manager = ConfigManager()

    if args.command == "show":
        config = manager.load_config()
        print(yaml.dump(asdict(config), default_flow_style=False, allow_unicode=True))

    elif args.command == "init":
        content = manager.generate_default_config_file(args.path)
        print(f"Generated config file: {args.path}")

    elif args.command == "route":
        executor = manager.get_executor_for_task(args.task, args.file)
        print(f"Recommended executor: {executor}")

    elif args.command == "test":
        print("Running config manager self-test...")

        config = manager.load_config()
        print(f"✅ Loaded config (version: {config.version})")

        # Test routing
        test_cases = [
            ("Create a React component", "src/components/Button.tsx", "gemini"),
            ("Implement REST API endpoint", "src/api/users.ts", "codex"),
            ("Design system architecture", None, "claude"),
            ("Create login form", "src/components/LoginForm.vue", "gemini"),
            ("Add database migration", "src/db/migrations/001.sql", "codex"),
        ]

        for task, file, expected in test_cases:
            result = manager.get_executor_for_task(task, file)
            status = "✅" if result == expected else "❌"
            print(f"  {status} '{task[:30]}...' -> {result} (expected: {expected})")

        print("\n🎉 Self-test complete!")

    else:
        parser.print_help()
