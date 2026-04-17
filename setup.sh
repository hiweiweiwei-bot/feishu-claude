#!/usr/bin/env bash
set -e

# ─────────────────────────────────────────────
# feishu-claude 一键安装脚本
# 使用: bash setup.sh
# 免交互: FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx bash setup.sh
# ─────────────────────────────────────────────

INSTALL_DIR="${FEISHU_INSTALL_DIR:-$HOME/feishu-claude}"
VENV="$INSTALL_DIR/.venv"
PYTHON="$VENV/bin/python3"
PIP="$VENV/bin/pip"
PLIST="$HOME/Library/LaunchAgents/com.feishu.claude-bot.plist"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   feishu-claude 一键安装             ║"
echo "║   MCP Server + ChatBot 双模          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Step 1: 检查前置条件 ─────────────────────
echo "Step 1/7: 检查前置条件..."

PYTHON3=$(command -v python3.12 || command -v python3 || echo "")
[ -z "$PYTHON3" ] && error "需要 Python 3.12+，安装：brew install python@3.12"

command -v claude >/dev/null 2>&1 || error "未找到 claude 命令，安装：npm install -g @anthropic-ai/claude-code"
info "前置条件检查通过"

# ── Step 2: 收集配置 ─────────────────────────
echo "Step 2/7: 配置信息..."

# 如果已有 config.json，自动读取原有值（升级时无需重新输入）
EXISTING_CONFIG="$INSTALL_DIR/config.json"
if [ -f "$EXISTING_CONFIG" ]; then
    warn "检测到已有配置文件，自动读取原有 App ID / Secret（升级模式）"
    _read_cfg() { "$PYTHON3" -c "import json; d=json.load(open('$EXISTING_CONFIG')); print(d.get('$1',''))" 2>/dev/null || echo ""; }
    [ -z "$FEISHU_APP_ID" ]     && FEISHU_APP_ID=$(_read_cfg app_id)
    [ -z "$FEISHU_APP_SECRET" ] && FEISHU_APP_SECRET=$(_read_cfg app_secret)
    [ -z "$FEISHU_PROXY" ]      && FEISHU_PROXY=$(_read_cfg proxy)
    [ -z "$FEISHU_BOT_NAME" ]   && FEISHU_BOT_NAME=$(_read_cfg bot_name)
    [ -z "$FEISHU_BOT_INTRO" ]  && FEISHU_BOT_INTRO=$(_read_cfg bot_intro)
fi

if [ -z "$FEISHU_APP_ID" ]; then
    echo "请输入飞书 App ID（https://open.feishu.cn/app 获取）："
    read -r FEISHU_APP_ID
fi

if [ -z "$FEISHU_APP_SECRET" ]; then
    echo "请输入飞书 App Secret："
    read -r -s FEISHU_APP_SECRET
    echo ""
fi

[ -z "$FEISHU_APP_ID" ] && error "App ID 不能为空"
[ -z "$FEISHU_APP_SECRET" ] && error "App Secret 不能为空"

PROXY="${FEISHU_PROXY:-}"
BOT_NAME="${FEISHU_BOT_NAME:-飞书助手}"
BOT_INTRO="${FEISHU_BOT_INTRO:-Claude Code AI 助手}"

info "配置收集完成"

# ── Step 3: 创建目录 + venv ──────────────────
echo "Step 3/7: 创建虚拟环境..."
mkdir -p "$INSTALL_DIR"/{workspace/groups,workspace_templates}
"$PYTHON3" -m venv "$VENV"
"$PIP" install --upgrade pip -q
"$PIP" install lark-oapi "mcp[cli]" httpx -q
info "依赖安装完成"

# ── Step 4: 写入主文件 ───────────────────────
echo "Step 4/7: 写入程序文件..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/feishu_claude.py" ]; then
    cp "$SCRIPT_DIR/feishu_claude.py" "$INSTALL_DIR/feishu_claude.py"
else
    error "未找到 feishu_claude.py，请确认 setup.sh 和 feishu_claude.py 在同一目录"
fi

cat > "$INSTALL_DIR/config.json" << EOF
{
  "app_id": "$FEISHU_APP_ID",
  "app_secret": "$FEISHU_APP_SECRET",
  "proxy": "$PROXY",
  "work_dir": "$INSTALL_DIR",
  "bot_name": "$BOT_NAME",
  "bot_intro": "$BOT_INTRO"
}
EOF

