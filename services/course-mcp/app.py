"""课程 MCP 服务的 mock 实现：接口形状与 contracts/mcp-tools.yaml 一致。"""
from __future__ import annotations

import secrets
from collections import defaultdict
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="课程 MCP 服务（mock）", version="0.1.0")

COURSE = {
    "course_id": "RAG",
    "latest_tag": "v0.1.0",
    "changelog": "首版：检索增强生成基本结构",
    "migration_required": False,
}
ANNOUNCEMENTS = [
    {"id": "ANN-001", "title": "第一节已发布", "body": "请按 warm-up 提示开始。", "tag": "v0.1.0"}
]

# 邀请码 -> (student_id, role)，一次性使用
INVITES: dict[str, tuple[str, str]] = {
    "INV-ALPHA": ("2026101", "student"),
    "INV-BETA": ("2026102", "student"),
    "INV-TEACHER": ("T-001", "teacher"),
}
TOKENS: dict[str, dict] = {}
REPORTS: dict[str, dict] = {}          # report_id -> report
ISSUES: list[dict] = []
KP_STATES = ["unseen", "gap", "partial", "transfer"]


# ---------- 模型 ----------
class RegisterIn(BaseModel):
    student_id: str = Field(min_length=2)
    invite_code: str


class KpStat(BaseModel):
    kp_id: str
    state: Literal["unseen", "gap", "partial", "transfer"]
    attempts: int = 0
    correct_alone: int = 0
    correct_with_hint: int = 0
    wrong: int = 0
    hint_level_max: int = 0


class ReportIn(BaseModel):
    schema_version: str = "report.v0.2"
    report_id: str
    course_id: str
    course_version: str
    session_id: str
    tier: Literal["standard", "minimal"] = "standard"
    kp_stats: list[KpStat] = Field(default_factory=list)
    content_gaps: list[dict] = Field(default_factory=list)
    overlay_stats: dict = Field(default_factory=dict)


class IssueIn(BaseModel):
    course_id: str
    kp_id: str
    question: str = Field(min_length=1)
    context: dict = Field(default_factory=dict)


# ---------- 鉴权 ----------
def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="AUTH-401-01 缺少 token")
    token = authorization.removeprefix("Bearer ").strip()
    user = TOKENS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="AUTH-401-01 token 无效或已吊销")
    return user


def require_role(role: str):
    def _dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] != role:
            raise HTTPException(status_code=403, detail="AUTH-403-01 越权访问")
        return user
    return _dep


# ---------- 接口 ----------
@app.post("/auth/register")
def register(body: RegisterIn) -> dict:
    entry = INVITES.pop(body.invite_code, None)
    if not entry:
        raise HTTPException(status_code=403, detail="AUTH-403-02 邀请码无效或已使用")
    if entry[0] != body.student_id:
        raise HTTPException(status_code=403, detail="AUTH-403-03 学号与邀请码不匹配")
    token = secrets.token_urlsafe(24)
    TOKENS[token] = {"student_id": entry[0], "role": entry[1]}
    return {"token": token, "role": entry[1], "student_id": entry[0]}


@app.get("/tools/get_course_version")
def get_course_version(course_id: str = "RAG", user: dict = Depends(current_user)) -> dict:
    if course_id != COURSE["course_id"]:
        raise HTTPException(status_code=404, detail="DATA-404-01 课程不存在")
    return dict(COURSE)


@app.get("/tools/get_announcements")
def get_announcements(course_id: str = "RAG", user: dict = Depends(current_user)) -> dict:
    return {"course_id": course_id, "announcements": ANNOUNCEMENTS}


@app.post("/tools/report_progress")
def report_progress(body: ReportIn, user: dict = Depends(require_role("student"))) -> dict:
    if body.report_id in REPORTS:
        return {"accepted": 0, "rejected": 1, "errors": ["DATA-409-01 report_id 重复"]}
    if body.course_version != COURSE["latest_tag"]:
        return {"accepted": 0, "rejected": 1, "errors": ["DATA-422-02 课程版本不匹配"]}
    REPORTS[body.report_id] = {
        "student_id": user["student_id"],
        "report": body.model_dump(),
    }
    return {"accepted": 1, "rejected": 0, "errors": []}


@app.post("/tools/report_issue")
def report_issue(body: IssueIn, user: dict = Depends(require_role("student"))) -> dict:
    issue = {
        "issue_id": f"ISS-{len(ISSUES) + 1:03d}",
        "student_id": user["student_id"],
        **body.model_dump(),
        "status": "pending",
    }
    ISSUES.append(issue)
    return {"issue_id": issue["issue_id"], "eta": "一个工作日内"}


@app.get("/tools/get_class_view")
def get_class_view(course_id: str = "RAG", user: dict = Depends(require_role("teacher"))) -> dict:
    latest: dict[str, dict[str, dict]] = defaultdict(dict)
    for item in REPORTS.values():
        sid = item["student_id"]
        for stat in item["report"]["kp_stats"]:
            latest[stat["kp_id"]][sid] = stat

    out = []
    for kp_id, per_student in latest.items():
        n = len(per_student)
        if n < 5:
            out.append({"kp_id": kp_id, "students": n, "suppressed": True})
            continue
        dist = {s: 0 for s in KP_STATES}
        for stat in per_student.values():
            dist[stat["state"]] += 1
        out.append({
            "kp_id": kp_id,
            "students": n,
            "suppressed": False,
            "distribution": dist,
            "unmastered_ratio": round((dist["gap"] + dist["unseen"]) / n, 3),
            "correct_alone_rate": _rate(per_student, "correct_alone"),
            "correct_with_hint_rate": _rate(per_student, "correct_with_hint"),
        })
    return {"course_id": course_id, "kp_stats": out}


def _rate(per_student: dict, field: str) -> float | None:
    total = sum(getattr(s, field) + s.wrong for s in per_student.values())
    if total == 0:
        return None
    return round(sum(getattr(s, field) for s in per_student.values()) / total, 3)


@app.get("/tools/list_issues")
def list_issues(status: str = "pending", user: dict = Depends(require_role("teacher"))) -> dict:
    items = [i for i in ISSUES if i["status"] == status]
    return {"issues": items}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
