"""mock 服务的接口行为测试：鉴权、越权、去重、小样本抑制。"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app  # noqa: E402


@pytest.fixture()
def client():
    import app as app_module
    app_module.INVITES.update({
        "INV-ALPHA": ("2026101", "student"),
        "INV-BETA": ("2026102", "student"),
        "INV-TEACHER": ("T-001", "teacher"),
    })
    app_module.TOKENS.clear()
    app_module.REPORTS.clear()
    app_module.ISSUES.clear()
    with TestClient(app) as c:
        yield c


def register(client, code, sid):
    r = client.post("/auth/register", json={"student_id": sid, "invite_code": code})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_requires_token(client):
    assert client.get("/tools/get_course_version").status_code == 401
    assert client.get("/tools/get_course_version",
                      headers={"Authorization": "Bearer nope"}).status_code == 401


def test_invite_is_single_use(client):
    register(client, "INV-ALPHA", "2026101")
    r = client.post("/auth/register", json={"student_id": "2026101", "invite_code": "INV-ALPHA"})
    assert r.status_code == 403


def test_student_cannot_read_class_view(client):
    token = register(client, "INV-ALPHA", "2026101")
    assert client.get("/tools/get_class_view", headers=auth(token)).status_code == 403


def test_report_dedup(client):
    token = register(client, "INV-ALPHA", "2026101")
    report = {
        "report_id": "RPT-001",
        "course_id": "RAG",
        "course_version": "v0.1.0",
        "session_id": "S01",
        "kp_stats": [{"kp_id": "KP-RAG-001", "state": "gap", "attempts": 3, "wrong": 2}],
    }
    first = client.post("/tools/report_progress", json=report, headers=auth(token)).json()
    second = client.post("/tools/report_progress", json=report, headers=auth(token)).json()
    assert first["accepted"] == 1
    assert second["accepted"] == 0 and second["rejected"] == 1


def test_version_mismatch_rejected(client):
    token = register(client, "INV-ALPHA", "2026101")
    report = {
        "report_id": "RPT-002",
        "course_id": "RAG",
        "course_version": "v9.9.9",
        "session_id": "S01",
        "kp_stats": [],
    }
    r = client.post("/tools/report_progress", json=report, headers=auth(token)).json()
    assert r["accepted"] == 0


def test_small_sample_is_suppressed(client):
    token = register(client, "INV-ALPHA", "2026101")
    teacher = register(client, "INV-TEACHER", "T-001")
    client.post("/tools/report_progress", headers=auth(token), json={
        "report_id": "RPT-003", "course_id": "RAG", "course_version": "v0.1.0",
        "session_id": "S01", "kp_stats": [{"kp_id": "KP-RAG-001", "state": "gap"}],
    })
    view = client.get("/tools/get_class_view", headers=auth(teacher)).json()
    row = view["kp_stats"][0]
    assert row["suppressed"] is True and "distribution" not in row


def test_teacher_can_list_issues(client):
    token = register(client, "INV-ALPHA", "2026101")
    teacher = register(client, "INV-TEACHER", "T-001")
    client.post("/tools/report_issue", headers=auth(token), json={
        "course_id": "RAG", "kp_id": "KP-RAG-001", "question": "检索结果为什么没被用上？",
    })
    issues = client.get("/tools/list_issues", headers=auth(teacher)).json()["issues"]
    assert len(issues) == 1 and issues[0]["kp_id"] == "KP-RAG-001"
