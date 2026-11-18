#!/usr/bin/env python3
"""课程仓库基础校验：YAML 可解析、ID 唯一、先修完整无环、来源与页面引用存在。"""
import sys
import pathlib

try:
    import yaml
except ImportError:
    sys.exit("缺少依赖：pip install pyyaml")

ROOT = pathlib.Path(__file__).resolve().parents[1]
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


def check_ids(items, prefix, kind):
    seen = set()
    for item in items:
        iid = item.get("id")
        if not iid:
            errors.append(f"{kind}：存在缺少 id 的条目")
            continue
        if not str(iid).startswith(prefix):
            errors.append(f"{kind}：{iid} 不符合 {prefix}* 命名")
        if iid in seen:
            errors.append(f"{kind}：id 重复 {iid}")
        seen.add(iid)
    return seen


syllabus = load("course/syllabus.yaml")
kps_doc = load("course/knowledge/knowledge_points.yaml")
sources_doc = load("course/knowledge/sources.yaml")
manifest = load("materials/manifest.yaml")

kps = (kps_doc or {}).get("knowledge_points", [])
sources = (sources_doc or {}).get("sources", [])
pages = (manifest or {}).get("pages", [])

kp_ids = check_ids(kps, "KP-", "知识点")
src_ids = check_ids(sources, "SRC-", "来源")
page_ids = {p.get("id") for p in pages if p.get("id")}

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

# 先修环检测
graph = {kp.get("id"): list(kp.get("prerequisites") or []) for kp in kps if kp.get("id")}
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

# 页面清单反向检查
for page in pages:
    kp = page.get("kp")
    if kp and kp not in kp_ids:
        errors.append(f"页面 {page.get('id')}：知识点 {kp} 不存在")
    rel = page.get("file")
    if rel and not (ROOT / rel).exists():
        errors.append(f"页面 {page.get('id')}：文件 {rel} 不存在")

for msg in warnings:
    print("WARN", msg)
for msg in errors:
    print("ERROR", msg)

if errors:
    print(f"\n校验失败：{len(errors)} 个错误，{len(warnings)} 个警告")
    sys.exit(1)

n_core = sum(1 for kp in kps if kp.get("core"))
print(f"校验通过：{len(kp_ids)} 个知识点（必修 {n_core}），{len(src_ids)} 条来源，{len(page_ids)} 个页面")
