/**
 * Codex CLI Agent 实现
 *
 * 使用 Codex CLI 作为辩论参与者
 */

import { CLIType, DebateRole } from '../types';
import { BaseCLIAgent } from './base-agent';

export class CodexAgent extends BaseCLIAgent {
  readonly cliType = CLIType.CODEX;

  constructor(role: DebateRole, timeout = 300000) {
    super(role, timeout, []);
  }

  protected getCommand(): string {
    return 'codex';
  }

  protected getArgs(prompt: string): string[] {
    return [
      '--approval-mode',
      'full-auto',
      `"${prompt.replace(/"/g, '\\"')}"`,
      ...this.extraArgs
    ];
  }

  async isAvailable(): Promise<boolean> {
    return this.checkCommandExists('codex');
  }
}
