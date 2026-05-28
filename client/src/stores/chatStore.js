import { create } from 'zustand';
import { sendMessageStream } from '../api/chat';

const NODE_LABELS = {
  feeling_detect: '正在分析情绪...',
  router: '正在思考...',
  retrieve: '正在检索知识库...',
  plan: '正在规划任务...',
  execute_task: '正在执行任务...',
  check_task_complete: '正在检查任务...',
  call_model: '正在生成回答...'
};

/**
 * 聊天消息类型定义
 * @typedef {Object} Message
 * @property {string} type - 消息类型，'user' | 'bot'
 * @property {string} content - 消息内容
 * @property {number} [id] - 消息唯一标识
 * @property {boolean} [isTyping] - 是否正在打字
 */

/**
 * 聊天状态管理 Store
 * @description 管理聊天消息、会话状态、发送消息等
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
   * 当前执行节点
   * @type {string | null}
   */
  currentNode: null,

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
      messages: [...state.messages, { type: 'bot', content, id, isTyping: true }]
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
   * 设置当前节点
   * @param {string | null} node - 当前节点名称
   */
  setCurrentNode: (node) => set({ currentNode: node }),

  /**
   * 获取节点显示文本
   * @param {string} node - 节点名称
   * @returns {string} 显示文本
   */
  getNodeLabel: (node) => NODE_LABELS[node] || `正在处理: ${node}`,

  /**
   * 发送消息（SSE 流式）
   * @param {string} message - 用户输入的消息
   */
  sendMessage: async (message) => {
    const { addUserMessage, addBotMessage, appendToMessage, updateMessage, setLoading, setCurrentNode } = get();

    addUserMessage(message);
    setLoading(true);
    setCurrentNode('start');

    const messageId = Date.now();
    addBotMessage('', messageId);

    let fullContent = '';

    await sendMessageStream(message, get().sessionId, {
      onToken: (token) => {
        fullContent += token;
        appendToMessage(messageId, token);
      },
      onNodeUpdate: (data) => {
        setCurrentNode(data.node);
      },
      onDone: (data) => {
        updateMessage(messageId, fullContent, false);
        setLoading(false);
        setCurrentNode(null);
      },
      onError: (error) => {
        console.error('SSE 错误:', error);
        updateMessage(messageId, '抱歉，服务暂时不可用，请稍后再试。', false);
        setLoading(false);
        setCurrentNode(null);
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
    currentNode: null
  })
}));

export default useChatStore;