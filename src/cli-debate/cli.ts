#!/usr/bin/env node
/**
 * CLI 辩论系统命令行入口
 *
 * 支持命令:
 * - debate: 标准辩论模式
 * - review: 代码审查模式
 */

import { DebateOrchestrator } from './orchestrator';
import { CodeReviewOrchestrator } from './code-review';
import {
  DebateConfig,
  CodeReviewConfig,
  CLIType,
  DebateRole,
  DebateEvent,
  IssueType
} from './types';

// ============ 辅助函数 ============

/** 获取角色标签 */
function getRoleLabel(role: DebateRole): string {
  switch (role) {
    case DebateRole.MODERATOR:
      return '🎙️ 主持人';
    case DebateRole.CHALLENGER:
      return '⚔️ 挑战者';
    case DebateRole.DEFENDER:
      return '🛡️ 辩护者';
  }
}

/** 获取 CLI 标签 */
function getCLILabel(cliType: CLIType): string {
  switch (cliType) {
    case CLIType.CLAUDE:
      return 'Claude';
    case CLIType.CODEX:
      return 'Codex';
    case CLIType.GEMINI:
      return 'Gemini';
  }
}

/** 解析 CLI 类型 */
function parseCLIType(cli: string): CLIType {
  const cliMap: Record<string, CLIType> = {
    claude: CLIType.CLAUDE,
    codex: CLIType.CODEX,
    gemini: CLIType.GEMINI
  };
  return cliMap[cli?.toLowerCase()] || CLIType.CLAUDE;
}

/** 解析问题类型 */
function parseIssueTypes(focus: string): IssueType[] {
  if (!focus) return [];
  return focus.split(',').map((f) => {
    const typeMap: Record<string, IssueType> = {
      bug: IssueType.BUG,
      security: IssueType.SECURITY,
      performance: IssueType.PERFORMANCE,
      design: IssueType.DESIGN
    };
    return typeMap[f.trim().toLowerCase()] || IssueType.BUG;
  });
}

// ============ 参数解析 ============

interface ParsedArgs {
  command: 'debate' | 'review' | 'help';
  topic?: string;
  path?: string;
  challenger?: CLIType;
  defender?: CLIType;
  moderator?: CLIType;
  rounds?: number;
  focus?: IssueType[];
  autoFix?: boolean;
  buildCommand?: string;
  streaming?: boolean;
}

/** 解析命令行参数 */
function parseArgs(args: string[]): ParsedArgs {
  const result: ParsedArgs = {
    command: 'help',
    streaming: true
  };

  let i = 0;
  while (i < args.length) {
    const arg = args[i];

    if (arg === 'debate' || arg === 'review' || arg === 'help') {
      result.command = arg;
    } else if (arg === '--topic' || arg === '-t') {
      result.topic = args[++i];
    } else if (arg === '--path' || arg === '-p') {
      result.path = args[++i];
    } else if (arg === '--challenger' || arg === '-c') {
      result.challenger = parseCLIType(args[++i]);
    } else if (arg === '--defender' || arg === '-d') {
      result.defender = parseCLIType(args[++i]);
    } else if (arg === '--moderator' || arg === '-m') {
      result.moderator = parseCLIType(args[++i]);
    } else if (arg === '--rounds' || arg === '-r') {
      result.rounds = parseInt(args[++i], 10) || 2;
    } else if (arg === '--focus' || arg === '-f') {
      result.focus = parseIssueTypes(args[++i]);
    } else if (arg === '--auto-fix') {
      result.autoFix = true;
    } else if (arg === '--build') {
      result.buildCommand = args[++i];
    } else if (arg === '--no-stream') {
      result.streaming = false;
    }

    i++;
  }

  return result;
}

// ============ 帮助信息 ============

