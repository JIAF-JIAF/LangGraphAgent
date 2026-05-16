import React from 'react';
import './Header.css';

function Header() {
  const handleNavigateToVectorDB = () => {
    window.navigateTo('/vector-db');
  };

  return (
    <div className="header">
      <div className="header-left">
        <div className="customer-service-icon">🤖</div>
        <span className="customer-service-name">智能客服</span>
      </div>
      <button className="header-action" onClick={handleNavigateToVectorDB}>
        📊 向量数据库
      </button>
    </div>
  );
}

export default Header;