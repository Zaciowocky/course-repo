#!/usr/bin/env python3
"""扫描 materials/ 下的课件页面，反向生成 materials/manifest.yaml。

契约约定：manifest 由检查脚本扫描页面中的 data-kp / data-node-id 反向生成，
不由人手写，保证装配图纸与页面实际内容不漂移。

页面约定：
- 文件头注释 `<!-- pg: PG-S01-001 kp: KP-RAG-001 -->` 声明页面 ID 与主知识点；
- 页面内扩展节点用 `data-node-id="NODE-S01-001"` 标记；
- 无头注释的 HTML（如 index.html）视为导航页，不进入 manifest。
"""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "materials"
MANIFEST = MATERIALS / "manifest.yaml"

HEADER = re.compile(
    r"<!--\s*pg:\s*(PG-S\d{2}-\d{3})\s+kp:\s*(KP-[A-Z]{3,4}-\d{3})\s*-->", re.I)
NODE = re.compile(r'data-node-id="(NODE-S\d{2}-\d{3})"')
TITLE = re.compile(r"<title>\s*(.*?)\s*</title>", re.S | re.I)


def scan_pages():
    """扫描全部课件页面，返回 manifest pages 列表（按页面 ID 排序）。"""
    pages = []
    if not MATERIALS.exists():
        return pages
    for html in sorted(MATERIALS.rglob("*.html")):
        text = html.read_text(encoding="utf8")
        head = HEADER.search(text)
        if not head:
            continue
        nodes = list(dict.fromkeys(NODE.findall(text)))
        title = TITLE.search(text)
        pages.append({
            "id": head.group(1),
            "file": html.relative_to(ROOT).as_posix(),
            "kp": head.group(2),
            "title": title.group(1) if title else "",
            "slots": nodes,
        })
    pages.sort(key=lambda p: p["id"])
    return pages


def main():
    pages = scan_pages()
    version = "0.1.0"
    if MANIFEST.exists():
        old = yaml.safe_load(MANIFEST.read_text(encoding="utf8")) or {}
        version = old.get("version", version)
    doc = {
        "version": version,
        # 契约：本文件由 tools/build_manifest.py 扫描生成，禁止手改
        "pages": pages,
    }
    MANIFEST.write_text(
        "# 由 tools/build_manifest.py 扫描生成，请勿手写；改动请改页面后重新生成\n"
        + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf8",
    )
    print(f"manifest 已生成：{len(pages)} 个页面，"
          f"{sum(len(p['slots']) for p in pages)} 个扩展节点")


if __name__ == "__main__":
    sys.exit(main())
