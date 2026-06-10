/**
 * AG-UI (Agent-User Interaction) 协议事件类型定义
 *
 * 对齐 AG-UI 协议标准，统一管理所有 SSE 事件类型，
 * 避免字符串硬编码散落各处，防止拼写错误。
 */

export const EventType = Object.freeze({
  STEP_STARTED: "STEP_STARTED",
  STEP_PROGRESS: "STEP_PROGRESS",
  STEP_FINISHED: "STEP_FINISHED",
  TEXT_MESSAGE_CONTENT: "TEXT_MESSAGE_CONTENT",
  RUN_FINISHED: "RUN_FINISHED",
  RUN_ERROR: "RUN_ERROR",
});

export const StepStatus = Object.freeze({
  STARTED: "started",
  PROGRESS: "progress",
  COMPLETED: "completed",
});
