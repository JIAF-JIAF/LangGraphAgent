import { memo } from 'react';
import useDatabaseStore from '../../stores/databaseStore';
import useUiStore from '../../stores/uiStore';
import { ALLOWED_EXTENSIONS, ACCEPT_STRING } from '../../constants/fileExtensions';

export const DatabasePanel = memo(() => {
  const {
    selectedDb,
    documents,
    uploading,
    uploadProgress,
    uploadFiles,
    deleteDocument
  } = useDatabaseStore();
  const { openPreviewSidebar } = useUiStore();

  /**
   * 处理文件拖拽放置
   * @param {DragEvent} e - 拖拽事件
   */
  const handleFileDrop = (e) => {
    e.preventDefault();
    uploadFiles(e.dataTransfer.files);
  };

  /**
   * 处理文件选择
   * @param {ChangeEvent} e - 文件选择事件
   */
  const handleFileSelect = (e) => {
    uploadFiles(e.target.files);
  };

  /**
   * 处理删除文档
   * @param {string} docName - 文档名称
   * @returns {Promise<void>}
   */
  const handleDeleteDocument = async (docName) => {
    if (!window.confirm(`确定要删除文档 "${docName}" 吗？`)) {
      return;
    }
    await deleteDocument(docName);
  };

  if (!selectedDb) {
    return (
      <div className="empty-db-selection">
        <div className="warning-icon">⚠️</div>
        <p>请先在左侧选择一个数据库</p>
      </div>
    );
  }

  return (
    <div className="database-content">
      <div className="section-card">
        <div className="section-header">
          <h3>上传文件</h3>
          <span className="selected-db-badge">当前数据库: {selectedDb.name}</span>
        </div>
        <div className="upload-area" onDrop={handleFileDrop} onDragOver={(e) => e.preventDefault()}>
          <input
            type="file"
            multiple
            accept={ACCEPT_STRING}
            onChange={handleFileSelect}
            className="hidden-file-input"
            disabled={uploading}
          />
          {uploading ? (
            <div className="uploading-state">
              <div className="spinner"></div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
              </div>
              <span>{uploadProgress}%</span>
            </div>
          ) : (
            <>
              <div className="upload-icon">📄</div>
              <p>
                拖拽文件到此处，或{' '}
                <span
                  className="click-link"
                  onClick={() => document.querySelector('.hidden-file-input')?.click()}
                >
                  点击选择
                </span>
              </p>
              <p className="upload-hint">支持多文件上传</p>
              <div className="supported-formats">
                {ALLOWED_EXTENSIONS.map((ext) => (
                  <span key={ext} className="format-tag">
                    {ext.toUpperCase().slice(1)}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="section-card">
        <div className="section-header">
          <h3>开始使用</h3>
        </div>
        <div className="start-guide">
          <div className="rocket-icon">🚀</div>
          <p>创建一个向量数据库，然后上传您的文档。系统会自动进行</p>
          <p>分词和向量化处理。</p>
          <div className="steps">
            <div className="step">
              <span className="step-number">1</span>
              <span className="step-text">创建数据库</span>
            </div>
            <div className="step">
              <span className="step-number">2</span>
              <span className="step-text">选择数据库</span>
            </div>
            <div className="step">
              <span className="step-number">3</span>
              <span className="step-text">上传文件</span>
            </div>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-header">
          <h3>文档列表</h3>
        </div>
        {documents.length === 0 ? (
          <div className="empty-documents">
            <span className="empty-icon">📄</span>
            <p>暂无文档</p>
            <p className="empty-hint">上传文件开始构建知识库</p>
          </div>
        ) : (
          <div className="documents-list">
            {documents.map((doc) => (
              <div key={doc.filename} className="document-item">
                <span className="doc-icon">📄</span>
                <div className="doc-info">
                  <span className="doc-name">{doc.filename}</span>
                  <span className="doc-meta">
                    {doc.chunk_count} 个分块 · {doc.vector_count} 个向量
                  </span>
                </div>
                <div className="doc-actions">
                  <button
                    className="btn btn-sm btn-preview"
                    onClick={() => openPreviewSidebar({ filename: doc.filename, fileId: doc.id })}
                  >
                    查看
                  </button>
                  <button
                    className="btn btn-sm btn-delete"
                    onClick={() => handleDeleteDocument(doc.filename)}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
});

DatabasePanel.displayName = 'DatabasePanel';