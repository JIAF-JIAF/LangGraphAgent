import axios from 'axios';
import { EventType } from './events';

const API_BASE_URL = 'http://localhost:5000';

/**
 * 发送消息到后端
 * @param {string} message - 用户消息
 * @param {string} sessionId - 会话ID
 * @returns {Promise} - 包含回复的 Promise
 */
export const sendMessage = async (message, sessionId) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/chat`, {
      message: message,
      session_id: sessionId
    });
    return response.data;
  } catch (error) {
    console.error('发送消息失败:', error);
    throw error;
  }
};

/**
 * SSE 流式发送消息（对齐 AG-UI 协议）
 * @param {string} message - 用户消息
 * @param {string} sessionId - 会话ID
 * @param {Object} callbacks - 回调函数
 * @param {Function} callbacks.onStepStarted - 思考步骤开始时的回调 (step, label, icon, detail)
 * @param {Function} callbacks.onStepProgress - 思考步骤进度更新时的回调 (step, label, icon, detail)
 * @param {Function} callbacks.onStepFinished - 思考步骤完成时的回调 (step, label, icon, detail)
 * @param {Function} callbacks.onToken - 收到 token 时的回调 (content, node)
 * @param {Function} callbacks.onDone - 完成时的回调 (data)
 * @param {Function} callbacks.onError - 错误时的回调 (error)
 * @returns {Promise<void>}
 */
export const sendMessageStream = async (message, sessionId, callbacks) => {
  const { onToken, onStepStarted, onStepProgress, onStepFinished, onDone, onError } = callbacks;

  try {
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        session_id: sessionId
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            
            switch (data.type) {
              case EventType.STEP_STARTED:
                onStepStarted?.(data.step, data.label, data.icon, data.detail);
                break;
              case EventType.STEP_PROGRESS:
                onStepProgress?.(data.step, data.label, data.icon, data.detail);
                break;
              case EventType.STEP_FINISHED:
                onStepFinished?.(data.step, data.label, data.icon, data.detail);
                break;
              case EventType.TEXT_MESSAGE_CONTENT:
                onToken?.(data.content, data.node);
                break;
              case EventType.RUN_FINISHED:
                onDone?.(data);
                break;
              case EventType.RUN_ERROR:
                onError?.(data.error);
                break;
            }
          } catch (e) {
            console.error('解析 SSE 数据失败:', e);
          }
        }
      }
    }
  } catch (error) {
    console.error('SSE 流式请求失败:', error);
    onError?.(error.message);
  }
};

/**
 * 检查服务状态
 * @returns {Promise} - 服务状态
 */
export const checkStatus = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/start`);
    return response.data;
  } catch (error) {
    console.error('检查服务状态失败:', error);
    throw error;
  }
};
