/**
 * Gemini CLI Agent 实现
 *
 * 使用 Gemini CLI 作为辩论参与者
 */

import { CLIType, DebateRole } from '../types';
import { BaseCLIAgent } from './base-agent';

export class GeminiAgent extends BaseCLIAgent {
  readonly cliType = CLIType.GEMINI;

  constructor(role: DebateRole, timeout = 300000) {
    super(role, timeout, ['--yolo', '-o', 'text']);
  }

  protected getCommand(): string {
    return 'gemini';
  }

  protected getArgs(prompt: string): string[] {
    return [
      `"${prompt.replace(/"/g, '\\"')}"`,
      '--yolo',
      '-o',
      'text',
      ...this.extraArgs
    ];
  }

  async isAvailable(): Promise<boolean> {
    return this.checkCommandExists('gemini');
  }
}
