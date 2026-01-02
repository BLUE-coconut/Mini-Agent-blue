"""CLI 交互式输入组件 - 基于 prompt_toolkit 的公共输入模块"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, List, Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, WordCompleter, PathCompleter
from prompt_toolkit.completion.fuzzy_completer import FuzzyCompleter
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText


class Colors:
    """终端颜色定义"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    @staticmethod
    def supports_color() -> bool:
        """检查终端是否支持颜色"""
        if os.environ.get("TERM", "") == "dumb":
            return False
        if os.environ.get("NO_COLOR", ""):
            return False
        return sys.stdout.isatty()


class FilePathCompleter(Completer):
    """文件路径补全器 - 支持 @ 符号触发"""

    def __init__(self, base_dirs: Optional[List[str]] = None, show_hidden: bool = False):
        """
        初始化文件路径补全器

        Args:
            base_dirs: 基础目录列表，None 则自动检测
            show_hidden: 是否显示隐藏文件
        """
        self.base_dirs = base_dirs or [os.getcwd()]
        self.show_hidden = show_hidden

    def get_completions(self, document, complete_event):
        """获取补全项"""
        text = document.text_before_cursor

        # 检查是否以 @ 开头
        if not text.endswith('@'):
            return

        # 提取 @ 后的搜索词
        word = ''
        for char in reversed(text[:-1]):
            if char in ' /\t\n"\'\\':
                break
            word = char + word

        # 获取当前光标位置前的路径
        before_at = text[:-1].rstrip()
        if ' ' in before_at:
            last_space = before_at.rfind(' ')
            base_path = before_at[:last_space + 1]
        else:
            base_path = ''

        # 搜索文件
        search_base = os.getcwd()
        if self.base_dirs:
            for base in self.base_dirs:
                if text.startswith(base) or base in text:
                    search_base = base
                    break

        full_search_path = os.path.join(search_base, base_path, word + '*')

        try:
            # 查找匹配的文件
            matches = []
            search_dir = os.path.join(search_base, base_path) if base_path else search_base

            if os.path.isdir(search_dir):
                for item in sorted(os.listdir(search_dir)):
                    if not self.show_hidden and item.startswith('.'):
                        continue
                    if item.lower().startswith(word.lower()):
                        full_path = os.path.join(search_dir, item)
                        is_dir = os.path.isdir(full_path)
                        display = item + ('/' if is_dir else '')
                        # 使用相对路径显示
                        try:
                            rel_path = os.path.relpath(full_path, search_base)
                            display = rel_path + ('/' if is_dir else '')
                        except ValueError:
                            pass

                        matches.append((display, is_dir))

            # 生成补全项
            for display, is_dir in matches:
                yield Completion(
                    display,
                    start_position=-len(word),
                    display_meta='directory' if is_dir else 'file'
                )

        except Exception:
            pass


