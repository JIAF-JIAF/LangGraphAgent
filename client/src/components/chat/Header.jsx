import { memo } from 'react';
import './Header.css';

/**
 * 聊天头部组件
 * @description 显示智能助手标题，提供跳转向量数据库的入口
 *
 * @returns {React.ReactElement}
 */
export const Header = memo((props) => {
  /**
   * 处理跳转向量数据库
   */
  const handleNavigateToVectorDB = () => {
    window.navigateTo('/vector-db');
  };

  return (
    <div className="header">
      <div className="header-left">
        <div className="customer-service-icon">🤖</div>
        <span className="customer-service-name">智能助手</span>
      </div>
      <button className="header-action" onClick={handleNavigateToVectorDB}>
        📊 向量数据库
      </button>
    </div>
  );
});

Header.displayName = 'Header';