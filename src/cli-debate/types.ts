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
  FINAL = 'final'
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
