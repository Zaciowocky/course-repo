"""契约⑭：learner.db 建表语句（contracts/learner.sql）与画像规则（contracts/profile-rules.yaml）。

每个测试在内存里新建一个空库，不碰磁盘。
"""
import json
import pathlib
import re
import sqlite3
import uuid

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SQL = (ROOT / "contracts" / "learner.sql").read_text(encoding="utf8")
RULES = yaml.safe_load((ROOT / "contracts" / "profile-rules.yaml").read_text(encoding="utf8"))
EVENTS = json.loads((ROOT / "contracts" / "events.schema.json").read_text(encoding="utf8"))
REPORT = json.loads((ROOT / "contracts" / "report.schema.json").read_text(encoding="utf8"))
KNOWLEDGE = json.loads((ROOT / "contracts" / "knowledge.schema.json").read_text(encoding="utf8"))
GATE = yaml.safe_load((ROOT / "contracts" / "state-gate.yaml").read_text(encoding="utf8"))

NOW = "2026-11-27T20:15:00+08:00"
STATES = {"unseen", "gap", "partial", "transfer"}
MEMORY_TABLES = ("mistakes", "qa_memory", "strategies", "sessions")


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SQL)
    yield con
    con.close()


def columns(db, table):
    return {row[1]: row for row in db.execute(f"PRAGMA table_info({table})")}


def add_event(db, **overrides):
    event = {"event_id": str(uuid.uuid4()), "ts": NOW, "course_id": "RAG", "version": "v0.1.0",
             "session_id": "S01", "kp_id": "KP-RAG-001", "page_id": "PG-S01-001", "activity_id": "ACT-S01-001",
             "op": "answer", "result": "correct", "hint_level": 0, "duration_s": 42, "done": 1,
             "item_kind": "check", "is_transfer": 0, "item_hash": None, "misconception": None}
    event.update(overrides)
    keys = ", ".join(event)
    db.execute(f"INSERT INTO events ({keys}) VALUES ({', '.join(':' + k for k in event)})", event)
    return event["event_id"]


def add_kp(db, kp_id="KP-RAG-001", **overrides):
    row = {"kp_id": kp_id, "course_version": "v0.1.0", "updated_at": NOW, "updated_by": "event"}
    row.update(overrides)
    db.execute(f"INSERT INTO kp_state ({', '.join(row)}) VALUES ({', '.join(':' + k for k in row)})", row)


def add_mistake(db, **overrides):
    row = {"kp_id": "KP-RAG-001", "activity_id": "ACT-S01-001", "stem_snapshot": "题干",
           "judged_by": "auto", "first_wrong_at": NOW, "updated_at": NOW}
    row.update(overrides)
    cur = db.execute(f"INSERT INTO mistakes ({', '.join(row)}) VALUES ({', '.join(':' + k for k in row)})", row)
    return cur.lastrowid


# ---------- 建表语句本身 ----------

def test_sqlite_supports_strict_and_json():
    # STRICT 表要 3.37+，内置 JSON 函数要 3.38+
    assert sqlite3.sqlite_version_info >= (3, 38), sqlite3.sqlite_version


def test_meta_version_matches_header(db):
    header = re.search(r"^-- version: (\S+)$", SQL, re.M).group(1)
    stored = db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0]
    assert stored == header


def test_all_tables_present(db):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert names == {"meta", "events", "student_profile", "kp_state", "kp_misconceptions", "lesson_state",
                     "evidence", "corrections", "mistakes", "qa_memory", "strategies", "sessions"}


def test_all_tables_strict(db):
    rows = db.execute("SELECT name, strict FROM pragma_table_list WHERE schema = 'main' "
                      "AND name NOT LIKE 'sqlite_%'").fetchall()
    assert rows and all(strict == 1 for _, strict in rows), rows


# ---------- 事件表：与 events.schema.json 一一对应、只追加 ----------

def test_events_columns_match_event_schema(db):
    """任何合法学习事件都能原样落库，库里也没有 schema 之外的列。"""
    assert set(columns(db, "events")) == set(EVENTS["properties"])


