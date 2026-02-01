/**
 * CLI 辩论系统模块导出
 */

// 类型导出
export * from './types';

// Prompt 模板导出
export * from './prompts';

// Agent 导出
export { BaseCLIAgent } from './agents/base-agent';
export { ClaudeAgent } from './agents/claude-agent';
export { CodexAgent } from './agents/codex-agent';
export { GeminiAgent } from './agents/gemini-agent';

// 编排器导出
export { DebateOrchestrator } from './orchestrator';
export { CodeReviewOrchestrator } from './code-review';
