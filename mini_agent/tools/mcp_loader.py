"""MCP tool loader with real MCP client integration."""

import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base import Tool, ToolResult

# Load environment variables from .env file if available
# This ensures MCP tools can access environment variables
def _load_env_for_mcp():
    """Load .env file for MCP tools."""
    # Try to load from common locations
    env_paths = [
        Path.cwd() / "mini_agent" / "config" / ".env",
        Path.home() / ".mini-agent" / "config" / ".env",
        Path(__file__).parent.parent / "config" / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            break

# Load environment variables at module import time
_load_env_for_mcp()


class MCPTool(Tool):
    """Wrapper for MCP tools."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        session: ClientSession,
    ):
        self._name = name
        self._description = description
        self._parameters = parameters
        self._session = session

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs) -> ToolResult:
        """Execute MCP tool via the session."""
        try:
            result = await self._session.call_tool(self._name, arguments=kwargs)

            # MCP tool results are a list of content items
            content_parts = []
            for item in result.content:
                if hasattr(item, 'text'):
                    content_parts.append(item.text)
                else:
                    content_parts.append(str(item))

            content_str = '\n'.join(content_parts)

            is_error = result.isError if hasattr(result, 'isError') else False

            return ToolResult(
                success=not is_error,
                content=content_str,
                error=None if not is_error else "Tool returned error"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"MCP tool execution failed: {str(e)}"
            )


class MCPServerConnection:
    """Manages connection to a single MCP server."""

    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str] | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.session: ClientSession | None = None
        self.exit_stack: AsyncExitStack | None = None
        self.tools: list[MCPTool] = []

    async def connect(self) -> bool:
        """Connect to the MCP server using proper async context management."""
        try:
            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=self.env if self.env else None
            )

            # Use AsyncExitStack to properly manage multiple async context managers
            self.exit_stack = AsyncExitStack()
            
            # Enter stdio client context
            read_stream, write_stream = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            # Enter client session context
            session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            self.session = session

            # Initialize the session
            await session.initialize()

            # List available tools
            tools_list = await session.list_tools()

            # Wrap each tool
            for tool in tools_list.tools:
                # Convert MCP tool schema to our format
                parameters = tool.inputSchema if hasattr(tool, 'inputSchema') else {}

                mcp_tool = MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=parameters,
                    session=session
                )
                self.tools.append(mcp_tool)

            print(f"✓ Connected to MCP server '{self.name}' - loaded {len(self.tools)} tools")
            for tool in self.tools:
                desc = tool.description[:60] if len(tool.description) > 60 else tool.description
                print(f"  - {tool.name}: {desc}...")
            return True

        except Exception as e:
            print(f"✗ Failed to connect to MCP server '{self.name}': {e}")
            # Clean up exit stack if connection failed
            if self.exit_stack:
                await self.exit_stack.aclose()
                self.exit_stack = None
            import traceback
            traceback.print_exc()
            return False

    async def disconnect(self):
        """Properly disconnect from the MCP server."""
        if self.exit_stack:
            try:
                # AsyncExitStack handles all cleanup properly
                await self.exit_stack.aclose()
            except asyncio.CancelledError:
                # Ignore CancelledError during shutdown
                # This happens when the event loop is being cancelled
                # The subprocess will be terminated when the parent process exits anyway.
                pass
            except RuntimeError as e:
                # Ignore "Attempted to exit cancel scope in a different task" error
                # This happens when cleanup is called from a different async task than
                # the one that created the connection (e.g., during KeyboardInterrupt).
                # The subprocess will be terminated when the parent process exits anyway.
                if "cancel scope" not in str(e) and "different task" not in str(e):
                    raise
            except Exception:
                # Ignore other cleanup errors during shutdown
                # The MCP server process will be killed when parent exits
                pass
            finally:
                self.exit_stack = None
                self.session = None


# Global connections registry
_mcp_connections: list[MCPServerConnection] = []


async def load_mcp_tools_async(config_path: str = "mcp.json") -> list[Tool]:
    """
    Load MCP tools from config file.

    This function:
    1. Reads the MCP config file
    2. Starts MCP server processes
    3. Connects to each server
    4. Fetches tool definitions
    5. Wraps them as Tool objects

    Args:
        config_path: Path to MCP configuration file (default: "mcp.json")

    Returns:
        List of Tool objects representing MCP tools
    """
    global _mcp_connections

    config_file = Path(config_path)

    if not config_file.exists():
        print(f"MCP config not found: {config_path}")
        return []

    try:
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)

        mcp_servers = config.get("mcpServers", {})

        if not mcp_servers:
            print("No MCP servers configured")
            return []

        all_tools = []

        # Connect to each enabled server
        for server_name, server_config in mcp_servers.items():
            if server_config.get("disabled", False):
                print(f"Skipping disabled server: {server_name}")
                continue

            command = server_config.get("command")
            args = server_config.get("args", [])
            env = server_config.get("env", {})

            if not command:
                print(f"No command specified for server: {server_name}")
                continue

            # Replace environment variables in env dict with values from os.environ
            # This allows sensitive values to be stored in .env file
            resolved_env = {}
            for key, value in env.items():
                # If value is empty string or looks like a placeholder, try to get from environment
                if not value or value.startswith("YOUR_") or value.startswith("your-"):
                    env_value = os.getenv(key)
                    if env_value:
                        resolved_env[key] = env_value
                    else:
                        # Keep original value if env var not found (might be intentionally empty)
                        resolved_env[key] = value
                else:
                    # Use value from config file as-is
                    resolved_env[key] = value

            connection = MCPServerConnection(server_name, command, args, resolved_env)
            success = await connection.connect()

            if success:
                _mcp_connections.append(connection)
                all_tools.extend(connection.tools)

        print(f"\nTotal MCP tools loaded: {len(all_tools)}")

        return all_tools

    except Exception as e:
        print(f"Error loading MCP config: {e}")
        import traceback
        traceback.print_exc()
        return []


async def cleanup_mcp_connections():
    """Clean up all MCP connections.
    
    This function safely handles cleanup errors that may occur during shutdown,
    especially when called from signal handlers or different async tasks.
    """
    global _mcp_connections
    for connection in _mcp_connections:
        try:
            await connection.disconnect()
        except (asyncio.CancelledError, Exception):
            # Ignore individual connection cleanup errors (including CancelledError)
            # The subprocess will terminate when parent exits
            pass
    _mcp_connections.clear()
