import json, os, tempfile, pytest, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from feishu_claude import Config

def test_config_defaults(tmp_path):
    cfg = Config(path=str(tmp_path / "config.json"))
    assert cfg.app_id == ""
    assert cfg.app_secret == ""
    assert cfg.proxy == ""
    assert cfg.work_dir.endswith("feishu-claude")

def test_config_save_and_load(tmp_path):
    path = str(tmp_path / "config.json")
    cfg = Config(path=path)
    cfg.app_id = "cli_test"
    cfg.app_secret = "secret_test"
    cfg.save()
    cfg2 = Config(path=path)
    assert cfg2.app_id == "cli_test"
    assert cfg2.app_secret == "secret_test"

def test_config_work_dir_created(tmp_path):
    work = str(tmp_path / "mybot")
    cfg = Config(path=str(tmp_path / "config.json"))
    cfg.work_dir = work
    cfg.save()
    cfg2 = Config(path=str(tmp_path / "config.json"))
    cfg2.ensure_dirs()
    assert os.path.isdir(os.path.join(work, "workspace", "groups"))  # 嵌套结构
    assert os.path.isdir(os.path.join(work, "workspace"))            # 父目录
