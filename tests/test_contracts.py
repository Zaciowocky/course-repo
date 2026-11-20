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
