/**
 * 代码审查辩论模式
 *
 * 实现完整的代码审查辩论流程:
 * - Phase 0: Build 检查
 * - Phase 1: 挑战者质疑
 * - Phase 2: 辩护者回应
 * - Phase 3: 主持人裁决
 * - Phase 4: 并行修复
 */

import { spawn } from 'child_process';
import { v4 as uuidv4 } from 'uuid';
import {
  CodeReviewConfig,
  CodeReviewResult,
  BuildCheckResult,
  CodeIssue,
  FixTask,
  DebateStatus,
  DebatePhase,
  DebateRole,
  DebateMessage,
  CLIType,
  ICLIAgent,
  IssueType,
  IssueSeverity,
  DebateEvent,
  DebateEventCallback
} from './types';
import {
  getCodeReviewChallengerPrompt,
  getCodeReviewDefenderPrompt,
  getCodeReviewVerdictPrompt,
  getFixTaskPrompt
} from './prompts';
import { ClaudeAgent } from './agents/claude-agent';
import { CodexAgent } from './agents/codex-agent';
import { GeminiAgent } from './agents/gemini-agent';

/** 创建 Agent 实例 */
function createAgent(cliType: CLIType, role: DebateRole, timeout?: number): ICLIAgent {
  switch (cliType) {
    case CLIType.CLAUDE:
      return new ClaudeAgent(role, timeout);
    case CLIType.CODEX:
      return new CodexAgent(role, timeout);
    case CLIType.GEMINI:
      return new GeminiAgent(role, timeout);
    default:
      throw new Error(`不支持的 CLI 类型: ${cliType}`);
  }
}

/** 代码审查编排器 */
export class CodeReviewOrchestrator {
  private config: CodeReviewConfig;
  private challenger: ICLIAgent;
  private defender: ICLIAgent;
  private moderator: ICLIAgent;
  private fixers: Map<CLIType, ICLIAgent> = new Map();
  private eventCallbacks: DebateEventCallback[] = [];
  private messages: DebateMessage[] = [];

  constructor(config: CodeReviewConfig) {
    this.config = config;

    // 创建主要 Agent
    this.challenger = createAgent(
      config.challenger.cliType,
      DebateRole.CHALLENGER,
      config.challenger.timeout
    );
    this.defender = createAgent(
      config.defender.cliType,
      DebateRole.DEFENDER,
      config.defender.timeout
    );
    this.moderator = createAgent(
      config.moderator.cliType,
      DebateRole.MODERATOR,
      config.moderator.timeout
    );

    // 创建修复者 Agent（如果配置了）
    if (config.fixers) {
      for (const fixer of config.fixers) {
        if (!this.fixers.has(fixer.cliType)) {
          this.fixers.set(
            fixer.cliType,
            createAgent(fixer.cliType, DebateRole.DEFENDER, fixer.timeout)
          );
        }
      }
    }

    // 默认添加所有 CLI 作为修复者
    if (this.fixers.size === 0) {
      this.fixers.set(CLIType.CLAUDE, createAgent(CLIType.CLAUDE, DebateRole.DEFENDER));
      this.fixers.set(CLIType.CODEX, createAgent(CLIType.CODEX, DebateRole.DEFENDER));
      this.fixers.set(CLIType.GEMINI, createAgent(CLIType.GEMINI, DebateRole.DEFENDER));
    }
  }

  /** 注册事件回调 */
  on(callback: DebateEventCallback): void {
    this.eventCallbacks.push(callback);
  }

  /** 触发事件 */
  private emit(type: DebateEvent['type'], data: any): void {
    const event: DebateEvent = {
      type,
      timestamp: new Date(),
      data
    };
    this.eventCallbacks.forEach((cb) => cb(event));
  }

  /** 创建消息 */
  private createMessage(
    role: DebateRole,
    cliType: CLIType,
    content: string,
    phase: DebatePhase
  ): DebateMessage {
    const message: DebateMessage = {
      id: uuidv4(),
      role,
      cliType,
      content,
      timestamp: new Date(),
      phase
    };
    this.messages.push(message);
    return message;
  }

