---
name: knowledge-note-generator
description: 使用 Banana API 生成知识笔记可视化图。支持思维导图、卡片、时间线、层级图、信息图等多种样式。当用户需要将知识点可视化、生成学习笔记图、知识总结图时使用此skill。
license: Apache 2.0
---

# Knowledge Note Generator Skill

使用 Banana API 生成专业的知识笔记可视化图。

## 使用场景

- 将知识点可视化为图片
- 生成学习笔记配图
- 创建知识总结图
- 制作 PPT/文档的知识图示

## 使用方法

通过 `scripts/generate_note.py` 脚本生成知识笔记图：

```bash
python .claude/skills/knowledge-note-generator/scripts/generate_note.py \
  --topic "主题名称" \
  --content "知识要点1; 知识要点2; 知识要点3" \
  --style card \
  --image-size 2K \
  --aspect-ratio 16:9
```

## 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--topic` | 是 | - | 笔记主题 |
| `--content` | 是 | - | 知识要点（用分号或换行分隔） |
| `--style` | 否 | card | 图表样式 |
| `--custom-style` | 否 | - | 自定义样式描述 |
| `--aspect-ratio` | 否 | 16:9 | 宽高比 (1:1, 4:3, 16:9, 3:4, 9:16) |
| `--image-size` | 否 | 2K | 尺寸 (256, 512, 1K, 2K) |
| `--output-filename` | 否 | 时间戳 | 输出文件名 |
| `--output-dir` | 否 | knowledge_notes | 输出目录 |

## 样式选项

| 样式 | 说明 |
|------|------|
| `mindmap` | 思维导图 - 中心发散式布局 |
| `card` | 卡片式 - 清晰的卡片排列 |
| `timeline` | 时间线 - 线性流程展示 |
| `hierarchy` | 层级图 - 金字塔/树状结构 |
| `infographic` | 信息图 - 图标+数据+文字混合 |

## 示例

### 生成 Python 基础知识卡片
```bash
python .claude/skills/knowledge-note-generator/scripts/generate_note.py \
  --topic "Python 基础语法" \
  --content "变量与数据类型; 条件判断 if/else; 循环 for/while; 函数定义 def; 列表与字典" \
  --style card
```

### 生成机器学习流程图
```bash
python .claude/skills/knowledge-note-generator/scripts/generate_note.py \
  --topic "机器学习流程" \
  --content "数据收集 -> 数据预处理 -> 特征工程 -> 模型训练 -> 模型评估 -> 部署上线" \
  --style timeline
```

### 生成思维导图
```bash
python .claude/skills/knowledge-note-generator/scripts/generate_note.py \
  --topic "设计模式" \
  --content "创建型: 单例、工厂、建造者; 结构型: 适配器、装饰器、代理; 行为型: 观察者、策略、命令" \
  --style mindmap
```

## 环境配置

确保 `BANANA_API_KEY` 已配置（环境变量或 `.env` 文件）。

## 依赖

需要安装: `pip install requests pillow python-dotenv`

## 工作流程

### 第一步：准备知识内容

整理要可视化的知识点：
- 列出主题和核心概念
- 梳理知识点之间的关系
- 确定展示样式（思维导图、卡片、时间线等）

### 第二步：选择合适的样式

| 场景 | 推荐样式 |
|------|----------|
| 概念总结、知识归纳 | `card` 卡片式 |
| 知识结构、主题发散 | `mindmap` 思维导图 |
| 流程步骤、发展历程 | `timeline` 时间线 |
| 层级关系、组织架构 | `hierarchy` 层级图 |
| 数据展示、多维信息 | `infographic` 信息图 |

### 第三步：执行生成

```bash
python .claude/skills/knowledge-note-generator/scripts/generate_note.py \
  --topic "你的主题" \
  --content "要点1; 要点2; 要点3" \
  --style card \
  --image-size 2K
```

### 第四步：检查输出

- 图片默认保存到 `knowledge_notes/` 目录
- API 日志保存到 `banana_logs/` 目录

## 最佳实践

### Prompt 设计技巧

1. **主题要明确**：使用简洁有力的主题名称
2. **要点要结构化**：用分号或换行分隔不同要点
3. **层级要清晰**：使用冒号表示子分类（如 "创建型: 单例、工厂"）
4. **流程用箭头**：时间线样式建议用 "->" 连接步骤

### 内容组织建议

```
# 好的示例
--content "变量与数据类型; 条件判断; 循环语句; 函数定义"

# 更好的示例（带层级）
--content "数据类型: 整数、浮点、字符串; 控制流: if/else、for、while; 函数: 定义、参数、返回值"
```

## 故障排除

**问题：API Key 未找到**
- 检查环境变量 `BANANA_API_KEY` 是否设置
- 检查项目根目录是否有 `.env` 文件

**问题：生成的文字不清晰**
- 使用 `--image-size 2K` 获取更高分辨率
- 减少单张图的知识点数量

**问题：布局不理想**
- 尝试不同的 `--style` 选项
- 使用 `--custom-style` 自定义布局描述

## 备注

- 所有图片使用 PNG 格式保存
- 默认使用微软雅黑字体确保中文清晰
- 支持 16:9（横版）、9:16（竖版）等多种比例
- 适合用于 PPT、文档、博客、社交媒体等场景
