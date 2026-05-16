import { useState, useEffect } from 'react';
import './VectorDBManager.css';
import vectorDbApi from '../api/vectorDb';

function VectorDBManager() {
  const [databases, setDatabases] = useState([]);
  const [selectedDb, setSelectedDb] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('success');

  const allowedExtensions = ['.txt', '.pdf', '.md', '.csv', '.docx'];

  const showMessage = (msg, type) => {
    setMessage(msg);
    setMessageType(type);
    setTimeout(() => setMessage(''), 3000);
  };

  const loadDatabases = async () => {
    try {
      const response = await vectorDbApi.getDatabases();
      if (response.status === 'success') {
        setDatabases(response.data);
        if (!selectedDb && response.data.length > 0) {
          setSelectedDb(response.data[0]);
        }
      } else {
        showMessage('加载数据库列表失败', 'error');
      }
    } catch (error) {
      console.error('加载数据库失败:', error);
      showMessage('加载数据库列表失败', 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadDocuments = async (dbName) => {
    try {
      const response = await vectorDbApi.getDocuments(dbName);
      if (response.status === 'success') {
        setDocuments(response.data);
      } else {
        setDocuments([]);
      }
    } catch (error) {
      console.error('加载文档列表失败:', error);
      setDocuments([]);
    }
  };

  useEffect(() => {
    loadDatabases();
  }, []);

  useEffect(() => {
    if (selectedDb) {
      loadDocuments(selectedDb.name);
    } else {
      setDocuments([]);
    }
  }, [selectedDb]);

  const handleSelectDb = (db) => {
    setSelectedDb(db);
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };

  const handleFileSelect = (e) => {
    handleFiles(e.target.files);
  };

  const handleFiles = async (files) => {
    if (!selectedDb) {
      showMessage('请先选择一个数据库', 'warning');
      return;
    }
    const validFiles = Array.from(files).filter(file => {
      const ext = file.name.split('.').pop().toLowerCase();
      return allowedExtensions.includes(`.${ext}`);
    });
    if (validFiles.length === 0) {
      showMessage('没有有效的文件，请上传 TXT、PDF、MD、CSV 或 DOCX 文件', 'error');
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    try {
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 50) {
            clearInterval(progressInterval);
            return 50;
          }
          return prev + 10;
        });
      }, 200);
      const response = await vectorDbApi.uploadFiles(selectedDb.name, validFiles);
      clearInterval(progressInterval);
      setUploadProgress(100);
      if (response.status === 'success') {
        showMessage(response.message, 'success');
        loadDatabases();
        loadDocuments(selectedDb.name);
        setSelectedDb(prev => ({
          ...prev,
          document_count: prev.document_count + validFiles.length,
          vector_count: response.data.vector_count
        }));
      } else {
        showMessage(response.message, 'error');
      }
    } catch (error) {
      console.error('上传文件失败:', error);
      showMessage('上传文件失败', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (docName) => {
    if (!window.confirm(`确定要删除文档 "${docName}" 吗？`)) {
      return;
    }
    try {
      const response = await vectorDbApi.deleteDocument(selectedDb.name, docName);
      if (response.status === 'success') {
        showMessage(response.message, 'success');
        loadDocuments(selectedDb.name);
        setSelectedDb(prev => ({
          ...prev,
          document_count: prev.document_count - 1,
          vector_count: response.data.vector_count
        }));
      } else {
        showMessage(response.message, 'error');
      }
    } catch (error) {
      console.error('删除文档失败:', error);
      showMessage('删除文档失败', 'error');
    }
  };

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newDbName, setNewDbName] = useState('');
  const [newDbDescription, setNewDbDescription] = useState('');

  const handleCreateDb = async () => {
    if (!newDbName.trim()) {
      showMessage('请输入数据库名称', 'warning');
      return;
    }
    // 验证数据库名称格式：只允许英文、数字、下划线、连字符，长度3-512
    const nameRegex = /^[a-zA-Z0-9][a-zA-Z0-9-_.]{2,511}$/;
    if (!nameRegex.test(newDbName.trim())) {
      showMessage('数据库名称格式不正确，请使用英文、数字、下划线或连字符，长度3-512', 'warning');
      return;
    }
    try {
      const response = await vectorDbApi.createDatabase(newDbName.trim(), newDbDescription.trim());
      if (response.status === 'success') {
        showMessage(response.message, 'success');
        loadDatabases();
        setShowCreateModal(false);
        setNewDbName('');
        setNewDbDescription('');
      } else {
        showMessage(response.message, 'error');
      }
    } catch (error) {
      console.error('创建数据库失败:', error);
      showMessage('创建数据库失败', 'error');
    }
  };

  const handleDeleteDb = async (dbName) => {
    if (!window.confirm(`确定要删除数据库 "${dbName}" 及其所有内容吗？`)) {
      return;
    }
    try {
      const response = await vectorDbApi.deleteDatabase(dbName);
      if (response.status === 'success') {
        showMessage(response.message, 'success');
        loadDatabases();
        if (selectedDb && selectedDb.name === dbName) {
          setSelectedDb(null);
          setDocuments([]);
        }
      } else {
        showMessage(response.message, 'error');
      }
    } catch (error) {
      console.error('删除数据库失败:', error);
      showMessage('删除数据库失败', 'error');
    }
  };

  return (
    <div className="vector-db-manager">
      {message && (
        <div className={`message message-${messageType}`}>
          {message}
        </div>
      )}

      <div className="main-content">
        <div className="sidebar">
          <div className="sidebar-header">
            <h2>知识库列表</h2>
            <button className="btn btn-primary btn-new-db" onClick={() => setShowCreateModal(true)}>
              + 新建知识库
            </button>
          </div>
          <div className="db-list">
            {loading ? (
              <div className="empty-state">
                <div className="loading-state">
                  <div className="spinner"></div>
                  <span className="progress-text">加载中...</span>
                </div>
              </div>
            ) : databases.length === 0 ? (
              <div className="empty-state">
                <span className="empty-icon">📚</span>
                <p>暂无知识库</p>
                <p className="empty-hint">点击上方按钮创建新知识库</p>
              </div>
            ) : (
              databases.map(db => (
                <div
                  key={db.name}
                  className={`db-item ${selectedDb?.name === db.name ? 'selected' : ''}`}
                  onClick={() => handleSelectDb(db)}
                >
                  <div className="db-info">
                    <div className="db-name">{db.name}</div>
                    <div className="db-description">{db.description || '暂无描述'}</div>
                    <div className="db-meta">
                      <span>{db.document_count} 文档</span>
                      <span>·</span>
                      <span>{db.vector_count} 向量</span>
                    </div>
                  </div>
                  <button className="btn-delete" onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteDb(db.name);
                  }}>✕</button>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="content">
          {selectedDb ? (
            <>
              <div className="upload-section">
                <div className="section-header">
                  <h2>上传文件</h2>
                  <span className="selected-db-badge">当前数据库: {selectedDb.name}</span>
                </div>
                <div className="upload-area" onDrop={handleFileDrop} onDragOver={(e) => e.preventDefault()}>
                  <input
                    type="file"
                    multiple
                    accept=".txt,.pdf,.md,.csv,.docx"
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
                      <span className="progress-text">{uploadProgress}%</span>
                    </div>
                  ) : (
                    <>
                      <div className="upload-icon">📄</div>
                      <p>拖拽文件到此处，或 <span className="click-link" onClick={() => document.querySelector('.hidden-file-input')?.click()}>点击选择</span></p>
                      <p className="upload-hint">支持多文件上传</p>
                      <div className="supported-formats">
                        {allowedExtensions.map(ext => (
                          <span key={ext} className="format-tag">{ext.toUpperCase().slice(1)}</span>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>

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
                    {documents.map(doc => (
                      <div key={doc.filename} className="document-item">
                        <span className="doc-icon">📄</span>
                        <span className="doc-name">{doc.filename}</span>
                        <span className="doc-meta">{doc.chunk_count} 个分块 · {doc.vector_count} 个向量</span>
                        <button className="doc-delete" onClick={() => handleDeleteDocument(doc.filename)}>✕</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="welcome-section">
              <span className="welcome-icon">📚</span>
              <h2>欢迎使用向量数据库管理器</h2>
              <p>从左侧选择一个知识库开始管理，或创建一个新的知识库来上传和管理您的文档。</p>
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
          )}
        </div>
      </div>

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>新建知识库</h3>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
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
                <p className="form-hint">名称只能包含英文、数字、下划线(_)和连字符(-)，长度3-512个字符</p>
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
              <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>取消</button>
              <button className="btn btn-primary" onClick={handleCreateDb}>创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default VectorDBManager;
