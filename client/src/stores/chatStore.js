import { create } from 'zustand';
import { sendMessageStream } from '../api/chat';

/**
 * 聊天消息类型定义
 * @typedef {Object} Message
 * @property {string} type - 消息类型，'user' | 'bot'
 * @property {string} content - 消息内容
 * @property {number} [id] - 消息唯一标识
 * @property {boolean} [isTyping] - 是否正在打字
 * @property {Step[]} [steps] - 思考步骤列表
 */

/**
 * 思考步骤类型定义
 * @typedef {Object} Step
 * @property {string} step - 步骤标识
 * @property {string} label - 步骤显示名称
 * @property {string} icon - 步骤图标
 * @property {string} status - 步骤状态，'started' | 'completed'
 * @property {string} [detail] - 步骤详情
 */

/**
 * 聊天状态管理 Store
 * @description 管理聊天消息、会话状态、思考步骤、发送消息等
 *
 * @returns {Object} 聊天状态和方法
 *
 * @example
 * ```jsx
 * const { messages, loading, sendMessage } = useChatStore();
 * await sendMessage('你好');
 * ```
 */
const useChatStore = create((set, get) => ({
  /**
   * 消息列表
   * @type {Message[]}
   */
  messages: [
    { type: 'bot', content: '您好！我是智能助手，有什么可以帮助您的吗？' }
  ],

  /**
   * 会话 ID
   * @type {string}
   */
  sessionId: Date.now().toString(),

  /**
   * 加载状态
   * @type {boolean}
   */
  loading: false,

  /**
   * 添加用户消息
   * @param {string} content - 消息内容
   */
  addUserMessage: (content) => {
    set((state) => ({
      messages: [...state.messages, { type: 'user', content }]
    }));
  },

  /**
   * 添加机器人消息
   * @param {string} content - 消息内容
   * @param {number} [id] - 消息 ID，默认为当前时间戳
   */
  addBotMessage: (content, id = Date.now()) => {
    set((state) => ({
      messages: [...state.messages, { type: 'bot', content, id, isTyping: true, steps: [] }]
    }));
  },

  /**
   * 更新消息内容
   * @param {number} id - 消息 ID
   * @param {string} content - 新内容
   * @param {boolean} [isTyping] - 是否正在打字
   */
  updateMessage: (id, content, isTyping = false) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content, isTyping } : msg
      )
    }));
  },

  /**
   * 追加内容到消息
   * @param {number} id - 消息 ID
   * @param {string} token - 要追加的 token
   */
  appendToMessage: (id, token) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content: msg.content + token } : msg
      )
    }));
  },

  /**
   * 添加思考步骤到消息
   * @param {number} id - 消息 ID
   * @param {Step} step - 思考步骤
   */
  addStepToMessage: (id, step) => {
    set((state) => ({
      messages: state.messages.map((msg) => {
        if (msg.id !== id) return msg;
        const steps = [...(msg.steps || [])];
        const existingIdx = steps.findIndex((s) => s.step === step.step);
        if (existingIdx >= 0) {
          // 合并：保留已有的 progressList，更新新字段
          const existing = steps[existingIdx];
          const updated = { ...existing, ...step };
          // 如果是 progress 事件，追加到 progressList
          if (step.status === 'progress' && step.detail) {
            updated.progressList = [...(existing.progressList || []), step.detail];
          }
          steps[existingIdx] = updated;
        } else {
          // 新步骤：初始化 progressList
          const newStep = { ...step, progressList: [] };
          if (step.status === 'progress' && step.detail) {
            newStep.progressList = [step.detail];
          }
          steps.push(newStep);
        }
        return { ...msg, steps };
      })
    }));
  },

  /**
   * 发送消息（SSE 流式，对齐 AG-UI 协议）
   * @param {string} message - 用户输入的消息
   */
  sendMessage: async (message) => {
    const { addUserMessage, addBotMessage, appendToMessage, updateMessage, addStepToMessage, setLoading } = get();

    addUserMessage(message);
    setLoading(true);

    const messageId = Date.now();
    addBotMessage('', messageId);

    let fullContent = '';

    await sendMessageStream(message, get().sessionId, {
      onStepStarted: (step, label, icon, detail) => {
        addStepToMessage(messageId, { step, label, icon, status: 'started', detail });
      },
      onStepProgress: (step, label, icon, detail) => {
        addStepToMessage(messageId, { step, label, icon, status: 'progress', detail });
      },
      onStepFinished: (step, label, icon, detail) => {
        addStepToMessage(messageId, { step, label, icon, status: 'completed', detail });
      },
      onToken: (token) => {
        fullContent += token;
        appendToMessage(messageId, token);
      },
      onDone: () => {
        updateMessage(messageId, fullContent, false);
        setLoading(false);
      },
      onError: (error) => {
        console.error('SSE 错误:', error);
        updateMessage(messageId, '抱歉，服务暂时不可用，请稍后再试。', false);
        setLoading(false);
      }
    });
  },

  /**
   * 设置加载状态
   * @param {boolean} loading - 加载状态
   */
  setLoading: (loading) => set({ loading }),

  /**
   * 重置会话
   * @description 清空消息列表并生成新的会话 ID
   */
  resetSession: () => set({
    messages: [{ type: 'bot', content: '您好！我是智能助手，有什么可以帮助您的吗？' }],
    sessionId: Date.now().toString(),
  })
}));

export default useChatStore;
