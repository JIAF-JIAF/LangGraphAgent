/**
 * 欢迎页面组件
 * @description 未选择数据库时显示的欢迎引导页面
 * @returns {React.ReactElement}
 */
export const WelcomeSection = () => {
  return (
    <div className="welcome-section">
      <span className="welcome-icon">📚</span>
      <h2>欢迎使用向量数据库管理器</h2>
      <p>
        从左侧选择一个知识库开始管理，或创建一个新的知识库来上传和管理您的文档。
      </p>
      <div className="steps">
        <div className="step">
          <span className="step-number">1</span>
          <span className="step-text">选择知识库</span>
        </div>
        <div className="step">
          <span className="step-number">2</span>
          <span className="step-text">上传文件</span>
        </div>
        <div className="step">
          <span className="step-number">3</span>
          <span className="step-text">自动向量化</span>
        </div>
      </div>
    </div>
  );
};