def test_events_required_fields_not_null(db):
    cols = columns(db, "events")
    for field in EVENTS["required"] + ["ts"]:
        assert cols[field][3] == 1, f"{field} 应为 NOT NULL"
    assert cols["event_id"][5] == 1, "event_id 应为主键"


def test_events_append_only(db):
    event_id = add_event(db)
    with pytest.raises(sqlite3.DatabaseError, match="只追加"):
        db.execute("UPDATE events SET result = 'incorrect' WHERE event_id = ?", (event_id,))
    with pytest.raises(sqlite3.DatabaseError, match="只追加"):
        db.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
    assert db.execute("SELECT result FROM events").fetchone()[0] == "correct"


@pytest.mark.parametrize("field,value", [("hint_level", 5), ("duration_s", 3601), ("done", 2), ("is_transfer", -1)])
def test_events_reject_out_of_range(db, field, value):
    with pytest.raises(sqlite3.IntegrityError):
        add_event(db, **{field: value})


def test_events_accept_new_op_without_rebuild(db):
    """op 不写 CHECK：契约新增 op 时不用重建只追加的事件表。"""
    add_event(db, op="some_future_op", result=None)


def test_event_ranges_match_schema():
    props = EVENTS["properties"]
    assert (props["hint_level"]["minimum"], props["hint_level"]["maximum"]) == (0, 4)
    assert (props["duration_s"]["minimum"], props["duration_s"]["maximum"]) == (0, 3600)
    assert "hint_level BETWEEN 0 AND 4" in SQL and "duration_s BETWEEN 0 AND 3600" in SQL


# ---------- 画像 ----------

def test_four_states_agree_across_contracts(db):
    report_states = set(REPORT["properties"]["kp_stats"]["items"]["properties"]["state"]["enum"])
    gate_states = set(GATE["states"])
    rule_states = {step["state"] for step in RULES["states"]["decide"]}
    assert report_states == gate_states == rule_states == STATES
    for i, state in enumerate(sorted(STATES)):
        add_kp(db, f"KP-RAG-00{i + 1}", state=state)
    with pytest.raises(sqlite3.IntegrityError):
        add_kp(db, "KP-RAG-009", state="pending")   # 待确认是标记，不是第五档


def test_kp_state_counters_consistent(db):
    with pytest.raises(sqlite3.IntegrityError):
        add_kp(db, attempts=2, correct_alone=2, wrong=1)
    with pytest.raises(sqlite3.IntegrityError):
        add_kp(db, "KP-RAG-002", transfer_attempts=1, transfer_correct=2)
    with pytest.raises(sqlite3.IntegrityError):
        add_kp(db, "KP-RAG-003", p_mastery=1.2)


def test_kp_state_defaults_to_unseen_and_pending(db):
    add_kp(db)
    state, pending, p = db.execute("SELECT state, pending, p_mastery FROM kp_state").fetchone()
    assert (state, pending, p) == ("unseen", 1, None)


@pytest.mark.parametrize("table,column,bad", [
    ("kp_state", "prereq_gaps", "{}"),
    ("kp_state", "prereq_gaps", "不是 JSON"),
])
def test_json_columns_checked(db, table, column, bad):
    with pytest.raises(sqlite3.DatabaseError):
        add_kp(db, **{column: bad})


def test_student_profile_single_row(db):
    db.execute("INSERT INTO student_profile (id, updated_at) VALUES (1, ?)", (NOW,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO student_profile (id, updated_at) VALUES (2, ?)", (NOW,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE student_profile SET prior_self = '[1, 2]'")


def test_profile_children_need_kp_state(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO kp_misconceptions (kp_id, code, first_seen_at, last_seen_at) "
                   "VALUES ('KP-RAG-001', 'MIS-RAG-001-01', ?, ?)", (NOW, NOW))
    add_kp(db)
    db.execute("INSERT INTO kp_misconceptions (kp_id, code, first_seen_at, last_seen_at) "
               "VALUES ('KP-RAG-001', 'MIS-RAG-001-01', ?, ?)", (NOW, NOW))


def test_evidence_needs_source_events(db):
    add_kp(db)
    sql = ("INSERT INTO evidence (kp_id, event_ids, kind, result, state_after, pending_after, created_at) "
           "VALUES ('KP-RAG-001', ?, 'check', 'correct', 'gap', 1, ?)")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, ("[]", NOW))
    db.execute(sql, (json.dumps([add_event(db)]), NOW))