class MentionCompleter(Completer):
    """@文件引用补全器 - 支持模糊搜索和路径层级补全
    
    功能：
    1. 输入 @ 后显示根目录内容
    2. 边输入边过滤（模糊匹配）
    3. 支持路径层级补全（如 @folder/subfolder/）
    4. 文件夹显示 📁，文件显示大小
    """

    def __init__(self, workspace_dir: str, max_items: int = 100):
        """
        初始化文件补全器

        Args:
            workspace_dir: 工作目录
            max_items: 最大索引条目数
        """
        self.workspace_dir = Path(workspace_dir)
        self.max_items = max_items
        self._file_cache = None
        self._cache_time = 0
        self._cache_ttl = 5  # 缓存有效期（秒）

    def _build_file_index(self) -> List[tuple]:
        """构建完整的文件索引（包含所有文件和文件夹）
        
        Returns:
            List of (rel_path, full_path, is_dir) tuples
        """
        import time
        current_time = time.time()
        
        # 如果缓存有效，直接返回
        if self._file_cache is not None and (current_time - self._cache_time) < self._cache_ttl:
            return self._file_cache
        
        items = []
        count = 0
        
        try:
            for file_path in self.workspace_dir.rglob('*'):
                if count >= self.max_items:
                    break
                
                # 跳过隐藏文件和 __pycache__ 目录
                if file_path.name.startswith('.') or '__pycache__' in str(file_path):
                    continue
                
                try:
                    rel_path = str(file_path.relative_to(self.workspace_dir))
                    is_dir = file_path.is_dir()
                    if is_dir:
                        rel_path += '/'
                    items.append((rel_path, file_path, is_dir))
                    count += 1
                except ValueError:
                    pass
        except Exception:
            pass
        
        # 按路径排序（文件夹优先，然后按名称）
        items.sort(key=lambda x: (not x[2], x[0].lower()))
        
        self._file_cache = items
        self._cache_time = current_time
        return items

    def _get_meta_str(self, full_path: Path, is_dir: bool) -> str:
        """获取元信息字符串"""
        if is_dir:
            return "📁"
        else:
            try:
                size = full_path.stat().st_size
                if size > 1024 * 1024:
                    return f"📄 {size / (1024*1024):.1f}MB"
                elif size > 1024:
                    return f"📄 {size / 1024:.1f}KB"
                else:
                    return f"📄 {size}B"
            except:
                return "📄"

    def _fuzzy_match(self, pattern: str, text: str) -> tuple:
        """模糊匹配
        
        Args:
            pattern: 搜索模式（小写）
            text: 要匹配的文本
            
        Returns:
            (is_match, score) - 是否匹配和匹配分数（分数越高越好）
        """
        text_lower = text.lower()
        
        # 精确匹配（最高分）
        if pattern == text_lower:
            return (True, 1000)
        
        # 前缀匹配（高分）
        if text_lower.startswith(pattern):
            return (True, 500 + (100 - len(text)))
        
        # 包含匹配（中分）
        if pattern in text_lower:
            # 位置越靠前分数越高
            pos = text_lower.find(pattern)
            return (True, 200 - pos)
        
        # 模糊匹配：检查 pattern 中的每个字符是否按顺序出现在 text 中
        pattern_idx = 0
        score = 0
        consecutive = 0
        
        for i, char in enumerate(text_lower):
            if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
                pattern_idx += 1
                consecutive += 1
                score += consecutive * 10  # 连续匹配加分
            else:
                consecutive = 0
        
        if pattern_idx == len(pattern):
            return (True, score)
        
        return (False, 0)

    def _list_directory(self, dir_path: Path) -> List[tuple]:
        """列出目录内容
        
        Args:
            dir_path: 要列出的目录路径
            
        Returns:
            List of (name, full_path, is_dir) tuples
        """
        items = []
        try:
            for item in sorted(dir_path.iterdir()):
                # 跳过隐藏文件和 __pycache__ 目录
                if item.name.startswith('.') or item.name == '__pycache__':
                    continue
                
                name = item.name
                is_dir = item.is_dir()
                if is_dir:
                    name += '/'
                items.append((name, item, is_dir))
        except (PermissionError, OSError):
            pass
        
        # 文件夹优先
        items.sort(key=lambda x: (not x[2], x[0].lower()))
        return items

    def get_completions(self, document, complete_event):
        """获取补全项 - 支持模糊搜索和路径层级补全"""
        text = document.text_before_cursor

        # 查找最后一个 @
        last_at = text.rfind('@')
        if last_at == -1:
            return

        # 提取搜索词（@ 之后的内容）
        search_term = text[last_at + 1:]

        # 如果搜索词中有空格，说明 @ 引用已结束
        if ' ' in search_term:
            return

        # 检查是否是路径层级补全模式
        if '/' in search_term:
            # 路径层级补全：分离目录和文件名部分
            last_slash = search_term.rfind('/')
            dir_part = search_term[:last_slash + 1]  # 包含最后的 /
            name_part = search_term[last_slash + 1:]  # 文件名部分（可能为空）
            
            # 构建目录路径
            target_dir = self.workspace_dir / dir_part.rstrip('/')
            
            if not target_dir.exists() or not target_dir.is_dir():
                return
            
            # 列出目录内容
            items = self._list_directory(target_dir)
            
            # 过滤和排序
            matches = []
            name_lower = name_part.lower()
            
            for name, full_path, is_dir in items:
                display_path = dir_part + name
                
                if not name_part:
                    # 没有输入文件名，显示所有
                    matches.append((display_path, full_path, is_dir, 100))
                else:
                    # 模糊匹配文件名
                    is_match, score = self._fuzzy_match(name_lower, name.rstrip('/'))
                    if is_match:
                        matches.append((display_path, full_path, is_dir, score))
            
            # 按分数排序
            matches.sort(key=lambda x: -x[3])
            
            for display_path, full_path, is_dir, _ in matches[:20]:
                yield Completion(
                    display_path,
                    start_position=-len(search_term),
                    display_meta=self._get_meta_str(full_path, is_dir)
                )
        else:
            # 全局模糊搜索模式
            all_items = self._build_file_index()
            
            if not search_term:
                # 没有搜索词，显示根目录内容
                root_items = self._list_directory(self.workspace_dir)
                for name, full_path, is_dir in root_items[:20]:
                    yield Completion(
                        name,
                        start_position=0,
                        display_meta=self._get_meta_str(full_path, is_dir)
                    )
            else:
                # 模糊搜索所有文件
                search_lower = search_term.lower()
                matches = []
                
                for rel_path, full_path, is_dir in all_items:
                    # 匹配文件名或完整路径
                    filename = rel_path.rstrip('/').split('/')[-1]
                    
                    # 优先匹配文件名
                    is_match, score = self._fuzzy_match(search_lower, filename)
                    if is_match:
                        matches.append((rel_path, full_path, is_dir, score + 100))
                        continue
                    
                    # 其次匹配完整路径
                    is_match, score = self._fuzzy_match(search_lower, rel_path.rstrip('/'))
                    if is_match:
                        matches.append((rel_path, full_path, is_dir, score))
                
                # 按分数排序（高分优先）
                matches.sort(key=lambda x: -x[3])
                
                for rel_path, full_path, is_dir, _ in matches[:20]:
                    yield Completion(
                        rel_path,
                        start_position=-len(search_term),
                        display_meta=self._get_meta_str(full_path, is_dir)
                    )


