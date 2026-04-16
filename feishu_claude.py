#!/usr/bin/env python3
"""feishu-claude: 飞书 x Claude Code 双模工具（MCP Server + ChatBot）"""

import json, os, sys, argparse
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
            self.app_id = data.get("app_id", "")
            self.app_secret = data.get("app_secret", "")
            self.proxy = data.get("proxy", "")
            self.work_dir = data.get("work_dir", DEFAULT_WORK_DIR)
            self.bot_name = data.get("bot_name", "飞书助手")
            self.bot_intro = data.get("bot_intro", "Claude Code AI 助手")

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
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
