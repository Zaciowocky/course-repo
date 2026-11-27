"""课程 MCP mock 的行为测试。

覆盖三类：契约校验（报文按 report.v0.2 收）、鉴权与越权、班级视图聚合与抑制。
"""
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as svc  # noqa: E402


@pytest.fixture()
def client():
    svc.INVITES.clear()
    svc.INVITES.update({
        "INV-ALPHA": ("2026101", "student"),
        "INV-BETA": ("2026102", "student"),
        "INV-GAMMA": ("2026103", "student"),
        "INV-DELTA": ("2026104", "student"),
        "INV-EPS": ("2026105", "student"),
        "INV-TEACHER": ("T-001", "teacher"),
    })
    svc.TOKENS.clear()
    svc.REPORTS.clear()
    svc.ISSUES.clear()
    with TestClient(svc.app) as c:
        yield c


def register(client, code, sid):
    r = client.post("/auth/register", json={"student_id": sid, "invite_code": code})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def rid(n):
    return f"01936b2e-6c4a-7d3e-9f10-{n:012x}"


def report_payload(n=1, kp="KP-RAG-001", state="gap", version="v0.1.0", tier="standard", **over):
    stat = {"kp_id": kp, "state": state}
    if tier == "standard":
        stat.update({"mastery_band": "low", "attempts": 4, "correct_alone": 1,
                     "correct_with_hint": 2, "wrong": 1, "hint_level_max": 2,
                     "misconceptions": [{"code": "MIS-RAG-001-01", "count": 2}],
                     "duration_s": 600})
    data = {
        "schema_version": "report.v0.2",
        "report_id": rid(n),
        "course_id": "RAG",
        "course_version": version,
        "session_id": "S01",
        "tier": tier,
        "period": {"from": "2026-11-27", "to": "2026-11-27"},
        "progress": {"pages_total": 8, "pages_done": 6,
                     "warmup_branch": "remedial", "study_seconds": 1800},
        "kp_stats": [stat],
    }
    data.update(over)
    return data


# ---------- 鉴权与越权 ----------

def test_requires_token(client):
    assert client.get("/tools/get_course_version").status_code == 401
    assert client.get("/tools/get_course_version", headers=auth("nope")).status_code == 401


def test_invite_single_use(client):
    register(client, "INV-ALPHA", "2026101")
    r = client.post("/auth/register", json={"student_id": "2026101", "invite_code": "INV-ALPHA"})
    assert r.status_code == 403


def test_revoked_token_rejected(client):
    t = register(client, "INV-ALPHA", "2026101")
    assert client.post("/auth/revoke", headers=auth(t)).status_code == 200
    r = client.get("/tools/get_course_version", headers=auth(t))
    assert r.status_code == 401 and "AUTH-401-03" in r.json()["detail"]


def test_expired_token_rejected(client):
    t = register(client, "INV-ALPHA", "2026101")
    svc.TOKENS[t]["expires_at"] = time.time() - 1
    r = client.get("/tools/get_course_version", headers=auth(t))
    assert r.status_code == 401 and "AUTH-401-02" in r.json()["detail"]


def test_student_cannot_read_class_view(client):
    t = register(client, "INV-ALPHA", "2026101")
    assert client.get("/tools/get_class_view", headers=auth(t)).status_code == 403
    assert client.get("/tools/list_issues", headers=auth(t)).status_code == 403


def test_teacher_cannot_report(client):
    t = register(client, "INV-TEACHER", "T-001")
    r = client.post("/tools/report_progress", json=report_payload(), headers=auth(t))
    assert r.status_code == 403


# ---------- 契约校验 ----------

def test_standard_report_accepted(client):
    t = register(client, "INV-ALPHA", "2026101")
    r = client.post("/tools/report_progress", json=report_payload(), headers=auth(t))
    assert r.status_code == 200 and r.json()["accepted"] == 1


def test_minimal_report_accepted(client):
    t = register(client, "INV-ALPHA", "2026101")
    r = client.post("/tools/report_progress",
                    json=report_payload(tier="minimal"), headers=auth(t))
    assert r.json()["accepted"] == 1


@pytest.mark.parametrize("patch", [
    {"question_text": "学生原话"},
    {"events": [{"op": "answer"}]},
])
def test_free_text_rejected(client, patch):
    t = register(client, "INV-ALPHA", "2026101")
    r = client.post("/tools/report_progress",
                    json=report_payload(**patch), headers=auth(t))
    assert r.status_code == 422
    assert "DATA-422-01" in r.json()["detail"]


def test_missing_period_rejected(client):
    t = register(client, "INV-ALPHA", "2026101")
    data = report_payload()
    data.pop("period")
    r = client.post("/tools/report_progress", json=data, headers=auth(t))
    assert r.status_code == 422 and "period" in r.json()["detail"]


