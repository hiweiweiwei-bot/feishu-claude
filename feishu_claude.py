#!/usr/bin/env python3
"""feishu-claude: 飞书 x Claude Code 双模工具（MCP Server + ChatBot）"""

import json, os
from pathlib import Path


# Windows encoding fix
import sys as _sys
if hasattr(_sys.stdout, "reconfigure"): _sys.stdout.reconfigure(encoding="utf-8")
if hasattr(_sys.stderr, "reconfigure"): _sys.stderr.reconfigure(encoding="utf-8")

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
            try:
                with open(self.history_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return []
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

# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

import time, warnings, webbrowser, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import httpx

OAUTH_PORT = 19823
REDIRECT_URI = f"http://localhost:{OAUTH_PORT}/callback"
TOKEN_PATH = str(Path.home() / ".feishu-claude-tokens.json")

# 所有工具所需的 OAuth scope（一次申请，覆盖全部工具）
OAUTH_SCOPES = " ".join([
    "offline_access",
    "im:chat:readonly", "im:message:readonly", "im:message",
    "docx:document", "docx:document:readonly",
    "sheets:spreadsheet", "drive:drive", "search:docs:read",
    "bitable:app", "bitable:app:readonly",
    "task:task:write", "calendar:calendar:readonly",
    "okr:okr:readonly",
])

class _OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.server.auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>授权成功，请关闭此页面返回终端。</h2>".encode())
    def log_message(self, *args): pass  # 静默日志

class Auth:
    def __init__(self, app_id: str, app_secret: str, proxy: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        self.proxy = proxy
        self._tokens: dict = self._load_tokens()
        self._identity = "user"  # "user" | "app"

    def _http(self) -> httpx.Client:
        kwargs = {"timeout": 30}
        if self.proxy:
            kwargs["proxy"] = self.proxy  # httpx 0.28+ uses 'proxy' instead of 'proxies'
        return httpx.Client(**kwargs)

    def _load_tokens(self) -> dict:
        if os.path.exists(TOKEN_PATH):
            try:
                with open(TOKEN_PATH) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_tokens(self):
        tmp = TOKEN_PATH + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(self._tokens, f, indent=2)
            os.chmod(tmp, 0o600) if os.name != "nt" else None
            os.replace(tmp, TOKEN_PATH)  # POSIX 原子操作
        except OSError as e:
            warnings.warn(f"token 持久化失败（本次会话仍有效）：{e}")
            try:
                os.unlink(tmp)
            except OSError:
                pass

    # ── OAuth2 用户授权 ──────────────────────────
    def do_oauth(self):
        """打开浏览器完成 OAuth2 授权，获取 user_access_token"""
        auth_url = (
            f"https://open.feishu.cn/open-apis/authen/v1/authorize"
            f"?app_id={self.app_id}"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
            f"&scope={urllib.parse.quote(OAUTH_SCOPES)}"
            f"&state=feishu-claude"
        )
        server = HTTPServer(("localhost", OAUTH_PORT), _OAuthHandler)
        server.auth_code = None
        print(f"\n正在打开浏览器授权，若未自动打开请手动访问：\n{auth_url}\n")
        webbrowser.open(auth_url)
        while not server.auth_code:
            server.handle_request()
        code = server.auth_code
        if not code:
            raise RuntimeError("未获取到授权码，请重试")
        self._exchange_code(code)
        print("✅ OAuth2 授权成功")

    def _exchange_code(self, code: str):
        with self._http() as client:
            resp = client.post(
                "https://open.feishu.cn/open-apis/authen/v2/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                    "redirect_uri": REDIRECT_URI,
                },
            )
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"token 换取失败：{data}")
        self._store_user_tokens(data)

    def _store_user_tokens(self, data: dict):
        self._tokens["user_access_token"] = data["access_token"]
        self._tokens["refresh_token"] = data["refresh_token"]
        self._tokens["user_token_expire"] = time.time() + data.get("expires_in", 7200) - 60
        self._save_tokens()

    def _refresh_user_token(self):
        if not self._tokens.get("refresh_token"):
            raise RuntimeError("refresh_token 不存在，请重新执行 OAuth2 授权")
        with self._http() as client:
            resp = client.post(
                "https://open.feishu.cn/open-apis/authen/v2/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": self._tokens["refresh_token"],
                    "client_id": self.app_id,
                    "client_secret": self.app_secret,
                },
            )
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"token 刷新失败：{data}")
        self._store_user_tokens(data)

    # ── 应用身份 token ────────────────────────────
    def _get_tenant_token(self) -> str:
        if (self._tokens.get("tenant_access_token") and
                time.time() < self._tokens.get("tenant_token_expire", 0)):
            return self._tokens["tenant_access_token"]
        with self._http() as client:
            resp = client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
        data = resp.json()
        token = data.get("tenant_access_token", "")
        if not token:
            raise RuntimeError(f"获取 tenant token 失败：{data}")
        self._tokens["tenant_access_token"] = token
        self._tokens["tenant_token_expire"] = time.time() + data.get("expire", 7200) - 60
        self._save_tokens()
        return token

    # ── 对外接口 ──────────────────────────────────
    def get_token(self) -> str:
        """返回当前身份的有效 token（自动刷新）"""
        if self._identity == "app":
            return self._get_tenant_token()
        # 用户身份
        if not self._tokens.get("user_access_token"):
            raise RuntimeError("尚未完成 OAuth2 授权，请先调用 feishu_auth 工具")
        if time.time() >= self._tokens.get("user_token_expire", 0):
            self._refresh_user_token()
        return self._tokens["user_access_token"]

    def switch_identity(self, mode: str):
        """mode: 'user' | 'app'"""
        if mode not in ("user", "app"):
            raise ValueError("mode 必须是 'user' 或 'app'")
        self._identity = mode

    def status(self) -> dict:
        has_user = bool(self._tokens.get("user_access_token"))
        expire = self._tokens.get("user_token_expire", 0)
        return {
            "identity": self._identity,
            "has_user_token": has_user,
            "user_token_expires_in": max(0, int(expire - time.time())) if has_user else 0,
            "has_refresh_token": bool(self._tokens.get("refresh_token")),
        }


