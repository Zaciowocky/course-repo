"""课程 MCP 服务的 mock 实现。

报文校验以 contracts/report.schema.json 为准，服务端不重复定义字段；
数据结构在内存里，重启即清空（真实实现见 README 的「换成 PostgreSQL」）。
"""
from __future__ import annotations

import json
import pathlib
import secrets
import time
from collections import defaultdict
from typing import Literal

import jsonschema
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_SCHEMA = json.loads((ROOT / "contracts" / "report.schema.json").read_text("utf8"))
VALIDATOR = jsonschema.Draft7Validator(REPORT_SCHEMA)

app = FastAPI(title="课程 MCP 服务（mock）", version="0.2.0")

COURSE = {
    "course_id": "RAG",
    "latest_tag": "v0.1.0",
    "changelog": "首版：检索增强生成基本结构",
    "migration_required": False,
    "report_schema_version": "report.v0.2",
}
ANNOUNCEMENTS = [
    {"id": "ANN-001", "title": "第一节已发布", "body": "请按 warm-up 提示开始。", "tag": "v0.1.0"}
]

TOKEN_TTL_SECONDS = 7 * 24 * 3600

# 班级视图阈值（任务书 4.4，老师可改）
MIN_SAMPLE = 5
UNMASTERED_RATIO = 0.6
HINT_GAP = 0.25
MISCONCEPTION_SHARE = 0.30
CONTENT_GAP_STUDENTS = 3

INVITES: dict[str, tuple[str, str]] = {
    "INV-ALPHA": ("2026101", "student"),
    "INV-BETA": ("2026102", "student"),
    "INV-GAMMA": ("2026103", "student"),
    "INV-DELTA": ("2026104", "student"),
    "INV-EPS": ("2026105", "student"),
    "INV-TEACHER": ("T-001", "teacher"),
}
TOKENS: dict[str, dict] = {}
REPORTS: dict[str, dict] = {}
ISSUES: list[dict] = []
STATE_ORDER = ["unseen", "gap", "partial", "transfer"]


class RegisterIn(BaseModel):
    student_id: str = Field(min_length=2)
    invite_code: str


class IssueIn(BaseModel):
    course_id: str
    kp_id: str
    question: str = Field(min_length=1)
    context: dict = Field(default_factory=dict)


# ---------- 鉴权 ----------

bearer_scheme = HTTPBearer(auto_error=False, description="注册接口返回的 token")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    if cred is None or not cred.credentials:
        raise HTTPException(status_code=401, detail="AUTH-401-01 缺少 token")
    token = cred.credentials.strip()
    record = TOKENS.get(token)
    if not record:
        raise HTTPException(status_code=401, detail="AUTH-401-01 token 无效")
    if record["revoked"]:
        raise HTTPException(status_code=401, detail="AUTH-401-03 token 已吊销")
    if record["expires_at"] < time.time():
        raise HTTPException(status_code=401, detail="AUTH-401-02 token 已过期")
    return {**record, "_token": token}


def require_role(role: str):
    def _dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] != role:
            raise HTTPException(status_code=403, detail="AUTH-403-01 越权访问")
        return user
    return _dep


def _issue_token(student_id: str, role: str) -> str:
    token = secrets.token_urlsafe(24)
    TOKENS[token] = {
        "student_id": student_id,
        "role": role,
        "issued_at": time.time(),
        "expires_at": time.time() + TOKEN_TTL_SECONDS,
        "revoked": False,
    }
    return token


def _json_path(err: jsonschema.ValidationError) -> str:
    parts = [str(p) for p in err.absolute_path]
    return ".".join(parts) or "<root>"


# ---------- 接口 ----------

@app.post("/auth/register")
def register(body: RegisterIn) -> dict:
    entry = INVITES.get(body.invite_code)
    if not entry:
        raise HTTPException(status_code=403, detail="AUTH-403-02 邀请码无效或已使用")
    if entry[0] != body.student_id:
        # 先校验学号再消耗，避免填错学号也把邀请码烧掉
        raise HTTPException(status_code=403, detail="AUTH-403-03 学号与邀请码不匹配")
    INVITES.pop(body.invite_code)
    return {"token": _issue_token(*entry), "role": entry[1], "student_id": entry[0]}


@app.post("/auth/revoke")
def revoke(user: dict = Depends(current_user)) -> dict:
    TOKENS[user["_token"]]["revoked"] = True
    return {"revoked": True, "student_id": user["student_id"]}


@app.get("/tools/get_course_version")
def get_course_version(course_id: str = "RAG", user: dict = Depends(current_user)) -> dict:
    if course_id != COURSE["course_id"]:
        raise HTTPException(status_code=404, detail="DATA-404-01 课程不存在")
    return dict(COURSE)


@app.get("/tools/get_announcements")
def get_announcements(course_id: str = "RAG", user: dict = Depends(current_user)) -> dict:
    return {"course_id": course_id, "announcements": ANNOUNCEMENTS}


