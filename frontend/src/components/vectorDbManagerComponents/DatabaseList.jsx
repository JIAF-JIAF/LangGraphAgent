/**
 * 数据库项组件
 * @description 显示单个数据库的信息
 * @param {Object} props
 * @param {Object} props.database - 数据库对象
 * @param {boolean} props.isSelected - 是否选中
 * @param {Function} props.onSelect - 选择回调
 * @param {Function} props.onDelete - 删除回调
 * @returns {React.ReactElement}
 */
export const DatabaseItem = ({ database, isSelected, onSelect, onDelete }) => {
  return (
    <div
      className={`db-item ${isSelected ? 'selected' : ''}`}
      onClick={() => onSelect(database)}
    >
      <div className="db-info">
        <div className="db-name">{database.name}</div>
        <div className="db-description">{database.description || '暂无描述'}</div>
        <div className="db-meta">
          <span>{database.document_count} 文档</span>
          <span>·</span>
          <span>{database.vector_count} 向量</span>
        </div>
      </div>
      <button
        className="btn-delete"
        onClick={(e) => {
          e.stopPropagation();
          onDelete(database.name);
        }}
      >
        ✕
      </button>
    </div>
  );
};

/**
 * 数据库列表组件
 * @description 显示数据库列表，包含加载状态和空状态
 * @param {Object} props
 * @param {Array} props.databases - 数据库列表
 * @param {Object|null} props.selectedDb - 当前选中的数据库
 * @param {boolean} props.loading - 加载状态
 * @param {Function} props.onSelect - 选择数据库回调
 * @param {Function} props.onDelete - 删除数据库回调
 * @returns {React.ReactElement}
 */
export const DatabaseList = ({ databases, selectedDb, loading, onSelect, onDelete }) => {
  if (loading) {
    return (
      <div className="empty-state">
        <div className="loading-state">
          <div className="spinner"></div>
          <span className="progress-text">加载中...</span>
        </div>
      </div>
    );
  }

  if (databases.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-icon">📚</span>
        <p>暂无知识库</p>
        <p className="empty-hint">点击上方按钮创建新知识库</p>
      </div>
    );
  }

  return (
    <>
      {databases.map((db) => (
        <DatabaseItem
          key={db.name}
          database={db}
          isSelected={selectedDb?.name === db.name}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      ))}
    </>
  );
};
