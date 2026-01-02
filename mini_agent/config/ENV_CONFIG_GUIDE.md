# 环境变量配置指南

## 概述

为了安全地管理敏感信息（如 API Key），Mini-Agent 现在支持使用 `.env` 文件来存储这些信息。敏感信息不再需要直接写在配置文件中。

## 配置优先级

系统会按以下优先级顺序查找 `.env` 文件：

1. `mini_agent/config/.env` - 开发模式（当前目录）
2. `~/.mini-agent/config/.env` - 用户配置目录
3. `<package>/mini_agent/config/.env` - 包安装目录
4. `.env` - 项目根目录

## 快速开始

### 1. 创建 .env 文件

复制示例文件并填写你的实际值：

```bash
# 在 mini_agent/config/ 目录下
cp .env.example .env

# 或者使用绝对路径
cp mini_agent/config/.env.example mini_agent/config/.env
```

### 2. 配置 API Key

编辑 `.env` 文件，设置你的 API Key：

```bash
MINIMAX_API_KEY=your_actual_api_key_here
```

### 3. 配置 MCP 工具

在 `mcp.json` 中，你可以将敏感信息留空或设置为空字符串，系统会自动从环境变量读取：

```json
{
  "mcpServers": {
    "minimax": {
      "env": {
        "MINIMAX_API_KEY": "",
        "JINA_API_KEY": "",
        "SERPER_API_KEY": ""
      }
    }
  }
}
```

系统会自动从 `.env` 文件中读取对应的环境变量值。

## 支持的环境变量

### LLM 配置

- `MINIMAX_API_KEY` - MiniMax API Key（必需）
- `MINIMAX_API_BASE` - API 基础 URL（可选，默认：https://api.minimax.io）
- `MINIMAX_MODEL` - 模型名称（可选，默认：MiniMax-M2.1）
- `LLM_PROVIDER` - LLM 提供商（可选，默认：anthropic）

### MCP 工具配置

- `MINIMAX_API_KEY` - MiniMax MCP 服务器 API Key
- `JINA_API_KEY` - Jina API Key（用于搜索功能）
- `SERPER_API_KEY` - Serper API Key（用于搜索功能）

## 配置示例

### .env 文件示例

```bash
# LLM 配置
MINIMAX_API_KEY=your_minimax_api_key_here
MINIMAX_API_BASE=https://api.minimaxi.com
MINIMAX_MODEL=MiniMax-M2.1
LLM_PROVIDER=anthropic

# MCP 工具配置
JINA_API_KEY=your_jina_api_key_here
SERPER_API_KEY=your_serper_api_key_here
```

### config.yaml 配置

在 `config.yaml` 中，`api_key` 字段现在是可选的。如果设置了环境变量，系统会优先使用环境变量：

```yaml
# api_key 字段可以省略，系统会从环境变量读取
# api_key: "YOUR_API_KEY_HERE"  # 可选，推荐使用环境变量

api_base: "https://api.minimax.io"
model: "MiniMax-M2.1"
provider: "anthropic"
```

### mcp.json 配置

在 `mcp.json` 中，敏感信息可以留空，系统会自动从环境变量读取：

```json
{
  "mcpServers": {
    "minimax": {
      "env": {
        "MINIMAX_API_KEY": "",
        "MINIMAX_MCP_BASE_PATH": "./workspace/images",
        "MINIMAX_API_HOST": "https://api.minimaxi.com"
      }
    }
  }
}
```

## 安全提示

1. **永远不要将 `.env` 文件提交到 Git**
   - `.env` 文件已经在 `.gitignore` 中被忽略
   - 只提交 `.env.example` 作为模板

2. **使用不同的 API Key**
   - 为不同环境（开发、测试、生产）使用不同的 API Key
   - 定期轮换 API Key

3. **保护 .env 文件权限**
   ```bash
   chmod 600 .env  # 仅所有者可读写
   ```

## 迁移指南

如果你之前已经在 `config.yaml` 或 `mcp.json` 中配置了 API Key：

1. 创建 `.env` 文件
2. 将 API Key 从配置文件中移动到 `.env` 文件
3. 在配置文件中移除或注释掉 API Key
4. 对于 `mcp.json`，将敏感字段设置为空字符串

## 故障排除

### 问题：找不到 API Key

**错误信息：**
```
ValueError: Please configure a valid API Key. Set MINIMAX_API_KEY environment variable or configure api_key in config.yaml
```

**解决方案：**
1. 确保 `.env` 文件存在于正确的目录
2. 检查 `.env` 文件中的 `MINIMAX_API_KEY` 是否正确设置
3. 确保 `.env` 文件格式正确（每行一个变量，使用 `KEY=value` 格式）

### 问题：MCP 工具无法连接

**可能原因：**
- MCP 配置中的 API Key 未正确设置
- 环境变量名称不匹配

**解决方案：**
1. 检查 `mcp.json` 中的环境变量名称
2. 确保 `.env` 文件中有对应的环境变量
3. 确保环境变量名称完全匹配（区分大小写）

## 更多信息

- 查看 `config-example.yaml` 了解完整的配置选项
- 查看 `mcp.json.example` 了解 MCP 配置示例

