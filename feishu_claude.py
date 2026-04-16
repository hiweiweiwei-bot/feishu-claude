#!/usr/bin/env python3
"""feishu-claude: 飞书 x Claude Code 双模工具（MCP Server + ChatBot）"""

import json, os
from pathlib import Path

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

DEFAULT_WORK_DIR = str(Path.home() / "feishu-claude")

class Config:
    def __init__(self, path: str = None):
        self.path = path or str(Path.home() / "feishu-claude" / "config.json")
        self.app_id: str = ""
        self.app_secret: str = ""
        self.proxy: str = ""
        self.work_dir: str = DEFAULT_WORK_DIR
        self.bot_name: str = "飞书助手"
        self.bot_intro: str = "Claude Code AI 助手"
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                data = json.load(f)
            self.app_id = data.get("app_id", self.app_id)
            self.app_secret = data.get("app_secret", self.app_secret)
            self.proxy = data.get("proxy", self.proxy)
            self.work_dir = data.get("work_dir", self.work_dir)
            self.bot_name = data.get("bot_name", self.bot_name)
            self.bot_intro = data.get("bot_intro", self.bot_intro)

    def save(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump({
                "app_id": self.app_id,
                "app_secret": self.app_secret,
                "proxy": self.proxy,
                "work_dir": self.work_dir,
                "bot_name": self.bot_name,
                "bot_intro": self.bot_intro,
            }, f, indent=2, ensure_ascii=False)

    def ensure_dirs(self):
        workspace = os.path.join(self.work_dir, "workspace")
        groups = os.path.join(workspace, "groups")   # 嵌套在 workspace 下
        os.makedirs(groups, exist_ok=True)           # makedirs 会同时创建父目录
        return workspace

# ─────────────────────────────────────────────
# Memory
# ─────────────────────────────────────────────

MAX_HISTORY = 50

class Memory:
    def __init__(self, workspace: str, chat_id: str):
        self.workspace = workspace
        self.chat_id = chat_id
        self.group_dir = os.path.join(workspace, "groups", chat_id)
        os.makedirs(self.group_dir, exist_ok=True)
        self.history_path = os.path.join(self.group_dir, "history.json")
        self.group_memory_path = os.path.join(self.group_dir, "MEMORY.md")
        self.history: list[dict] = self._load_history()

    def _load_history(self) -> list[dict]:
        if os.path.exists(self.history_path):
            with open(self.history_path) as f:
                return json.load(f)
        return []

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    def save_history(self):
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def _read_file(self, path: str) -> str:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def build_system_prompt(self) -> str:
        parts = []
        for filename in ["IDENTITY.md", "SOUL.md", "USER.md", "MEMORY.md"]:
            content = self._read_file(os.path.join(self.workspace, filename))
            if content:
                parts.append(content)
        group_mem = self._read_file(self.group_memory_path)
        if group_mem:
            parts.append(f"## 本群记忆\n{group_mem}")
        return "\n\n---\n\n".join(parts)