def create_key_bindings() -> KeyBindings:
    """创建通用快捷键绑定"""
    kb = KeyBindings()

    @kb.add("c-u")
    def _(event):
        """Ctrl+U: 清除当前行"""
        event.current_buffer.reset()

    @kb.add("c-l")
    def _(event):
        """Ctrl+L: 清除屏幕"""
        event.app.renderer.clear()

    @kb.add("@")
    def _(event):
        """@: 触发文件补全"""
        # 插入 @ 符号
        event.current_buffer.insert_text("@")
        # 强制开始补全
        event.current_buffer.start_completion(select_first=False)

    @kb.add("/")
    def _(event):
        """/: 在 @ 路径中触发层级补全"""
        text = event.current_buffer.text
        cursor_pos = event.current_buffer.cursor_position
        text_before = text[:cursor_pos]
        
        # 插入 / 符号
        event.current_buffer.insert_text("/")
        
        # 如果在 @ 路径中，触发补全
        last_at = text_before.rfind('@')
        if last_at != -1:
            # 检查 @ 和当前位置之间没有空格
            between = text_before[last_at + 1:]
            if ' ' not in between:
                event.current_buffer.start_completion(select_first=False)

    return kb


def create_prompt_session(
    history_file: Optional[Path] = None,
    completions: Optional[List[str]] = None,
    workspace_dir: Optional[str] = None,
) -> PromptSession:
    """
    创建 prompt_toolkit 会话

    Args:
        history_file: 历史记录文件路径，None 则使用内存历史
        completions: 自动补全词列表
        workspace_dir: 工作目录（用于文件补全）

    Returns:
        PromptSession 实例
    """
    # 历史记录
    if history_file:
        history = FileHistory(str(history_file))
    else:
        history = InMemoryHistory()

    # 自动补全
    completer = None
    if completions:
        completer = WordCompleter(completions, ignore_case=True, sentence=True)

    # 样式
    style = Style.from_dict({
        "prompt": "#00ff00 bold",
        "separator": "#666666",
    })

    return PromptSession(
        history=history,
        completer=completer,
        auto_suggest=AutoSuggestFromHistory(),
        style=style,
        key_bindings=create_key_bindings(),
        complete_while_typing=True,
        validate_while_typing=True,
    )


