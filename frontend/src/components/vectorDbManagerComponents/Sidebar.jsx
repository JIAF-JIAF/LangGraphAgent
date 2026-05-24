import useVectorDbManagerStore from '../../stores/vectorDbManagerStore';
import { DatabaseList } from './DatabaseList';

/**
 * 侧边栏组件
 * @description 显示知识库列表和新建按钮
 * @returns {React.ReactElement}
 */
export const Sidebar = () => {
  const {
    databases,
    selectedDb,
    loading,
    selectDatabase,
    deleteDatabase,
    openCreateModal
  } = useVectorDbManagerStore();

  /**
   * 处理删除数据库
   * @param {string} dbName - 数据库名称
   */
  const handleDeleteDatabase = async (dbName) => {
    if (!window.confirm(`确定要删除数据库 "${dbName}" 及其所有内容吗？`)) {
      return;
    }
    await deleteDatabase(dbName);
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>知识库列表</h2>
        <button className="btn btn-primary btn-new-db" onClick={openCreateModal}>
          + 新建知识库
        </button>
      </div>
      <div className="db-list">
        <DatabaseList
          databases={databases}
          selectedDb={selectedDb}
          loading={loading}
          onSelect={selectDatabase}
          onDelete={handleDeleteDatabase}
        />
      </div>
    </div>
  );
};
