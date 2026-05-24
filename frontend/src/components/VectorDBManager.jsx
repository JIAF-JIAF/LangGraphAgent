import { useEffect } from 'react';
import './VectorDBManager.css';
import useVectorDbManagerStore from '../stores/vectorDbManagerStore';
import {
  MessageToast,
  Sidebar,
  UploadSection,
  DocumentsSection,
  WelcomeSection,
  CreateDatabaseModal
} from './vectorDbManagerComponents';

/**
 * 向量数据库管理器组件
 * @description 主组件，整合所有子组件，管理知识库的创建、文档上传和向量化
 * @returns {React.ReactElement}
 */
export const VectorDBManager = () => {
  const { message, messageType, selectedDb, loadDatabases } = useVectorDbManagerStore();

  useEffect(() => {
    loadDatabases();
  }, [loadDatabases]);

  return (
    <div className="vector-db-manager">
      <MessageToast message={message} type={messageType} />

      <div className="main-content">
        <Sidebar />

        <div className="content">
          {selectedDb ? (
            <>
              <UploadSection />
              <DocumentsSection />
            </>
          ) : (
            <WelcomeSection />
          )}
        </div>
      </div>

      <CreateDatabaseModal />
    </div>
  );
};