class CombinedCompleter(Completer):
    """组合补全器 - 合并多个补全器"""

    def __init__(self, completers: List[Completer], priority: Optional[List[int]] = None):
        """
        初始化组合补全器

        Args:
            completers: 补全器列表
            priority: 优先级列表，对应每个补全器的优先级（数字越大优先级越高）
        """
        self.completers = completers
        self.priority = priority or [len(completers) - i for i in range(len(completers))]  # 最后一个优先级最高

    def get_completions(self, document, complete_event):
        """获取补全项"""
        # 按优先级排序补全器
        sorted_completers = sorted(
            zip(self.completers, self.priority),
            key=lambda x: x[1],
            reverse=True
        )

        # 收集所有补全项
        all_completions = []
        seen = set()

        for completer, _ in sorted_completers:
            try:
                for completion in completer.get_completions(document, complete_event):
                    # 去重
                    if completion.text not in seen:
                        seen.add(completion.text)
                        all_completions.append(completion)
            except Exception:
                pass

        return all_completions


def create_enhanced_session(
    history_file: Optional[Path] = None,
    workspace_dir: Optional[str] = None,
    command_completions: Optional[List[str]] = None,
) -> PromptSession:
    """
    创建增强版 prompt_toolkit 会话（支持 @ 文件引用）

    Args:
        history_file: 历史记录文件路径
        workspace_dir: 工作目录（用于 @ 文件补全）
        command_completions: 命令自动补全列表

    Returns:
        PromptSession 实例
    """
    # 历史记录
    if history_file:
        history = FileHistory(str(history_file))
    else:
        history = InMemoryHistory()

    # 构建补全器列表
    completers = []

    # 命令补全
    if command_completions:
        command_completer = WordCompleter(command_completions, ignore_case=True, sentence=True)
        completers.append(command_completer)

    # @文件补全（如果提供了 workspace_dir）
    if workspace_dir:
        try:
            mention_completer = MentionCompleter(workspace_dir)
            completers.append(mention_completer)
        except Exception as e:
            # 如果 MentionCompleter 失败，使用 PathCompleter 作为备选
            path_completer = PathCompleter()
            completers.append(path_completer)

    # 使用组合补全器
    if len(completers) == 1:
        final_completer = completers[0]
    elif len(completers) > 1:
        # 使用自定义组合补全器，@文件补全优先
        final_completer = CombinedCompleter(completers)
    else:
        final_completer = None

    # 样式 - 更美观的补全菜单
    style = Style.from_dict({
        "prompt": "#00ff00 bold",          # 绿色加粗提示符
        "separator": "#666666",            # 灰色分隔符
        
        # 补全菜单样式
        "completion-menu": "bg:#2d2d2d",    # 深灰色背景
        "completion-menu.border": "#444444",  # 边框颜色
        
        # 补全项样式
        "completion-menu.completion": "fg:#e0e0e0",  # 浅灰白色文字
        "completion-menu.completion.current": "bg:#4a9eff fg:#ffffff",  # 选中项
        "completion-menu.completion.selected": "bg:#4a9eff fg:#ffffff",
        
        # 元信息样式
        "completion-menu.meta": "fg:#888888 italic",
        "completion-menu.meta.current": "fg:#4a9eff",
        "completion-menu.meta.selected": "fg:#4a9eff",
        
        # 滚动条样式
        "scrollbar.background": "#333333",
        "scrollbar.button": "#555555",
    })

    return PromptSession(
        history=history,
        completer=final_completer,
        auto_suggest=AutoSuggestFromHistory(),
        style=style,
        key_bindings=create_key_bindings(),
    )


async def async_input(
    prompt_text: str,
    session: Optional[PromptSession] = None,
    multiline: bool = True,
    color: str = "green",
) -> str:
    """
    异步交互式输入

    Args:
        prompt_text: 提示文本
        session: PromptSession 实例，None 则创建临时会话
        multiline: 是否支持多行输入
        color: 提示符颜色 (green, yellow, cyan)

    Returns:
        用户输入的字符串
    """
    if session is None:
        session = create_prompt_session()

    color_map = {
        "green": "fg:green bold",
        "yellow": "fg:yellow bold",
        "cyan": "fg:cyan bold",
    }
    fg_color = color_map.get(color, "fg:green bold")

    def get_prompt():
        if Colors.supports_color():
            return FormattedText([
                (fg_color, prompt_text),
                ("", " › "),
            ])
        else:
            return f"{prompt_text} › "

    result = await session.prompt_async(
        get_prompt(),
        multiline=multiline,
        enable_history_search=True,
    )
    return result.strip()


