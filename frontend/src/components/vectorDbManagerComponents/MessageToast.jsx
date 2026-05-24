/**
 * 消息提示组件
 * @description 显示操作结果的提示消息
 * @param {Object} props
 * @param {string} props.message - 消息内容
 * @param {'success'|'error'|'warning'} props.type - 消息类型
 * @returns {React.ReactElement|null}
 */
export const MessageToast = ({ message, type }) => {
  if (!message) return null;

  return (
    <div className={`message message-${type}`}>
      {message}
    </div>
  );
};
