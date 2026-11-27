#!/usr/bin/env python3
"""课程仓库结构校验：ID 规范、先修无环、来源与页面引用、误区编码。"""
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("缺少依赖：pip install pyyaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]

P = {
    "kp": r"^KP-[A-Z]{3,4}-[0-9]{3}$",
    "page": r"^PG-S[0-9]{2}-[0-9]{3}$",
    "src": r"^SRC-[0-9]{3}$",
    "mis": r"^MIS-[A-Z]{3,4}-[0-9]{3}-[0-9]{2}$",
}

errors = []
warnings = []


def load(rel):
    path = ROOT / rel
    if not path.exists():
        errors.append(f"{rel}：文件不存在")
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf8"))
    except Exception as exc:
        errors.append(f"{rel}：YAML 解析失败（{exc}）")
        return None


def check_id(value, kind, where):
    if not isinstance(value, str) or not re.match(P[kind], value):
        errors.append(f"{where}：{value} 不符合 {kind} 的 ID 规范")


def unique(ids, kind):
    seen = set()
    for i in ids:
        if i in seen:
            errors.append(f"{kind}：id 重复 {i}")
        seen.add(i)
    return seen


# 契约里的 ID 规则若存在，用契约里的
ids_doc = load("contracts/ids.yaml") or {}
prefixes = (ids_doc.get("prefixes") or {}) if isinstance(ids_doc, dict) else {}
for key, name in (("knowledge", "kp"), ("source", "src"),
                  ("page", "page"), ("misconception", "mis")):
    pat = (prefixes.get(key) or {}).get("pattern")
    if pat:
        P[name] = pat

syllabus = load("course/syllabus.yaml")
kps_doc = load("course/knowledge/knowledge_points.yaml")
sources_doc = load("course/knowledge/sources.yaml")
manifest = load("materials/manifest.yaml")

# manifest 防漂移：与页面实际扫描结果比对，不一致要求重新生成（契约：不手写）
try:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from build_manifest import scan_pages
    scanned = scan_pages()
    current = (manifest or {}).get("pages") or []
    normalize = lambda ps: [{k: p.get(k) for k in ("id", "file", "kp", "title", "slots")}
                            for p in ps]
    if normalize(current) != normalize(scanned):
        errors.append("manifest.yaml 与页面实际内容不一致："
                      "请运行 python tools/build_manifest.py 重新生成")
except Exception as exc:
    warnings.append(f"manifest 扫描比对跳过：{exc}")

kps = (kps_doc or {}).get("knowledge_points", [])
sources = (sources_doc or {}).get("sources", [])
pages = (manifest or {}).get("pages", [])

kp_ids, src_ids, page_ids = set(), set(), set()
for kp in kps:
    check_id(kp.get("id"), "kp", "知识点")
    kp_ids.add(kp.get("id"))
    for mis in kp.get("misconceptions") or []:
        check_id(mis.get("code"), "mis", f"{kp.get('id')} 的误区")
    if not kp.get("misconceptions"):
        warnings.append(f"{kp.get('id')}：未登记常见误区，学伴判错只能记 other")
for src in sources:
    check_id(src.get("id"), "src", "来源")
    src_ids.add(src.get("id"))
for page in pages:
    check_id(page.get("id"), "page", "页面")
    page_ids.add(page.get("id"))

unique([k.get("id") for k in kps], "知识点")
unique([s.get("id") for s in sources], "来源")
unique([p.get("id") for p in pages], "页面")

mis_seen = {}
for kp in kps:
    kp_id = kp.get("id", "?")
    for pre in kp.get("prerequisites") or []:
        if pre not in kp_ids:
            errors.append(f"{kp_id}：先修 {pre} 不存在")
    for src in kp.get("sources") or []:
        if src not in src_ids:
            errors.append(f"{kp_id}：来源 {src} 未登记")
    if not (kp.get("sources") or []):
        errors.append(f"{kp_id}：没有登记来源")
    for page in kp.get("pages") or []:
        if page not in page_ids:
            warnings.append(f"{kp_id}：页面 {page} 尚未在 manifest 登记")
    for field in ("objectives", "assessment", "difficulty"):
        if not kp.get(field):
            errors.append(f"{kp_id}：缺少 {field}")
    for mis in kp.get("misconceptions") or []:
        code = mis.get("code")
        if code in mis_seen:
            errors.append(f"误区编码重复：{code}（{mis_seen[code]} 与 {kp_id}）")
        mis_seen[code] = kp_id

graph = {k.get("id"): list(k.get("prerequisites") or []) for k in kps if k.get("id")}
state = {}


def visit(node, stack):
    if state.get(node) == 1:
        errors.append("先修关系存在环：" + " -> ".join(stack + [node]))
        return
    if state.get(node) == 2:
        return
    state[node] = 1
    for nxt in graph.get(node, []):
        if nxt in graph:
            visit(nxt, stack + [node])
    state[node] = 2


for node in graph:
    visit(node, [])

for page in pages:
    kp = page.get("kp")
    if kp and kp not in kp_ids:
        errors.append(f"页面 {page.get('id')}：知识点 {kp} 不存在")
    rel = page.get("file")
    if rel and not (ROOT / rel).exists():
        errors.append(f"页面 {page.get('id')}：文件 {rel} 不存在")

if syllabus and not (syllabus.get("course") or {}).get("id"):
    errors.append("syllabus.yaml：缺少 course.id")

for msg in warnings:
    print("WARN", msg)
for msg in errors:
    print("ERROR", msg)

if errors:
    print(f"\n校验失败：{len(errors)} 个错误，{len(warnings)} 个警告")
    sys.exit(1)

n_core = sum(1 for kp in kps if kp.get("core"))
print(f"校验通过：{len(kp_ids)} 个知识点（必修 {n_core}）、{len(mis_seen)} 个误区编码、"
      f"{len(src_ids)} 条来源、{len(page_ids)} 个页面")
