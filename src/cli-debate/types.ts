/**
 * CLI 辩论系统类型定义
 *
 * 定义辩论系统中使用的所有类型、接口和枚举
 */

// ============ 基础枚举 ============

/** 辩论角色 */
export enum DebateRole {
  /** 主持人 - 负责开场、评估和裁决 */
  MODERATOR = 'moderator',
  /** 挑战者 - 负责质疑和提出问题 */
  CHALLENGER = 'challenger',
  /** 辩护者 - 负责回应和辩护 */
  DEFENDER = 'defender'
}

/** CLI 类型 */
export enum CLIType {
  CLAUDE = 'claude',
  CODEX = 'codex',
  GEMINI = 'gemini'
}

/** 辩论阶段 */
export enum DebatePhase {
  /** 开场介绍 */
  OPENING = 'opening',
  /** 辩论回合 */
  ROUND = 'round',
  /** 最终裁决 */
  FINAL = 'final',
  /** 构建检查 */
  BUILD_CHECK = 'build_check',
  /** 代码分析 */
  CODE_ANALYSIS = 'code_analysis',
  /** 问题辩护 */
  ISSUE_DEFENSE = 'issue_defense',
  /** 裁决分配 */
  VERDICT_ASSIGNMENT = 'verdict_assignment',
  /** 并行修复 */
  PARALLEL_FIX = 'parallel_fix'
}

/** 辩论模式 */
export enum DebateMode {
  /** 标准辩论 */
  STANDARD = 'standard',
  /** 代码审查 */
  CODE_REVIEW = 'code_review'
}

/** 辩论状态 */
export enum DebateStatus {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed',
  TIMEOUT = 'timeout'
}

// ============ 配置接口 ============

/** Agent 配置 */
export interface AgentConfig {
  /** CLI 类型 */
  cliType: CLIType;
  /** 辩论角色 */
  role: DebateRole;
  /** 超时时间（毫秒） */
  timeout?: number;
  /** 额外参数 */
  extraArgs?: string[];
}

/** 辩论配置 */
export interface DebateConfig {
  /** 辩题 */
  topic: string;
  /** 辩论回合数 */
  rounds: number;
  /** 主持人配置 */
  moderator: AgentConfig;
  /** 挑战者配置 */
  challenger: AgentConfig;
  /** 辩护者配置 */
  defender: AgentConfig;
  /** 全局超时（毫秒） */
  globalTimeout?: number;
  /** 是否启用流式输出 */
  streaming?: boolean;
  /** 语言 */
  language?: 'zh' | 'en';
}

// ============ 消息接口 ============

/** 辩论消息 */
export interface DebateMessage {
  /** 消息ID */
  id: string;
  /** 发送者角色 */
  role: DebateRole;
  /** CLI 类型 */
  cliType: CLIType;
  /** 消息内容 */
  content: string;
  /** 时间戳 */
  timestamp: Date;
  /** 所属阶段 */
  phase: DebatePhase;
  /** 回合号（如果在回合阶段） */
  roundNumber?: number;
}

/** 回合结果 */
export interface RoundResult {
  /** 回合号 */
  roundNumber: number;
  /** 挑战者消息 */
  challengerMessage: DebateMessage;
  /** 辩护者消息 */
  defenderMessage: DebateMessage;
  /** 主持人评估 */
  moderatorEvaluation: DebateMessage;
  /** 回合耗时（毫秒） */
  duration: number;
}

/** 辩论结果 */
export interface DebateResult {
  /** 辩论ID */
  id: string;
  /** 辩题 */
  topic: string;
  /** 状态 */
  status: DebateStatus;
  /** 开场消息 */
  opening?: DebateMessage;
  /** 各回合结果 */
  rounds: RoundResult[];
  /** 最终裁决 */
  finalVerdict?: DebateMessage;
  /** 开始时间 */
  startTime: Date;
  /** 结束时间 */
  endTime?: Date;
  /** 总耗时（毫秒） */
  totalDuration?: number;
  /** 错误信息 */
  error?: string;
}

// ============ 事件接口 ============

/** 辩论事件类型 */
export type DebateEventType =
  | 'debate:start'
  | 'debate:end'
  | 'phase:start'
  | 'phase:end'
  | 'round:start'
  | 'round:end'
  | 'message:start'
  | 'message:chunk'
  | 'message:end'
  | 'error';