# ─────────────────────────────────────────────
# API（lark-oapi 封装）
# ─────────────────────────────────────────────

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest, CreateMessageRequestBody,
    ListChatRequest,
)
from lark_oapi.api.docx.v1 import (
    CreateDocumentRequest, CreateDocumentRequestBody,
    RawContentDocumentRequest,
)
from lark_oapi.api.bitable.v1 import (
    ListAppTableRecordRequest, CreateAppTableRecordRequest,
    AppTableRecord,
)


class API:
    def __init__(self, auth: "Auth"):
        self.auth = auth

    def _get_client(self) -> lark.Client:
        """每次调用前重新获取 token，确保不过期"""
        builder = (
            lark.Client.builder()
            .app_id(self.auth.app_id)
            .app_secret(self.auth.app_secret)
            .log_level(lark.LogLevel.ERROR)
        )
        if self.auth.proxy:
            builder = builder.http_host(self.auth.proxy)
        return builder.build()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.auth.get_token()}"}

    def _http(self) -> "httpx.Client":
        """返回配置了代理的 httpx.Client（上下文管理器）"""
        import httpx
        proxies = (
            {"https://": self.auth.proxy, "http://": self.auth.proxy}
            if self.auth.proxy
            else None
        )
        return httpx.Client(proxies=proxies, timeout=30)

    # ── 授权 ─────────────────────────────────────
    def auth_status(self) -> dict:
        return self.auth.status()

    def switch_identity(self, mode: str) -> str:
        self.auth.switch_identity(mode)
        return f"已切换到 {mode} 身份"

    # ── 文档 ─────────────────────────────────────
    def create_document(self, title: str, content: str = "") -> dict:
        client = self._get_client()
        req = (
            CreateDocumentRequest.builder()
            .request_body(
                CreateDocumentRequestBody.builder()
                .title(title)
                .folder_token("")
                .build()
            )
            .build()
        )
        resp = client.docx.v1.document.create(req)
        if not resp.success():
            raise RuntimeError(f"创建文档失败：{resp.msg}")
        return {
            "document_id": resp.data.document.document_id,
            "url": resp.data.document.share_url,
        }

    def get_document(self, document_id: str) -> str:
        client = self._get_client()
        req = (
            RawContentDocumentRequest.builder()
            .document_id(document_id)
            .build()
        )
        resp = client.docx.v1.document.raw_content(req)
        if not resp.success():
            raise RuntimeError(f"读取文档失败：{resp.msg}")
        return resp.data.content

    def list_documents(self, query: str) -> list:
        with self._http() as client:
            resp = client.get(
                "https://open.feishu.cn/open-apis/suite/docs-api/search/object",
                headers=self._headers(),
                params={"query": query, "count": 20, "offset": 0},
            )
        data = resp.json()
        if resp.status_code != 200 or data.get("code", 0) != 0:
            raise RuntimeError(f"API 调用失败：{data}")
        return data.get("data", {}).get("docs_entities", [])

    # ── 消息 ─────────────────────────────────────
    def send_message(
        self, chat_id: str, text: str, receive_id_type: str = "chat_id"
    ) -> dict:
        client = self._get_client()
        req = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .build()
            )
            .build()
        )
        resp = client.im.v1.message.create(req)
        if not resp.success():
            raise RuntimeError(f"发送消息失败：{resp.msg}")
        return {"message_id": resp.data.message_id}

    def list_chats(self) -> list:
        client = self._get_client()
        req = ListChatRequest.builder().page_size(50).build()
        resp = client.im.v1.chat.list(req)
        if not resp.success():
            raise RuntimeError(f"获取群聊失败：{resp.msg}")
        return [
            {"chat_id": c.chat_id, "name": c.name}
            for c in (resp.data.items or [])
        ]

    # ── 表格 ─────────────────────────────────────
    def read_sheet(
        self, spreadsheet_token: str, sheet_id: str, range_: str
    ) -> list:
        with self._http() as client:
            resp = client.get(
                f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets"
                f"/{spreadsheet_token}/values/{sheet_id}!{range_}",
                headers=self._headers(),
            )
        data = resp.json()
        if resp.status_code != 200 or data.get("code", 0) != 0:
            raise RuntimeError(f"API 调用失败：{data}")
        return data.get("data", {}).get("valueRange", {}).get("values", [])

    def write_sheet(
        self,
        spreadsheet_token: str,
        sheet_id: str,
        range_: str,
        values: list,
    ) -> dict:
        with self._http() as client:
            resp = client.put(
                f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets"
                f"/{spreadsheet_token}/values",
                headers=self._headers(),
                json={
                    "valueRange": {
                        "range": f"{sheet_id}!{range_}",
                        "values": values,
                    }
                },
            )
        data = resp.json()
        if resp.status_code != 200 or data.get("code", 0) != 0:
            raise RuntimeError(f"API 调用失败：{data}")
        return data

    # ── Bitable ───────────────────────────────────
    def query_records(
        self, app_token: str, table_id: str, filter_: str = ""
    ) -> list:
        client = self._get_client()
        builder = (
            ListAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .page_size(100)
        )
        if filter_:
            builder = builder.filter(filter_)
        resp = client.bitable.v1.app_table_record.list(builder.build())
        if not resp.success():
            raise RuntimeError(f"查询记录失败：{resp.msg}")
        return [r.fields for r in (resp.data.items or [])]

    def create_record(
        self, app_token: str, table_id: str, fields: dict
    ) -> dict:
        client = self._get_client()
        req = (
            CreateAppTableRecordRequest.builder()
            .app_token(app_token)
            .table_id(table_id)
            .request_body(AppTableRecord.builder().fields(fields).build())
            .build()
        )
        resp = client.bitable.v1.app_table_record.create(req)
        if not resp.success():
            raise RuntimeError(f"创建记录失败：{resp.msg}")
        return {"record_id": resp.data.record.record_id}

    # ── OKR ──────────────────────────────────────
    def get_okr(self, user_id: str, period_id: str = "") -> dict:
        params: dict = {"user_id": user_id, "user_id_type": "open_id"}
        if period_id:
            params["period_ids"] = period_id
        with self._http() as client:
            resp = client.get(
                "https://open.feishu.cn/open-apis/okr/v1/okrs/batch_get",
                headers=self._headers(),
                params=params,
            )
        data = resp.json()
        if resp.status_code != 200 or data.get("code", 0) != 0:
            raise RuntimeError(f"API 调用失败：{data}")
        return data.get("data", {})

    def update_okr_progress(
        self,
        okr_id: str,
        kr_id: str,
        progress: float,
        remark: str = "",
    ) -> dict:
        with self._http() as client:
            resp = client.patch(
                "https://open.feishu.cn/open-apis/okr/v1/progress_records",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={
                    "source_type": 2,
                    "target_id": kr_id,
                    "metric_current_value": progress,
                    "content": {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "paragraph": {
                                    "elements": [
                                        {
                                            "type": "textRun",
                                            "textRun": {"text": remark},
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
            )
        data = resp.json()
        if resp.status_code != 200 or data.get("code", 0) != 0:
            raise RuntimeError(f"API 调用失败：{data}")
        return data

    def add_okr_comment(self, okr_id: str, comment: str) -> dict:
        with self._http() as client:
            resp = client.post(
                f"https://open.feishu.cn/open-apis/okr/v1/okrs/{okr_id}/progress_records",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={
                    "content": {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "paragraph": {
                                    "elements": [
                                        {
                                            "type": "textRun",
                                            "textRun": {"text": comment},
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                },
            )
        data = resp.json()
        if resp.status_code != 200 or data.get("code", 0) != 0:
            raise RuntimeError(f"API 调用失败：{data}")
        return data

    # ── 通用工具（全量兜底）──────────────────────
    def feishu_api(self, module: str, method: str, params: dict) -> dict:
        """
        调用任意飞书 API（HTTP fallback 方式）。
        module: 'service.version.resource'，如 'im.v1.message' / 'drive.v1.file'
        method: 'list' / 'create' / 'get' / 'update' / 'delete'
        params: 请求参数字典

        示例：
            feishu_api("drive.v1.file", "create_folder",
                       {"name": "投研底稿", "folder_token": "xxx"})
        """
        parts = module.split(".")
        if len(parts) < 3:
            raise ValueError(
                "module 格式应为 'service.version.resource'，如 'im.v1.message'"
            )
        service, version = parts[0], parts[1]
        resource = "/".join(parts[2:])
        url = f"https://open.feishu.cn/open-apis/{service}/{version}/{resource}"
        GET_METHODS = {"list", "get", "batch_get", "search"}
        PUT_METHODS = {"put", "update_all"}
        PATCH_METHODS = {"update", "patch"}
        DELETE_METHODS = {"delete"}
        if method in GET_METHODS:
            http_method = "GET"
        elif method in PUT_METHODS:
            http_method = "PUT"
        elif method in PATCH_METHODS:
            http_method = "PATCH"
        elif method in DELETE_METHODS:
            http_method = "DELETE"
        else:
            http_method = "POST"
        with self._http() as client:
            if http_method == "GET":
                resp = client.get(url, headers=self._headers(), params=params)
            else:
                resp = client.request(
                    http_method, url, headers=self._headers(), json=params
                )
        data = resp.json()
        if resp.status_code != 200 or data.get("code", 0) != 0:
            raise RuntimeError(f"API 调用失败：{data}")
        return data


# ─────────────────────────────────────────────
# MCP Server 模式
# ─────────────────────────────────────────────

from mcp.server.fastmcp import FastMCP


def run_mcp_server():
    cfg = Config()
    auth = Auth(cfg.app_id, cfg.app_secret, cfg.proxy)
    api = API(auth)
    mcp = FastMCP("feishu")

    @mcp.tool()
    def feishu_auth() -> str:
        """发起 OAuth2 用户授权（打开浏览器完成飞书登录授权）"""
        auth.do_oauth()
        return "授权成功"

    @mcp.tool()
    def feishu_auth_status() -> dict:
        """查看当前身份模式和 token 状态"""
        return api.auth_status()

    @mcp.tool()
    def feishu_switch_identity(mode: str) -> str:
        """切换身份模式。mode: 'user'（默认，继承用户权限）或 'app'（应用身份）"""
        return api.switch_identity(mode)

    @mcp.tool()
    def feishu_create_document(title: str, content: str = "") -> dict:
        """创建飞书文档。返回 document_id 和分享链接"""
        return api.create_document(title, content)

    @mcp.tool()
    def feishu_get_document(document_id: str) -> str:
        """读取飞书文档的纯文本内容"""
        return api.get_document(document_id)

    @mcp.tool()
    def feishu_list_documents(query: str) -> list:
        """按关键词搜索飞书文档"""
        return api.list_documents(query)

    @mcp.tool()
    def feishu_send_message(chat_id: str, text: str, receive_id_type: str = "chat_id") -> dict:
        """向指定会话发送文本消息。receive_id_type: 'chat_id' 或 'open_id'"""
        return api.send_message(chat_id, text, receive_id_type)

    @mcp.tool()
    def feishu_list_chats() -> list:
        """列出当前用户所在的所有群聊和会话"""
        return api.list_chats()

    @mcp.tool()
    def feishu_read_sheet(spreadsheet_token: str, sheet_id: str, range_: str) -> list:
        """读取飞书电子表格数据。range_ 格式如 'A1:D10'"""
        return api.read_sheet(spreadsheet_token, sheet_id, range_)

    @mcp.tool()
    def feishu_write_sheet(spreadsheet_token: str, sheet_id: str, range_: str, values: list) -> dict:
        """写入飞书电子表格数据。values 为二维数组"""
        return api.write_sheet(spreadsheet_token, sheet_id, range_, values)

    @mcp.tool()
    def feishu_query_records(app_token: str, table_id: str, filter_: str = "") -> list:
        """查询多维表格（Bitable）记录。filter_ 为飞书筛选语法"""
        return api.query_records(app_token, table_id, filter_)

    @mcp.tool()
    def feishu_create_record(app_token: str, table_id: str, fields: dict) -> dict:
        """在多维表格中新增一条记录"""
        return api.create_record(app_token, table_id, fields)

    @mcp.tool()
    def feishu_get_okr(user_id: str, period_id: str = "") -> dict:
        """读取用户 OKR 完整内容（O + KR 详情）"""
        return api.get_okr(user_id, period_id)

    @mcp.tool()
    def feishu_update_okr_progress(okr_id: str, kr_id: str, progress: float, remark: str = "") -> dict:
        """更新 OKR 中某个 KR 的进度值和进度说明"""
        return api.update_okr_progress(okr_id, kr_id, progress, remark)

    @mcp.tool()
    def feishu_add_okr_comment(okr_id: str, comment: str) -> dict:
        """在 OKR 下添加评论或备注"""
        return api.add_okr_comment(okr_id, comment)

    @mcp.tool()
    def feishu_api(module: str, method: str, params: dict) -> dict:
        """
        调用任意飞书 API（通用兜底工具）。
        module: 服务路径，如 'drive.v1.file' / 'calendar.v4.calendar_event'
        method: 操作，如 'list' / 'create' / 'delete'
        params: 请求参数字典

        示例：feishu_api('drive.v1.file', 'create_folder', {'name': '底稿', 'folder_token': 'xxx'})
        """
        return api.feishu_api(module, method, params)

    mcp.run()


# ─────────────────────────────────────────────
# Bot 模式（WebSocket ChatBot）
# ─────────────────────────────────────────────

import subprocess
import shutil
import threading


def run_bot():
    cfg = Config()
    workspace = os.path.join(cfg.work_dir, "workspace")
    cfg.ensure_dirs()

    def call_claude(system_prompt: str, history: list, user_msg: str) -> str:
        claude_bin = shutil.which("claude")
        if not claude_bin:
            return "❌ 未找到 claude 命令，请确认 Claude Code CLI 已安装"
        messages = history + [{"role": "user", "content": user_msg}]
        prompt_parts = []
        if system_prompt:
            prompt_parts.append(f"<system>\n{system_prompt}\n</system>\n")
        for m in messages:
            role = "Human" if m["role"] == "user" else "Assistant"
            prompt_parts.append(f"{role}: {m['content']}")
        full_prompt = "\n".join(prompt_parts)
        env = os.environ.copy()
        if cfg.proxy:
            env["HTTPS_PROXY"] = cfg.proxy
        try:
            result = subprocess.run(
                [claude_bin, "-p", full_prompt, "--output-format", "text"],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            return result.stdout.strip() or result.stderr.strip() or "（无回复）"
        except subprocess.TimeoutExpired:
            return "⏱ 回复超时（120秒），请重试"
        except Exception as e:
            return f"❌ 调用 Claude 失败：{e}"

    def handle_message(chat_id: str, sender_id: str, text: str, is_group: bool):
        mem = Memory(workspace, chat_id)
        system_prompt = mem.build_system_prompt()
        reply = call_claude(system_prompt, mem.history, text)
        auth = Auth(cfg.app_id, cfg.app_secret, cfg.proxy)
        api = API(auth)
        try:
            api.send_message(chat_id, reply)
        except Exception as e:
            print(f"发送失败：{e}")
        mem.add_message("user", text)
        mem.add_message("assistant", reply)
        mem.save_history()

    import lark_oapi as lark
    from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

    def do_receive(data: P2ImMessageReceiveV1) -> None:
        try:
            msg = data.event.message
            chat_id = msg.chat_id
            chat_type = msg.chat_type  # "p2p" | "group"
            is_group = chat_type == "group"
            content_raw = json.loads(msg.content)
            text = content_raw.get("text", "").strip()
            if is_group:
                mentions = msg.mentions or []
                bot_mentioned = any(m.name == cfg.bot_name for m in mentions)
                if not bot_mentioned:
                    return
                for m in mentions:
                    text = text.replace(f"@{m.name}", "").strip()
            if not text:
                return
            sender_id = data.event.sender.sender_id.open_id
            threading.Thread(
                target=handle_message,
                args=(chat_id, sender_id, text, is_group),
                daemon=True,
            ).start()
        except Exception as e:
            print(f"消息处理异常：{e}")

    print(f"✅ 飞书 Bot 启动中（{cfg.bot_name}）...")
    cli = lark.ws.Client(
        cfg.app_id,
        cfg.app_secret,
        event_handler=lark.EventDispatcherHandler.builder(
            lark.ENCRYPT_KEY_IS_EMPTY,
            lark.VERIFICATION_TOKEN_IS_EMPTY,
        )
        .register(P2ImMessageReceiveV1, do_receive)
        .build(),
        log_level=lark.LogLevel.ERROR,
    )
    cli.start()


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

import argparse


def main():
    parser = argparse.ArgumentParser(description="feishu-claude 双模工具")
    parser.add_argument("--mode", choices=["mcp", "bot"], default="mcp")
    args = parser.parse_args()
    if args.mode == "mcp":
        run_mcp_server()
    else:
        run_bot()


if __name__ == "__main__":
    main()