WORKSPACE="$INSTALL_DIR/workspace"
for f in IDENTITY.md SOUL.md USER.md; do
    [ ! -f "$WORKSPACE/$f" ] && [ -f "$SCRIPT_DIR/workspace_templates/$f" ] && \
        cp "$SCRIPT_DIR/workspace_templates/$f" "$WORKSPACE/$f"
done
touch "$WORKSPACE/MEMORY.md"
info "程序文件写入完成"

# ── Step 5: 配置 Claude Code settings.json ──
echo "Step 5/7: 配置 Claude Code MCP..."
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
mkdir -p "$(dirname "$CLAUDE_SETTINGS")"

if [ ! -f "$CLAUDE_SETTINGS" ]; then
    echo '{}' > "$CLAUDE_SETTINGS"
fi

"$PYTHON" - << PYEOF
import json
path = "$CLAUDE_SETTINGS"
with open(path) as f:
    cfg = json.load(f)
cfg.setdefault("mcpServers", {})["feishu"] = {
    "command": "$PYTHON",
    "args": ["$INSTALL_DIR/feishu_claude.py", "--mode", "mcp"]
}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print("MCP 配置写入成功")
PYEOF
info "Claude Code MCP 配置完成"

# ── Step 6: OAuth2 授权 ──────────────────────
echo "Step 6/7: 飞书 OAuth2 授权..."
echo ""
warn "即将打开浏览器，请使用你的飞书账号登录并授权"
warn "授权完成后浏览器会显示成功提示，请关闭页面"
echo ""
"$PYTHON" - << PYEOF
import sys
sys.path.insert(0, "$INSTALL_DIR")
from feishu_claude import Config, Auth
cfg = Config("$INSTALL_DIR/config.json")
auth = Auth(cfg.app_id, cfg.app_secret, cfg.proxy)
auth.do_oauth()
PYEOF
info "OAuth2 授权完成"

# ── Step 7: launchd 开机自启 ─────────────────
echo "Step 7/7: 配置 Bot 开机自启..."
PROXY_ENV=""
if [ -n "$PROXY" ]; then
    PROXY_ENV="<key>HTTPS_PROXY</key><string>$PROXY</string>"
fi

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.feishu.claude-bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$INSTALL_DIR/feishu_claude.py</string>
        <string>--mode</string>
        <string>bot</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        $PROXY_ENV
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/feishu-claude-bot.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/feishu-claude-bot.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
info "Bot 已启动并设置开机自启"

# ── 注册 feishu-claude 命令 ──────────────────
sudo tee /usr/local/bin/feishu-claude > /dev/null << EOF
#!/usr/bin/env bash
case "\$1" in
    update)
        bash <(curl -s https://raw.githubusercontent.com/hiweiweiwei-bot/feishu-claude/main/setup.sh)
        ;;
    stop)
        launchctl unload "$PLIST"
        echo "Bot 已停止"
        ;;
    start)
        launchctl load "$PLIST"
        echo "Bot 已启动"
        ;;
    log)
        tail -f /tmp/feishu-claude-bot.log
        ;;
    status)
        launchctl list | grep feishu-claude || echo "Bot 未运行"
        ;;
    *)
        echo "用法: feishu-claude [update|start|stop|log|status]"
        ;;
esac
EOF
sudo chmod +x /usr/local/bin/feishu-claude

# ── 完成提示 ────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ✅ feishu-claude 安装完成！                        ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  【还需手动完成 2 步（飞书后台）】                   ║"
echo "║                                                      ║"
echo "║  1. 开通权限：开放平台 → 权限管理 → 开通：          ║"
echo "║     im:message / docx:document / sheets:spreadsheet  ║"
echo "║     bitable:app / okr:okr:write / drive:drive 等     ║"
echo "║                                                      ║"
echo "║  2. 事件订阅：事件与回调 → WebSocket 模式           ║"
echo "║     → 添加事件：im.message.receive_v1               ║"
echo "║                                                      ║"
echo "║  完成后在飞书给机器人发一条消息验证 ✓               ║"
echo "║                                                      ║"
echo "║  常用命令：                                          ║"
echo "║    feishu-claude log      查看 Bot 日志             ║"
echo "║    feishu-claude status   查看运行状态              ║"
echo "║    feishu-claude update   更新到最新版              ║"
echo "╚══════════════════════════════════════════════════════╝"
