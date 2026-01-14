# CLI 辩论系统实现任务

## 任务描述

基于现有的 CLI 执行器模块创建一个本地代码辩论 Agent 系统。

## 完成状态

### ✅ 已完成

1. **types.ts** - 类型定义
   - DebateRole, CLIType, DebatePhase, DebateStatus 枚举
   - AgentConfig, DebateConfig 配置接口
   - DebateMessage, RoundResult, DebateResult 消息接口
   - DebateEvent, DebateEventCallback 事件接口
   - ICLIAgent Agent 接口

2. **agents/base-agent.ts** - 基础 CLI Agent 抽象类
   - 通用执行逻辑
   - 超时处理
   - 流式输出支持

3. **agents/claude-agent.ts** - Claude CLI Agent
4. **agents/codex-agent.ts** - Codex CLI Agent
5. **agents/gemini-agent.ts** - Gemini CLI Agent

6. **prompts.ts** - Prompt 模板
   - 主持人开场、评估、最终裁决
   - 挑战者质疑
   - 辩护者回应

7. **orchestrator.ts** - 辩论编排器
   - 标准辩论流程实现
   - 事件回调机制
   - 错误处理

8. **index.ts** - 模块导出
9. **test.ts** - 测试脚本

## 目录结构

```
src/cli-debate/
├── types.ts           # 类型定义
├── prompts.ts         # Prompt 模板
├── orchestrator.ts    # 辩论编排器
├── index.ts           # 模块导出
├── test.ts            # 测试脚本
└── agents/
    ├── base-agent.ts
    ├── claude-agent.ts
    ├── codex-agent.ts
    └── gemini-agent.ts
```

## 辩论流程

1. Round 0: 主持人开场介绍辩题
2. Round 1-N: 挑战者质疑 → 辩护者回应 → 主持人评估
3. Final: 主持人给出最终裁决
