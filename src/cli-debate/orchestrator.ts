/**
 * 辩论编排器
 *
 * 负责协调多个 CLI Agent 进行辩论
 */

import { v4 as uuidv4 } from 'uuid';
import {
  DebateConfig,
  DebateResult,
  DebateStatus,
  DebatePhase,
  DebateMessage,
  DebateRole,
  RoundResult,
  DebateEvent,
  DebateEventCallback,
  CLIType,
  ICLIAgent
} from './types';
import {
  getModeratorOpeningPrompt,
  getModeratorEvaluationPrompt,
  getModeratorFinalVerdictPrompt,
  getChallengerPrompt,
  getDefenderPrompt
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

/** 辩论编排器 */
export class DebateOrchestrator {
  private config: DebateConfig;
  private moderator: ICLIAgent;
  private challenger: ICLIAgent;
  private defender: ICLIAgent;
  private eventCallbacks: DebateEventCallback[] = [];
  private messages: DebateMessage[] = [];

  constructor(config: DebateConfig) {
    this.config = config;

    // 创建 Agent 实例
    this.moderator = createAgent(
      config.moderator.cliType,
      DebateRole.MODERATOR,
      config.moderator.timeout
    );
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
    phase: DebatePhase,
    roundNumber?: number
  ): DebateMessage {
    const message: DebateMessage = {
      id: uuidv4(),
      role,
      cliType,
      content,
      timestamp: new Date(),
      phase,
      roundNumber
    };
    this.messages.push(message);
    return message;
  }

  /** 检查所有 Agent 是否可用 */
  async checkAgentsAvailable(): Promise<{ available: boolean; errors: string[] }> {
    const errors: string[] = [];

    const [modAvail, chalAvail, defAvail] = await Promise.all([
      this.moderator.isAvailable(),
      this.challenger.isAvailable(),
      this.defender.isAvailable()
    ]);

    if (!modAvail) {
      errors.push(`主持人 CLI (${this.config.moderator.cliType}) 不可用`);
    }
    if (!chalAvail) {
      errors.push(`挑战者 CLI (${this.config.challenger.cliType}) 不可用`);
    }
    if (!defAvail) {
      errors.push(`辩护者 CLI (${this.config.defender.cliType}) 不可用`);
    }

    return { available: errors.length === 0, errors };
  }

  /** 执行开场阶段 */
  private async executeOpening(): Promise<DebateMessage> {
    this.emit('phase:start', { phase: DebatePhase.OPENING });

    const prompt = getModeratorOpeningPrompt(this.config.topic);

    this.emit('message:start', {
      role: DebateRole.MODERATOR,
      cliType: this.config.moderator.cliType
    });

    const result = await this.moderator.execute({
      prompt,
      onChunk: (chunk) => {
        if (this.config.streaming) {
          this.emit('message:chunk', { chunk, role: DebateRole.MODERATOR });
        }
      }
    });

    if (!result.success) {
      throw new Error(`主持人开场失败: ${result.error}`);
    }

    const message = this.createMessage(
      DebateRole.MODERATOR,
      this.config.moderator.cliType,
      result.output,
      DebatePhase.OPENING
    );

    this.emit('message:end', { message });
    this.emit('phase:end', { phase: DebatePhase.OPENING });

    return message;
  }

  /** 执行单个回合 */
  private async executeRound(roundNumber: number): Promise<RoundResult> {
    const startTime = Date.now();

    this.emit('round:start', { roundNumber });

    // 1. 挑战者质疑
    const challengerPrompt = getChallengerPrompt(
      this.config.topic,
      roundNumber,
      this.messages
    );

    this.emit('message:start', {
      role: DebateRole.CHALLENGER,
      cliType: this.config.challenger.cliType
    });

    const challengerResult = await this.challenger.execute({
      prompt: challengerPrompt,
      context: this.messages,
      onChunk: (chunk) => {
        if (this.config.streaming) {
          this.emit('message:chunk', { chunk, role: DebateRole.CHALLENGER });
        }
      }
    });

    if (!challengerResult.success) {
      throw new Error(`挑战者质疑失败: ${challengerResult.error}`);
    }

    const challengerMessage = this.createMessage(
      DebateRole.CHALLENGER,
      this.config.challenger.cliType,
      challengerResult.output,
      DebatePhase.ROUND,
      roundNumber
    );

    this.emit('message:end', { message: challengerMessage });

    // 2. 辩护者回应
    const defenderPrompt = getDefenderPrompt(
      this.config.topic,
      roundNumber,
      this.messages
    );

    this.emit('message:start', {
      role: DebateRole.DEFENDER,
      cliType: this.config.defender.cliType
    });

    const defenderResult = await this.defender.execute({
      prompt: defenderPrompt,
      context: this.messages,
      onChunk: (chunk) => {
        if (this.config.streaming) {
          this.emit('message:chunk', { chunk, role: DebateRole.DEFENDER });
        }
      }
    });

    if (!defenderResult.success) {
      throw new Error(`辩护者回应失败: ${defenderResult.error}`);
    }

    const defenderMessage = this.createMessage(
      DebateRole.DEFENDER,
      this.config.defender.cliType,
      defenderResult.output,
      DebatePhase.ROUND,
      roundNumber
    );

    this.emit('message:end', { message: defenderMessage });

    // 3. 主持人评估
    const evaluationPrompt = getModeratorEvaluationPrompt(
      this.config.topic,
      roundNumber,
      this.messages
    );

    this.emit('message:start', {
      role: DebateRole.MODERATOR,
      cliType: this.config.moderator.cliType
    });

    const evaluationResult = await this.moderator.execute({
      prompt: evaluationPrompt,
      context: this.messages,
      onChunk: (chunk) => {
        if (this.config.streaming) {
          this.emit('message:chunk', { chunk, role: DebateRole.MODERATOR });
        }
      }
    });

    if (!evaluationResult.success) {
      throw new Error(`主持人评估失败: ${evaluationResult.error}`);
    }

    const moderatorEvaluation = this.createMessage(
      DebateRole.MODERATOR,
      this.config.moderator.cliType,
      evaluationResult.output,
      DebatePhase.ROUND,
      roundNumber
    );

    this.emit('message:end', { message: moderatorEvaluation });

    const roundResult: RoundResult = {
      roundNumber,
      challengerMessage,
      defenderMessage,
      moderatorEvaluation,
      duration: Date.now() - startTime
    };

    this.emit('round:end', { roundResult });

    return roundResult;
  }

  /** 执行最终裁决 */
  private async executeFinalVerdict(): Promise<DebateMessage> {
    this.emit('phase:start', { phase: DebatePhase.FINAL });

    const prompt = getModeratorFinalVerdictPrompt(this.config.topic, this.messages);

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
      throw new Error(`最终裁决失败: ${result.error}`);
    }

    const message = this.createMessage(
      DebateRole.MODERATOR,
      this.config.moderator.cliType,
      result.output,
      DebatePhase.FINAL
    );

    this.emit('message:end', { message });
    this.emit('phase:end', { phase: DebatePhase.FINAL });

    return message;
  }

  /** 运行辩论 */
  async run(): Promise<DebateResult> {
    const debateId = uuidv4();
    const startTime = new Date();

    const result: DebateResult = {
      id: debateId,
      topic: this.config.topic,
      status: DebateStatus.PENDING,
      rounds: [],
      startTime
    };

    try {
      // 检查 Agent 可用性
      const { available, errors } = await this.checkAgentsAvailable();
      if (!available) {
        throw new Error(`Agent 不可用: ${errors.join(', ')}`);
      }

      result.status = DebateStatus.IN_PROGRESS;
      this.emit('debate:start', { debateId, topic: this.config.topic });

      // 1. 开场
      result.opening = await this.executeOpening();

      // 2. 辩论回合
      for (let i = 1; i <= this.config.rounds; i++) {
        const roundResult = await this.executeRound(i);
        result.rounds.push(roundResult);
      }

      // 3. 最终裁决
      result.finalVerdict = await this.executeFinalVerdict();

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
