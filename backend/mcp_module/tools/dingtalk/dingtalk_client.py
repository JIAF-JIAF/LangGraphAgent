"""
钉钉API客户端
"""
import os
import requests
from typing import Optional, Dict, Any
from mcp_module.logger import info, error
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class DingTalkClient:
    """钉钉API客户端"""
    
    def __init__(self):
        self.app_key = os.getenv("DINGTALK_CLIENT_ID")
        self.app_secret = os.getenv("DINGTALK_CLIENT_SECRET")
        self.user_id = os.getenv("DINGTALK_USER_ID")
    
    def get_current_user_id(self, user_id: str = None) -> str:
        """
        获取当前用户 ID
        
        优先级：参数传入 > 环境变量 DINGTALK_CURRENT_USER_ID > 配置文件中的 DINGTALK_USER_ID
        
        Args:
            user_id: 可选参数，直接传入用户ID
            
        Returns:
            当前用户 ID
        """
        if user_id:
            return user_id
        return os.getenv("DINGTALK_CURRENT_USER_ID", self.user_id)
    
    def get_access_token(self) -> str:
        """获取access_token"""
        if not all([self.app_key, self.app_secret]):
            raise ValueError("钉钉配置信息不完整")
        
        try:
            info('[钉钉API] 正在获取access_token...')
            
            response = requests.post(
                "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                json={"appKey": self.app_key, "appSecret": self.app_secret}
            )
            response.raise_for_status()
            token = response.json().get("accessToken")
            
            if not token:
                raise ValueError("获取钉钉访问令牌失败")
            
            info('[钉钉API] access_token获取成功')
            return token
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"获取访问令牌失败: {str(e)}")
    
    def request(self, method: str, endpoint: str, params: Dict[str, Any] = None,
               data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        发送钉钉 API 请求

        Args:
            method: HTTP 方法 (GET/POST/PUT/DELETE)
            endpoint: API 端点路径
            params: URL 查询参数
            data: 请求体数据

        Returns:
            API 响应结果字典
        """
        try:
            access_token = self.get_access_token()
        except Exception as e:
            error(f'[钉钉API] 获取access_token失败: {str(e)}')
            return {'errcode': -1, 'errmsg': f'获取access_token失败: {str(e)}'}
        
        url = f'https://api.dingtalk.com{endpoint}'
        
        # 新版API使用header
        headers = {
            'x-acs-dingtalk-access-token': access_token
        }
        
        try:
            info(f'[钉钉API] 发起请求: {method} {endpoint}')
            info(f'[钉钉API] 请求数据: {data}')
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, params=params, timeout=10)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, params=params, timeout=10)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=10)
            else:
                return {'errcode': -1, 'errmsg': '不支持的HTTP方法'}
            
            info(f'[钉钉API] 响应状态码: {response.status_code}')
            info(f'[钉钉API] 响应头: {response.headers}')
            
            response.raise_for_status()
            result = response.json()
            info(f'[钉钉API] 请求完成: {result.get("code", result.get("errcode", "unknown"))}')
            return result
            
        except requests.exceptions.HTTPError as e:
            error(f'[钉钉API] HTTP错误: {str(e)}')
            try:
                error_response = response.json()
                error(f'[钉钉API] 错误响应: {error_response}')
                return {'errcode': -1, 'errmsg': f'HTTP错误: {error_response.get("message", str(e))}'}
            except:
                error(f'[钉钉API] 错误响应内容: {response.text[:500]}')
                return {'errcode': -1, 'errmsg': f'HTTP错误: {response.text[:200]}'}
        except Exception as e:
            error(f'[钉钉API] 请求异常: {str(e)}')
            return {'errcode': -1, 'errmsg': f'请求异常: {str(e)}'}

    def get_union_id(self, access_token: str, userid: str) -> Optional[str]:
        """
        获取用户 unionId

        Args:
            access_token: 钉钉访问令牌
            userid: 用户 ID

        Returns:
            用户的 unionId，获取失败返回 None
        """
        info(f'[钉钉API] 正在获取用户unionId，userid={userid}')
        
        try:
            url = 'https://oapi.dingtalk.com/topapi/v2/user/get'
            headers = {'Content-Type': 'application/json'}
            params = {'access_token': access_token}
            data = {'userid': userid}
            
            response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result.get('errcode') == 0:
                unionid = result.get('result', {}).get('unionid')
                info(f'[钉钉API] unionId获取成功: {unionid}')
                return unionid
            else:
                error(f'[钉钉API] 获取unionId失败: {result.get("errmsg")}')
                return None
                
        except Exception as e:
            error(f'[钉钉API] 获取unionId异常: {str(e)}')
            return None


def get_dingtalk_client() -> DingTalkClient:
    """获取钉钉客户端实例"""
    return DingTalkClient()