def sync_input(
    prompt_text: str,
    multiline: bool = True,
    color: str = "green",
) -> str:
    """
    同步交互式输入 - 适用于异步上下文

    Args:
        prompt_text: 提示文本
        multiline: 是否支持多行输入
        color: 提示符颜色

    Returns:
        用户输入的字符串
    """
    session = create_prompt_session()

    color_map = {
        "green": "fg:green bold",
        "yellow": "fg:yellow bold",
        "cyan": "fg:cyan bold",
    }
    fg_color = color_map.get(color, "fg:green bold")

    def get_prompt():
        if Colors.supports_color():
            return FormattedText([
                (fg_color, prompt_text),
                ("", " › "),
            ])
        else:
            return f"{prompt_text} › "

    # 在异步上下文中安全运行
    # 注意: 在 Python 3.11 中，我们不再尝试嵌套运行事件循环
    # 因为这可能导致不稳定的行为。我们直接使用同步的 prompt() 方法
    # 这在所有 Python 版本中都能稳定工作
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_running_loop()

        # 检查事件循环是否正在运行
        if loop.is_running():
            # 事件循环正在运行中，直接使用 session.prompt() 是安全的
            # prompt_toolkit 的 prompt() 会自动处理事件循环
            result = session.prompt(
                get_prompt(),
                multiline=multiline,
                enable_history_search=True,
            )
        else:
            # 事件循环存在但未运行（边缘情况），同样使用同步方法
            result = session.prompt(
                get_prompt(),
                multiline=multiline,
                enable_history_search=True,
            )

    except (RuntimeError, AttributeError):
        # 没有运行的事件循环 (Python 3.11 中更常见)
        # 或者事件循环已被关闭，使用标准方法
        result = session.prompt(
            get_prompt(),
            multiline=multiline,
            enable_history_search=True,
        )

    return result.strip()


async def _async_prompt_wrapper(session: PromptSession, get_prompt, multiline: bool) -> str:
    """异步包装器，用于在已运行的事件循环中获取输入"""
    return await session.prompt_async(
        get_prompt(),
        multiline=multiline,
        enable_history_search=True,
    )


    return text


# 命令定义
class Commands:
    """支持的命令列表"""
    HELP = "/help"
    CLEAR = "/clear"
    HISTORY = "/history"
    STATS = "/stats"
    EXIT = "/exit"
    QUIT = "/quit"
    Q = "/q"

    ALL = [HELP, CLEAR, HISTORY, STATS, EXIT, QUIT, Q]

    # 退出命令列表
    EXIT_COMMANDS = [EXIT, QUIT, Q, "exit", "quit", "q"]

    @staticmethod
    def is_command(text: str) -> bool:
        """检查输入是否为命令"""
        text = text.strip().lower()
        return any(text == cmd.lower() for cmd in Commands.ALL)

    @staticmethod
    def is_exit_command(text: str) -> bool:
        """检查是否为退出命令"""
        text = text.strip().lower()
        return text in [cmd.lower() for cmd in Commands.EXIT_COMMANDS]


def print_help():
    """打印帮助信息"""
    help_text = f"""
{Colors.BOLD}{Colors.BRIGHT_YELLOW}Available Commands:{Colors.RESET}
  {Colors.BRIGHT_GREEN}/help{Colors.RESET}      - Show this help message
  {Colors.BRIGHT_GREEN}/clear{Colors.RESET}     - Clear session history (keep system prompt)
  {Colors.BRIGHT_GREEN}/history{Colors.RESET}   - Show current session message count
  {Colors.BRIGHT_GREEN}/stats{Colors.RESET}     - Show session statistics
  {Colors.BRIGHT_GREEN}/exit{Colors.RESET}      - Exit program (also: exit, quit, q)

{Colors.BOLD}{Colors.BRIGHT_YELLOW}Keyboard Shortcuts:{Colors.RESET}
  {Colors.BRIGHT_CYAN}Ctrl+U{Colors.RESET}     - Clear current input line
  {Colors.BRIGHT_CYAN}Ctrl+L{Colors.RESET}     - Clear screen
  {Colors.BRIGHT_CYAN}Ctrl+J{Colors.RESET}     - Insert newline (also Ctrl+Enter)
  {Colors.BRIGHT_CYAN}Tab{Colors.RESET}        - Auto-complete commands
  {Colors.BRIGHT_CYAN}↑/↓{Colors.RESET}        - Browse command history
  {Colors.BRIGHT_CYAN}→{Colors.RESET}          - Accept auto-suggestion

{Colors.BOLD}{Colors.BRIGHT_YELLOW}Usage:{Colors.RESET}
  - Enter your task directly, Agent will help you complete it
  - Agent remembers all conversation content in this session
  - Use {Colors.BRIGHT_GREEN}/clear{Colors.RESET} to start a new session
  - Press {Colors.BRIGHT_CYAN}Enter{Colors.RESET} to submit your message
  - Use {Colors.BRIGHT_CYAN}Ctrl+J{Colors.RESET} to insert line breaks within your message
"""
    print(help_text)


