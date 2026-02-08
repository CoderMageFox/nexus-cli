#!/usr/bin/env python3
"""
Nexus CLI Internationalization (i18n) Module

Provides multi-language support with:
- Automatic locale detection
- JSON-based translation files
- Fallback to default language
- Template variable substitution
- Pluralization support

Supported languages:
- en-US (English - Default)
- zh-CN (Simplified Chinese)
"""

import json
import os
import locale
from pathlib import Path
from typing import Dict, Optional, Any, Union
from functools import lru_cache


class Language:
    """Language constants"""
    EN_US = "en-US"
    ZH_CN = "zh-CN"
    AUTO = "auto"

    @classmethod
    def all(cls) -> list:
        return [cls.EN_US, cls.ZH_CN]


class I18n:
    """
    Internationalization manager for Nexus CLI

    Usage:
        i18n = I18n()
        print(i18n.t("welcome_message"))
        print(i18n.t("task_count", count=5))
    """

    DEFAULT_LANGUAGE = Language.EN_US
    LOCALE_DIR = "locales"

    def __init__(
        self,
        language: str = Language.AUTO,
        locale_dir: Optional[str] = None
    ):
        """
        Initialize i18n manager

        Args:
            language: Language code (en-US, zh-CN) or 'auto' for detection
            locale_dir: Custom locale directory path
        """
        self._locale_dir = Path(locale_dir) if locale_dir else self._get_default_locale_dir()
        self._translations: Dict[str, Dict] = {}
        self._current_language = self._resolve_language(language)

        # Load translations
        self._load_translations()

    def _get_default_locale_dir(self) -> Path:
        """Get the default locale directory"""
        # Try relative to this file
        module_dir = Path(__file__).parent.parent
        locale_dir = module_dir / self.LOCALE_DIR

        if locale_dir.exists():
            return locale_dir

        # Try current working directory
        cwd_locale = Path.cwd() / self.LOCALE_DIR
        if cwd_locale.exists():
            return cwd_locale

        # Create default locale directory
        locale_dir.mkdir(parents=True, exist_ok=True)
        return locale_dir

    def _resolve_language(self, language: str) -> str:
        """Resolve language setting, including auto-detection"""
        if language == Language.AUTO:
            return self._detect_language()

        # Normalize language code
        language = language.replace("_", "-")

        if language in Language.all():
            return language

        # Try to match prefix (e.g., "zh" -> "zh-CN")
        prefix = language.split("-")[0]
        for lang in Language.all():
            if lang.startswith(prefix):
                return lang

        return self.DEFAULT_LANGUAGE

    def _detect_language(self) -> str:
        """Auto-detect system language"""
        # Check environment variables first
        env_lang = os.environ.get("NEXUS_LANGUAGE") or os.environ.get("LANG") or ""

        if "zh" in env_lang.lower():
            return Language.ZH_CN

        # Try system locale (compatible with Python 3.11+)
        try:
            system_locale = locale.getlocale()[0] or ""
            if "zh" in system_locale.lower():
                return Language.ZH_CN
        except Exception:
            pass

        return self.DEFAULT_LANGUAGE

    def _load_translations(self):
        """Load all translation files"""
        for lang in Language.all():
            self._translations[lang] = self._load_language_file(lang)

    def _load_language_file(self, language: str) -> Dict:
        """Load a single language file"""
        file_path = self._locale_dir / f"{language}.json"

        if not file_path.exists():
            # Create default file if it's the default language
            if language == self.DEFAULT_LANGUAGE:
                self._create_default_translations(file_path)
            elif language == Language.ZH_CN:
                self._create_chinese_translations(file_path)
            else:
                return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load translation file {file_path}: {e}")
            return {}

    def _create_default_translations(self, file_path: Path):
        """Create default English translations"""
        translations = {
            "_meta": {
                "language": "en-US",
                "name": "English (US)",
                "version": "1.0.0"
            },
            "common": {
                "yes": "Yes",
                "no": "No",
                "ok": "OK",
                "cancel": "Cancel",
                "error": "Error",
                "warning": "Warning",
                "success": "Success",
                "loading": "Loading...",
                "please_wait": "Please wait..."
            },
            "cli": {
                "welcome": "Welcome to Nexus CLI",
                "version": "Version {version}",
                "help": "Use /nexus --help for usage information",
                "goodbye": "Goodbye!"
            },
            "executor": {
                "selecting": "Selecting executor for task...",
                "selected": "Selected executor: {executor}",
                "claude": "Claude (Architecture & Analysis)",
                "gemini": "Gemini (Frontend & UI)",
                "codex": "Codex (Backend & API)",
                "confirm_prompt": "Use {executor} for this task?",
                "routing_by_pattern": "Routing by file pattern: {pattern}",
                "routing_by_keyword": "Routing by keyword: {keyword}",
                "routing_default": "Using default executor"
            },
            "task": {
                "starting": "Starting task: {name}",
                "completed": "Task completed: {name}",
                "failed": "Task failed: {name}",
                "skipped": "Task skipped: {name}",
                "retry": "Retrying task ({attempt}/{max}): {name}",
                "timeout": "Task timed out after {seconds} seconds",
                "cancelled": "Task cancelled by user"
            },
            "batch": {
                "starting": "Starting batch {id}: {name}",
                "completed": "Batch completed: {success}/{total} succeeded",
                "serial": "Executing tasks sequentially",
                "parallel": "Executing {count} tasks in parallel"
            },
            "progress": {
                "overall": "Overall Progress",
                "batch": "Batch Progress",
                "task": "Task Progress",
                "completed": "Completed",
                "failed": "Failed",
                "pending": "Pending",
                "running": "Running",
                "estimated_remaining": "Estimated remaining: {time}"
            },
            "checkpoint": {
                "saving": "Saving checkpoint...",
                "saved": "Checkpoint saved",
                "loading": "Loading checkpoint...",
                "loaded": "Checkpoint loaded",
                "resume_prompt": "Resume from checkpoint?",
                "resume_from": "Resuming from batch {batch}: {name}",
                "no_checkpoint": "No checkpoint found"
            },
            "config": {
                "loading": "Loading configuration...",
                "loaded": "Configuration loaded from {path}",
                "not_found": "Configuration file not found, using defaults",
                "invalid": "Invalid configuration: {error}"
            },
            "error": {
                "generic": "An error occurred: {message}",
                "network": "Network error: {message}",
                "timeout": "Operation timed out",
                "permission": "Permission denied: {path}",
                "not_found": "Not found: {item}",
                "invalid_input": "Invalid input: {message}",
                "executor_failed": "Executor failed: {executor}",
                "recovery_prompt": "How would you like to proceed?",
                "recovery_retry": "Retry the failed task",
                "recovery_skip": "Skip and continue",
                "recovery_abort": "Abort execution"
            },
            "spec": {
                "generating": "Generating specification...",
                "requirements": "Requirements Document",
                "design": "Design Document",
                "tasks": "Task Breakdown",
                "validation": "Validating specification...",
                "valid": "Specification is valid",
                "invalid": "Specification validation failed"
            },
            "install": {
                "checking": "Checking installation...",
                "installing": "Installing Nexus CLI...",
                "installed": "Nexus CLI installed successfully",
                "updating": "Updating Nexus CLI...",
                "updated": "Nexus CLI updated to version {version}",
                "uninstalling": "Uninstalling Nexus CLI...",
                "uninstalled": "Nexus CLI uninstalled"
            }
        }

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(translations, f, indent=2, ensure_ascii=False)

    def _create_chinese_translations(self, file_path: Path):
        """Create Chinese translations"""
        translations = {
            "_meta": {
                "language": "zh-CN",
                "name": "简体中文",
                "version": "1.0.0"
            },
            "common": {
                "yes": "是",
                "no": "否",
                "ok": "确定",
                "cancel": "取消",
                "error": "错误",
                "warning": "警告",
                "success": "成功",
                "loading": "加载中...",
                "please_wait": "请稍候..."
            },
            "cli": {
                "welcome": "欢迎使用 Nexus CLI",
                "version": "版本 {version}",
                "help": "使用 /nexus --help 查看使用说明",
                "goodbye": "再见！"
            },
            "executor": {
                "selecting": "正在选择执行器...",
                "selected": "已选择执行器: {executor}",
                "claude": "Claude (架构与分析)",
                "gemini": "Gemini (前端与UI)",
                "codex": "Codex (后端与API)",
                "confirm_prompt": "使用 {executor} 执行此任务？",
                "routing_by_pattern": "根据文件模式路由: {pattern}",
                "routing_by_keyword": "根据关键词路由: {keyword}",
                "routing_default": "使用默认执行器"
            },
            "task": {
                "starting": "开始任务: {name}",
                "completed": "任务完成: {name}",
                "failed": "任务失败: {name}",
                "skipped": "任务跳过: {name}",
                "retry": "重试任务 ({attempt}/{max}): {name}",
                "timeout": "任务超时 ({seconds} 秒)",
                "cancelled": "任务已被用户取消"
            },
            "batch": {
                "starting": "开始批次 {id}: {name}",
                "completed": "批次完成: {success}/{total} 成功",
                "serial": "顺序执行任务",
                "parallel": "并行执行 {count} 个任务"
            },
            "progress": {
                "overall": "总体进度",
                "batch": "批次进度",
                "task": "任务进度",
                "completed": "已完成",
                "failed": "失败",
                "pending": "待处理",
                "running": "执行中",
                "estimated_remaining": "预计剩余: {time}"
            },
            "checkpoint": {
                "saving": "保存检查点...",
                "saved": "检查点已保存",
                "loading": "加载检查点...",
                "loaded": "检查点已加载",
                "resume_prompt": "是否从检查点恢复？",
                "resume_from": "从批次 {batch} 恢复: {name}",
                "no_checkpoint": "未找到检查点"
            },
            "config": {
                "loading": "加载配置...",
                "loaded": "已从 {path} 加载配置",
                "not_found": "未找到配置文件，使用默认配置",
                "invalid": "配置无效: {error}"
            },
            "error": {
                "generic": "发生错误: {message}",
                "network": "网络错误: {message}",
                "timeout": "操作超时",
                "permission": "权限被拒绝: {path}",
                "not_found": "未找到: {item}",
                "invalid_input": "输入无效: {message}",
                "executor_failed": "执行器失败: {executor}",
                "recovery_prompt": "您想如何处理？",
                "recovery_retry": "重试失败的任务",
                "recovery_skip": "跳过并继续",
                "recovery_abort": "中止执行"
            },
            "spec": {
                "generating": "生成规格说明...",
                "requirements": "需求文档",
                "design": "设计文档",
                "tasks": "任务分解",
                "validation": "验证规格说明...",
                "valid": "规格说明有效",
                "invalid": "规格说明验证失败"
            },
            "install": {
                "checking": "检查安装状态...",
                "installing": "安装 Nexus CLI...",
                "installed": "Nexus CLI 安装成功",
                "updating": "更新 Nexus CLI...",
                "updated": "Nexus CLI 已更新到版本 {version}",
                "uninstalling": "卸载 Nexus CLI...",
                "uninstalled": "Nexus CLI 已卸载"
            }
        }

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(translations, f, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def language(self) -> str:
        """Get current language"""
        return self._current_language

    @language.setter
    def language(self, value: str):
        """Set current language"""
        self._current_language = self._resolve_language(value)

    def t(self, key: str, **kwargs) -> str:
        """
        Translate a key with optional variable substitution

        Args:
            key: Translation key (e.g., "task.starting" or "common.yes")
            **kwargs: Variables to substitute in the translation

        Returns:
            Translated string
        """
        # Get translation from current language
        translation = self._get_translation(key, self._current_language)

        # Fallback to default language
        if translation is None and self._current_language != self.DEFAULT_LANGUAGE:
            translation = self._get_translation(key, self.DEFAULT_LANGUAGE)

        # Fallback to key itself
        if translation is None:
            return key

        # Substitute variables
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except KeyError:
                pass  # Keep original if substitution fails

        return translation

    def _get_translation(self, key: str, language: str) -> Optional[str]:
        """Get a translation by key path"""
        translations = self._translations.get(language, {})

        # Handle nested keys (e.g., "task.starting")
        parts = key.split(".")
        value = translations

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value if isinstance(value, str) else None

    def get_available_languages(self) -> Dict[str, str]:
        """Get list of available languages with their names"""
        languages = {}
        for lang, translations in self._translations.items():
            meta = translations.get("_meta", {})
            languages[lang] = meta.get("name", lang)
        return languages

    def pluralize(self, count: int, singular: str, plural: str) -> str:
        """
        Simple pluralization helper

        Args:
            count: Number to check
            singular: Singular form
            plural: Plural form

        Returns:
            Appropriate form based on count
        """
        # Chinese doesn't have plural forms
        if self._current_language == Language.ZH_CN:
            return singular

        return singular if count == 1 else plural

    def format_list(self, items: list, conjunction: str = None) -> str:
        """
        Format a list for display

        Args:
            items: List of items to format
            conjunction: Word to use before last item (default: "and"/"和")

        Returns:
            Formatted string
        """
        if not items:
            return ""

        if len(items) == 1:
            return str(items[0])

        if conjunction is None:
            conjunction = "和" if self._current_language == Language.ZH_CN else "and"

        if len(items) == 2:
            return f"{items[0]} {conjunction} {items[1]}"

        return ", ".join(str(i) for i in items[:-1]) + f" {conjunction} {items[-1]}"


# ─────────────────────────────────────────────────────────────────────────────
# Global Instance
# ─────────────────────────────────────────────────────────────────────────────

_global_i18n: Optional[I18n] = None


def get_i18n() -> I18n:
    """Get the global i18n instance"""
    global _global_i18n
    if _global_i18n is None:
        _global_i18n = I18n()
    return _global_i18n


def set_language(language: str):
    """Set the global language"""
    get_i18n().language = language


def t(key: str, **kwargs) -> str:
    """Shortcut for translation"""
    return get_i18n().t(key, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# CLI Interface
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Nexus CLI i18n Module")
    parser.add_argument("--lang", default="auto", help="Language code (en-US, zh-CN, auto)")
    parser.add_argument("--list", action="store_true", help="List available languages")
    parser.add_argument("--test", action="store_true", help="Run translation test")
    parser.add_argument("key", nargs="?", help="Translation key to look up")

    args = parser.parse_args()

    i18n = I18n(language=args.lang)

    if args.list:
        print("Available languages:")
        for code, name in i18n.get_available_languages().items():
            marker = " (current)" if code == i18n.language else ""
            print(f"  {code}: {name}{marker}")

    elif args.test:
        print(f"Current language: {i18n.language}")
        print("")
        print("Sample translations:")
        print(f"  welcome: {i18n.t('cli.welcome')}")
        print(f"  version: {i18n.t('cli.version', version='4.0.2')}")
        print(f"  task.starting: {i18n.t('task.starting', name='Test Task')}")
        print(f"  batch.completed: {i18n.t('batch.completed', success=8, total=10)}")
        print("")

        # Test language switching
        print("Testing language switch:")
        for lang in Language.all():
            i18n.language = lang
            print(f"  [{lang}] {i18n.t('cli.welcome')}")

    elif args.key:
        print(i18n.t(args.key))

    else:
        parser.print_help()
