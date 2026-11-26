"""契约与样例数据的自动校验，CI 与本地共用。"""
import json
import pathlib
import subprocess
import sys

import jsonschema
import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_yaml(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf8"))


def load_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf8"))


@pytest.mark.parametrize("data_rel,schema_rel", [
    ("course/knowledge/knowledge_points.yaml", "contracts/knowledge.schema.json"),
    ("materials/manifest.yaml", "contracts/manifest.schema.json"),
])
def test_sample_matches_schema(data_rel, schema_rel):
    jsonschema.validate(load_yaml(data_rel), load_json(schema_rel))


def test_event_sample_matches_schema():
    event = {
        "course_id": "RAG",
        "version": "v0.1.0",
        "kp_id": "KP-RAG-001",
        "page_id": "PG-S01-001",
        "activity_id": "ACT-S01-001",
        "op": "answer",
        "result": "correct",
        "hint_level": 1,
        "duration_s": 42,
        "done": True,
    }
    jsonschema.validate(event, load_json("contracts/events.schema.json"))


def test_event_rejects_free_text():
    bad = {"course_id": "RAG", "version": "v0.1.0", "kp_id": "KP-RAG-001",
           "op": "answer", "raw_text": "学生原话"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load_json("contracts/events.schema.json"))


def test_contracts_have_version():
    for rel in ("contracts/ids.yaml", "contracts/mcp-tools.yaml",
                "course/knowledge/knowledge_points.yaml"):
        assert "version" in load_yaml(rel), f"{rel} 缺少 version"


def test_course_check_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_course.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ---------- 学习事件 v0.2（只增不改，v0.1 样例由上面的测试继续覆盖） ----------

EVENTS = "contracts/events.schema.json"
CONTEXT = "contracts/context.schema.json"
BASE_EVENT = {"course_id": "RAG", "version": "v0.1.0", "kp_id": "KP-RAG-001"}


def test_event_v02_sample_matches_schema():
    event = dict(
        BASE_EVENT,
        event_id="01936b2e-6c4a-7d3e-9f10-2a3b4c5d6e7f",
        ts="2026-11-27T14:03:05+08:00",
        session_id="S01",
        page_id="PG-S01-001",
        item_hash="3f9a1c0be47d2a85",
        item_kind="review",
        is_transfer=False,
        op="answer",
        result="incorrect",
        misconception="MIS-RAG-001-01",
        hint_level=0,
        duration_s=35,
        done=True,
    )
    jsonschema.validate(event, load_json(EVENTS))


@pytest.mark.parametrize("op", ["ask", "revisit", "answer_change"])
def test_event_v02_new_ops(op):
    jsonschema.validate(dict(BASE_EVENT, op=op, page_id="PG-S01-001"), load_json(EVENTS))


@pytest.mark.parametrize("code", ["MIS-RAG-1-1", "误区一", "OTHER"])
def test_event_rejects_bad_misconception_code(code):
    bad = dict(BASE_EVENT, op="answer", result="incorrect", misconception=code)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load_json(EVENTS))


def test_event_misconception_other_allowed():
    ok = dict(BASE_EVENT, op="answer", result="partial", misconception="other")
    jsonschema.validate(ok, load_json(EVENTS))


@pytest.mark.parametrize("extra", [
    {"op": "answer", "result": "correct"},   # 做对了不该带误区
    {"op": "hint", "hint_level": 2},         # 不是作答不该带误区
    {"op": "answer"},                        # 作答没给结果
])
def test_event_misconception_only_on_wrong_answer(extra):
    bad = dict(BASE_EVENT, misconception="MIS-RAG-001-01", **extra)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load_json(EVENTS))


@pytest.mark.parametrize("field,value", [
    ("ts", "2026-11-27 14:03"),       # 缺 T 和时区
    ("event_id", "evt-001"),          # 不是 UUID
    ("session_id", "第一课"),          # 不是 S01 格式
])
def test_event_rejects_bad_v02_formats(field, value):
    bad = dict(BASE_EVENT, op="page_enter", **{field: value})
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load_json(EVENTS))


# ---------- 上下文包 v0.1 ----------

def context_sample():
    return {
        "course_id": "RAG",
        "version": "v0.1.0",
        "session_id": "S01",
        "kp_id": "KP-RAG-002",
        "page_id": "PG-S01-003",
        "node_id": "NODE-S01-007",
        "trigger": "hint",
        "hint_level": 1,
        "activity": {"activity_id": "ACT-S01-002", "item_kind": "check",
                     "is_transfer": False, "status": "in_progress"},
        "recent_answers": [
            {"event_id": "01936b2e-6c4a-7d3e-9f10-2a3b4c5d6e7f", "kp_id": "KP-RAG-002",
             "activity_id": "ACT-S01-002", "result": "incorrect", "hint_level": 0,
             "misconception": "MIS-RAG-002-01"},
            {"kp_id": "KP-RAG-001", "activity_id": "ACT-S01-001",
             "result": "correct", "hint_level": 0},
        ],
    }


def test_context_sample_matches_schema():
    jsonschema.validate(context_sample(), load_json(CONTEXT))


def test_context_minimal_matches_schema():
    minimal = {"course_id": "RAG", "version": "v0.1.0", "kp_id": "KP-RAG-001",
               "trigger": "warmup", "hint_level": 0}
    jsonschema.validate(minimal, load_json(CONTEXT))


def test_context_rejects_free_text():
    bad = context_sample()
    bad["message"] = "学生原话"      # 原话走请求体的 message，不进上下文包
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load_json(CONTEXT))


def test_context_caps_recent_answers():
    bad = context_sample()
    bad["recent_answers"] = [bad["recent_answers"][1]] * 6
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load_json(CONTEXT))


def test_context_activity_needs_an_id():
    bad = context_sample()
    bad["activity"] = {"item_kind": "check"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load_json(CONTEXT))


@pytest.mark.parametrize("rel", [EVENTS, CONTEXT])
def test_json_contracts_are_valid_and_versioned(rel):
    schema = load_json(rel)
    jsonschema.Draft7Validator.check_schema(schema)
    assert "version" in schema, f"{rel} 缺少 version"
