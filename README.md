# feishu-claude

飞书 x Claude Code 一键部署：**MCP Server + ChatBot 双模**

- **MCP 工具模式**：在 Claude Code 里直接操作飞书（写文档、发消息、读表格、更新 OKR）
- **ChatBot 模式**：在飞书群/私聊中和 Claude 对话，群记忆隔离，对话历史永久保存

## 安装（一行命令）

```bash
bash <(curl -s https://raw.githubusercontent.com/hiweiweiwei-bot/feishu-claude/main/setup.sh)
```

## 前置条件

- macOS + Python 3.12+（`brew install python@3.12`）
- Claude Code CLI（`npm install -g @anthropic-ai/claude-code` + `claude auth login`）
- 飞书企业自建应用（App ID + App Secret）

## 飞书后台配置

安装完成后需在飞书开放平台手动完成 2 步，详见 [docs/feishu-setup.md](docs/feishu-setup.md)

## 可用 MCP 工具（16 个）

| 工具 | 说明 |
|------|------|
| `feishu_auth` | OAuth2 用户授权 |
| `feishu_auth_status` | 查看 token 状态 |
| `feishu_switch_identity` | 切换用户/应用身份 |
| `feishu_create_document` | 创建飞书文档 |
| `feishu_get_document` | 读取文档内容 |
| `feishu_list_documents` | 搜索文档 |
| `feishu_send_message` | 发送消息 |
| `feishu_list_chats` | 列出群聊 |
| `feishu_read_sheet` | 读取表格 |
| `feishu_write_sheet` | 写入表格 |
| `feishu_query_records` | 查询多维表格 |
| `feishu_create_record` | 新增多维表格记录 |
| `feishu_get_okr` | 读取 OKR |
| `feishu_update_okr_progress` | 更新 KR 进度 |
| `feishu_add_okr_comment` | OKR 添加评论 |
| `feishu_api` | 调用任意飞书 API（通用兜底） |

## 常用命令

```bash
feishu-claude log      # 查看 Bot 实时日志
feishu-claude status   # 查看运行状态
feishu-claude stop     # 停止 Bot
feishu-claude start    # 启动 Bot
feishu-claude update   # 更新到最新版
```

## 架构

```
MCP 模式：Claude Code → feishu_claude.py --mode mcp → lark-oapi → 飞书 API
Bot 模式：飞书消息 → WebSocket → feishu_claude.py --mode bot → claude -p → 飞书回复
```