  /** Phase 0: 构建检查 */
  private async executeBuildCheck(): Promise<BuildCheckResult> {
    this.emit('phase:start', { phase: DebatePhase.BUILD_CHECK });

    const command = this.config.buildCommand || 'npm run build';
    const startTime = Date.now();

    return new Promise((resolve) => {
      const [cmd, ...args] = command.split(' ');
      let output = '';
      let errorOutput = '';

      const childProcess = spawn(cmd, args, {
        shell: true,
        cwd: this.config.path,
        env: { ...process.env }
      });

      childProcess.stdout?.on('data', (data: Buffer) => {
        const chunk = data.toString();
        output += chunk;
        if (this.config.streaming) {
          this.emit('message:chunk', { chunk, phase: DebatePhase.BUILD_CHECK });
        }
      });

      childProcess.stderr?.on('data', (data: Buffer) => {
        errorOutput += data.toString();
      });

      childProcess.on('close', (code) => {
        const result: BuildCheckResult = {
          success: code === 0,
          command,
          output: output + errorOutput,
          errors: code !== 0 ? errorOutput.split('\n').filter(Boolean) : undefined,
          duration: Date.now() - startTime
        };

        this.emit('phase:end', { phase: DebatePhase.BUILD_CHECK, result });
        resolve(result);
      });

      childProcess.on('error', (err) => {
        resolve({
          success: false,
          command,
          output: '',
          errors: [err.message],
          duration: Date.now() - startTime
        });
      });
    });
  }

  /** Phase 1: 挑战者分析代码问题 */
  private async executeChallengerAnalysis(): Promise<CodeIssue[]> {
    this.emit('phase:start', { phase: DebatePhase.CODE_ANALYSIS });

    const prompt = getCodeReviewChallengerPrompt(this.config.path, this.config.focus);

    this.emit('message:start', {
      role: DebateRole.CHALLENGER,
      cliType: this.config.challenger.cliType
    });

    const result = await this.challenger.execute({
      prompt,
      onChunk: (chunk) => {
        if (this.config.streaming) {
          this.emit('message:chunk', { chunk, role: DebateRole.CHALLENGER });
        }
      }
    });

    if (!result.success) {
      throw new Error(`挑战者分析失败: ${result.error}`);
    }

    // 解析 JSON 输出
    const issues = this.parseIssuesFromOutput(result.output);

    const message = this.createMessage(
      DebateRole.CHALLENGER,
      this.config.challenger.cliType,
      result.output,
      DebatePhase.CODE_ANALYSIS
    );

    this.emit('message:end', { message });
    this.emit('phase:end', { phase: DebatePhase.CODE_ANALYSIS, issues });

    return issues;
  }

  /** 解析问题列表 */
  private parseIssuesFromOutput(output: string): CodeIssue[] {
    try {
      // 尝试提取 JSON
      const jsonMatch = output.match(/```json\s*([\s\S]*?)\s*```/);
      const jsonStr = jsonMatch ? jsonMatch[1] : output;
      const parsed = JSON.parse(jsonStr);

      if (parsed.issues && Array.isArray(parsed.issues)) {
        return parsed.issues.map((issue: any, index: number) => ({
          id: `issue-${index + 1}`,
          type: this.parseIssueType(issue.type),
          severity: this.parseSeverity(issue.severity),
          description: issue.description || '',
          filePath: issue.filePath,
          lineNumber: issue.lineNumber,
          suggestedFix: issue.suggestedFix
        }));
      }
    } catch (e) {
      // 解析失败，返回空数组
      console.error('解析问题列表失败:', e);
    }
    return [];
  }

  /** 解析问题类型 */
  private parseIssueType(type: string): IssueType {
    const typeMap: Record<string, IssueType> = {
      bug: IssueType.BUG,
      security: IssueType.SECURITY,
      performance: IssueType.PERFORMANCE,
      design: IssueType.DESIGN
    };
    return typeMap[type?.toLowerCase()] || IssueType.BUG;
  }

  /** 解析严重程度 */
  private parseSeverity(severity: string): IssueSeverity {
    const severityMap: Record<string, IssueSeverity> = {
      critical: IssueSeverity.CRITICAL,
      high: IssueSeverity.HIGH,
      medium: IssueSeverity.MEDIUM,
      low: IssueSeverity.LOW
    };
    return severityMap[severity?.toLowerCase()] || IssueSeverity.MEDIUM;
  }

