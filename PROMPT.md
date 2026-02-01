# CLI 辩论系统实现任务

## 任务描述

基于现有的 CLI 执行器模块创建一个本地代码辩论 Agent 系统。

## 完成状态

### ✅ 全部完成

1. **types.ts** - 类型定义
   - DebateRole, CLIType, DebatePhase, DebateStatus, DebateMode 枚举
   - AgentConfig, DebateConfig 配置接口
   - DebateMessage, RoundResult, DebateResult 消息接口
   - DebateEvent, DebateEventCallback 事件接口
   - ICLIAgent Agent 接口
   - **代码审查类型**: IssueSeverity, IssueType, CodeIssue, BuildCheckResult
   - **代码审查配置**: CodeReviewConfig, FixTask, CodeReviewResult

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
   - **代码审查 Prompt**: 挑战者分析、辩护者回应、主持人裁决、修复任务

7. **orchestrator.ts** - 辩论编排器
   - 标准辩论流程实现
   - 事件回调机制
   - 错误处理

8. **code-review.ts** - 代码审查编排器 ✅ 新增
   - Phase 0: Build 检查 (运行构建命令)
   - Phase 1: 挑战者分析代码问题
   - Phase 2: 辩护者回应质疑
   - Phase 3: 主持人裁决并分配修复任务
   - Phase 4: 并行修复功能

9. **cli.ts** - 命令行入口 ✅ 新增
   - debate 命令: 标准辩论模式
   - review 命令: 代码审查模式
   - 完整参数支持

10. **index.ts** - 模块导出
11. **test.ts** - 测试脚本
12. **package.json** - 项目配置 ✅ 新增
13. **tsconfig.json** - TypeScript 配置 ✅ 新增

## 目录结构

```
src/cli-debate/
├── types.ts           # 类型定义 (含代码审查类型)
├── prompts.ts         # Prompt 模板 (含代码审查 Prompt)
├── orchestrator.ts    # 标准辩论编排器
├── code-review.ts     # 代码审查编排器 ✅
├── cli.ts             # 命令行入口 ✅
├── index.ts           # 模块导出
├── test.ts            # 测试脚本
├── package.json       # 项目配置 ✅
├── tsconfig.json      # TypeScript 配置 ✅
└── agents/
    ├── base-agent.ts
    ├── claude-agent.ts
    ├── codex-agent.ts
    └── gemini-agent.ts
```

## 辩论流程

### 标准辩论模式
1. Round 0: 主持人开场介绍辩题
2. Round 1-N: 挑战者质疑 → 辩护者回应 → 主持人评估
3. Final: 主持人给出最终裁决

### 代码审查模式 ✅
1. Phase 0: Build 检查 (可选，运行构建命令)
2. Phase 1: 挑战者分析代码问题 (Bug、安全、性能、设计)
3. Phase 2: 辩护者回应质疑
4. Phase 3: 主持人裁决并分配修复任务
5. Phase 4: 并行修复 (多个 CLI 并行修复各自负责的问题)

## 使用方法

```bash
# 安装依赖
cd src/cli-debate && npm install

# 标准辩论
npx tsx cli.ts debate -t "TypeScript vs JavaScript" -c claude -d codex -m gemini

# 代码审查
npx tsx cli.ts review -p ./src -f bug,security --auto-fix

# 代码审查带构建检查
npx tsx cli.ts review -p ./src --build "npm run build" --auto-fix

# 显示帮助
npx tsx cli.ts help
```

## 验证状态

- ✅ TypeScript 类型检查通过
- ✅ CLI 帮助命令正常工作
- ✅ 所有模块正确导出
