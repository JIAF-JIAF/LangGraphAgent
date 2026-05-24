import { useState, useCallback } from 'react';
import { ALLOWED_EXTENSIONS } from '../constants/fileExtensions';

/**
 * 自定义 Hook - 文件上传
 * @description 处理文件上传逻辑，包含文件验证、上传进度、错误处理
 * @param {Function} onUpload - 实际上传函数，接收 File[] 数组
 * @param {Object} [options] - 配置选项
 * @param {string[]} [options.allowedExtensions] - 允许的文件扩展名
 * @param {number} [options.maxSize=50*1024*1024] - 单个文件最大字节数
 * @returns {Object} 上传状态和方法
 * @returns {boolean} return.uploading - 是否正在上传
 * @returns {number} return.progress - 上传进度 (0-100)
 * @returns {string} return.error - 错误信息
 * @returns {Function} return.upload - 触发上传的方法
 * @returns {Function} return.clearError - 清除错误信息
 *
 * @example
 * ```jsx
 * const { uploading, progress, error, upload } = useFileUpload(async (files) => {
 *   const formData = new FormData();
 *   files.forEach(f => formData.append('files', f));
 *   return await fetch('/api/upload', { method: 'POST', body: formData });
 * });
 *
 * <input type="file" onChange={(e) => upload(e.target.files)} />
 * ```
 */
const useFileUpload = (onUpload, options = {}) => {
  const {
    allowedExtensions = ALLOWED_EXTENSIONS,
    maxSize = 50 * 1024 * 1024
  } = options;

  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');

  const validateFiles = useCallback((files) => {
    const validFiles = Array.from(files).filter((file) => {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!allowedExtensions.includes(ext)) {
        setError(`不支持的文件格式: ${file.name}`);
        return false;
      }
      if (file.size > maxSize) {
        setError(`文件过大: ${file.name} (最大 ${maxSize / 1024 / 1024}MB)`);
        return false;
      }
      return true;
    });
    return validFiles;
  }, [allowedExtensions, maxSize]);

  const upload = useCallback(async (files) => {
    const validFiles = validateFiles(files);
    if (validFiles.length === 0) {
      return { success: false, error: '没有有效的文件' };
    }

    setUploading(true);
    setProgress(0);
    setError('');

    try {
      const progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 50) {
            clearInterval(progressInterval);
            return 50;
          }
          return prev + 10;
        });
      }, 200);

      const result = await onUpload(validFiles);

      clearInterval(progressInterval);
      setProgress(100);

      return result;
    } catch (err) {
      setError(err.message || '上传失败');
      return { success: false, error: err.message };
    } finally {
      setUploading(false);
      setTimeout(() => setProgress(0), 500);
    }
  }, [validateFiles, onUpload]);

  const clearError = useCallback(() => {
    setError('');
  }, []);

  return {
    uploading,
    progress,
    error,
    upload,
    clearError,
    validateFiles
  };
};

export default useFileUpload;