@app.post("/tools/report_progress")
def report_progress(body: dict, user: dict = Depends(require_role("student"))) -> dict:
    """报文以契约校验：多一个字段、少一个必填字段都会被拒。"""
    try:
        VALIDATOR.validate(body)
    except jsonschema.ValidationError as err:
        raise HTTPException(
            status_code=422,
            detail=f"DATA-422-01 {_json_path(err)}: {err.message}",
        )

    report_id = body["report_id"]
    if report_id in REPORTS:
        return {"accepted": 0, "rejected": 1, "errors": ["DATA-409-01 report_id 重复"]}
    if body["course_version"] != COURSE["latest_tag"]:
        return {"accepted": 0, "rejected": 1, "errors": ["DATA-422-03 课程版本不匹配"]}
    if body["course_id"] != COURSE["course_id"]:
        return {"accepted": 0, "rejected": 1, "errors": ["DATA-422-04 课程不存在"]}

    REPORTS[report_id] = {
        "student_id": user["student_id"],
        "seq": len(REPORTS),
        "report": body,
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


def _latest_per_student() -> dict[str, dict[str, tuple]]:
    """每个知识点下，每名学生取 (period_to, seq) 最大的一条。"""
    latest: dict[str, dict[str, tuple]] = defaultdict(dict)
    for item in REPORTS.values():
        report = item["report"]
        rank_date = f"{report['period']['to']}|{item['seq']:06d}"
        for stat in report["kp_stats"]:
            current = latest[stat["kp_id"]].get(item["student_id"])
            if current is None or rank_date > current[0]:
                latest[stat["kp_id"]][item["student_id"]] = (rank_date, stat, report["tier"])
    return latest


@app.get("/tools/get_class_view")
def get_class_view(course_id: str = "RAG", user: dict = Depends(require_role("teacher"))) -> dict:
    latest = _latest_per_student()
    rows = []
    for kp_id, per_student in sorted(latest.items()):
        n = len(per_student)
        if n < MIN_SAMPLE:
            rows.append({"kp_id": kp_id, "students": n, "suppressed": True})
            continue

        dist = {s: 0 for s in STATE_ORDER}
        for _rank, stat, _tier in per_student.values():
            dist[stat["state"]] += 1

        standard = [s for _r, s, tier in per_student.values() if tier == "standard"]
        alone_rate = _rate(standard, "correct_alone")
        hint_rate = _rate(standard, "correct_with_hint")
        unmastered_ratio = round((dist["gap"] + dist["unseen"]) / n, 3)

        mis_share = defaultdict(int)
        for _r, stat, _t in per_student.values():
            for code in {m["code"] for m in stat.get("misconceptions", [])}:
                mis_share[code] += 1
        misconceptions = [
            {"code": code, "students": cnt, "share": round(cnt / n, 3)}
            for code, cnt in sorted(mis_share.items(), key=lambda kv: -kv[1])
        ]

        markers = []
        if unmastered_ratio >= UNMASTERED_RATIO:
            markers.append("unmastered_high")
        if alone_rate is not None and hint_rate is not None and hint_rate - alone_rate >= HINT_GAP:
            markers.append("hint_dependent")
        if any(m["share"] >= MISCONCEPTION_SHARE for m in misconceptions):
            markers.append("misconception_common")

        rows.append({
            "kp_id": kp_id,
            "students": n,
            "suppressed": False,
            "distribution": dist,
            "unmastered_ratio": unmastered_ratio,
            "correct_alone_rate": alone_rate,
            "correct_with_hint_rate": hint_rate,
            "misconceptions": misconceptions,
            "markers": markers,
        })

    return {
        "course_id": course_id,
        "min_sample": MIN_SAMPLE,
        "kp_stats": rows,
        "content_gaps": _content_gaps(),
    }


def _rate(stats: list[dict], field: str) -> float | None:
    total = sum(s.get(field, 0) + s.get("wrong", 0) for s in stats)
    if total == 0:
        return None
    return round(sum(s.get(field, 0) for s in stats) / total, 3)


def _content_gaps() -> list[dict]:
    """同一页面被 3 名以上学生报「找不到答案」时列出。"""
    pages: dict[str, set] = defaultdict(set)
    for item in REPORTS.values():
        for gap in item["report"].get("content_gaps", []):
            pages[gap["page_id"]].add(item["student_id"])
    return [
        {"page_id": page, "students": len(ids)}
        for page, ids in sorted(pages.items())
        if len(ids) >= CONTENT_GAP_STUDENTS
    ]


@app.get("/tools/list_issues")
def list_issues(status: str = "pending", user: dict = Depends(require_role("teacher"))) -> dict:
    return {"issues": [i for i in ISSUES if i["status"] == status]}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "reports": len(REPORTS), "tokens": len(TOKENS)}
