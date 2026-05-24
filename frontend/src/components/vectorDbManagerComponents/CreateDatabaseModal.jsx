import useVectorDbManagerStore from '../../stores/vectorDbManagerStore';

/**
 * 创建数据库模态框组件
 * @description 用于创建新的知识库
 * @returns {React.ReactElement|null}
 */
export const CreateDatabaseModal = () => {
  const {
    showCreateModal,
    newDbName,
    newDbDescription,
    closeCreateModal,
    setNewDbName,
    setNewDbDescription,
    createDatabase
  } = useVectorDbManagerStore();

  if (!showCreateModal) return null;

  /**
   * 处理模态框背景点击
   * @param {Event} e - 点击事件
   */
  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      closeCreateModal();
    }
  };

  /**
   * 处理表单提交
   */
  const handleSubmit = async () => {
    await createDatabase();
  };

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>新建知识库</h3>
          <button className="modal-close" onClick={closeCreateModal}>
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="form-group">
            <label>知识库名称</label>
            <input
              type="text"
              value={newDbName}
              onChange={(e) => setNewDbName(e.target.value)}
              placeholder="请输入知识库名称（英文、数字、下划线或连字符）"
            />
            <p className="form-hint">
              名称只能包含英文、数字、下划线(_)和连字符(-)，长度3-512个字符
            </p>
          </div>
          <div className="form-group">
            <label>描述（可选）</label>
            <textarea
              value={newDbDescription}
              onChange={(e) => setNewDbDescription(e.target.value)}
              placeholder="请输入知识库描述"
              rows={3}
            />
            <p className="form-hint">描述将帮助理解知识库的内容和用途</p>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={closeCreateModal}>
            取消
          </button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            创建
          </button>
        </div>
      </div>
    </div>
  );
};
