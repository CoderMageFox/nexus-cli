/**
 * 辩论角色 Prompt 模板
 *
 * 为不同角色提供专业的提示词模板
 */

import { DebateRole, DebateMessage } from './types';

/** 格式化对话历史 */
function formatHistory(messages: DebateMessage[]): string {
  if (!messages.length) return '';

  return messages
    .map((m) => {
      const roleLabel = getRoleLabel(m.role);
      return `【${roleLabel}】:\n${m.content}`;
    })
    .join('\n\n---\n\n');
}

/** 获取角色标签 */
function getRoleLabel(role: DebateRole): string {
  switch (role) {
    case DebateRole.MODERATOR:
      return '主持人';
    case DebateRole.CHALLENGER:
      return '挑战者';
    case DebateRole.DEFENDER:
      return '辩护者';
  }
}

// ============ 主持人 Prompts ============

/** 主持人开场 Prompt */
export function getModeratorOpeningPrompt(topic: string): string {
  return `你是一场技术辩论的主持人。

## 辩题
${topic}

## 你的任务
作为主持人，请进行开场介绍：
1. 欢迎观众并介绍今天的辩题
2. 简要说明辩题的背景和重要性
3. 介绍辩论规则：挑战者将提出质疑，辩护者将进行回应
4. 宣布辩论开始

## 输出要求
- 使用中文
- 保持专业、客观的主持风格
- 控制在 200-300 字`;
}

/** 主持人评估 Prompt */
export function getModeratorEvaluationPrompt(
  topic: string,
  roundNumber: number,
  history: DebateMessage[]
): string {
  return `你是一场技术辩论的主持人。

## 辩题
${topic}

## 当前回合
第 ${roundNumber} 回合

## 对话历史
${formatHistory(history)}

## 你的任务
作为主持人，请对本回合进行评估：
1. 总结挑战者提出的核心问题
2. 评价辩护者的回应质量
3. 指出双方论点的优缺点
4. 引导进入下一回合（如有）

## 输出要求
- 使用中文
- 保持客观公正
- 控制在 150-250 字`;
}

/** 主持人最终裁决 Prompt */
export function getModeratorFinalVerdictPrompt(
  topic: string,
  history: DebateMessage[]
): string {
  return `你是一场技术辩论的主持人。

## 辩题
${topic}

## 完整对话历史
${formatHistory(history)}

## 你的任务
作为主持人，请给出最终裁决：
1. 回顾整场辩论的核心争议点
2. 评估双方的论证质量和说服力
3. 指出哪方的论点更有说服力，并说明原因
4. 给出你的最终结论和建议
5. 感谢双方的精彩辩论

## 输出要求
- 使用中文
- 保持客观公正，有理有据
- 控制在 300-400 字`;
}

// ============ 挑战者 Prompts ============

/** 挑战者质疑 Prompt */
export function getChallengerPrompt(
  topic: string,
  roundNumber: number,
  history: DebateMessage[]
): string {
  const isFirstRound = roundNumber === 1;

  return `你是一场技术辩论的挑战者。

## 辩题
${topic}

## 当前回合
第 ${roundNumber} 回合

${history.length > 0 ? `## 对话历史\n${formatHistory(history)}` : ''}

## 你的任务
作为挑战者，你需要${isFirstRound ? '首先提出' : '继续深入'}质疑：
${isFirstRound ? `1. 针对辩题提出核心质疑
2. 指出可能存在的问题或风险
3. 提出具体的反对理由` : `1. 基于之前的讨论，提出更深入的质疑
2. 针对辩护者的回应找出漏洞
3. 提出新的角度或证据`}

## 输出要求
- 使用中文
- 保持逻辑清晰，论据充分
- 态度专业但有攻击性
- 控制在 200-300 字`;
}

// ============ 辩护者 Prompts ============

/** 辩护者回应 Prompt */
export function getDefenderPrompt(
  topic: string,
  roundNumber: number,
  history: DebateMessage[]
): string {
  return `你是一场技术辩论的辩护者。

## 辩题
${topic}

## 当前回合
第 ${roundNumber} 回合

## 对话历史
${formatHistory(history)}

## 你的任务
作为辩护者，你需要回应挑战者的质疑：
1. 直接回应挑战者提出的核心问题
2. 提供有力的论据和证据支持你的立场
3. 指出挑战者论点中的不足之处
4. 强化你的核心观点

## 输出要求
- 使用中文
- 保持逻辑清晰，论据充分
- 态度专业且有说服力
- 控制在 200-300 字`;
}
