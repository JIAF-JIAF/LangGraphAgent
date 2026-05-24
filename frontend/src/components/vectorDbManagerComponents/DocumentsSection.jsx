import useVectorDbManagerStore from '../../stores/vectorDbManagerStore';

/**
 * 文档项组件
 * @description 显示单个文档的信息
 * @param {Object} props
 * @param {Object} props.document - 文档对象
 * @param {Function} props.onDelete - 删除回调
 * @returns {React.ReactElement}
 */
export const DocumentItem = ({ document, onDelete }) => {
  return (
    <div className="document-item">
      <span className="doc-icon">📄</span>
      <span className="doc-name">{document.filename}</span>
      <span className="doc-meta">
        {document.chunk_count} 个分块 · {document.vector_count} 个向量
      </span>
      <button className="doc-delete" onClick={() => onDelete(document.filename)}>
        ✕
      </button>
    </div>
  );
};

/**
 * 文档列表组件
 * @description 显示已上传的文档列表
 * @returns {React.ReactElement}
 */
export const DocumentsSection = () => {
  const { documents, deleteDocument } = useVectorDbManagerStore();

  /**
   * 处理删除文档
   * @param {string} docName - 文档名称
   */
  const handleDeleteDocument = async (docName) => {
    if (!window.confirm(`确定要删除文档 "${docName}" 吗？`)) {
      return;
    }
    await deleteDocument(docName);
  };

  return (
    <div className="documents-section">
      <h3>已上传文档</h3>
      {documents.length === 0 ? (
        <div className="empty-documents">
          <span className="empty-icon">📄</span>
          <p>暂无文档</p>
          <p className="empty-hint">上传文件开始构建知识库</p>
        </div>
      ) : (
        <div className="documents-list">
          {documents.map((doc) => (
            <DocumentItem
              key={doc.filename}
              document={doc}
              onDelete={handleDeleteDocument}
            />
          ))}
        </div>
      )}
    </div>
  );
};
