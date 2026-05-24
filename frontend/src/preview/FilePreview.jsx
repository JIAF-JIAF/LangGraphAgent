import { useState, useEffect } from 'react';
import useUiStore from '../stores/uiStore';
import useDatabaseStore from '../stores/databaseStore';
import vectorDbApi from '../api/vectorDb';
import { TextPreview, PdfPreview, WordPreview, ExcelPreview } from './previews';
import { convertWordToCangjieFormat } from './utils/wordConverter';

export const FilePreview = () => {
  const { previewFile, closePreviewSidebar } = useUiStore();
  const { selectedDb } = useDatabaseStore();
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);
  const [excelBlob, setExcelBlob] = useState(null);
  const [fileType, setFileType] = useState(null);
  const [wordData, setWordData] = useState(null);

  const getFileExtension = (filename) => {
    return filename.split('.').pop().toLowerCase();
  };

  const getFileType = (extension) => {
    switch (extension) {
      case 'txt':
      case 'md':
      case 'csv':
        return 'text';
      case 'pdf':
        return 'pdf';
      case 'doc':
      case 'docx':
        return 'word';
      case 'xlsx':
      case 'xls':
        return 'excel';
      default:
        return 'unsupported';
    }
  };

  const fetchFileContent = async () => {
    if (!previewFile || !selectedDb) return;

    setLoading(true);
    setError(null);
    setContent('');
    setPdfBlob(null);
    setExcelBlob(null);
    setFileType(null);
    setWordData(null);

    const extension = getFileExtension(previewFile.filename);
    const type = getFileType(extension);
    setFileType(type);

    if (type === 'unsupported') {
      setContent(`不支持预览此文件类型: ${extension}`);
      setLoading(false);
      return;
    }

    try {
      const blob = await vectorDbApi.getDocumentContent(selectedDb.name, previewFile.filename);

      switch (type) {
        case 'text':
          const text = await blob.text();
          setContent(text);
          setLoading(false);
          break;

        case 'pdf':
          setPdfBlob(blob);
          setLoading(false);
          break;

        case 'word':
          const arrayBuffer = await blob.arrayBuffer();
          const jsonML = await convertWordToCangjieFormat(arrayBuffer);
          setWordData(jsonML);
          setLoading(false);
          break;

        case 'excel':
          setExcelBlob(blob);
          setLoading(false);
          break;

        default:
          setContent(`不支持预览此文件类型: ${extension}`);
          setLoading(false);
      }
    } catch (err) {
      setError(err.message || '文件获取失败');
      console.error('文件预览失败:', err);
      setLoading(false);
    }
  };

  useEffect(() => {
    if (previewFile && selectedDb) {
      fetchFileContent();
    }
  }, [previewFile, selectedDb]);

  const renderPreviewContent = () => {
    if (loading) {
      return (
        <div className="preview-loading">
          <div className="spinner"></div>
          <span>加载中...</span>
        </div>
      );
    }

    if (error) {
      return (
        <div className="preview-error">
          <span className="error-icon">❌</span>
          <p>{error}</p>
        </div>
      );
    }

    switch (fileType) {
      case 'text':
        return <TextPreview content={content} />;
      case 'pdf':
        return <PdfPreview blob={pdfBlob} onError={setError} />;
      case 'word':
        return <WordPreview wordData={wordData} />;
      case 'excel':
        return <ExcelPreview blob={excelBlob} />;
      case 'unsupported':
        return <TextPreview content={content} />;
      default:
        return <TextPreview content="文件内容为空" />;
    }
  };

  if (!previewFile) {
    return null;
  }

  return (
    <div className="preview-sidebar">
      <div className="preview-header">
        <div className="preview-title">
          <span className="preview-icon">👁️</span>
          <span className="preview-filename">{previewFile.filename}</span>
        </div>
        <button className="preview-close" onClick={closePreviewSidebar}>
          ✕
        </button>
      </div>

      <div className="preview-content">
        {renderPreviewContent()}
      </div>
    </div>
  );
};