function showHelp(): void {
  console.log(`
CLI 辩论系统 - 多 AI CLI 协作辩论工具

用法:
  cli-debate <command> [options]

命令:
  debate    标准辩论模式
  review    代码审查模式
  help      显示帮助信息

标准辩论选项:
  --topic, -t <topic>       辩题 (必需)
  --challenger, -c <cli>    挑战者 CLI (claude|codex|gemini)
  --defender, -d <cli>      辩护者 CLI (claude|codex|gemini)
  --moderator, -m <cli>     主持人 CLI (claude|codex|gemini)
  --rounds, -r <number>     辩论回合数 (默认: 2)
  --no-stream               禁用流式输出

代码审查选项:
  --path, -p <path>         代码路径 (必需)
  --focus, -f <types>       审查焦点 (bug,security,performance,design)
  --build <command>         构建命令
  --auto-fix                启用自动修复
  --challenger, -c <cli>    挑战者 CLI
  --defender, -d <cli>      辩护者 CLI
  --moderator, -m <cli>     主持人 CLI

示例:
  # 标准辩论
  cli-debate debate -t "TypeScript vs JavaScript" -c claude -d codex -m gemini

  # 代码审查
  cli-debate review -p ./src -f bug,security --auto-fix

  # 代码审查带构建检查
  cli-debate review -p ./src --build "npm run build" --auto-fix
`);
}

// ============ 事件处理 ============

function handleDebateEvent(event: DebateEvent): void {
  switch (event.type) {
    case 'debate:start':
      console.log('🚀 辩论开始\n');
      break;

    case 'phase:start':
      const phase = event.data.phase;
      if (phase === 'opening') {
        console.log('📢 开场阶段');
      } else if (phase === 'final') {
        console.log('\n📜 最终裁决阶段');
      } else if (phase === 'build_check') {
        console.log('🔨 构建检查阶段');
      } else if (phase === 'code_analysis') {
        console.log('\n🔍 代码分析阶段');
      } else if (phase === 'issue_defense') {
        console.log('\n🛡️ 问题辩护阶段');
      } else if (phase === 'verdict_assignment') {
        console.log('\n⚖️ 裁决分配阶段');
      } else if (phase === 'parallel_fix') {
        console.log('\n🔧 并行修复阶段');
      }
      break;

    case 'round:start':
      console.log(`\n🔔 第 ${event.data.roundNumber} 回合开始`);
      console.log('─'.repeat(40));
      break;

    case 'message:start':
      if (event.data.role) {
        const label = getRoleLabel(event.data.role);
        const cli = getCLILabel(event.data.cliType);
        console.log(`\n${label} (${cli}):`);
      }
      break;

    case 'message:chunk':
      process.stdout.write(event.data.chunk);
      break;

    case 'message:end':
      if (event.data.message?.content && !event.data.message.content.endsWith('\n')) {
        console.log();
      }
      break;

    case 'round:end':
      const duration = event.data.roundResult?.duration / 1000;
      if (duration) {
        console.log(`\n⏱️ 回合耗时: ${duration.toFixed(1)}秒`);
      }
      break;

    case 'debate:end':
      console.log('\n🏁 辩论结束');
      break;

    case 'error':
      console.error(`\n❌ 错误: ${event.data.error}`);
      break;
  }
}

// ============ 命令执行 ============

