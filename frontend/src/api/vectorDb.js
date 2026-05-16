import axios from 'axios';

const BASE_URL = 'http://localhost:5001/api';

const vectorDbApi = {
  // 获取所有数据库列表
  getDatabases: async () => {
    const response = await axios.get(`${BASE_URL}/databases`);
    return response.data;
  },

  // 获取单个数据库详情
  getDatabase: async (dbName) => {
    const response = await axios.get(`${BASE_URL}/databases/${dbName}`);
    return response.data;
  },

  // 创建新数据库
  createDatabase: async (name, description) => {
    const response = await axios.post(`${BASE_URL}/databases`, {
      name,
      description
    });
    return response.data;
  },

  // 更新数据库信息
  updateDatabase: async (dbName, description) => {
    const response = await axios.put(`${BASE_URL}/databases/${dbName}`, {
      description
    });
    return response.data;
  },

  // 删除数据库
  deleteDatabase: async (dbName) => {
    const response = await axios.delete(`${BASE_URL}/databases/${dbName}`);
    return response.data;
  },

  // 上传文件到数据库
  uploadFiles: async (dbName, files) => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    
    const response = await axios.post(
      `${BASE_URL}/databases/${dbName}/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    );
    return response.data;
  },

  // 获取数据库中的文档列表
  getDocuments: async (dbName) => {
    const response = await axios.get(`${BASE_URL}/databases/${dbName}/documents`);
    return response.data;
  },

  // 删除文档
  deleteDocument: async (dbName, docName) => {
    const response = await axios.delete(`${BASE_URL}/databases/${dbName}/documents/${docName}`);
    return response.data;
  }
};

export default vectorDbApi;