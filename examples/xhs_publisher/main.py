"""小红书发布助手 - 主程序入口

使用方法:
    python main.py

需要配置:
    在 Mini-Agent/mini_agent/config/config.yaml 中配置 LLM API
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mini_agent import LLMClient
from mini_agent.agent import Agent
from mini_agent.config import Config as MiniAgentConfig
from mini_agent.tools import ReadTool, WriteTool, BashTool

from tools import KnowledgeReadTool, SmartKnowledgeReadTool, XHSBrowserTool, BananaImageGenTool
from prompts import SYSTEM_PROMPT, get_image_tool_description
from config import Config
from cli_input import Colors, create_command_session, async_input, print_help, Commands


def print_welcome():
    """打印欢迎界面"""
    print()
    if Colors.supports_color():
        print(f"{Colors.BRIGHT_CYAN}{Colors.BOLD}╔═══════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}{Colors.BOLD}║                                                       ║{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}{Colors.BOLD}║                🌺 小红书发布助手 v1.0                 ║{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}{Colors.BOLD}║                                                       ║{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}{Colors.BOLD}╚═══════════════════════════════════════════════════════╝{Colors.RESET}")
    else:
        print("╔═══════════════════════════════════════════════════════╗")
        print("║                                                       ║")
        print("║              小红书发布助手 v1.0                      ║")
        print("║                                                       ║")
        print("╚═══════════════════════════════════════════════════════╝")
    print()
    
    # 显示当前配置
    if Colors.supports_color():
        print(f"{Colors.BRIGHT_WHITE}当前配置:{Colors.RESET}")
        print(f"  🎨 图像生成: ", end="")
        if Config.IMAGE_GEN_TOOL == 'mcp':
            print(f"{Colors.BRIGHT_GREEN}MCP 模式{Colors.RESET}")
            print(f"     {Colors.DIM}工具: text_to_image (需要配置 mcp.json){Colors.RESET}")
        else:
            print(f"{Colors.BRIGHT_BLUE}内置模式{Colors.RESET}")
            print(f"     {Colors.DIM}工具: banana_image_gen (无需额外配置){Colors.RESET}")
        if Config.ENABLE_MCP:
            print(f"  🔧 MCP 工具: {Colors.BRIGHT_GREEN}已启用{Colors.RESET}")
        else:
            print(f"  🔧 MCP 工具: {Colors.DIM}未启用{Colors.RESET}")
    else:
        print("当前配置:")
        print("  图像生成: ", end="")
        if Config.IMAGE_GEN_TOOL == 'mcp':
            print("MCP 模式")
        else:
            print("内置模式")
        if Config.ENABLE_MCP:
            print("  MCP 工具: 已启用")
        else:
            print("  MCP 工具: 未启用")
    print()


def print_stats(agent: Agent, session_start: datetime):
    """打印会话统计信息"""
    duration = datetime.now() - session_start
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    # 统计不同类型的消息
    user_msgs = sum(1 for m in agent.messages if m.role == "user")
    assistant_msgs = sum(1 for m in agent.messages if m.role == "assistant")
    tool_msgs = sum(1 for m in agent.messages if m.role == "tool")

    print(f"\n{Colors.BOLD}{Colors.BRIGHT_CYAN}会话统计:{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
    print(f"  会话时长: {hours:02d}:{minutes:02d}:{seconds:02d}")
    print(f"  总消息数: {len(agent.messages)}")
    print(f"    - 用户消息: {Colors.BRIGHT_GREEN}{user_msgs}{Colors.RESET}")
    print(f"    - AI 回复: {Colors.BRIGHT_BLUE}{assistant_msgs}{Colors.RESET}")
    print(f"    - 工具调用: {Colors.BRIGHT_YELLOW}{tool_msgs}{Colors.RESET}")
    print(f"  可用工具: {len(agent.tools)}")
    print(f"{Colors.DIM}{'─' * 40}{Colors.RESET}\n")


async def main():
    """主函数"""
    print_welcome()
    
    # 记录会话开始时间
    session_start = datetime.now()

    # 确保目录存在
    Config.ensure_dirs()

    # 加载配置
    config_path = project_root / "mini_agent" / "config" / "config.yaml"
    if not config_path.exists():
        print("❌ 配置文件不存在")
        print(f"   请先创建: {config_path}")
        print("   可参考: config-example.yaml")
        return

    try:
        mini_config = MiniAgentConfig.from_yaml(config_path)
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return

    if not mini_config.llm.api_key or mini_config.llm.api_key.startswith("YOUR_"):
        print("❌ API Key 未配置")
        print("   请在 config.yaml 中设置有效的 api_key")
        return

    # 初始化 LLM 客户端
    llm_client = LLMClient(
        api_key=mini_config.llm.api_key,
        api_base=mini_config.llm.api_base,
        model=mini_config.llm.model,
    )

    # 初始化工具
    workspace_dir = str(Config.WORKSPACE_DIR)
    tools = [
        # 基础工具
        # ReadTool(workspace_dir=workspace_dir),
        WriteTool(workspace_dir=Config.CONTENT_DIR),
        BashTool(),
        # 自定义工具 - 使用智能知识库工具
        SmartKnowledgeReadTool(workspace_dir=workspace_dir),
        XHSBrowserTool(),
    ]

    # 加载 MCP 工具（如果启用）
    mcp_tools = []
    if Config.ENABLE_MCP:
        try:
            from mini_agent.tools.mcp_loader import load_mcp_tools_async
            mcp_tools = await load_mcp_tools_async()
            if mcp_tools:
                # 根据图像生成工具配置决定是否过滤 text_to_image 工具
                if Config.IMAGE_GEN_TOOL == 'banana':
                    # 过滤掉 text_to_image 工具，使用内置的 banana 工具
                    filtered_mcp_tools = [tool for tool in mcp_tools if tool.name != 'text_to_image']
                    filtered_count = len(mcp_tools) - len(filtered_mcp_tools)
                    if filtered_count > 0:
                        print(f"✅ 已加载 {len(filtered_mcp_tools)} 个 MCP 工具（已过滤 {filtered_count} 个图像生成工具）")
                    else:
                        print(f"✅ 已加载 {len(filtered_mcp_tools)} 个 MCP 工具")
                    tools.extend(filtered_mcp_tools)
                else:
                    # 保留所有 MCP 工具（包括 text_to_image）
                    tools.extend(mcp_tools)
                    print(f"✅ 已加载 {len(mcp_tools)} 个 MCP 工具")
        except Exception as e:
            print(f"⚠️ MCP 工具加载失败 (可选): {e}")
            print(f"💡 提示: 可在 config.py 中设置 ENABLE_MCP=False 禁用 MCP 工具")
    
    # 根据配置决定使用哪个图像生成工具
    if Config.IMAGE_GEN_TOOL == 'banana':
        # 使用内置的 BananaImageGenTool
        tools.append(BananaImageGenTool(workspace_dir=workspace_dir, output_dir=Config.IMAGES_DIR))
        print(f"✅ 已加载内置图像生成工具 (banana_image_gen)")
    elif Config.IMAGE_GEN_TOOL == 'mcp':
        # 检查是否加载了 text_to_image 工具
        has_text_to_image = any(tool.name == 'text_to_image' for tool in tools)
        if not has_text_to_image:
            print(f"⚠️ 未找到 MCP 的 text_to_image 工具")
            print(f"💡 提示: 请确保 ENABLE_MCP=True 且 mcp.json 中配置了图像生成服务")
            print(f"   或设置 IMAGE_GEN_TOOL='banana' 使用内置工具")

    # 创建 Agent
    agent = Agent(
        llm_client=llm_client,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        max_steps=Config.MAX_STEPS,
        workspace_dir=workspace_dir,
        token_limit=Config.TOKEN_LIMIT,
    )

    print()
    if Colors.supports_color():
        print(f"{Colors.BRIGHT_YELLOW}💡 提示: 输入您的创作需求，例如:{Colors.RESET}")
    else:
        print("💡 提示: 输入您的创作需求，例如:")
    print("   '帮我写一篇关于Python学习的小红书笔记'")
    print("   '根据 /path/to/docs 目录下的资料，写一篇科技产品评测'")
    print()
    if Colors.supports_color():
        print(f"{Colors.BRIGHT_CYAN}✨ 新功能: @文件引用{Colors.RESET}")
        print("   输入 @ 后会自动显示可引用的文件列表")
        print("   例如: '根据 @PersonalKB/01.md 的内容，写一篇笔记'")
    else:
        print("✨ 新功能: @文件引用")
        print("   输入 @ 后会自动显示可引用的文件列表")
    print()
    
    # 显示当前图像生成方式
    if Config.IMAGE_GEN_TOOL == 'mcp':
        print(f"{Colors.BRIGHT_BLUE}🎨 图像生成: MCP 模式 (text_to_image){Colors.RESET}")
        if not Config.ENABLE_MCP:
            print(f"   {Colors.DIM}⚠️ 需要设置 ENABLE_MCP=True 才能使用 MCP 工具{Colors.RESET}")
    else:
        print(f"{Colors.BRIGHT_BLUE}🎨 图像生成: 内置模式 (banana_image_gen){Colors.RESET}")
        print(f"   {Colors.DIM}如需切换到 MCP 模式，请在 config.py 中设置 IMAGE_GEN_TOOL='mcp'{Colors.RESET}")
    print()
    
    print("输入 '/help' 查看命令帮助")
    print("输入 '/exit' 退出程序")
    print("=" * 60)
    print()

    # 设置增强版 prompt_toolkit 会话（支持 @ 文件引用和命令补全）
    session = create_command_session(
        history_file=Config.WORKSPACE_DIR / ".input_history",
        workspace_dir=str(Config.WORKSPACE_DIR.parent),  # 使用项目根目录
    )

    # 交互式对话循环
    while True:
        try:
            # 使用 async_input 获取输入
            user_input = await async_input("📝 您的问题", session=session, color="green")

            if not user_input:
                continue

            # 处理命令
            if user_input.startswith("/"):
                command = user_input.lower()

                if Commands.is_exit_command(command):
                    if Colors.supports_color():
                        print(f"\n{Colors.BRIGHT_YELLOW}👋 再见！{Colors.RESET}\n")
                    else:
                        print("\n👋 再见！\n")
                    print_stats(agent, session_start)
                    
                    # 清理 MCP 连接
                    try:
                        from mini_agent.tools.mcp_loader import cleanup_mcp_connections
                        await cleanup_mcp_connections()
                    except Exception:
                        pass  # 忽略清理错误
                    break

                elif command == Commands.HELP:
                    print_help()
                    continue

                elif command == Commands.CLEAR:
                    import os
                    os.system("clear" if os.name == "posix" else "cls")
                    print_welcome()
                    continue

                elif command == Commands.HISTORY:
                    print(f"\n{Colors.BRIGHT_CYAN}当前会话消息数: {len(agent.messages)}{Colors.RESET}\n")
                    continue

                elif command == Commands.STATS:
                    print_stats(agent, session_start)
                    continue

                else:
                    if Colors.supports_color():
                        print(f"{Colors.RED}❌ 未知命令: {user_input}{Colors.RESET}")
                        print(f"{Colors.DIM}输入 /help 查看可用命令{Colors.RESET}\n")
                    else:
                        print(f"❌ 未知命令: {user_input}")
                        print("输入 /help 查看可用命令\n")
                    continue

            # 添加用户消息并运行
            agent.add_user_message(user_input)

            if Colors.supports_color():
                print(f"\n{Colors.BRIGHT_CYAN}🤖 Agent 正在处理...{Colors.RESET}\n")
            else:
                print("\n🤖 Agent 正在处理...\n")

            try:
                result = await agent.run()
                print("\n" + "=" * 60)
                if Colors.supports_color():
                    print(f"{Colors.BRIGHT_GREEN}✅ Agent 完成{Colors.RESET}")
                else:
                    print("✅ Agent 完成")
                print("=" * 60)
                print(result)
                print()
            except Exception as e:
                if Colors.supports_color():
                    print(f"\n{Colors.RED}❌ 执行出错: {e}{Colors.RESET}")
                else:
                    print(f"\n❌ 执行出错: {e}")
                import traceback
                traceback.print_exc()

        except KeyboardInterrupt:
            if Colors.supports_color():
                print(f"\n\n{Colors.BRIGHT_YELLOW}👋 已中断，再见！{Colors.RESET}\n")
            else:
                print("\n\n👋 已中断，再见！\n")
            print_stats(agent, session_start)
            
            # 清理 MCP 连接
            try:
                from mini_agent.tools.mcp_loader import cleanup_mcp_connections
                await cleanup_mcp_connections()
            except Exception:
                pass  # 忽略清理错误
            break
        except EOFError:
            if Colors.supports_color():
                print(f"\n{Colors.BRIGHT_YELLOW}👋 再见！{Colors.RESET}\n")
            else:
                print("\n👋 再见！\n")
            print_stats(agent, session_start)
            
            # 清理 MCP 连接
            try:
                from mini_agent.tools.mcp_loader import cleanup_mcp_connections
                await cleanup_mcp_connections()
            except Exception:
                pass  # 忽略清理错误
            break


if __name__ == "__main__":
    asyncio.run(main())