def test_wrong_schema_version_rejected(client):
    t = register(client, "INV-ALPHA", "2026101")
    r = client.post("/tools/report_progress",
                    json=report_payload(schema_version="report.v0.1"), headers=auth(t))
    assert r.status_code == 422


def test_duplicate_report_id(client):
    t = register(client, "INV-ALPHA", "2026101")
    first = client.post("/tools/report_progress", json=report_payload(), headers=auth(t))
    second = client.post("/tools/report_progress", json=report_payload(), headers=auth(t))
    assert first.json()["accepted"] == 1
    assert second.json()["accepted"] == 0 and second.json()["rejected"] == 1
    assert "DATA-409-01" in second.json()["errors"][0]


def test_course_version_mismatch(client):
    t = register(client, "INV-ALPHA", "2026101")
    r = client.post("/tools/report_progress",
                    json=report_payload(version="v9.9.9"), headers=auth(t))
    assert r.json()["accepted"] == 0
    assert "DATA-422-03" in r.json()["errors"][0]


def test_course_version_exposed(client):
    t = register(client, "INV-ALPHA", "2026101")
    body = client.get("/tools/get_course_version", headers=auth(t)).json()
    assert body["report_schema_version"] == "report.v0.2"


# ---------- 班级视图 ----------

def test_class_view_suppresses_small_sample(client):
    t = register(client, "INV-ALPHA", "2026101")
    teacher = register(client, "INV-TEACHER", "T-001")
    client.post("/tools/report_progress", json=report_payload(), headers=auth(t))
    row = client.get("/tools/get_class_view", headers=auth(teacher)).json()["kp_stats"][0]
    assert row["suppressed"] is True and "distribution" not in row


def test_class_view_marks_low_mastery(client):
    codes = [("INV-ALPHA", "2026101"), ("INV-BETA", "2026102"), ("INV-GAMMA", "2026103"),
             ("INV-DELTA", "2026104"), ("INV-EPS", "2026105")]
    tokens = [register(client, c, s) for c, s in codes]
    teacher = register(client, "INV-TEACHER", "T-001")
    for i, t in enumerate(tokens, start=1):
        client.post("/tools/report_progress",
                    json=report_payload(n=i, state="gap"), headers=auth(t))
    view = client.get("/tools/get_class_view", headers=auth(teacher)).json()
    row = view["kp_stats"][0]
    assert row["suppressed"] is False
    assert row["students"] == 5
    assert row["unmastered_ratio"] == 1.0
    assert "unmastered_high" in row["markers"]
    assert "misconception_common" in row["markers"]


def test_class_view_counts_content_gaps(client):
    codes = [("INV-ALPHA", "2026101"), ("INV-BETA", "2026102"), ("INV-GAMMA", "2026103")]
    tokens = [register(client, c, s) for c, s in codes]
    teacher = register(client, "INV-TEACHER", "T-001")
    for i, t in enumerate(tokens, start=1):
        payload = report_payload(n=i, content_gaps=[
            {"page_id": "PG-S01-001", "kp_id": "KP-RAG-001", "count": 2}])
        client.post("/tools/report_progress", json=payload, headers=auth(t))
    gaps = client.get("/tools/get_class_view", headers=auth(teacher)).json()["content_gaps"]
    assert gaps == [{"page_id": "PG-S01-001", "students": 3}]


def test_class_view_uses_latest_per_student(client):
    t = register(client, "INV-ALPHA", "2026101")
    teacher = register(client, "INV-TEACHER", "T-001")
    for i, state in enumerate(["gap", "partial"], start=1):
        payload = report_payload(n=i, state=state)
        payload["period"]["to"] = f"2026-11-2{6 + i}"
        client.post("/tools/report_progress", json=payload, headers=auth(t))
    row = client.get("/tools/get_class_view", headers=auth(teacher)).json()["kp_stats"][0]
    assert row["students"] == 1  # 同一学生两条报告只算一人


# ---------- 其它 ----------

def test_healthz(client):
    assert client.get("/healthz").json()["ok"] is True


def test_teacher_sees_issue(client):
    t = register(client, "INV-ALPHA", "2026101")
    teacher = register(client, "INV-TEACHER", "T-001")
    client.post("/tools/report_issue", headers=auth(t), json={
        "course_id": "RAG", "kp_id": "KP-RAG-001", "question": "检索结果为什么没被用上？"})
    issues = client.get("/tools/list_issues", headers=auth(teacher)).json()["issues"]
    assert len(issues) == 1 and issues[0]["kp_id"] == "KP-RAG-001"