  /** Phase 2: 辩护者回应 */
  private async executeDefenderResponse(issues: CodeIssue[]): Promise<DebateMessage> {
    this.emit('phase:start', { phase: DebatePhase.ISSUE_DEFENSE });

    const prompt = getCodeReviewDefenderPrompt(this.config.path, issues);

    this.emit('message:start', {
      role: DebateRole.DEFENDER,
      cliType: this.config.defender.cliType
    });

    const result = await this.defender.execute({
      prompt,
      context: this.messages,
      onChunk: (chunk) => {
        if (this.config.streaming) {
          this.emit('message:chunk', { chunk, role: DebateRole.DEFENDER });
        }
      }
    });

    if (!result.success) {
      throw new Error(`辩护者回应失败: ${result.error}`);
    }

    const message = this.createMessage(
      DebateRole.DEFENDER,
      this.config.defender.cliType,
      result.output,
      DebatePhase.ISSUE_DEFENSE
    );

    this.emit('message:end', { message });
    this.emit('phase:end', { phase: DebatePhase.ISSUE_DEFENSE });

    return message;
  }

  /** Phase 3: 主持人裁决 */
  private async executeModeratorVerdict(
    issues: CodeIssue[],
    defenseResponse: string
  ): Promise<{ verdict: DebateMessage; confirmedIssues: CodeIssue[] }> {
    this.emit('phase:start', { phase: DebatePhase.VERDICT_ASSIGNMENT });

    const prompt = getCodeReviewVerdictPrompt(this.config.path, issues, defenseResponse);

    this.emit('message:start', {
      role: DebateRole.MODERATOR,
      cliType: this.config.moderator.cliType
    });

    const result = await this.moderator.execute({
      prompt,
      context: this.messages,
      onChunk: (chunk) => {
        if (this.config.streaming) {
          this.emit('message:chunk', { chunk, role: DebateRole.MODERATOR });
        }
      }
    });

    if (!result.success) {
      throw new Error(`主持人裁决失败: ${result.error}`);
    }

    const message = this.createMessage(
      DebateRole.MODERATOR,
      this.config.moderator.cliType,
      result.output,
      DebatePhase.VERDICT_ASSIGNMENT
    );

    // 解析裁决结果，更新问题分配
    const confirmedIssues = this.parseVerdictAndAssign(result.output, issues);

    this.emit('message:end', { message });
    this.emit('phase:end', { phase: DebatePhase.VERDICT_ASSIGNMENT, confirmedIssues });

    return { verdict: message, confirmedIssues };
  }

  /** 解析裁决并分配修复任务 */
  private parseVerdictAndAssign(output: string, issues: CodeIssue[]): CodeIssue[] {
    try {
      const jsonMatch = output.match(/```json\s*([\s\S]*?)\s*```/);
      const jsonStr = jsonMatch ? jsonMatch[1] : output;
      const parsed = JSON.parse(jsonStr);

      if (parsed.confirmedIssues && Array.isArray(parsed.confirmedIssues)) {
        const confirmedIssues: CodeIssue[] = [];
        for (const issue of issues) {
          const confirmed = parsed.confirmedIssues.find(
            (c: any) => c.issueId === issue.id
          );
          if (confirmed?.confirmed) {
            confirmedIssues.push({
              ...issue,
              assignedTo: this.parseCLIType(confirmed.assignTo)
            });
          }
        }
        return confirmedIssues;
      }
    } catch (e) {
      console.error('解析裁决失败:', e);
    }
    return issues;
  }

  /** 解析 CLI 类型 */
  private parseCLIType(cli: string): CLIType {
    const cliMap: Record<string, CLIType> = {
      claude: CLIType.CLAUDE,
      codex: CLIType.CODEX,
      gemini: CLIType.GEMINI
    };
    return cliMap[cli?.toLowerCase()] || CLIType.CLAUDE;
  }

