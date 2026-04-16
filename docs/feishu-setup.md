# 飞书后台配置指引

安装脚本完成后，需在飞书开放平台手动完成以下 2 步。

## 第 1 步：开通权限

进入 [飞书开放平台](https://open.feishu.cn/app) → 选择你的应用 → 左侧菜单「权限管理」

搜索并开通以下权限：

| 权限 | 说明 |
|------|------|
| `im:chat:readonly` | 读取会话列表 |
| `im:message:readonly` | 读取消息内容 |
| `im:message` | 发送消息 |
| `docx:document` | 读写飞书文档 |
| `sheets:spreadsheet` | 读写电子表格 |
| `drive:drive` | 云空间操作 |
| `bitable:app` | 读写多维表格 |
| `okr:okr:readonly` | 读取 OKR |
| `okr:okr:write` | 更新 OKR |
| `search:docs:read` | 搜索文档 |

开通后点击「申请发布」，等待管理员审批。

## 第 2 步：开通事件订阅（Bot 模式必须）

左侧菜单「事件与回调」→「事件订阅」

1. 选择「使用 WebSocket 方式接收事件」
2. 点击「添加事件」→ 搜索 `im.message.receive_v1` → 开通
3. 保存

## 验证

完成后在飞书给机器人发一条消息，收到回复即表示配置成功。

## 常见问题

**权限申请一直待审批？**
企业版需要管理员审批，联系飞书管理员开通。

**Bot 不响应群消息？**
群聊必须 @机器人 才会响应，私聊直接发消息即可。

**token 过期了怎么办？**
在 Claude Code 中调用 `feishu_auth` 工具重新授权。
