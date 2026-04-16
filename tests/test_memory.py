import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from feishu_claude import Memory

def test_load_empty_history(tmp_path):
    m = Memory(str(tmp_path), "chat_001")
    assert m.history == []

def test_add_and_load_history(tmp_path):
    m = Memory(str(tmp_path), "chat_001")
    m.add_message("user", "你好")
    m.add_message("assistant", "你好！")
    m.save_history()
    m2 = Memory(str(tmp_path), "chat_001")
    assert len(m2.history) == 2
    assert m2.history[0]["role"] == "user"
    assert m2.history[1]["content"] == "你好！"

def test_history_truncated_to_50(tmp_path):
    m = Memory(str(tmp_path), "chat_001")
    for i in range(60):
        m.add_message("user", f"msg {i}")
    assert len(m.history) == 50
    assert m.history[0]["content"] == "msg 10"

def test_load_identity_files(tmp_path):
    workspace = str(tmp_path)
    identity_path = os.path.join(workspace, "IDENTITY.md")
    with open(identity_path, "w") as f:
        f.write("# 身份\n我是测试 Bot")
    m = Memory(workspace, "chat_001")
    prompt = m.build_system_prompt()
    assert "我是测试 Bot" in prompt

def test_group_memory_isolated(tmp_path):
    m1 = Memory(str(tmp_path), "chat_A")
    m2 = Memory(str(tmp_path), "chat_B")
    m1.add_message("user", "A 群消息")
    m1.save_history()
    m2.add_message("user", "B 群消息")
    m2.save_history()
    m1r = Memory(str(tmp_path), "chat_A")
    m2r = Memory(str(tmp_path), "chat_B")
    assert m1r.history[0]["content"] == "A 群消息"
    assert m2r.history[0]["content"] == "B 群消息"

def test_group_dirs_are_isolated(tmp_path):
    m1 = Memory(str(tmp_path), "chat_A")
    m2 = Memory(str(tmp_path), "chat_B")
    assert m1.group_dir != m2.group_dir
    assert "chat_A" in m1.group_dir
    assert "chat_B" in m2.group_dir

def test_build_system_prompt_includes_group_memory(tmp_path):
    workspace = str(tmp_path)
    group_mem_path = os.path.join(workspace, "groups", "chat_001", "MEMORY.md")
    os.makedirs(os.path.dirname(group_mem_path), exist_ok=True)
    with open(group_mem_path, "w") as f:
        f.write("群内记住：用户叫Franco")
    m = Memory(workspace, "chat_001")
    prompt = m.build_system_prompt()
    assert "群内记住：用户叫Franco" in prompt
    assert "## 本群记忆" in prompt
