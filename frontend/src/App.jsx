import { useState } from 'react';
import Header from './components/Header';
import ChatArea from './components/ChatArea';
import InputArea from './components/InputArea';
import { sendMessage } from './api/chat';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { type: 'bot', content: '您好！我是智能客服，有什么可以帮助您的吗？' }
  ]);
  const [sessionId, setSessionId] = useState(Date.now().toString());
  const [loading, setLoading] = useState(false);

  const handleSend = async (message) => {
    // 添加用户消息
    setMessages(prev => [...prev, { type: 'user', content: message }]);
    setLoading(true);

    try {
      // 调用 API
      const response = await sendMessage(message, sessionId);
      
      // 添加 AI 回复（打字机效果）
      if (response.reply) {
        await typeWriterEffect(response.reply);
      }
    } catch (error) {
      console.error('发送消息失败:', error);
      await typeWriterEffect('抱歉，服务暂时不可用，请稍后再试。');
    } finally {
      setLoading(false);
    }
  };

  // 打字机效果函数
  const typeWriterEffect = async (fullText) => {
    const messageId = Date.now();
    
    // 添加空消息
    setMessages(prev => [...prev, { 
      type: 'bot', 
      content: '', 
      id: messageId,
      isTyping: true 
    }]);

    // 逐字添加
    for (let i = 0; i < fullText.length; i++) {
      await new Promise(resolve => setTimeout(resolve, 30));
      setMessages(prev => prev.map(msg => 
        msg.id === messageId 
          ? { ...msg, content: fullText.substring(0, i + 1) }
          : msg
      ));
    }

    // 完成打字
    setMessages(prev => prev.map(msg => 
      msg.id === messageId 
        ? { ...msg, isTyping: false }
        : msg
    ));
  };

  return (
    <div className="app">
      <Header />
      <ChatArea messages={messages} loading={loading} />
      <InputArea onSend={handleSend} loading={loading} />
    </div>
  );
}

export default App;