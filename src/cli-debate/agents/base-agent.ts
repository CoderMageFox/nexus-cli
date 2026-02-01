/**
 * 基础 CLI Agent 抽象类
 *
 * 提供所有 CLI Agent 的通用功能和接口
 */

import { spawn, ChildProcess } from 'child_process';
import {
  CLIType,
  DebateRole,
  ICLIAgent,
  AgentExecuteOptions,
  AgentExecuteResult
} from '../types';

export abstract class BaseCLIAgent implements ICLIAgent {
  abstract readonly cliType: CLIType;
  public role: DebateRole;
  protected timeout: number;
  protected extraArgs: string[];

  constructor(role: DebateRole, timeout = 300000, extraArgs: string[] = []) {
    this.role = role;
    this.timeout = timeout;
    this.extraArgs = extraArgs;
  }

  /** 获取 CLI 命令 */
  protected abstract getCommand(): string;

  /** 获取命令参数 */
  protected abstract getArgs(prompt: string): string[];

  /** 检查 CLI 是否可用 */
  abstract isAvailable(): Promise<boolean>;

  /** 执行命令 */
  async execute(options: AgentExecuteOptions): Promise<AgentExecuteResult> {
    const startTime = Date.now();
    const timeout = options.timeout || this.timeout;

    return new Promise((resolve) => {
      const command = this.getCommand();
      const args = this.getArgs(options.prompt);

      let output = '';
      let errorOutput = '';
      let resolved = false;

      const childProcess = spawn(command, args, {
        shell: true,
        env: { ...global.process.env }
      });

      // 超时处理
      const timer = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          childProcess.kill('SIGTERM');
          resolve({
            success: false,
            output: output,
            error: '执行超时',
            duration: Date.now() - startTime
          });
        }
      }, timeout);

      // 处理标准输出
      childProcess.stdout?.on('data', (data: Buffer) => {
        const chunk = data.toString();
        output += chunk;
        options.onChunk?.(chunk);
      });

      // 处理错误输出
      childProcess.stderr?.on('data', (data: Buffer) => {
        errorOutput += data.toString();
      });

      // 处理完成
      childProcess.on('close', (code) => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timer);
          resolve({
            success: code === 0,
            output: output.trim(),
            error: code !== 0 ? errorOutput || `退出码: ${code}` : undefined,
            duration: Date.now() - startTime
          });
        }
      });

      // 处理错误
      childProcess.on('error', (err) => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timer);
          resolve({
            success: false,
            output: '',
            error: err.message,
            duration: Date.now() - startTime
          });
        }
      });
    });
  }

  /** 检查命令是否存在 */
  protected async checkCommandExists(cmd: string): Promise<boolean> {
    return new Promise((resolve) => {
      const checkProcess = spawn('which', [cmd], { shell: true });
      checkProcess.on('close', (code) => resolve(code === 0));
      checkProcess.on('error', () => resolve(false));
    });
  }
}
