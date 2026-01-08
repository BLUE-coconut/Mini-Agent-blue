"""Banana 图片生成工具 - 使用 Banana API 生成图像

此工具可以在 Skill 环境中独立使用，或作为模块被其他脚本导入。
"""

import json
import sys
import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

import requests
from PIL import Image
import io

# 尝试加载环境变量
def load_env_manually(env_file_path: Path) -> bool:
    """手动读取 .env 文件并设置环境变量（备用方法）"""
    try:
        with open(env_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ[key] = value
        return True
    except Exception:
        return False

# 尝试加载环境变量
try:
    from dotenv import load_dotenv
    # 尝试从多个位置加载 .env 文件
    possible_env_paths = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent.parent / ".env",
        Path(__file__).parent / ".env",
    ]
    for env_file in possible_env_paths:
        if env_file.exists() and env_file.is_file():
            try:
                load_dotenv(env_file)
                break
            except Exception:
                load_env_manually(env_file)
                break
except ImportError:
    # 如果没有 dotenv 库，尝试手动读取
    for env_file in possible_env_paths:
        if env_file.exists() and env_file.is_file():
            load_env_manually(env_file)
            break


class BananaImageGenTool:
    """使用 Banana API 生成图像的工具"""

    def __init__(self, workspace_dir: Optional[str] = None, output_dir: Optional[str] = None):
        """初始化工具
        
        Args:
            workspace_dir: 工作目录，用于保存生成的图像
            output_dir: 输出目录，相对于工作目录
        """
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self.output_dir = self.workspace_dir / (output_dir or "banana_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def execute(
        self,
        prompt: str,
        aspect_ratio: str = "4:3",
        image_size: str = "1K",
        output_filename: Optional[str] = None
    ) -> dict:
        """调用 Banana API 生成图像
        
        Args:
            prompt: 生成图像的提示词
            aspect_ratio: 宽高比
            image_size: 图像尺寸
            output_filename: 输出文件名
            
        Returns:
            dict: 包含 success, content, error 字段
        """
        try:
            # 调用 API
            resp, headers = self._call_banana_api(prompt, aspect_ratio, image_size)
            
            if resp is None:
                return {
                    "success": False,
                    "content": "",
                    "error": "API 调用失败"
                }
            
            # 提取图像数据
            img_data = self._extract_image_from_response(resp)
            
            if img_data is None:
                return {
                    "success": False,
                    "content": "",
                    "error": "无法从响应中提取图像数据"
                }
            
            # 生成输出路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if output_filename:
                output_path = self.output_dir / f"{output_filename}.png"
            else:
                output_path = self.output_dir / f"banana_{timestamp}.png"
            
            # 保存图像
            result = self._decode_and_save_image(img_data, str(output_path))
            
            if result is None:
                return {
                    "success": False,
                    "content": "",
                    "error": "图像保存失败"
                }
            
            # 保存响应日志
            self._save_response_to_log(resp, headers)
            
            return {
                "success": True,
                "content": f"图像生成成功！保存到: {output_path}",
                "path": str(output_path)
            }
            
        except Exception as e:
            return {
                "success": False,
                "content": "",
                "error": f"图像生成失败: {str(e)}"
            }

    def _call_banana_api(self, prompt: str, aspect_ratio: str, image_size: str) -> Tuple[Optional[dict], Optional[dict]]:
        """调用 Banana API"""
        base_url = os.getenv("BANANA_API_URL")
        model = "g3-pro-image-preview"
        token = os.getenv("BANANA_API_KEY")
        
        if not base_url:
            raise ValueError("未找到 BANANA_API_URL 环境变量")
        if not token:
            raise ValueError("未找到 BANANA_API_KEY 环境变量")
        
        url = f"{base_url}/v1beta/models/{model}:generateContent"
        
        payload = json.dumps({
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ],
                    "role": "user"
                }
            ],
            "generationConfig": {
                "responseModalities": [
                    "TEXT",
                    "IMAGE"
                ],
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": image_size
                }
            }
        })
        
        headers = {
            'X-Biz-Id': 'op',
            'Content-Type': 'application/json',
            "Authorization": f"Bearer {token}",
        }
        
        try:
            response = requests.request(
                "POST", 
                url, 
                headers=headers, 
                data=payload, 
                timeout=600
            )
            
            if response.status_code != 200:
                print(f"API 请求失败，状态码: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None, None
            
            try:
                resp_json = response.json()
                resp_headers = dict(response.headers)
                return resp_json, resp_headers
            except json.JSONDecodeError as e:
                print(f"JSON 解析失败: {e}")
                print(f"响应内容: {response.text[:500]}")
                return None, None
                
        except requests.exceptions.Timeout:
            print("请求超时")
            return None, None
        except requests.exceptions.ConnectionError:
            print("连接错误")
            return None, None
        except Exception as e:
            print(f"请求错误: {e}")
            return None, None

    def _extract_image_from_response(self, resp: dict) -> Optional[str]:
        """从 API 响应中提取图像数据"""
        if resp is None:
            print("响应为空")
            return None
        
        if not isinstance(resp, dict):
            print(f"响应格式错误，期望字典类型，实际为 {type(resp)}")
            return None
        
        if 'error' in resp:
            print(f"API 返回错误: {resp.get('error')}")
            return None
        
        if 'candidates' not in resp:
            print("响应中缺少 'candidates' 字段")
            print(f"可用字段: {list(resp.keys())}")
            return None
        
        candidates = resp['candidates']
        if not isinstance(candidates, list) or len(candidates) == 0:
            print("'candidates' 为空或格式不正确")
            return None
        
        candidate = candidates[0]
        if 'content' not in candidate:
            print("候选结果中缺少 'content' 字段")
            return None
        
        content = candidate['content']
        if 'parts' not in content:
            print("内容中缺少 'parts' 字段")
            return None
        
        parts = content['parts']
        if not isinstance(parts, list) or len(parts) == 0:
            print("'parts' 为空或格式不正确")
            return None
        
        for part in parts:
            if 'inlineData' in part:
                inline_data = part['inlineData']
                if 'data' in inline_data:
                    return inline_data['data']
        
        print("没有找到图像数据")
        return None

    def _decode_and_save_image(self, base64_data: str, output_path: str) -> Optional[Image.Image]:
        """将 base64 编码的图像数据解码并保存"""
        try:
            # 如果包含 data URI 前缀，去除它
            if ',' in base64_data and base64_data.startswith('data:'):
                base64_data = base64_data.split(',', 1)[1]
            
            # 解码 base64 数据
            img_bytes = base64.b64decode(base64_data)
            
            # 使用 PIL 打开图像
            img = Image.open(io.BytesIO(img_bytes))
            
            # 保存为 PNG 格式
            img.save(output_path, 'PNG')
            print(f"图像已保存到: {output_path}")
            return img
            
        except base64.binascii.Error as e:
            print(f"Base64 解码失败: {e}")
            return None
        except Exception as e:
            print(f"图像处理失败: {e}")
            return None

    def _save_response_to_log(self, resp_data: dict, resp_headers: dict):
        """将响应数据和 headers 保存到日志文件"""
        log_dir = self.workspace_dir / "banana_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f'response_{timestamp}.log'
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"请求时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                # 写入响应 Headers
                f.write("【响应 Headers】\n")
                f.write("-" * 80 + "\n")
                for key, value in resp_headers.items():
                    f.write(f"{key}: {value}\n")
                f.write("\n")
                
                # 写入响应 Body
                f.write("【响应 Body】\n")
                f.write("-" * 80 + "\n")
                f.write(json.dumps(resp_data, indent=2, ensure_ascii=False))
                f.write("\n\n")
                f.write("=" * 80 + "\n")
            
            print(f"响应已保存到日志文件: {log_file}")
        except Exception as e:
            print(f"保存日志文件失败: {e}")

