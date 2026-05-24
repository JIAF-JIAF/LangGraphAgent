import { create } from 'zustand';
import vectorDbApi from '../api/vectorDb';
import { ALLOWED_EXTENSIONS } from '../constants/fileExtensions';

/**
 * @typedef {Object} Database
 * @property {string} name - 数据库名称
 * @property {number} document_count - 文档数量
 * @property {number} vector_count - 向量数量
 * @property {string} [description] - 数据库描述
 */

/**
 * @typedef {Object} Document
 * @property {string} filename - 文件名
 * @property {number} chunk_count - 分块数量
 * @property {number} vector_count - 向量数量
 */

/**
 * @typedef {'success'|'error'|'warning'} MessageType
 */

/**
 * 向量数据库管理器状态 Store
 * @description 管理数据库列表、文档、上传、消息等状态
 */
const useVectorDbManagerStore = create((set, get) => ({
  /**
   * 数据库列表
   * @type {Database[]}
   */
  databases: [],

  /**
   * 当前选中的数据库
   * @type {Database|null}
   */
  selectedDb: null,

  /**
   * 当前数据库的文档列表
   * @type {Document[]}
   */
  documents: [],

  /**
   * 加载状态
   * @type {boolean}
   */
  loading: false,

  /**
   * 上传状态
   * @type {boolean}
   */
  uploading: false,

  /**
   * 上传进度 (0-100)
   * @type {number}
   */
  uploadProgress: 0,

  /**
   * 提示消息
   * @type {string}
   */
  message: '',

  /**
   * 消息类型
   * @type {MessageType}
   */
  messageType: 'success',

  /**
   * 创建模态框显示状态
   * @type {boolean}
   */
  showCreateModal: false,

  /**
   * 新数据库名称
   * @type {string}
   */
  newDbName: '',

  /**
   * 新数据库描述
   * @type {string}
   */
  newDbDescription: '',

  /**
   * 显示提示消息
   * @param {string} msg - 消息内容
   * @param {MessageType} [type='success'] - 消息类型
   */
  showMessage: (msg, type = 'success') => {
    set({ message: msg, messageType: type });
    setTimeout(() => set({ message: '' }), 3000);
  },

  /**
   * 清除消息
   */
  clearMessage: () => {
    set({ message: '' });
  },

  /**
   * 加载数据库列表
   * @returns {Promise<void>}
   */
  loadDatabases: async () => {
    set({ loading: true });
    try {
      const response = await vectorDbApi.getDatabases();
      if (response.status === 'success') {
        const databases = response.data;
        set({ databases });
        const { selectedDb } = get();
        if (!selectedDb && databases.length > 0) {
          set({ selectedDb: databases[0] });
        }
      } else {
        get().showMessage('加载数据库列表失败', 'error');
      }
    } catch (error) {
      console.error('加载数据库失败:', error);
      get().showMessage('加载数据库列表失败', 'error');
    } finally {
      set({ loading: false });
    }
  },

  /**
   * 加载指定数据库的文档列表
   * @param {string} dbName - 数据库名称
   * @returns {Promise<void>}
   */
  loadDocuments: async (dbName) => {
    try {
      const response = await vectorDbApi.getDocuments(dbName);
      if (response.status === 'success') {
        set({ documents: response.data });
      } else {
        set({ documents: [] });
      }
    } catch (error) {
      console.error('加载文档列表失败:', error);
      set({ documents: [] });
    }
  },

  /**
   * 选择数据库
   * @param {Database|null} db - 数据库对象
   */
  selectDatabase: (db) => {
    set({ selectedDb: db });
    if (db) {
      get().loadDocuments(db.name);
    } else {
      set({ documents: [] });
    }
  },

  /**
   * 验证文件扩展名
   * @param {File} file - 文件对象
   * @returns {boolean} 是否有效
   */
  isValidFile: (file) => {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    return ALLOWED_EXTENSIONS.includes(ext);
  },

  /**
   * 过滤有效文件
   * @param {FileList|File[]} files - 文件列表
   * @returns {File[]} 有效文件数组
   */
  filterValidFiles: (files) => {
    return Array.from(files).filter(file => get().isValidFile(file));
  },

  /**
   * 上传文件
   * @param {FileList|File[]} files - 文件列表
   * @returns {Promise<boolean>} 是否上传成功
   */
  uploadFiles: async (files) => {
    const { selectedDb, showMessage, loadDatabases, loadDocuments } = get();
    if (!selectedDb) {
      showMessage('请先选择一个数据库', 'warning');
      return false;
    }

    const validFiles = get().filterValidFiles(files);
    if (validFiles.length === 0) {
      showMessage('没有有效的文件，请上传 TXT、PDF、MD、CSV、DOCX、XLSX 或 XLS 文件', 'error');
      return false;
    }

    set({ uploading: true, uploadProgress: 0 });

    try {
      const progressInterval = setInterval(() => {
        set((state) => {
          if (state.uploadProgress >= 50) {
            clearInterval(progressInterval);
            return { uploadProgress: 50 };
          }
          return { uploadProgress: state.uploadProgress + 10 };
        });
      }, 200);

      const response = await vectorDbApi.uploadFiles(selectedDb.name, validFiles);
      clearInterval(progressInterval);
      set({ uploadProgress: 100 });

      if (response.status === 'success') {
        showMessage(response.message, 'success');
        await loadDatabases();
        await loadDocuments(selectedDb.name);
        set((state) => ({
          selectedDb: {
            ...state.selectedDb,
            document_count: state.selectedDb.document_count + validFiles.length,
            vector_count: response.data.vector_count
          }
        }));
        return true;
      } else {
        showMessage(response.message, 'error');
        return false;
      }
    } catch (error) {
      console.error('上传文件失败:', error);
      showMessage('上传文件失败', 'error');
      return false;
    } finally {
      set({ uploading: false, uploadProgress: 0 });
    }
  },

  /**
   * 删除文档
   * @param {string} docName - 文档名称
   * @returns {Promise<boolean>} 是否删除成功
   */
  deleteDocument: async (docName) => {
    const { selectedDb, loadDocuments, showMessage } = get();
    if (!selectedDb) return false;

    try {
      const response = await vectorDbApi.deleteDocument(selectedDb.name, docName);
      if (response.status === 'success') {
        showMessage(response.message, 'success');
        await loadDocuments(selectedDb.name);
        set((state) => ({
          selectedDb: {
            ...state.selectedDb,
            document_count: Math.max(0, state.selectedDb.document_count - 1),
            vector_count: response.data.vector_count
          }
        }));
        return true;
      } else {
        showMessage(response.message, 'error');
        return false;
      }
    } catch (error) {
      showMessage('删除文档失败', 'error');
      return false;
    }
  },

  /**
   * 打开创建数据库模态框
   */
  openCreateModal: () => {
    set({ showCreateModal: true });
  },

  /**
   * 关闭创建数据库模态框
   */
  closeCreateModal: () => {
    set({ showCreateModal: false, newDbName: '', newDbDescription: '' });
  },

  /**
   * 设置新数据库名称
   * @param {string} name - 数据库名称
   */
  setNewDbName: (name) => {
    set({ newDbName: name });
  },

  /**
   * 设置新数据库描述
   * @param {string} description - 数据库描述
   */
  setNewDbDescription: (description) => {
    set({ newDbDescription: description });
  },

  /**
   * 验证数据库名称格式
   * @param {string} name - 数据库名称
   * @returns {boolean} 是否有效
   */
  validateDbName: (name) => {
    const nameRegex = /^[a-zA-Z0-9][a-zA-Z0-9-_.]{2,511}$/;
    return nameRegex.test(name.trim());
  },

  /**
   * 创建数据库
   * @returns {Promise<boolean>} 是否创建成功
   */
  createDatabase: async () => {
    const { newDbName, newDbDescription, showMessage, loadDatabases, closeCreateModal, validateDbName } = get();

    if (!newDbName.trim()) {
      showMessage('请输入数据库名称', 'warning');
      return false;
    }

    if (!validateDbName(newDbName)) {
      showMessage('数据库名称格式不正确，请使用英文、数字、下划线或连字符，长度3-512', 'warning');
      return false;
    }

    try {
      const response = await vectorDbApi.createDatabase(newDbName.trim(), newDbDescription.trim());
      if (response.status === 'success') {
        showMessage(response.message, 'success');
        await loadDatabases();
        closeCreateModal();
        return true;
      } else {
        showMessage(response.message, 'error');
        return false;
      }
    } catch (error) {
      console.error('创建数据库失败:', error);
      showMessage('创建数据库失败', 'error');
      return false;
    }
  },

  /**
   * 删除数据库
   * @param {string} dbName - 数据库名称
   * @returns {Promise<boolean>} 是否删除成功
   */
  deleteDatabase: async (dbName) => {
    const { showMessage, loadDatabases, selectedDb } = get();

    try {
      const response = await vectorDbApi.deleteDatabase(dbName);
      if (response.status === 'success') {
        showMessage(response.message, 'success');
        await loadDatabases();
        if (selectedDb?.name === dbName) {
          set({ selectedDb: null, documents: [] });
        }
        return true;
      } else {
        showMessage(response.message, 'error');
        return false;
      }
    } catch (error) {
      console.error('删除数据库失败:', error);
      showMessage('删除数据库失败', 'error');
      return false;
    }
  }
}));

export default useVectorDbManagerStore;
