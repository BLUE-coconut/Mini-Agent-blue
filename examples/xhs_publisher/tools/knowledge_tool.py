"""智能知识库读取工具 - 增强版文件读取"""

import os
from pathlib import Path
from typing import Any, Optional, List

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from mini_agent.tools.base import Tool, ToolResult


class SmartKnowledgeReadTool(Tool):
    """智能读取知识库文件 - 支持多策略路径推断"""

    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.json', '.yaml', '.yml', '.py', '.js', '.html', '.css'}

    def __init__(self, workspace_dir: str):
        """
        初始化智能知识库工具

        Args:
            workspace_dir: Agent 的工作目录
        """
        self.workspace_dir = Path(workspace_dir)
        # 常见的知识库目录名称
        self.knowledge_dir_names = {'PersonalKB', 'knowledge', 'docs', 'documents', 'knowledge_base', 'kb'}

    @property
    def name(self) -> str:
        return "read_knowledge_smart"

    @property
    def description(self) -> str:
        return """智能读取知识库文件。自动推断文件路径，支持：
- 绝对路径
- 相对于 workspace 的路径 (推荐)
- 相对于知识库目录的路径
- 文件名模糊搜索

使用方式：
- read_knowledge_smart("PersonalKB/01.md") - 推荐方式
- read_knowledge_smart("/绝对/路径/文件.md")
- read_knowledge_smart("01.md") - 模糊搜索
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": """文件路径，支持多种格式：
- 绝对路径: "/Users/xxx/PersonalKB/01.md"
- 相对 workspace: "examples/xhs_publisher/PersonalKB/01.md"
- 相对知识库: "01.md" (会在常见知识库目录中搜索)
- 仅文件名: "01.md" (模糊搜索)
""",
                },
                "max_files": {
                    "type": "integer",
                    "description": "最多读取的文件数量，默认10",
                    "default": 10
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, max_files: int = 10) -> ToolResult:
        """执行智能知识库读取"""
        try:
            # 多策略路径推断
            candidates = self._infer_paths(path)

            for candidate_path in candidates:
                if candidate_path.exists():
                    if candidate_path.is_file():
                        content = self._read_file(candidate_path)
                        return ToolResult(
                            success=True,
                            content=f"✅ 成功读取: {candidate_path}\n\n=== {candidate_path.name} ===\n{content}"
                        )
                    else:
                        # 目录读取
                        result = await self._read_directory(candidate_path, max_files)
                        return result

            # 模糊搜索
            search_result = await self._fuzzy_search(path, max_files)
            if search_result:
                return search_result

            # 所有策略都失败
            paths_tried = "\n".join(str(p) for p in candidates)
            return ToolResult(
                success=False,
                error=f"""❌ 文件不存在: {path}

尝试过的路径:
{paths_tried}