/** 辩论事件 */
export interface DebateEvent {
  type: DebateEventType;
  timestamp: Date;
  data: any;
}

/** 事件回调 */
export type DebateEventCallback = (event: DebateEvent) => void;

// ============ Agent 接口 ============

/** Agent 执行选项 */
export interface AgentExecuteOptions {
  /** 提示词 */
  prompt: string;
  /** 上下文（之前的对话） */
  context?: DebateMessage[];
  /** 超时时间 */
  timeout?: number;
  /** 流式回调 */
  onChunk?: (chunk: string) => void;
}

/** Agent 执行结果 */
export interface AgentExecuteResult {
  /** 是否成功 */
  success: boolean;
  /** 输出内容 */
  output: string;
  /** 错误信息 */
  error?: string;
  /** 耗时（毫秒） */
  duration: number;
}

/** CLI Agent 接口 */
export interface ICLIAgent {
  /** CLI 类型 */
  readonly cliType: CLIType;
  /** 当前角色 */
  role: DebateRole;
  /** 执行命令 */
  execute(options: AgentExecuteOptions): Promise<AgentExecuteResult>;
  /** 检查是否可用 */
  isAvailable(): Promise<boolean>;
}

// ============ 代码审查类型 ============

/** 问题严重程度 */
export enum IssueSeverity {
  CRITICAL = 'critical',
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low'
}

/** 问题类型 */
export enum IssueType {
  BUG = 'bug',
  SECURITY = 'security',
  PERFORMANCE = 'performance',
  DESIGN = 'design'
}

/** 代码问题 */
export interface CodeIssue {
  /** 问题ID */
  id: string;
  /** 问题类型 */
  type: IssueType;
  /** 严重程度 */
  severity: IssueSeverity;
  /** 问题描述 */
  description: string;
  /** 文件路径 */
  filePath?: string;
  /** 行号 */
  lineNumber?: number;
  /** 建议修复方案 */
  suggestedFix?: string;
  /** 分配给哪个 CLI 修复 */
  assignedTo?: CLIType;
  /** 是否已修复 */
  fixed?: boolean;
  /** 修复结果 */
  fixResult?: string;
}

/** 构建检查结果 */
export interface BuildCheckResult {
  /** 是否成功 */
  success: boolean;
  /** 构建命令 */
  command: string;
  /** 输出内容 */
  output: string;
  /** 错误信息 */
  errors?: string[];
  /** 耗时 */
  duration: number;
}

/** 代码审查配置 */
export interface CodeReviewConfig {
  /** 代码路径 */
  path: string;
  /** 审查焦点 */
  focus?: IssueType[];
  /** 构建命令 */
  buildCommand?: string;
  /** 是否自动修复 */
  autoFix?: boolean;
  /** 挑战者 CLI */
  challenger: AgentConfig;
  /** 辩护者 CLI */
  defender: AgentConfig;
  /** 主持人 CLI */
  moderator: AgentConfig;
  /** 修复者 CLI 列表 */
  fixers?: AgentConfig[];
  /** 是否启用流式输出 */
  streaming?: boolean;
  /** 全局超时 */
  globalTimeout?: number;
}

/** 修复任务 */
export interface FixTask {
  /** 任务ID */
  id: string;
  /** 关联的问题 */
  issue: CodeIssue;
  /** 分配的 CLI */
  assignedCLI: CLIType;
  /** 状态 */
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  /** 修复结果 */
  result?: string;
  /** 耗时 */
  duration?: number;
}

/** 代码审查结果 */
export interface CodeReviewResult {
  /** 审查ID */
  id: string;
  /** 代码路径 */
  path: string;
  /** 状态 */
  status: DebateStatus;
  /** 构建检查结果 */
  buildCheck?: BuildCheckResult;
  /** 发现的问题 */
  issues: CodeIssue[];
  /** 辩护回应 */
  defenseResponses?: DebateMessage[];
  /** 最终裁决 */
  verdict?: DebateMessage;
  /** 修复任务 */
  fixTasks?: FixTask[];
  /** 开始时间 */
  startTime: Date;
  /** 结束时间 */
  endTime?: Date;
  /** 总耗时 */
  totalDuration?: number;
  /** 错误信息 */
  error?: string;
}
