/**
 * CLI 辩论系统测试脚本
 */

import {
  DebateOrchestrator,
  DebateConfig,
  CLIType,
  DebateRole,
  DebateEvent
} from './index';

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

/** 运行测试辩论 */
async function runTestDebate() {
  console.log('╔════════════════════════════════════════════════════╗');
  console.log('║           CLI 辩论系统测试                          ║');
  console.log('╚════════════════════════════════════════════════════╝\n');

  // 配置辩论
  const config: DebateConfig = {
    topic: 'TypeScript 是否应该成为所有 JavaScript 项目的默认选择？',
    rounds: 2,
    moderator: {
      cliType: CLIType.GEMINI,
      role: DebateRole.MODERATOR,
      timeout: 120000
    },
    challenger: {
      cliType: CLIType.CLAUDE,
      role: DebateRole.CHALLENGER,
      timeout: 120000
    },
    defender: {
      cliType: CLIType.CODEX,
      role: DebateRole.DEFENDER,
      timeout: 120000
    },
    streaming: true,
    language: 'zh'
  };

  console.log(`📋 辩题: ${config.topic}`);
  console.log(`📊 回合数: ${config.rounds}`);
  console.log(`🎙️ 主持人: ${getCLILabel(config.moderator.cliType)}`);
  console.log(`⚔️ 挑战者: ${getCLILabel(config.challenger.cliType)}`);
  console.log(`🛡️ 辩护者: ${getCLILabel(config.defender.cliType)}`);
  console.log('\n' + '─'.repeat(50) + '\n');

  // 创建编排器
  const orchestrator = new DebateOrchestrator(config);

  // 注册事件回调
  orchestrator.on((event: DebateEvent) => {
    handleEvent(event);
  });

  // 运行辩论
  const result = await orchestrator.run();

  // 输出结果摘要
  console.log('\n' + '═'.repeat(50));
  console.log('📊 辩论结果摘要');
  console.log('═'.repeat(50));
  console.log(`状态: ${result.status}`);
  console.log(`总耗时: ${(result.totalDuration || 0) / 1000}秒`);
  console.log(`回合数: ${result.rounds.length}`);

  if (result.error) {
    console.log(`❌ 错误: ${result.error}`);
  }
}

/** 处理事件 */
function handleEvent(event: DebateEvent) {
  switch (event.type) {
    case 'debate:start':
      console.log('🚀 辩论开始\n');
      break;

    case 'phase:start':
      if (event.data.phase === 'opening') {
        console.log('📢 开场阶段');
      } else if (event.data.phase === 'final') {
        console.log('\n📜 最终裁决阶段');
      }
      break;

    case 'round:start':
      console.log(`\n🔔 第 ${event.data.roundNumber} 回合开始`);
      console.log('─'.repeat(40));
      break;

    case 'message:start':
      const label = getRoleLabel(event.data.role);
      const cli = getCLILabel(event.data.cliType);
      console.log(`\n${label} (${cli}):`);
      break;

    case 'message:chunk':
      process.stdout.write(event.data.chunk);
      break;

    case 'message:end':
      if (!event.data.message.content.endsWith('\n')) {
        console.log();
      }
      break;

    case 'round:end':
      const duration = event.data.roundResult.duration / 1000;
      console.log(`\n⏱️ 回合耗时: ${duration.toFixed(1)}秒`);
      break;

    case 'debate:end':
      console.log('\n🏁 辩论结束');
      break;

    case 'error':
      console.error(`\n❌ 错误: ${event.data.error}`);
      break;
  }
}

// 运行测试
runTestDebate().catch(console.error);