  /** Phase 4: 并行修复 */
  async executeParallelFix(issues: CodeIssue[]): Promise<FixTask[]> {
    if (!this.config.autoFix || issues.length === 0) {
      return [];
    }

    this.emit('phase:start', { phase: DebatePhase.PARALLEL_FIX });

    // 按 CLI 分组
    const issuesByCliType = new Map<CLIType, CodeIssue[]>();
    for (const issue of issues) {
      const cli = issue.assignedTo || CLIType.CLAUDE;
      if (!issuesByCliType.has(cli)) {
        issuesByCliType.set(cli, []);
      }
      issuesByCliType.get(cli)!.push(issue);
    }

    // 并行执行修复
    const fixPromises: Promise<FixTask>[] = [];

    for (const [cliType, cliIssues] of issuesByCliType) {
      const fixer = this.fixers.get(cliType);
      if (!fixer) continue;

      for (const issue of cliIssues) {
        fixPromises.push(this.executeFixTask(fixer, cliType, issue));
      }
    }

    const fixTasks = await Promise.all(fixPromises);

    this.emit('phase:end', { phase: DebatePhase.PARALLEL_FIX, fixTasks });

    return fixTasks;
  }

  /** 执行单个修复任务 */
  private async executeFixTask(
    fixer: ICLIAgent,
    cliType: CLIType,
    issue: CodeIssue
  ): Promise<FixTask> {
    const taskId = uuidv4();
    const startTime = Date.now();

    const task: FixTask = {
      id: taskId,
      issue,
      assignedCLI: cliType,
      status: 'in_progress'
    };

    this.emit('message:start', {
      role: DebateRole.DEFENDER,
      cliType,
      taskId,
      issue
    });

    try {
      const prompt = getFixTaskPrompt(issue, this.config.path);
      const result = await fixer.execute({
        prompt,
        onChunk: (chunk) => {
          if (this.config.streaming) {
            this.emit('message:chunk', { chunk, taskId, cliType });
          }
        }
      });

      task.status = result.success ? 'completed' : 'failed';
      task.result = result.output;
      task.duration = Date.now() - startTime;

      this.emit('message:end', { task });
    } catch (error) {
      task.status = 'failed';
      task.result = error instanceof Error ? error.message : String(error);
      task.duration = Date.now() - startTime;
    }

    return task;
  }

  /** 运行代码审查 */
  async run(): Promise<CodeReviewResult> {
    const reviewId = uuidv4();
    const startTime = new Date();

    const result: CodeReviewResult = {
      id: reviewId,
      path: this.config.path,
      status: DebateStatus.PENDING,
      issues: [],
      startTime
    };

    try {
      result.status = DebateStatus.IN_PROGRESS;
      this.emit('debate:start', { reviewId, path: this.config.path });

      // Phase 0: 构建检查
      if (this.config.buildCommand) {
        result.buildCheck = await this.executeBuildCheck();
        if (!result.buildCheck.success) {
          // 构建失败，可以选择继续或停止
          this.emit('error', { error: '构建失败', buildCheck: result.buildCheck });
        }
      }

      // Phase 1: 挑战者分析
      result.issues = await this.executeChallengerAnalysis();

      if (result.issues.length === 0) {
        result.status = DebateStatus.COMPLETED;
        result.endTime = new Date();
        result.totalDuration = result.endTime.getTime() - startTime.getTime();
        this.emit('debate:end', { result });
        return result;
      }

      // Phase 2: 辩护者回应
      const defenseMessage = await this.executeDefenderResponse(result.issues);
      result.defenseResponses = [defenseMessage];

      // Phase 3: 主持人裁决
      const { verdict, confirmedIssues } = await this.executeModeratorVerdict(
        result.issues,
        defenseMessage.content
      );
      result.verdict = verdict;
      result.issues = confirmedIssues;

      // Phase 4: 并行修复
      if (this.config.autoFix && confirmedIssues.length > 0) {
        result.fixTasks = await this.executeParallelFix(confirmedIssues);
      }

      result.status = DebateStatus.COMPLETED;
      result.endTime = new Date();
      result.totalDuration = result.endTime.getTime() - startTime.getTime();

      this.emit('debate:end', { result });

      return result;
    } catch (error) {
      result.status = DebateStatus.FAILED;
      result.error = error instanceof Error ? error.message : String(error);
      result.endTime = new Date();
      result.totalDuration = result.endTime.getTime() - startTime.getTime();

      this.emit('error', { error: result.error });
      this.emit('debate:end', { result });

      return result;
    }
  }
}
