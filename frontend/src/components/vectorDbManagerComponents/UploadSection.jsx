import { useCallback } from 'react';
import useVectorDbManagerStore from '../../stores/vectorDbManagerStore';
import { ALLOWED_EXTENSIONS, ACCEPT_STRING } from '../../constants/fileExtensions';

/**
 * 上传区域组件
 * @description 文件拖拽上传区域
 * @returns {React.ReactElement}
 */
export const UploadSection = () => {
  const {
    selectedDb,
    uploading,
    uploadProgress,
    uploadFiles
  } = useVectorDbManagerStore();

  /**
   * 处理文件拖拽放置
   * @param {DragEvent} e - 拖拽事件
   */
  const handleFileDrop = useCallback((e) => {
    e.preventDefault();
    uploadFiles(e.dataTransfer.files);
  }, [uploadFiles]);

  /**
   * 处理文件选择
   * @param {Event} e - 文件选择事件
   */
  const handleFileSelect = useCallback((e) => {
    uploadFiles(e.target.files);
  }, [uploadFiles]);

  /**
   * 处理拖拽悬停
   * @param {DragEvent} e - 拖拽事件
   */
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
  }, []);

  /**
   * 触发文件选择
   */
  const triggerFileSelect = useCallback(() => {
    document.querySelector('.hidden-file-input')?.click();
  }, []);

  return (
    <div className="upload-section">
      <div className="section-header">
        <h2>上传文件</h2>
        <span className="selected-db-badge">当前数据库: {selectedDb?.name}</span>
      </div>
      <div
        className="upload-area"
        onDrop={handleFileDrop}
        onDragOver={handleDragOver}
      >
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
              <div
                className="progress-fill"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <span className="progress-text">{uploadProgress}%</span>
          </div>
        ) : (
          <>
            <div className="upload-icon">📄</div>
            <p>
              拖拽文件到此处，或{' '}
              <span className="click-link" onClick={triggerFileSelect}>
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
  );
};
