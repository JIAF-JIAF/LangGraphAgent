import axios from 'axios';

/**
 * Skill 配置 API 客户端
 * 提供 Skill 的安装、卸载和列表查询操作
 */
class SkillConfigApi {
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
   * 获取所有已安装的 Skill 列表
   * @returns {Promise<Object>} Skill 列表
   */
  async getSkills() {
    try {
      const response = await this.client.get('/skills/');
      return response.data;
    } catch (error) {
      console.error('获取 Skill 列表失败:', error);
      throw error;
    }
  }

  /**
   * 获取单个 Skill 详情
   * @param {string} skillName - Skill 名称
   * @returns {Promise<Object>} Skill 详情
   */
  async getSkill(skillName) {
    try {
      const response = await this.client.get(`/skills/${skillName}`);
      return response.data;
    } catch (error) {
      console.error(`获取 Skill ${skillName} 失败:`, error);
      throw error;
    }
  }

  /**
   * 从 GitHub URL 安装 Skill
   * @param {string} url - GitHub 仓库 URL
   * @returns {Promise<Object>} 安装结果
   */
  async installFromUrl(url) {
    try {
      const response = await this.client.post('/skills/install', { url });
      return response.data;
    } catch (error) {
      console.error('安装 Skill 失败:', error);
      throw error;
    }
  }

  /**
   * 卸载 Skill
   * @param {string} skillName - Skill 名称
   * @returns {Promise<Object>} 卸载结果
   */
  async uninstall(skillName) {
    try {
      const response = await this.client.delete(`/skills/${skillName}`);
      return response.data;
    } catch (error) {
      console.error(`卸载 Skill ${skillName} 失败:`, error);
      throw error;
    }
  }

  /**
   * 重新加载所有 Skill
   * @returns {Promise<Object>} 重新加载结果
   */
  async reloadSkills() {
    try {
      const response = await this.client.post('/skills/reload');
      return response.data;
    } catch (error) {
      console.error('重新加载 Skill 失败:', error);
      throw error;
    }
  }
}

const skillConfigApi = new SkillConfigApi();
export default skillConfigApi;