def create_command_session(
    history_file: Optional[Path] = None,
    workspace_dir: Optional[str] = None,
) -> PromptSession:
    """
    创建支持命令补全的 prompt_toolkit 会话

    Args:
        history_file: 历史记录文件路径
        workspace_dir: 工作目录（用于 @ 文件补全）

    Returns:
        PromptSession 实例
    """
    # 历史记录
    if history_file:
        history = FileHistory(str(history_file))
    else:
        history = InMemoryHistory()

    # 构建补全器列表
    completers = []

    # 命令补全
    command_completer = WordCompleter(Commands.ALL, ignore_case=True, sentence=True)
    completers.append(command_completer)

    # @文件补全（如果提供了 workspace_dir）
    if workspace_dir:
        try:
            mention_completer = MentionCompleter(workspace_dir)
            completers.append(mention_completer)
        except Exception:
            # 如果 MentionCompleter 失败，使用 PathCompleter 作为备选
            path_completer = PathCompleter()
            completers.append(path_completer)

    # 使用组合补全器
    if len(completers) == 1:
        final_completer = completers[0]
    elif len(completers) > 1:
        # 使用自定义组合补全器，@文件补全优先
        final_completer = CombinedCompleter(completers)
    else:
        final_completer = None

    # 样式 - 更美观的补全菜单
    style = Style.from_dict({
        "prompt": "#00ff00 bold",          # 绿色加粗提示符
        "separator": "#666666",            # 灰色分隔符

        # 补全菜单样式
        "completion-menu": "bg:#2d2d2d",    # 深灰色背景
        "completion-menu.border": "#444444",  # 边框颜色

        # 补全项样式
        "completion-menu.completion": "fg:#e0e0e0",  # 浅灰白色文字
        "completion-menu.completion.current": "bg:#4a9eff fg:#ffffff",  # 选中项
        "completion-menu.completion.selected": "bg:#4a9eff fg:#ffffff",

        # 元信息样式
        "completion-menu.meta": "fg:#888888 italic",
        "completion-menu.meta.current": "fg:#4a9eff",
        "completion-menu.meta.selected": "fg:#4a9eff",

        # 滚动条样式
        "scrollbar.background": "#333333",
        "scrollbar.button": "#555555",
    })

    return PromptSession(
        history=history,
        completer=final_completer,
        auto_suggest=AutoSuggestFromHistory(),
        style=style,
        key_bindings=create_key_bindings(),
        complete_while_typing=True,
        validate_while_typing=True,
    )


def process_mentions(text: str, workspace_dir: str) -> str:
    """
    处理文本中的 @ 文件引用

    Args:
        text: 用户输入的文本
        workspace_dir: 工作目录

    Returns:
        处理后的文本（@引用替换为文件内容）
    """
    import re

    # 查找所有 @ 引用
    mentions = re.findall(r'@(\S+)', text)

    for mention in mentions:
        file_path = Path(workspace_dir) / mention

        if file_path.exists() and file_path.is_file():
            try:
                content = file_path.read_text(encoding='utf-8')
                # 替换 @引用 为文件内容
                text = text.replace(
                    f'@{mention}',
                    f'\n# 从文件 {mention} 引用:\n{content}\n'
                )
            except Exception:
                pass

    return text