# ---------- 记忆库 ----------

def test_mistakes_need_item_id(db):
    with pytest.raises(sqlite3.IntegrityError):
        add_mistake(db, activity_id=None)
    add_mistake(db, activity_id=None, item_hash="0123456789abcdef")


def test_mistakes_one_row_per_item(db):
    add_mistake(db)
    with pytest.raises(sqlite3.IntegrityError):
        add_mistake(db)
    add_mistake(db, kp_id="KP-ABC-001")   # 活动 ID 只在课程内唯一，别的课程可以重号


def test_mistake_boxes_match_review_rules(db):
    intervals = RULES["review"]["box_intervals_days"]
    assert len(intervals) == 5 and intervals == sorted(set(intervals))
    add_mistake(db, box=len(intervals))
    with pytest.raises(sqlite3.IntegrityError):
        add_mistake(db, activity_id="ACT-S01-002", box=len(intervals) + 1)


def test_deleting_mistake_keeps_qa_but_clears_link(db):
    mistake_id = add_mistake(db)
    db.execute("INSERT INTO qa_memory (kp_id, question_summary, mistake_id, created_at, updated_at) "
               "VALUES ('KP-RAG-001', '问检索步骤', ?, ?, ?)", (mistake_id, NOW, NOW))
    db.execute("DELETE FROM mistakes WHERE id = ?", (mistake_id,))
    assert db.execute("SELECT mistake_id FROM qa_memory").fetchone() == (None,)


def test_memory_tables_deletable_by_student(db):
    """“我的记录”里能逐条删除：记忆四库上不能有拦删除的触发器。"""
    triggers = {r[0] for r in db.execute("SELECT tbl_name FROM sqlite_master WHERE type = 'trigger'")}
    assert triggers == {"events"}
    assert not triggers & set(MEMORY_TABLES)


def test_strategy_success_not_above_use(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO strategies (kp_id, kind, used_count, success_after, updated_at) "
                   "VALUES ('KP-RAG-001', 'analogy', 1, 2, ?)", (NOW,))


# ---------- 画像规则 ----------

def test_rule_thresholds_ordered_and_match_report():
    s = RULES["states"]
    assert 0 < s["gap_below"] == s["partial_at_least"] < s["transfer_at_least"] <= 1
    assert s["min_evidence"] >= 1
    band = REPORT["properties"]["kp_stats"]["items"]["properties"]["mastery_band"]["description"]
    assert str(s["gap_below"]) in band and str(s["transfer_at_least"]) in band


def test_rule_evidence_uses_event_vocabulary():
    props = EVENTS["properties"]
    ev = RULES["evidence"]
    assert ev["op"] in props["op"]["enum"]
    assert set(ev["item_kinds"]) <= set(props["item_kind"]["enum"])
    assert set(ev["results"]) <= set(props["result"]["enum"])
    assert set(ev["not_evidence_ops"]) <= set(props["op"]["enum"])
    assert ev["op"] not in ev["not_evidence_ops"]


def test_rule_bkt_params_cover_difficulties():
    m = RULES["mastery"]
    difficulties = set(KNOWLEDGE["properties"]["knowledge_points"]["items"]["properties"]["difficulty"]["enum"])
    assert set(m["default_params_by_difficulty"]) == difficulties
    for params in list(m["default_params_by_difficulty"].values()) + list(m["per_kp_params"].values()):
        assert set(params) == {"prior", "learn", "guess", "slip"}
        assert all(0 < v < 1 for v in params.values())
        # guess、slip 过大时“做对”不再说明“会”，BKT 退化
        assert params["guess"] < 0.5 and params["slip"] < 0.5
    assert 0 <= m["correct_max_hint_level"] <= 4


def test_rule_versioned():
    assert re.fullmatch(r"\d+\.\d+\.\d+", RULES["version"])
