# feishu-claude Windows Setup Script
# Usage: powershell -ExecutionPolicy Bypass -File setup_windows.ps1

param(
    [string]$AppId = $env:FEISHU_APP_ID,
    [string]$AppSecret = $env:FEISHU_APP_SECRET,
    [string]$Proxy = $env:FEISHU_PROXY,
    [string]$BotName = "",
    [string]$BotIntro = ""
)

$ErrorActionPreference = "Stop"
$INSTALL_DIR = if ($env:FEISHU_INSTALL_DIR) { $env:FEISHU_INSTALL_DIR } else { "$HOME\feishu-claude" }
$VENV = "$INSTALL_DIR\.venv"
$PYTHON = "$VENV\Scripts\python.exe"
$PIP = "$VENV\Scripts\pip.exe"
$CLAUDE_SETTINGS = "$HOME\.claude\settings.json"
$SCRIPT_URL = "https://raw.githubusercontent.com/hiweiweiwei-bot/feishu-claude/main/feishu_claude.py"

function Write-Step { param($n, $msg) Write-Host "`n[$n/7] $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "[X] $msg" -ForegroundColor Red; exit 1 }

Write-Host @"

  ============================================
    feishu-claude  Windows Installer
    MCP Server + ChatBot
  ============================================

"@ -ForegroundColor Cyan

# ── Step 1: Prerequisites ─────────────────────────────────────────
Write-Step 1 "Checking prerequisites..."

# Find Python 3.12+
$pythonCmd = $null
foreach ($cmd in @("python3", "python")) {
    $p = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($p) {
        $ver = & $p.Source --version 2>&1
        if ($ver -match "(\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 12) {
                $pythonCmd = $p.Source
                break
            }
        }
    }
}
if (-not $pythonCmd) { Write-Err "Python 3.12+ required. Download from https://python.org" }
Write-Ok "Python: $pythonCmd"

# Check claude CLI
$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudeCmd) { Write-Err "claude CLI not found. Install: npm install -g @anthropic-ai/claude-code" }
Write-Ok "Claude CLI: $($claudeCmd.Source)"

# ── Step 2: Configuration ─────────────────────────────────────────
Write-Step 2 "Collecting configuration..."

$IsUpgrade = $false
$configPath = "$INSTALL_DIR\config.json"

if (Test-Path $configPath) {
    $IsUpgrade = $true
    Write-Warn "Detected existing installation, reading config..."
    $oldCfg = Get-Content $configPath -Raw | ConvertFrom-Json
    if (-not $AppId)     { $AppId     = $oldCfg.app_id }
    if (-not $AppSecret) { $AppSecret = $oldCfg.app_secret }
    if (-not $Proxy)     { $Proxy     = $oldCfg.proxy }
    if (-not $BotName)   { $BotName   = $oldCfg.bot_name }
    if (-not $BotIntro)  { $BotIntro  = $oldCfg.bot_intro }
}

if (-not $AppId) {
    $AppId = Read-Host "Feishu App ID"
}
if (-not $AppSecret) {
    $AppSecret = Read-Host "Feishu App Secret"
}
if (-not $BotName) {
    $BotName = Read-Host "Bot name (default: Claude)"
    if (-not $BotName) { $BotName = "Claude" }
}
if (-not $BotIntro) {
    $BotIntro = Read-Host "Bot intro (default: AI assistant)"
    if (-not $BotIntro) { $BotIntro = "AI assistant powered by Claude" }
}

if ($AppId.Length -ge 4) { Write-Ok "App ID: $($AppId.Substring(0,4))****" } else { Write-Ok "App ID: $AppId" }

# ── Step 3: Virtual Environment ───────────────────────────────────
Write-Step 3 "Setting up Python virtual environment..."

New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\workspace\groups" | Out-Null
New-Item -ItemType Directory -Force -Path "$INSTALL_DIR\workspace_templates" | Out-Null

if (-not (Test-Path $VENV)) {
    & $pythonCmd -m venv $VENV
    Write-Ok "venv created"
} else {
    Write-Ok "venv already exists"
}

