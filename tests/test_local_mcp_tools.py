"""契约⑭ 工具清单：contracts/local-mcp-tools.yaml。

检查三件事：与其他契约对得上（门控、事件、建表、画像规则）；输入格式本身合法、样例能通过；
返回给学伴的字段里没有学生写的原文。
"""
import json
import pathlib
import re
import sqlite3

import jsonschema
import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOC = yaml.safe_load((ROOT / "contracts" / "local-mcp-tools.yaml").read_text(encoding="utf8"))
TOOLS = {tool["name"]: tool for tool in DOC["tools"]}
GATE = yaml.safe_load((ROOT / "contracts" / "state-gate.yaml").read_text(encoding="utf8"))
RULES = yaml.safe_load((ROOT / "contracts" / "profile-rules.yaml").read_text(encoding="utf8"))
SQL = (ROOT / "contracts" / "learner.sql").read_text(encoding="utf8")

# 学生写的原文：只在本机、只给工作台“我的记录”看，不能出现在任何工具的返回里
STUDENT_TEXT = {"question_raw", "student_answer", "reason"}
OUTPUT_META = {"list_of", "row_of", "columns", "extra", "nullable"}


def _table_columns():
    con = sqlite3.connect(":memory:")
    con.executescript(SQL)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    cols = {t: [r[1] for r in con.execute(f"PRAGMA table_info({t})")] for t in tables}
    con.close()
    return cols


COLUMNS = _table_columns()


def input_schema(tool):
    if "input_schema_file" in tool:
        return json.loads((ROOT / "contracts" / tool["input_schema_file"]).read_text(encoding="utf8"))
    return tool["input"]


def row_refs(node):
    """output 里每个 list_of / row_of 引用的 (表, 列)。"""
    if isinstance(node, dict):
        table = node.get("list_of") or node.get("row_of")
        if table:
            yield table, node["columns"]
        for value in node.values():
            yield from row_refs(value)


def output_field_names(output):
    names = set()

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key not in OUTPUT_META:
                    names.add(key)
                if key == "extra" and isinstance(value, dict):
                    names.update(value)
                walk(value)

    walk(output)
    for table, cols in row_refs(output):
        names.update(COLUMNS[table] if cols == "all" else cols)
    return names


def ddl_comment_values(label):
    """取建表语句里“label：a / b / c”这行注释列出的英文取值。"""
    line = next(l for l in SQL.splitlines() if f"{label}：" in l)
    return set(re.findall(r"[a-z_]+", line.split(f"{label}：", 1)[1]))


# ---------- 与其他契约对得上 ----------

def test_fourteen_tools_match_state_gate():
    assert len(DOC["tools"]) == len(TOOLS) == 14, "工具重名或数量不对"
    allowed = GATE["tools_always_allowed"]
    for group in ("memory", "profile"):
        assert {n for n, t in TOOLS.items() if t["group"] == group} == set(allowed[group])


def test_callers_known():
    for name, tool in TOOLS.items():
        assert tool["callers"] and set(tool["callers"]) <= set(DOC["callers"]), name


def test_record_event_input_is_event_contract():
    assert TOOLS["record_event"]["input_schema_file"] == "events.schema.json"


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_tables_and_columns_exist(name):
    tool = TOOLS[name]
    for table in tool.get("reads", []) + tool.get("writes", []):
        assert table in COLUMNS, f"{name} 读写了不存在的表 {table}"
    refs = list(row_refs(tool["output"]))
    for table, cols in refs:
        assert table in COLUMNS, f"{name} 引用了不存在的表 {table}"
        if cols != "all":
            missing = set(cols) - set(COLUMNS[table])
            assert not missing, f"{name} 引用了 {table} 不存在的列 {missing}"
        assert table in tool.get("reads", []) + tool.get("writes", []), f"{name} 返回 {table} 却没声明读写"


def test_review_limit_is_daily_max():
    limit = TOOLS["list_due_reviews"]["input"]["properties"]["limit"]
    assert limit["maximum"] == limit["default"] == RULES["review"]["daily_max"]


@pytest.mark.parametrize("label,tool,path", [
    ("讲法类型", "update_strategy", ["kind"]),
    ("判定方式", "add_mistake", ["judged_by"]),
])
def test_enums_match_ddl_comments(label, tool, path):
    prop = TOOLS[tool]["input"]["properties"][path[0]]
    assert set(prop["enum"]) == ddl_comment_values(label)


def test_struggle_values_are_rule_signals():
    struggle = TOOLS["add_qa"]["input"]["properties"]["struggle"]["items"]["enum"]
    assert set(struggle) <= set(RULES["struggle_signals"])


def test_correction_rules_present():
    c = RULES["corrections"]
    assert set(c) == set(TOOLS["apply_correction"]["input"]["properties"]["direction"]["enum"])
    assert c["lower"]["p_mastery_cap"] < RULES["states"]["gap_below"], "降档后下一次作答不该直接算回原档"


# ---------- 输入格式 ----------

@pytest.mark.parametrize("name", sorted(TOOLS))
def test_input_schema_valid_and_example_passes(name):
    tool = TOOLS[name]
    schema = input_schema(tool)
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.validate(tool["example"], schema)


@pytest.mark.parametrize("name", sorted(n for n in TOOLS if "input" in TOOLS[n]))
def test_inputs_closed(name):
    schema = TOOLS[name]["input"]
    assert schema["type"] == "object" and schema["additionalProperties"] is False


@pytest.mark.parametrize("tool,payload", [
    ("apply_correction", {"action": "resolve", "correction_id": 1}),                 # 缺验证题事件
    ("apply_correction", {"action": "open", "kp_id": "KP-RAG-001"}),                 # 缺方向
    ("update_strategy", {"kp_id": "KP-RAG-001", "kind": "analogy", "event": "rating"}),   # 缺评价
    ("add_qa", {"question_summary": "问检索步骤"}),                                   # 新建缺知识点
    ("add_mistake", {"kp_id": "KP-RAG-001", "stem_snapshot": "题", "judged_by": "auto",
                     "source_event_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                     "item": {"activity_id": "ACT-S01-001", "item_hash": "0123456789abcdef"}}),  # 题目 ID 二选一
    ("search_memory", {"text": "x" * 51}),
    ("list_due_reviews", {"limit": 6}),
    ("get_kp_state", {"kp_ids": ["KP-RAG-1"]}),
])
def test_inputs_reject_bad_payload(tool, payload):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, TOOLS[tool]["input"])


def test_add_qa_update_needs_only_id():
    jsonschema.validate({"qa_id": 3, "resolved": True, "followup_result": "correct"}, TOOLS["add_qa"]["input"])


# ---------- 隐私 ----------

def test_no_student_text_returned():
    for name, tool in TOOLS.items():
        leaked = output_field_names(tool["output"]) & STUDENT_TEXT
        assert not leaked, f"{name} 会把学生原文 {leaked} 返回给学伴"


def test_student_text_columns_marked_local():
    for col in STUDENT_TEXT:
        line = next(l for l in SQL.splitlines() if re.match(rf"\s+{col}\s", l))
        assert "[仅本地]" in line, col


def test_tutor_cannot_delete_or_write_raw_question():
    assert not any(word in name for name in TOOLS for word in ("delete", "remove", "purge"))
    assert "question_raw" not in TOOLS["add_qa"]["input"]["properties"]


def test_versioned():
    assert re.fullmatch(r"\d+\.\d+\.\d+", DOC["version"])
