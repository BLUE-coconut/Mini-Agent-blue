"""Banana 图片生成工具 - 使用 MiniMax Banana API 生成图像"""

import json
import sys
import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from PIL import Image
import io

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 尝试加载环境变量
try:
    from dotenv import load_dotenv
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

from mini_agent.tools.base import Tool, ToolResult


class BananaImageGenTool(Tool):
    """使用 MiniMax Banana API 生成图像的工具"""

    def __init__(self, workspace_dir: str = None, output_dir: str = None):
        """初始化工具
        
        Args:
            workspace_dir: 工作目录，用于保存生成的图像
            output_dir: 输出目录，相对于工作目录
        """
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "banana_image_gen"

    @property
    def description(self) -> str:
        return """使用 nano Banana API 生成图像。支持自定义提示词，可生成:
- 贴纸、表情包
- 艺术插画
- 宣传图片
- 社交媒体配图

生成的图像会保存指定目录的文件夹中，返回图像路径。"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "生成图像的提示词描述，建议详细描述场景、风格、元素等"
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["1:1", "4:3", "16:9", "3:4", "9:16"],
                    "description": "图像宽高比，默认 4:3",
                    "default": "4:3"
                },
                "image_size": {
                    "type": "string",
                    "enum": ["256", "512", "1K", "2K"],
                    "description": "图像尺寸，默认 1K（1024像素）",
                    "default": "1K"
                },
                "output_filename": {
                    "type": "string",
                    "description": "输出文件名（不含扩展名），默认使用时间戳"
                }
            },
            "required": ["prompt"]
        }

    async def execute(
        self,
        prompt: str,
        aspect_ratio: str = "4:3",
        image_size: str = "1K",
        output_filename: str = None
    ) -> ToolResult:
        """调用 Banana API 生成图像
        
        Args:
            prompt: 生成图像的提示词
            aspect_ratio: 宽高比
            image_size: 图像尺寸
            output_filename: 输出文件名
            
        Returns:
            ToolResult: 包含生成图像路径或错误信息
        """
        try:
            # 调用 API
            resp, headers = self._call_banana_api(prompt, aspect_ratio, image_size)
            
            if resp is None:
                return ToolResult(
                    success=False,
                    content="",
                    error="API 调用失败"
                )
            
            # 提取图像数据
            img_data = self._extract_image_from_response(resp)
            
            if img_data is None:
                return ToolResult(
                    success=False,
                    content="",
                    error="无法从响应中提取图像数据"
                )
            
            # 生成输出路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if output_filename:
                output_path = self.output_dir / f"{output_filename}.png"
            else:
                output_path = self.output_dir / f"banana_{timestamp}.png"
            
            # 保存图像
            result = self._decode_and_save_image(img_data, str(output_path))
            
            if result is None:
                return ToolResult(
                    success=False,
                    content="",
                    error="图像保存失败"
                )
            
            # 保存响应日志
            self._save_response_to_log(resp, headers)
            
            return ToolResult(
                success=True,
                content=f"图像生成成功！保存到: {output_path}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"图像生成失败: {str(e)}"
            )

    def _call_banana_api(self, prompt: str, aspect_ratio: str, image_size: str):
        """调用 Banana API
        
        Args:
            prompt: 提示词
            aspect_ratio: 宽高比
            image_size: 图像尺寸
            
        Returns:
            tuple: (响应JSON, 响应头)
        """
        base_url = os.getenv("BANANA_API_URL")
        model = "g3-pro-image-preview"
        token = os.getenv("BANANA_API_KEY")
        
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

    def _extract_image_from_response(self, resp):
        """从 API 响应中提取图像数据
        
        Args:
            resp: API 响应的 JSON 数据
            
        Returns:
            str: 图像的 base64 数据，失败返回 None
        """
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

    def _decode_and_save_image(self, base64_data, output_path):
        """将 base64 编码的图像数据解码并保存
        
        Args:
            base64_data: base64 编码的字符串
            output_path: 输出文件路径
            
        Returns:
            Image: PIL Image 对象，失败返回 None
        """
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

    def _save_response_to_log(self, resp_data, resp_headers):
        """将响应数据和 headers 保存到日志文件
        
        Args:
            resp_data: 响应的 JSON 数据
            resp_headers: 响应的 HTTP headers
        """
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