# Clear SOCKS proxy (causes pip failures without PySocks)
$env:ALL_PROXY = ""
$env:HTTPS_PROXY = ""
$env:HTTP_PROXY = ""
$MIRROR_ARGS = @("-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "--trusted-host", "pypi.tuna.tsinghua.edu.cn")
& $PYTHON -m pip install --upgrade pip -q @MIRROR_ARGS 2>$null
& $PYTHON -m pip install lark-oapi "mcp[cli]>=1.2,<1.27" httpx pysocks @MIRROR_ARGS
Write-Ok "Dependencies installed"

# ── Step 4: Deploy files ──────────────────────────────────────────
Write-Step 4 "Deploying program files..."

# Download feishu_claude.py
try {
    Invoke-WebRequest -Uri $SCRIPT_URL -OutFile "$INSTALL_DIR\feishu_claude.py" -UseBasicParsing
    Write-Ok "feishu_claude.py downloaded"
} catch {
    Write-Warn "Download failed, checking if local copy exists..."
    if (-not (Test-Path "$INSTALL_DIR\feishu_claude.py")) {
        Write-Err "feishu_claude.py not found. Place it manually in $INSTALL_DIR"
    }
}

# Apply Windows compatibility patch (encoding + chmod fix)
$patchScript = @"
import sys, re

path = r'$INSTALL_DIR\feishu_claude.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add encoding fix after imports if not present
if 'stdout.reconfigure' not in code:
    # Insert after the first import block
    import_end = code.find('\n\n', code.find('import '))
    if import_end > 0:
        patch = '\nimport sys as _sys\nif hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")\nif hasattr(_sys.stderr, "reconfigure"): _sys.stderr.reconfigure(encoding="utf-8")\n'
        code = code[:import_end] + patch + code[import_end:]

# 2. Fix os.chmod(tmp, 0o600) to be platform-aware
code = code.replace(
    'os.chmod(tmp, 0o600)',
    'os.chmod(tmp, 0o600) if os.name != "nt" else None  # Unix-only permission'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)

print('Patches applied')
"@
$patchFile = "$INSTALL_DIR\_patch_win.py"
Set-Content -Path $patchFile -Value $patchScript -Encoding UTF8
& $PYTHON $patchFile
Remove-Item $patchFile -ErrorAction SilentlyContinue

# Write config.json
$config = @{
    app_id     = $AppId
    app_secret = $AppSecret
    proxy      = $Proxy
    work_dir   = $INSTALL_DIR
    bot_name   = $BotName
    bot_intro  = $BotIntro
} | ConvertTo-Json -Depth 3
# Write without BOM (PowerShell 5.x UTF8 adds BOM which breaks Python json.load)
[IO.File]::WriteAllText($configPath, $config, [System.Text.UTF8Encoding]::new($false))
Write-Ok "config.json written"

# Deploy workspace templates (only if not exists)
$templates = @{
    "IDENTITY.md" = @"
# $BotName

You are $BotName, a Feishu bot powered by Claude.

## Capabilities
- Answer questions and have conversations
- Access Feishu documents, sheets, and bitable
- Help with OKR management
"@
    "SOUL.md" = @"
## Behavior Guidelines
- Be concise and direct
- Have opinions, back them with reasoning
- Never fabricate information
"@
    "USER.md" = @"
## User Context
- Timezone: Asia/Shanghai
"@
}

foreach ($file in $templates.Keys) {
    $dest = "$INSTALL_DIR\workspace\$file"
    if (-not (Test-Path $dest)) {
        Set-Content -Path $dest -Value $templates[$file] -Encoding UTF8
    }
}

# Ensure MEMORY.md exists
$memPath = "$INSTALL_DIR\workspace\MEMORY.md"
if (-not (Test-Path $memPath)) { New-Item -Path $memPath -ItemType File | Out-Null }

Write-Ok "Workspace templates deployed"

# ── Step 5: Claude Code MCP config ────────────────────────────────
Write-Step 5 "Configuring Claude Code MCP server..."

$settingsDir = Split-Path $CLAUDE_SETTINGS
if (-not (Test-Path $settingsDir)) {
    New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null
}
if (-not (Test-Path $CLAUDE_SETTINGS)) {
    [IO.File]::WriteAllText($CLAUDE_SETTINGS, '{}', [System.Text.UTF8Encoding]::new($false))
}

$mcpScript = @"
import json, sys

path = r'$CLAUDE_SETTINGS'
with open(path, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

cfg.setdefault('mcpServers', {})['feishu'] = {
    'command': r'$PYTHON',
    'args': [r'$INSTALL_DIR\feishu_claude.py', '--mode', 'mcp']
}

with open(path, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)

print('MCP server registered')
"@
$mcpFile = "$INSTALL_DIR\_mcp_config.py"
Set-Content -Path $mcpFile -Value $mcpScript -Encoding UTF8
& $PYTHON $mcpFile
Remove-Item $mcpFile -ErrorAction SilentlyContinue
Write-Ok "feishu MCP server registered in Claude Code"

# ── Step 6: OAuth2 Authorization ──────────────────────────────────
Write-Step 6 "Starting OAuth2 authorization..."

$oauthScript = @"
import sys
sys.path.insert(0, r'$INSTALL_DIR')
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from feishu_claude import Config, Auth
cfg = Config(r'$configPath')
auth = Auth(cfg.app_id, cfg.app_secret, cfg.proxy)
auth.do_oauth()
print('Authorization complete')
"@
$oauthFile = "$INSTALL_DIR\_oauth.py"
Set-Content -Path $oauthFile -Value $oauthScript -Encoding UTF8

try {
    & $PYTHON $oauthFile
    Write-Ok "OAuth2 authorization complete"
} catch {
    Write-Warn "OAuth failed: $($_.Exception.Message)"
    Write-Warn "You can retry later: & '$PYTHON' '$oauthFile'"
}
Remove-Item $oauthFile -ErrorAction SilentlyContinue

# ── Step 7: Management command + auto-start ───────────────────────
Write-Step 7 "Setting up management command and auto-start..."

# Create feishu-claude.cmd management command
$cmdContent = @"
@echo off
setlocal
set INSTALL_DIR=$INSTALL_DIR
set PYTHON=$PYTHON
set LOG_FILE=%INSTALL_DIR%\bot.log

if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="log" goto log
if "%1"=="status" goto status
if "%1"=="update" goto update
goto usage

:start
echo Starting feishu-claude bot...
start /b "" "%PYTHON%" "%INSTALL_DIR%\feishu_claude.py" "--mode" "bot" > "%LOG_FILE%" 2>&1
echo Bot started. Log: %LOG_FILE%
goto end

:stop
echo Stopping feishu-claude bot...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /v ^| findstr "feishu_claude"') do taskkill /pid %%i /f 2>nul
echo Bot stopped.
goto end

:log
if exist "%LOG_FILE%" (type "%LOG_FILE%" & echo. & echo --- Press Ctrl+C to exit --- & powershell -c "Get-Content '%LOG_FILE%' -Wait -Tail 20")
goto end

:status
tasklist /fi "imagename eq python.exe" /v 2>nul | findstr "feishu_claude" >nul 2>&1
if %errorlevel%==0 (echo feishu-claude bot is running) else (echo feishu-claude bot is NOT running)
goto end

:update
powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/hiweiweiwei-bot/feishu-claude/main/setup_windows.ps1' -OutFile '%TEMP%\setup_windows.ps1' -UseBasicParsing; & '%TEMP%\setup_windows.ps1'"
goto end

:usage
echo Usage: feishu-claude [start^|stop^|log^|status^|update]
goto end

:end
endlocal
"@
$cmdPath = "$INSTALL_DIR\feishu-claude.cmd"
Set-Content -Path $cmdPath -Value $cmdContent -Encoding ASCII
Write-Ok "Management command created: $cmdPath"

# Add to PATH if not already there
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$INSTALL_DIR*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$INSTALL_DIR", "User")
    Write-Ok "Added $INSTALL_DIR to user PATH (restart terminal to take effect)"
} else {
    Write-Ok "$INSTALL_DIR already in PATH"
}

# Create startup shortcut (replaces launchd)
$startupFolder = [Environment]::GetFolderPath("Startup")
$shortcutPath = "$startupFolder\feishu-claude-bot.lnk"

$createShortcut = Read-Host "Enable auto-start on login? (y/n, default: y)"
if ($createShortcut -ne "n") {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $PYTHON
    $shortcut.Arguments = "`"$INSTALL_DIR\feishu_claude.py`" --mode bot"
    $shortcut.WorkingDirectory = $INSTALL_DIR
    $shortcut.WindowStyle = 7  # Minimized
    $shortcut.Description = "feishu-claude bot auto-start"
    $shortcut.Save()
    Write-Ok "Auto-start shortcut created in Startup folder"
} else {
    if (Test-Path $shortcutPath) { Remove-Item $shortcutPath }
    Write-Ok "Auto-start disabled"
}

# ── Done ──────────────────────────────────────────────────────────
Write-Host @"

  ============================================
    Installation Complete!
  ============================================

  Install dir:  $INSTALL_DIR
  MCP mode:     Restart Claude Code, feishu tools will be available
  Bot mode:     feishu-claude start

  Commands:
    feishu-claude start    - Start the bot
    feishu-claude stop     - Stop the bot
    feishu-claude log      - View bot logs
    feishu-claude status   - Check if bot is running
    feishu-claude update   - Update to latest version

  IMPORTANT: Complete these steps in Feishu admin console:
  1. Enable bot capabilities (robot)
  2. Add permissions: im:message, im:chat, docx:document, etc.
  3. Enable WebSocket and subscribe to im.message.receive_v1
  4. Publish the app version

"@ -ForegroundColor Green
