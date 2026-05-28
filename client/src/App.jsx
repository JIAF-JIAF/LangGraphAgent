import { memo } from 'react';
import useChatStore from './stores/chatStore';
import { Header, ChatArea, InputArea } from './components/chat';
import './App.css';

/**
 * 应用主组件
 * @description 智能助手聊天界面主入口，整合 Header、ChatArea 和 InputArea
 *
 * @returns {React.ReactElement}
 */
export const App = memo((props) => {
  const { messages, loading, currentNode, getNodeLabel, sendMessage } = useChatStore();

  /**
   * 处理发送消息
   * @param {string} message - 消息内容
   */
  const handleSend = (message) => {
    sendMessage(message);
  };

  return (
    <div className="app">
      <Header />
      <ChatArea 
        messages={messages} 
        loading={loading} 
        currentNode={currentNode}
        getNodeLabel={getNodeLabel}
      />
      <InputArea onSend={handleSend} loading={loading} />
    </div>
  );
});

App.displayName = 'App';