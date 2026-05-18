import axios from 'axios';

/**
 * MCP 服务器配置 API 客户端
 * 提供 MCP 服务器的增删改查操作
 */
class MCPConfigApi {
  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || '/api';
    this.client = axios.create({
      baseURL: this.baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * 获取所有 MCP 服务器
   * @returns {Promise<Object>} 服务器列表
   */
  async getServers() {
    try {
      const response = await this.client.get('/mcp/servers');
      return response.data;
    } catch (error) {
      console.error('获取 MCP 服务器列表失败:', error);
      throw error;
    }
  }

  /**
   * 获取单个服务器
   * @param {number} serverId - 服务器 ID
   * @returns {Promise<Object>} 服务器信息
   */
  async getServer(serverId) {
    try {
      const response = await this.client.get(`/mcp/servers/${serverId}`);
      return response.data;
    } catch (error) {
      console.error(`获取服务器 ${serverId} 失败:', error`);
      throw error;
    }
  }

  /**
   * 添加新服务器
   * @param {Object} serverData - 服务器数据
   * @param {string} serverData.name - 服务器名称
   * @param {string} serverData.url - 服务器地址
   * @param {string} [serverData.protocol='StreamableHTTP'] - 协议类型
   * @param {string} [serverData.description=''] - 服务器描述
   * @returns {Promise<Object>} 创建的服务器信息
   */
  async addServer(serverData) {
    try {
      const response = await this.client.post('/mcp/servers', serverData);
      return response.data;
    } catch (error) {
      console.error('添加 MCP 服务器失败:', error);
      throw error;
    }
  }

  /**
   * 更新服务器
   * @param {number} serverId - 服务器 ID
   * @param {Object} updates - 更新的数据
   * @returns {Promise<Object>} 更新后的服务器信息
   */
  async updateServer(serverId, updates) {
    try {
      const response = await this.client.put(`/mcp/servers/${serverId}`, updates);
      return response.data;
    } catch (error) {
      console.error(`更新服务器 ${serverId} 失败:', error`);
      throw error;
    }
  }

  /**
   * 删除服务器
   * @param {number} serverId - 服务器 ID
   * @returns {Promise<Object>} 删除结果
   */
  async deleteServer(serverId) {
    try {
      const response = await this.client.delete(`/mcp/servers/${serverId}`);
      return response.data;
    } catch (error) {
      console.error(`删除服务器 ${serverId} 失败:', error`);
      throw error;
    }
  }

  /**
   * 测试服务器连接
   * @param {number} serverId - 服务器 ID
   * @returns {Promise<Object>} 连接测试结果
   */
  async testConnection(serverId) {
    try {
      const response = await this.client.post(`/mcp/servers/${serverId}/test`);
      return response.data;
    } catch (error) {
      console.error(`测试服务器 ${serverId} 连接失败:', error`);
      throw error;
    }
  }

  /**
   * 获取默认服务器
   * @returns {Promise<Object>} 默认服务器信息
   */
  async getDefaultServer() {
    try {
      const response = await this.client.get('/mcp/servers/default');
      return response.data;
    } catch (error) {
      console.error('获取默认服务器失败:', error);
      throw error;
    }
  }
}

// 创建单例实例
const mcpConfigApi = new MCPConfigApi();

export default mcpConfigApi;
