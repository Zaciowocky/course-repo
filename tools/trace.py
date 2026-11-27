#!/usr/bin/env python3
"""从知识点 ID 回溯一条可审计的链：知识点 → 来源 → 页面 → 最近改动。

用法：
    python tools/trace.py KP-RAG-001
    python tools/trace.py KP-RAG-001 --json
"""
import json
import pathlib
import subprocess
import sys

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(rel):
    path = ROOT / rel
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf8"))


def recent(paths, limit=3):
    cmd = ["git", "log", f"-{limit}", "--date=short",
           "--pretty=format:%h %ad %an %s", "--"] + paths
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        return [line for line in out.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def build(kp_id):
    kps = (load("course/knowledge/knowledge_points.yaml") or {}).get("knowledge_points", [])
    sources = (load("course/knowledge/sources.yaml") or {}).get("sources", [])
    pages = (load("materials/manifest.yaml") or {}).get("pages", [])

    kp = next((k for k in kps if k.get("id") == kp_id), None)
    if not kp:
        return None

    src_map = {s.get("id"): s for s in sources}
    used_sources = [src_map[s] for s in kp.get("sources", []) if s in src_map]
    bound_pages = [p for p in pages if p.get("kp") == kp_id]

    return {
        "knowledge_point": {
            "id": kp.get("id"),
            "title": kp.get("title"),
            "session": kp.get("session"),
            "difficulty": kp.get("difficulty"),
            "core": kp.get("core", False),
            "prerequisites": kp.get("prerequisites", []),
            "objectives": kp.get("objectives", []),
            "assessment": kp.get("assessment"),
            "misconceptions": kp.get("misconceptions", []),
        },
        "sources": [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "tier": s.get("tier"),
                "publisher": s.get("publisher"),
                "url": s.get("url"),
                "fetched": str(s.get("fetched")),
            }
            for s in used_sources
        ],
        "pages": [
            {"id": p.get("id"), "file": p.get("file"), "title": p.get("title")}
            for p in bound_pages
        ],
        "recent_changes": recent([
            "course/knowledge/knowledge_points.yaml",
            "course/knowledge/sources.yaml",
            "materials/manifest.yaml",
        ] + [p.get("file") for p in bound_pages if p.get("file")]),
    }


def render(data):
    kp = data["knowledge_point"]
    lines = [
        f"知识点 {kp['id']}  {kp['title']}",
        f"  课节 {kp['session']} · 难度 {kp['difficulty']} · {'必修' if kp['core'] else '选修'}",
    ]
    if kp["prerequisites"]:
        lines.append(f"  先修：{'、'.join(kp['prerequisites'])}")
    if kp["objectives"]:
        lines.append(f"  目标：{kp['objectives'][0]}")
    if kp["assessment"]:
        lines.append(f"  验收：{kp['assessment']}")
    for mis in kp["misconceptions"]:
        lines.append(f"  误区：{mis.get('code')}  {mis.get('name')}")

    lines.append("")
    lines.append(f"来源 {len(data['sources'])} 条")
    for s in data["sources"]:
        lines.append(f"  [{s['id']}] {s['tier']} · {s['publisher']} · 登记于 {s['fetched']}")
        lines.append(f"      {s['title']}")
        if s["url"] and s["url"] != "local":
            lines.append(f"      {s['url']}")

    lines.append("")
    if data["pages"]:
        lines.append(f"页面 {len(data['pages'])} 个")
        for p in data["pages"]:
            lines.append(f"  {p['id']}  {p['file']}  {p.get('title') or ''}".rstrip())
    else:
        lines.append("页面 0 个（尚未生成，manifest 未登记）")

    lines.append("")
    lines.append("最近改动")
    for c in data["recent_changes"] or ["（无提交记录）"]:
        lines.append(f"  {c}")
    return "\n".join(lines)


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    kp_id = argv[1]
    data = build(kp_id)
    if not data:
        print(f"找不到知识点 {kp_id}", file=sys.stderr)
        return 1
    if "--json" in argv:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