💡 提示:
- 使用相对于 workspace 的路径，如: "examples/xhs_publisher/PersonalKB/01.md"
- 使用绝对路径
- 如果忘记路径，可以先使用 bash 命令查看: ls -la"""
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _infer_paths(self, user_path: str) -> List[Path]:
        """
        多策略路径推断
        """
        candidates = []
        path = Path(user_path)

        # 策略 1: 已经是绝对路径
        if path.is_absolute():
            candidates.append(path)
            return candidates

        # 策略 2: 相对于 workspace (最常用)
        candidates.append(self.workspace_dir / user_path)

        # 策略 3: 相对于 workspace 的各个子目录
        for dir_name in self.knowledge_dir_names:
            candidates.append(self.workspace_dir / dir_name / user_path)

        # 策略 4: 如果用户输入包含路径分隔符，尝试在 workspace 父目录查找
        if '/' in user_path or '\\' in user_path:
            # 尝试 workspace 父目录
            parent = self.workspace_dir.parent
            candidates.append(parent / user_path)

            # 尝试常见的项目根目录
            for name in ['Mini-Agent', 'minimaxProjects', 'project']:
                if name in str(parent):
                    candidates.append(parent / name / user_path)
                    break

        # 策略 5: 如果输入只是文件名，在常见知识库目录中查找
        if '/' not in user_path and '\\' not in user_path:
            for dir_name in self.knowledge_dir_names:
                candidates.append(self.workspace_dir / dir_name / user_path)

        # 去重并返回
        seen = set()
        unique_candidates = []
        for p in candidates:
            if str(p) not in seen:
                seen.add(str(p))
                unique_candidates.append(p)

        return unique_candidates

    async def _fuzzy_search(self, filename: str, max_files: int = 10) -> Optional[ToolResult]:
        """模糊搜索文件"""
        if '/' in filename or '\\' in filename:
            return None  # 包含路径，不进行模糊搜索

        # 在 workspace 中搜索同名文件
        matches = []
        for file_path in self.workspace_dir.rglob("*"):
            if file_count >= max_files:
                break
            if file_path.is_file() and file_path.stem == Path(filename).stem:
                matches.append(file_path)

        if matches:
            # 读取找到的文件
            files_content = []
            file_count = 0
            for file_path in matches[:max_files]:
                if file_count >= max_files:
                    break
                if file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    content = self._read_file(file_path)
                    if content:
                        relative_path = file_path.relative_to(self.workspace_dir)
                        files_content.append(f"=== {relative_path} ===\n{content}")
                        file_count += 1

            if files_content:
                return ToolResult(
                    success=True,
                    content=f"🔍 模糊搜索找到 {file_count} 个匹配文件:\n\n" + "\n\n".join(files_content)
                )

        return None

    async def _read_directory(self, dir_path: Path, max_files: int) -> ToolResult:
        """读取目录下的所有文件"""
        files_content = []
        file_count = 0

        for file_path in sorted(dir_path.rglob("*")):
            if file_count >= max_files:
                break
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                content = self._read_file(file_path)
                if content:
                    relative_path = file_path.relative_to(dir_path)
                    files_content.append(f"=== {relative_path} ===\n{content}")
                    file_count += 1

        if not files_content:
            return ToolResult(success=False, error=f"目录中没有找到支持的文件: {dir_path}")

        result = f"📁 读取目录: {dir_path}\n读取了 {file_count} 个文件:\n\n" + "\n\n".join(files_content)
        return ToolResult(success=True, content=result)

    def _read_file(self, file_path: Path, max_chars: int = 10000) -> str:
        """读取单个文件内容"""
        try:
            content = file_path.read_text(encoding='utf-8')
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n... (内容已截断，共 {len(content)} 字符)"
            return content
        except Exception as e:
            return f"[读取失败: {e}]"


# 保留原有工具以保持向后兼容
class KnowledgeReadTool(Tool):
    """原有的知识库读取工具（保持不变）"""

    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.json', '.yaml', '.yml', '.py', '.js', 'html', 'css'}

    @property
    def name(self) -> str:
        return "read_knowledge"

    @property
    def description(self) -> str:
        return "读取指定目录下的知识库文件内容，支持txt/md/json/yaml等格式。用于获取创作参考资料。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件或目录的绝对路径。如果是目录，会读取目录下所有支持的文件。",
                },
                "max_files": {
                    "type": "integer",
                    "description": "最多读取的文件数量，默认10",
                    "default": 10
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, max_files: int = 10) -> ToolResult:
        """执行知识库读取"""
        try:
            target = Path(path)

            if not target.exists():
                return ToolResult(success=False, error=f"路径不存在: {path}")

            if target.is_file():
                content = self._read_file(target)
                return ToolResult(success=True, content=f"=== {target.name} ===\n{content}")

            # 目录：读取所有支持的文件
            files_content = []
            file_count = 0

            for file_path in sorted(target.rglob("*")):
                if file_count >= max_files:
                    break
                if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    content = self._read_file(file_path)
                    if content:
                        relative_path = file_path.relative_to(target)
                        files_content.append(f"=== {relative_path} ===\n{content}")
                        file_count += 1

            if not files_content:
                return ToolResult(success=False, error="目录中没有找到支持的文件")

            result = f"读取了 {file_count} 个文件:\n\n" + "\n\n".join(files_content)
            return ToolResult(success=True, content=result)

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _read_file(self, file_path: Path, max_chars: int = 10000) -> str:
        """读取单个文件内容"""
        try:
            content = file_path.read_text(encoding='utf-8')
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n... (内容已截断，共 {len(content)} 字符)"
            return content
        except Exception as e:
            return f"[读取失败: {e}]"
