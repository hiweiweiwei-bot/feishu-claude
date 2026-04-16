import json, os, sys, pytest, time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from feishu_claude import Auth
import feishu_claude as fc


def make_auth(tmp_path):
    """创建使用临时 token 文件的 Auth 实例"""
    token_file = str(tmp_path / "tokens.json")
    with patch.object(fc, "TOKEN_PATH", token_file):
        auth = Auth("test_app_id", "test_secret")
    auth._tokens = {}
    return auth, token_file


def test_switch_identity_valid():
    auth = Auth("id", "secret")
    auth.switch_identity("user")
    assert auth._identity == "user"
    auth.switch_identity("app")
    assert auth._identity == "app"


def test_switch_identity_invalid():
    auth = Auth("id", "secret")
    with pytest.raises(ValueError, match="'user' 或 'app'"):
        auth.switch_identity("admin")


def test_status_no_token():
    auth = Auth("id", "secret")
    auth._tokens = {}
    s = auth.status()
    assert s["has_user_token"] == False
    assert s["has_refresh_token"] == False
    assert "identity" in s
    assert "user_token_expires_in" in s


def test_get_token_raises_without_user_token():
    auth = Auth("id", "secret")
    auth._tokens = {}
    auth._identity = "user"
    with pytest.raises(RuntimeError, match="OAuth2"):
        auth.get_token()


def test_load_tokens_corrupt_json(tmp_path):
    token_file = tmp_path / "tokens.json"
    token_file.write_text("not valid json{{{")
    with patch.object(fc, "TOKEN_PATH", str(token_file)):
        auth = Auth("id", "secret")
        assert auth._tokens == {}


def test_refresh_token_missing_raises():
    auth = Auth("id", "secret")
    auth._tokens = {"user_access_token": "tok", "user_token_expire": 0}
    with pytest.raises(RuntimeError, match="refresh_token"):
        auth._refresh_user_token()
