import { useState, useEffect } from 'react';
import './AgentConfig.css';
import vectorDbApi from '../api/vectorDb';
import mcpConfigApi from '../api/mcpConfig';
import skillConfigApi from '../api/skillConfig';

function AgentConfig() {
  const [activeTab, setActiveTab] = useState('database');
  const [databases, setDatabases] = useState([]);
  const [selectedDb, setSelectedDb] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('success');

  // MCP 配置状态
  const [mcpServers, setMcpServers] = useState([]);
  const [newMcpName, setNewMcpName] = useState('');
  const [newMcpUrl, setNewMcpUrl] = useState('');
  const [newMcpDescription, setNewMcpDescription] = useState('');
  const [mcpProtocol, setMcpProtocol] = useState('StreamableHTTP');
  const [mcpLoading, setMcpLoading] = useState(false);

  // Skill 配置状态
  const [skills, setSkills] = useState([]);
  const [skillUrl, setSkillUrl] = useState('');
  const [skillInstalling, setSkillInstalling] = useState(false);

  const allowedExtensions = ['.txt', '.pdf', '.md', '.csv', '.docx'];
  const allowedSkillExtensions = ['.skill.md'];

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
      }
    } catch (error) {
      console.error('加载数据库失败:', error);
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
      setDocuments([]);
    }
  };

  const loadMcpServers = async () => {
    setMcpLoading(true);
    try {
      const response = await mcpConfigApi.getServers();
      if (response.status === 'success') {
        setMcpServers(response.data);
      } else {
        setMcpServers([]);
      }
    } catch (error) {
      console.error('加载 MCP 服务器失败:', error);
      setMcpServers([]);
    } finally {
      setMcpLoading(false);
    }
  };

  useEffect(() => {
    loadDatabases();
    loadMcpServers();
    loadSkills();
  }, []);

  useEffect(() => {
    // 切换标签时重新加载对应配置
    switch (activeTab) {
      case 'database':
        loadDatabases();
        break;
      case 'mcp':
        loadMcpServers();
        break;
      case 'skill':
        loadSkills();
        break;
      default:
        break;
    }
  }, [activeTab]);

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
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      return allowedExtensions.includes(ext);
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
    const nameRegex = /^[a-zA-Z0-9][a-zA-Z0-9-_.]{2,511}$/;
    if (!nameRegex.test(newDbName.trim())) {
      showMessage('数据库名称格式不正确', 'warning');
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
      showMessage('删除数据库失败', 'error');
    }
  };

  // MCP 配置方法
  const handleAddMcpServer = async () => {
    if (!newMcpName.trim()) {
      showMessage('请输入服务器名称', 'warning');
      return;
    }
    if (!newMcpUrl.trim()) {
      showMessage('请输入 MCP Server URL', 'warning');
      return;
    }
    try {
      const response = await mcpConfigApi.addServer({
        name: newMcpName.trim(),
        url: newMcpUrl.trim(),
        protocol: mcpProtocol,
        description: newMcpDescription.trim()
      });
      if (response.status === 'success') {
        setMcpServers([...mcpServers, response.data]);
        setNewMcpName('');
        setNewMcpUrl('');
        setNewMcpDescription('');
        showMessage('MCP Server 添加成功', 'success');
      } else {
        showMessage(response.message || '添加失败', 'error');
      }
    } catch (error) {
      console.error('添加 MCP Server 失败:', error);
      showMessage('添加 MCP Server 失败', 'error');
    }
  };

  const handleDeleteMcpServer = async (id) => {
    if (!window.confirm('确定要删除这个 MCP Server 吗？')) {
      return;
    }
    try {
      const response = await mcpConfigApi.deleteServer(id);
      if (response.status === 'success') {
        setMcpServers(mcpServers.filter(server => server.id !== id));
        showMessage('MCP Server 删除成功', 'success');
      } else {
        showMessage(response.message || '删除失败', 'error');
      }
    } catch (error) {
      console.error('删除 MCP Server 失败:', error);
      showMessage('删除 MCP Server 失败', 'error');
    }
  };

  // Skill 配置方法
  const loadSkills = async () => {
    try {
      const response = await skillConfigApi.getSkills();
      if (response.status === 'success') {
        const formattedSkills = response.data.map(skill => ({
          ...skill,
          updated: skill.updated ? new Date(skill.updated * 1000).toISOString().split('T')[0] : '未知'
        }));
        setSkills(formattedSkills);
      } else {
        setSkills([]);
      }
    } catch (error) {
      console.error('加载 Skill 列表失败:', error);
      setSkills([]);
    }
  };

  const handleInstallSkill = async () => {
    if (!skillUrl.trim()) {
      showMessage('请输入 Skill Git 地址', 'warning');
      return;
    }
    setSkillInstalling(true);
    try {
      const response = await skillConfigApi.installFromUrl(skillUrl.trim());
      if (response.status === 'success') {
        showMessage('Skill 安装成功', 'success');
        setSkillUrl('');
        await loadSkills();
      } else {
        showMessage(response.message || '安装失败', 'error');
      }
    } catch (error) {
      console.error('安装 Skill 失败:', error);
      showMessage('安装 Skill 失败', 'error');
    } finally {
      setSkillInstalling(false);
    }
  };

  const handleDeleteSkill = async (skillName) => {
    if (!window.confirm('确定要删除这个 Skill 吗？')) {
      return;
    }
    try {
      const response = await skillConfigApi.deleteSkill(skillName);
      if (response.status === 'success') {
        setSkills(skills.filter(skill => skill.name !== skillName));
        showMessage('Skill 删除成功', 'success');
      } else {
        showMessage(response.message || '删除失败', 'error');
      }
    } catch (error) {
      console.error('删除 Skill 失败:', error);
      showMessage('删除 Skill 失败', 'error');
    }
  };

  const tabs = [
    { id: 'database', label: '数据库', icon: '📊' },
    { id: 'mcp', label: 'MCP 配置', icon: '🔌' },
    { id: 'skill', label: 'Skill', icon: '⚡' }
  ];

  return (
    <div className="agent-config">
      {message && (
        <div className={`message message-${messageType}`}>
          {message}
        </div>
      )}

      <div className="main-content">
        <div className="sidebar">
          <div className="sidebar-header">
            <div className="logo">
              <span className="logo-icon">🤖</span>
              <span className="logo-text">Agent 配置中心</span>
            </div>
          </div>
          <div className="db-section">
            <h3>数据库列表</h3>
            <button className="btn btn-primary btn-new-db" onClick={() => setShowCreateModal(true)}>
              + 新建数据库
            </button>
            <div className="db-list">
              {loading ? (
                <div className="empty-state">
                  <div className="spinner"></div>
                  <span>加载中...</span>
                </div>
              ) : databases.length === 0 ? (
                <div className="empty-state">
                  <span className="empty-icon">📚</span>
                  <p>暂无数据库</p>
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
        </div>

        <div className="content">
          <div className="content-header">
            <div className="tabs">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  className={`tab ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <span className="tab-icon">{tab.icon}</span>
                  <span className="tab-label">{tab.label}</span>
                </button>
              ))}
            </div>
            <div className="stats-bar">
              <span className="stat-item">数据库: {databases.length}</span>
              <span className="stat-divider">|</span>
              <span className="stat-item">文档总数: {databases.reduce((sum, db) => sum + db.document_count, 0)}</span>
            </div>
          </div>

          <div className="tab-content">
            {/* 数据库标签页 */}
            {activeTab === 'database' && (
              <div className="database-content">
                {selectedDb ? (
                  <>
                    <div className="section-card">
                      <div className="section-header">
                        <h3>上传文件</h3>
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
                            <span>{uploadProgress}%</span>
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
                          {documents.map(doc => (
                            <div key={doc.filename} className="document-item">
                              <span className="doc-icon">📄</span>
                              <div className="doc-info">
                                <span className="doc-name">{doc.filename}</span>
                                <span className="doc-meta">{doc.chunk_count} 个分块 · {doc.vector_count} 个向量</span>
                              </div>
                              <button className="doc-delete" onClick={() => handleDeleteDocument(doc.filename)}>✕</button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="empty-db-selection">
                    <div className="warning-icon">⚠️</div>
                    <p>请先在左侧选择一个数据库</p>
                  </div>
                )}
              </div>
            )}

            {/* MCP 配置标签页 */}
            {activeTab === 'mcp' && (
              <div className="mcp-content">
                <div className="section-card">
                  <div className="section-header">
                    <h3>添加 MCP Server</h3>
                  </div>
                  <div className="mcp-form">
                    <input
                      type="text"
                      value={newMcpName}
                      onChange={(e) => setNewMcpName(e.target.value)}
                      placeholder="服务器名称"
                    />
                    <select value={mcpProtocol} onChange={(e) => setMcpProtocol(e.target.value)}>
                      <option value="StreamableHTTP">Streamable HTTP</option>
                      <option value="HTTP" disabled>HTTP (暂不可用)</option>
                      <option value="WebSocket" disabled>WebSocket (暂不可用)</option>
                    </select>
                    <input
                      type="text"
                      value={newMcpUrl}
                      onChange={(e) => setNewMcpUrl(e.target.value)}
                      placeholder="输入 MCP Server URL"
                    />
                    <input
                      type="text"
                      value={newMcpDescription}
                      onChange={(e) => setNewMcpDescription(e.target.value)}
                      placeholder="描述（可选）"
                    />
                    <button className="btn btn-primary" onClick={handleAddMcpServer}>确认添加</button>
                  </div>
                </div>

                <div className="section-card">
                  <div className="section-header">
                    <h3>MCP 服务器列表</h3>
                  </div>
                  {mcpServers.length === 0 ? (
                    <div className="empty-state">
                      <span className="empty-icon">🔌</span>
                      <p>暂无 MCP 配置</p>
                      <p className="empty-hint">添加服务器即可连接</p>
                    </div>
                  ) : (
                    <div className="mcp-list">
                      {mcpServers.map(server => (
                        <div key={server.id} className="mcp-item">
                          <div className="mcp-info">
                            <div className="mcp-header">
                              <span className="mcp-name">{server.name || '未命名服务器'}</span>
                              <span className={`mcp-status ${server.status}`}>
                                {server.status === 'connected' ? '已连接' : '未连接'}
                              </span>
                            </div>
                            <span className="mcp-url">{server.url}</span>
                            <div className="mcp-meta">
                              <span className="mcp-protocol">{server.protocol}</span>
                              {server.description && (
                                <span className="mcp-description">{server.description}</span>
                              )}
                            </div>
                          </div>
                          <button className="mcp-delete" onClick={() => handleDeleteMcpServer(server.id)}>✕</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Skill 配置标签页 */}
            {activeTab === 'skill' && (
              <div className="skill-content">
                <div className="section-card">
                  <div className="section-header">
                    <h3>安装 Skill</h3>
                  </div>
                  <div className="skill-install-form">
                    <input
                      type="text"
                      value={skillUrl}
                      onChange={(e) => setSkillUrl(e.target.value)}
                      placeholder="输入 Skill Git 地址"
                      disabled={skillInstalling}
                    />
                    <button
                      className="btn btn-primary"
                      onClick={handleInstallSkill}
                      disabled={skillInstalling}
                    >
                      {skillInstalling ? (
                        <>
                          <div className="spinner-small"></div>
                          <span>安装中...</span>
                        </>
                      ) : (
                        '安装'
                      )}
                    </button>
                  </div>
                </div>

                <div className="section-card">
                  <div className="section-header">
                    <h3>Skill 列表</h3>
                  </div>
                  {skills.length === 0 ? (
                    <div className="empty-state">
                      <span className="empty-icon">⚡</span>
                      <p>暂无 Skill</p>
                      <p className="empty-hint">输入 Git 地址安装技能</p>
                    </div>
                  ) : (
                    <div className="skill-list">
                      {skills.map(skill => (
                        <div key={skill.id} className="skill-item">
                          <div className="skill-info">
                            <span className="skill-name">{skill.title}</span>
                            <span className="skill-meta">{skill.file} · 更新于 {skill.updated}</span>
                          </div>
                          <button className="skill-delete" onClick={() => handleDeleteSkill(skill.name)}>✕</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>新建数据库</h3>
              <button className="modal-close" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>数据库名称</label>
                <input
                  type="text"
                  value={newDbName}
                  onChange={(e) => setNewDbName(e.target.value)}
                  placeholder="请输入数据库名称"
                />
                <p className="form-hint">名称只能包含英文、数字、下划线(_)和连字符(-)，长度3-512个字符</p>
              </div>
              <div className="form-group">
                <label>描述（可选）</label>
                <textarea
                  value={newDbDescription}
                  onChange={(e) => setNewDbDescription(e.target.value)}
                  placeholder="请输入数据库描述"
                  rows={3}
                />
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

export default AgentConfig;
