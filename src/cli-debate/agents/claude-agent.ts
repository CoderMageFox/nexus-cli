/**
 * Claude CLI Agent 实现
 *
 * 使用 Claude CLI 作为辩论参与者
 */

import { CLIType, DebateRole } from '../types';
import { BaseCLIAgent } from './base-agent';

export class ClaudeAgent extends BaseCLIAgent {
  readonly cliType = CLIType.CLAUDE;

  constructor(role: DebateRole, timeout = 300000) {
    super(role, timeout, ['--print']);
  }

  protected getCommand(): string {
    return 'claude';
  }

  protected getArgs(prompt: string): string[] {
    return [
      '--print',
      '-p',
      `"${prompt.replace(/"/g, '\\"')}"`,
      ...this.extraArgs
    ];
  }

  async isAvailable(): Promise<boolean> {
    return this.checkCommandExists('claude');
  }
}