/** 执行标准辩论 */
async function runDebate(args: ParsedArgs): Promise<void> {
  if (!args.topic) {
    console.error('❌ 错误: 请提供辩题 (--topic)');
    process.exit(1);
  }

  console.log('╔════════════════════════════════════════════════════╗');
  console.log('║           CLI 辩论系统 - 标准辩论模式               ║');
  console.log('╚════════════════════════════════════════════════════╝\n');

  const config: DebateConfig = {
    topic: args.topic,
    rounds: args.rounds || 2,
    moderator: {
      cliType: args.moderator || CLIType.GEMINI,
      role: DebateRole.MODERATOR
    },
    challenger: {
      cliType: args.challenger || CLIType.CLAUDE,
      role: DebateRole.CHALLENGER
    },
    defender: {
      cliType: args.defender || CLIType.CODEX,
      role: DebateRole.DEFENDER
    },
    streaming: args.streaming
  };

  console.log(`📋 辩题: ${config.topic}`);
  console.log(`📊 回合数: ${config.rounds}`);
  console.log(`🎙️ 主持人: ${getCLILabel(config.moderator.cliType)}`);
  console.log(`⚔️ 挑战者: ${getCLILabel(config.challenger.cliType)}`);
  console.log(`🛡️ 辩护者: ${getCLILabel(config.defender.cliType)}`);
  console.log('\n' + '─'.repeat(50) + '\n');

  const orchestrator = new DebateOrchestrator(config);
  orchestrator.on(handleDebateEvent);

  const result = await orchestrator.run();

  // 输出结果摘要
  console.log('\n' + '═'.repeat(50));
  console.log('📊 辩论结果摘要');
  console.log('═'.repeat(50));
  console.log(`状态: ${result.status}`);
  console.log(`总耗时: ${((result.totalDuration || 0) / 1000).toFixed(1)}秒`);
  console.log(`回合数: ${result.rounds.length}`);

  if (result.error) {
    console.log(`❌ 错误: ${result.error}`);
    process.exit(1);
  }
}

/** 执行代码审查 */
async function runCodeReview(args: ParsedArgs): Promise<void> {
  if (!args.path) {
    console.error('❌ 错误: 请提供代码路径 (--path)');
    process.exit(1);
  }

  console.log('╔════════════════════════════════════════════════════╗');
  console.log('║           CLI 辩论系统 - 代码审查模式               ║');
  console.log('╚════════════════════════════════════════════════════╝\n');

  const config: CodeReviewConfig = {
    path: args.path,
    focus: args.focus,
    buildCommand: args.buildCommand,
    autoFix: args.autoFix,
    challenger: {
      cliType: args.challenger || CLIType.CLAUDE,
      role: DebateRole.CHALLENGER
    },
    defender: {
      cliType: args.defender || CLIType.CODEX,
      role: DebateRole.DEFENDER
    },
    moderator: {
      cliType: args.moderator || CLIType.GEMINI,
      role: DebateRole.MODERATOR
    },
    streaming: args.streaming
  };

  console.log(`📁 代码路径: ${config.path}`);
  console.log(`🔍 审查焦点: ${args.focus?.join(', ') || '全面审查'}`);
  console.log(`🔨 构建命令: ${config.buildCommand || '无'}`);
  console.log(`🔧 自动修复: ${config.autoFix ? '是' : '否'}`);
  console.log(`⚔️ 挑战者: ${getCLILabel(config.challenger.cliType)}`);
  console.log(`🛡️ 辩护者: ${getCLILabel(config.defender.cliType)}`);
  console.log(`🎙️ 主持人: ${getCLILabel(config.moderator.cliType)}`);
  console.log('\n' + '─'.repeat(50) + '\n');

  const orchestrator = new CodeReviewOrchestrator(config);
  orchestrator.on(handleDebateEvent);

  const result = await orchestrator.run();

  // 输出结果摘要
  console.log('\n' + '═'.repeat(50));
  console.log('📊 代码审查结果摘要');
  console.log('═'.repeat(50));
  console.log(`状态: ${result.status}`);
  console.log(`总耗时: ${((result.totalDuration || 0) / 1000).toFixed(1)}秒`);
  console.log(`发现问题: ${result.issues.length}`);

  if (result.fixTasks?.length) {
    const fixed = result.fixTasks.filter((t) => t.status === 'completed').length;
    console.log(`修复任务: ${fixed}/${result.fixTasks.length} 完成`);
  }

  if (result.error) {
    console.log(`❌ 错误: ${result.error}`);
    process.exit(1);
  }
}

// ============ 主入口 ============

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  switch (args.command) {
    case 'debate':
      await runDebate(args);
      break;
    case 'review':
      await runCodeReview(args);
      break;
    case 'help':
    default:
      showHelp();
      break;
  }
}

// 运行
main().catch((error) => {
  console.error('❌ 未捕获的错误:', error);
  process.exit(1);
});
