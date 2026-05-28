import { useState, useCallback } from 'react';

/**
 * 自定义 Hook - 打字机效果
 * @description 逐字显示文本，模拟打字机效果，常用于 AI 回复展示
 * @param {Function} [onComplete] - 打字完成后的回调函数
 * @returns {Object} 打字机状态和方法
 * @returns {string} return.currentText - 当前已显示的文本
 * @returns {boolean} return.isTyping - 是否正在打字中
 * @returns {Function} return.startTyping - 开始打字的方法
 * @returns {Function} return.reset - 重置状态的方法
 *
 * @example
 * ```jsx
 * const { currentText, isTyping, startTyping } = useTypingEffect((fullText) => {
 *   console.log('打字完成:', fullText);
 * });
 *
 * // 模拟 AI 回复
 * startTyping('您好！我是智能助手...', 30);
 * ```
 */
const useTypingEffect = (onComplete) => {
  const [currentText, setCurrentText] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const startTyping = useCallback(async (fullText, speed = 30) => {
    setIsTyping(true);
    setCurrentText('');

    for (let i = 0; i < fullText.length; i++) {
      await new Promise((resolve) => setTimeout(resolve, speed));
      setCurrentText(fullText.substring(0, i + 1));
    }

    setIsTyping(false);
    onComplete?.(fullText);
  }, [onComplete]);

  const reset = useCallback(() => {
    setCurrentText('');
    setIsTyping(false);
  }, []);

  return {
    currentText,
    isTyping,
    startTyping,
    reset
  };
};

export default useTypingEffect;