# Windows compatibility modifications: 2026-09-06. AGPL-3.0-only; see WINDOWS-CHANGES.md.
#!/usr/bin/env python3
"""Sectioned Markdown site and complete flagship HTML for WeChat reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit


GENERATED_NAMES = {"wechat_daily_full.md", "wechat_daily_report.md"}
MARKDOWN_SITE_DIR = "wechat-report"
GROUP_VALUE_DIMENSIONS = (
    "AI", "赚钱", "培训", "商单", "出海", "产品", "Web3",
    "自媒体运营与增长", "合作", "B端AI赋能",
)


@dataclass(frozen=True)
class ReportSource:
    path: Path
    relative_path: str
    source_id: str
    title: str
    kind: str
    priority: int
    collapsed: bool = False


@dataclass(frozen=True)
class ReportPage:
    route: str
    filename: str
    title: str
    nav_label: str
    description: str
    glyph: str
    priority: int
    sources: tuple[ReportSource, ...]


SOURCE_RULES: tuple[tuple[str, str, str, int, bool], ...] = (
    ("final_report.md", "执行结论", "overview", 10, False),
    ("action_overview.md", "行动与商机机器总览", "internal", 79, True),
    ("group-daily/group_daily_topics.md", "话题日报", "groups", 20, False),
    ("group-daily/group_daily_groups.md", "重点群聊", "groups", 21, False),
    ("group-daily/group_daily_brief.md", "群聊日报", "groups", 22, False),
    ("contact-daily/contact_daily_brief.md", "重点联系人日报", "contacts", 30, False),
    ("group-daily/cross_group_links.md", "商单信号雷达", "radar", 40, False),
    ("group-daily/group_daily_appendix.md", "群聊证据附录", "internal", 80, True),
    ("group-daily/group_daily_digest.md", "群聊机器初筛", "internal", 81, True),
    ("group-daily/group_selection_matrix.md", "全部群聊价值矩阵", "internal", 82, True),
    ("contact-daily/contact_daily_digest.md", "私信机器初筛", "internal", 82, True),
)


PAGE_SPECS: tuple[tuple[str, str, str, str, str, str, int], ...] = (
    ("overview", "index.md", "综合行动报告", "综合行动", "先看结论、优先行动、正在推进的商机和覆盖范围。", "●", 10),
    ("groups", "groups.md", "群聊日报", "群聊日报", "在话题、重点群聊和全部群聊筛选之间切换；建议级别只针对本时段。", "#", 20),
    ("contacts", "contacts.md", "重点联系人", "重点联系人", "查看品牌方、中间人和自媒体博主的待回复、等待与复联。", "◎", 30),
    ("radar", "radar.md", "商单信号雷达", "信号雷达", "每个标准化链接只出现一次，用于判断哪些品牌正在集中投放。", "↗", 40),
)

KIND_LABELS = {kind: label for kind, _, _, label, _, _, _ in PAGE_SPECS}


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9\u3400-\u9fff]+", "-", value.lower()).strip("-")
    return value or "section"


def _markdown_title(text: str, fallback: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    if not match:
        return fallback
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", match.group(1))
    return re.sub(r"[`*_]", "", value).strip() or fallback


def _source_rule(relative_path: str) -> tuple[str, str, int, bool] | None:
    for pattern, title, kind, priority, collapsed in SOURCE_RULES:
        if relative_path == pattern:
            return title, kind, priority, collapsed
    return None


def discover_report_sources(report_dir: Path) -> list[ReportSource]:
    root = report_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"找不到报告目录：{root}")

    used_ids: set[str] = set()
    sources: list[ReportSource] = []
    dual_group_report = any(
        (root / "group-daily" / name).exists()
        for name in ("group_daily_topics.md", "group_daily_groups.md")
    )
    for path in sorted(root.rglob("*.md")):
        relative_path = path.relative_to(root).as_posix()
        if path.name in GENERATED_NAMES or path.name.startswith(".") or relative_path.startswith(f"{MARKDOWN_SITE_DIR}/"):
            continue
        if dual_group_report and relative_path == "group-daily/group_daily_brief.md":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rule = _source_rule(relative_path)
        if rule:
            title, kind, priority, collapsed = rule
        else:
            title = _markdown_title(text, path.stem.replace("_", " "))
            kind, priority, collapsed = "other", 60, True
        base = _slug(relative_path.removesuffix(".md"))
        source_id = base
        suffix = 2
        while source_id in used_ids:
            source_id = f"{base}-{suffix}"
            suffix += 1
        used_ids.add(source_id)
        sources.append(ReportSource(path, relative_path, source_id, title, kind, priority, collapsed))
    return sorted(sources, key=lambda item: (item.priority, item.relative_path))


def build_report_pages(sources: list[ReportSource]) -> list[ReportPage]:
    grouped: dict[str, list[ReportSource]] = {}
    for source in sources:
        grouped.setdefault(source.kind, []).append(source)
    pages: list[ReportPage] = []
    for kind, filename, title, nav_label, description, glyph, priority in PAGE_SPECS:
        page_sources = tuple(grouped.get(kind, []))
        if page_sources:
            pages.append(ReportPage(kind, filename, title, nav_label, description, glyph, priority, page_sources))
    return pages


def _normalize_details_markdown(text: str) -> str:
    """Turn leaked HTML disclosure markup into readable Markdown headings."""
    text = re.sub(r"(?is)<details(?:\s+open)?>\s*", "", text)
    text = re.sub(r"(?is)\s*</details>", "", text)

    def replace_summary(match: re.Match[str]) -> str:
        value = re.sub(r"(?is)</?strong>", "", match.group(1))
        value = re.sub(r"\s+", " ", value).strip()
        if "｜" in value:
            title, note = (part.strip() for part in value.split("｜", 1))
            return f"### {title}\n\n> {note}"
        return f"### {value}"

    text = re.sub(r"(?is)<summary>(.*?)</summary>", replace_summary, text)
    text = re.sub(r"(?ms)^##\s+(?:详细报告|报告路径)\s*\n.*?(?=^##\s+|\Z)", "", text)
    return text.strip()


def _strip_first_h1(text: str) -> str:
    return re.sub(r"(?m)^#\s+.+?\s*\n+", "", text, count=1).strip()


def build_combined_markdown(sources: list[ReportSource], *, title: str, generated_at: str) -> str:
    """Compatibility helper; the flagship renderer no longer writes this long form."""
    parts = [f"# {title}", "", f"> 综合 {len(sources)} 份本轮 Markdown 报告｜生成时间：{generated_at}", ""]
    for source in sources:
        text = source.path.read_text(encoding="utf-8", errors="replace")
        parts.extend([f"## {source.title}", "", f"> 来源文件：`{source.relative_path}`", "", _strip_first_h1(text), ""])
    return "\n".join(parts).rstrip() + "\n"


def _markdown_navigation(pages: list[ReportPage], current_route: str) -> str:
    links = []
    for page in pages:
        label = f"**{page.nav_label}**" if page.route == current_route else page.nav_label
        links.append(f"[{label}]({page.filename})")
    return " · ".join(links)


def _rewrite_markdown_links(
    text: str,
    *,
    source: ReportSource,
    source_pages: dict[Path, ReportPage],
    markdown_dir: Path,
) -> str:
    def replace(match: re.Match[str]) -> str:
        marker, label, href = match.group(1), match.group(2), match.group(3)
        try:
            parsed = urlsplit(href)
        except ValueError:
            return match.group(0)
        if parsed.scheme in {"http", "https", "mailto"} or href.startswith("#"):
            return match.group(0)
        candidate = (source.path.parent / unquote(parsed.path)).resolve()
        target_page = source_pages.get(candidate)
        if target_page:
            target = target_page.filename + (f"#{parsed.fragment}" if parsed.fragment else "")
            return f"{marker}[{label}]({target})"
        if candidate.name in GENERATED_NAMES:
            return f"{marker}[{label}](index.md)"
        if candidate.name == "wechat_daily_report.html":
            return f"{marker}[{label}](../wechat_daily_report.html#/overview)"
        if parsed.path:
            relative = Path(os.path.relpath(candidate, markdown_dir)).as_posix()
            target = relative + (f"#{parsed.fragment}" if parsed.fragment else "")
            return f"{marker}[{label}]({target})"
        return match.group(0)

    return re.sub(r"(!?)\[([^]]*)\]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)", replace, text)


def _build_page_markdown(
    page: ReportPage,
    *,
    pages: list[ReportPage],
    source_pages: dict[Path, ReportPage],
    markdown_dir: Path,
    generated_at: str,
) -> str:
    parts = [
        f"# {page.title}", "", f"> {page.description}｜生成时间：{generated_at}", "",
        _markdown_navigation(pages, page.route), "", "---", "",
    ]
    multiple = len(page.sources) > 1
    for source in page.sources:
        text = _normalize_details_markdown(_rewrite_markdown_links(
            source.path.read_text(encoding="utf-8", errors="replace"),
            source=source,
            source_pages=source_pages,
            markdown_dir=markdown_dir,
        ))
        if multiple:
            parts.extend([f"## {source.title}", "", f"> 来源：`{source.relative_path}`", ""])
        parts.extend([_strip_first_h1(text), ""])
    parts.extend(["---", "", f"[返回报告入口](../wechat_daily_full.md) · [打开交互版](../wechat_daily_report.html#/{page.route})", ""])
    return "\n".join(parts).rstrip() + "\n"


def write_markdown_site(
    report_dir: Path,
    pages: list[ReportPage],
    *,
    portal_path: Path,
    title: str,
    generated_at: str,
) -> dict[str, str]:
    root = report_dir.expanduser().resolve()
    markdown_dir = root / MARKDOWN_SITE_DIR
    markdown_dir.mkdir(parents=True, exist_ok=True)
    expected_files = {page.filename for page in pages}
    if any(page.route == "groups" and len(page.sources) > 1 for page in pages):
        expected_files.update({"group-topics.md", "key-groups.md"})
    for stale_path in markdown_dir.glob("*.md"):
        if stale_path.name not in expected_files:
            stale_path.unlink()
    source_pages = {source.path.resolve(): page for page in pages for source in page.sources}
    markdown_by_route: dict[str, str] = {}
    for page in pages:
        if page.route == "groups" and len(page.sources) > 1:
            group_links: list[str] = []
            for source in page.sources:
                filename = "group-topics.md" if source.relative_path.endswith("group_daily_topics.md") else "key-groups.md"
                source_page = ReportPage(page.route, filename, source.title, source.title, page.description, page.glyph, page.priority, (source,))
                source_content = _build_page_markdown(
                    source_page,
                    pages=pages,
                    source_pages=source_pages,
                    markdown_dir=markdown_dir,
                    generated_at=generated_at,
                )
                (markdown_dir / filename).write_text(source_content, encoding="utf-8")
                group_links.append(f"- [{source.title}]({filename})")
            matrix_path = root / "group-daily" / "group_selection_matrix.md"
            if matrix_path.exists():
                group_links.append("- [全部群聊价值矩阵](../group-daily/group_selection_matrix.md)")
            content = "\n".join([
                f"# {page.title}", "", f"> {page.description}", "", _markdown_navigation(pages, page.route), "",
                "## 选择阅读方式", "", *group_links, "",
                "话题日报用于跨群理解同一事件；重点群聊用于回到具体群查看上下文；全部群聊价值矩阵用于逐群调整关注级别。", "",
                "---", "", "[返回报告入口](../wechat_daily_full.md) · [打开交互版](../wechat_daily_report.html#/groups)", "",
            ])
        else:
            content = _build_page_markdown(
                page,
                pages=pages,
                source_pages=source_pages,
                markdown_dir=markdown_dir,
                generated_at=generated_at,
            )
        (markdown_dir / page.filename).write_text(content, encoding="utf-8")
        markdown_by_route[page.route] = content

    lines = [
        f"# {title}", "",
        f"> 生成时间：{generated_at}｜{len(pages)} 个阅读分区｜完整内容已按主题拆分，不再纵向拼成一篇长文。",
        "", "## 阅读入口", "", "- [打开旗舰版交互日报](wechat_daily_report.html)",
    ]
    lines.extend(f"- [{page.title}]({MARKDOWN_SITE_DIR}/{page.filename})：{page.description}" for page in pages)
    lines.extend([
        "", "## 阅读说明", "",
        "- 交互 HTML 只保留综合行动、群聊日报、重点联系人和商单信号雷达四个入口。",
        "- 群聊日报可切换话题视角和重点群视角；Markdown 也分成两份，不再纵向堆叠。",
        "- 证据附录和机器初筛仍保留在本地运行目录，但不作为阅读入口。",
        "- 所有微信读取均为本地只读，报告不会自动发送消息。", "",
    ])
    portal_path.parent.mkdir(parents=True, exist_ok=True)
    portal_path.write_text("\n".join(lines), encoding="utf-8")
    return markdown_by_route


def _pandoc_fragment(source: ReportSource, pandoc: str) -> str:
    command = [pandoc, "--from=gfm", "--to=html5", f"--id-prefix={source.source_id}-"]
    normalized = _normalize_details_markdown(source.path.read_text(encoding="utf-8", errors="replace"))
    result = subprocess.run(command, input=normalized, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Pandoc 转换失败").strip()
        raise RuntimeError(f"{source.relative_path}: {detail}")
    return re.sub(r"(?s)^.*?<h1[^>]*>.*?</h1>", "", result.stdout, count=1).strip()


def _rewrite_html_links(fragment: str, *, source: ReportSource, source_pages: dict[Path, ReportPage]) -> str:
    def replace(match: re.Match[str]) -> str:
        before, href, after = match.group(1), match.group(2), match.group(3)
        try:
            parsed = urlsplit(href)
        except ValueError:
            return match.group(0)
        if parsed.scheme in {"http", "https"}:
            return f'<a{before}href="{href}"{after} target="_blank" rel="noopener noreferrer" class="original-link">'
        if parsed.scheme:
            return match.group(0)
        if href.startswith("#"):
            return f'<a{before}href="#/{source.kind}/{source.source_id}-{parsed.fragment}"{after} class="internal-link">'
        candidate = (source.path.parent / unquote(parsed.path)).resolve()
        target_page = source_pages.get(candidate)
        if target_page:
            target_source = next(item for item in target_page.sources if item.path.resolve() == candidate)
            anchor = f"{target_source.source_id}-{parsed.fragment}" if parsed.fragment else f"source-{target_source.source_id}"
            return f'<a{before}href="#/{target_page.route}/{anchor}"{after} class="internal-link">'
        if candidate.name in GENERATED_NAMES or candidate.name == "wechat_daily_report.html":
            return f'<a{before}href="#/overview"{after} class="internal-link">'
        return match.group(0)

    return re.sub(r'<a([^>]*?)href="([^"]+)"([^>]*)>', replace, fragment)


def _external_urls(text: str) -> set[str]:
    urls = set(re.findall(r"https?://[^\s<>()\]\[\"']+", text))
    return {url.rstrip(".,;:!?，。；：！？") for url in urls}


def _reading_minutes(text: str) -> int:
    chinese = len(re.findall(r"[\u3400-\u9fff]", text))
    latin = len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", text))
    return max(1, round(chinese / 500 + latin / 250))


def _heading_count(page: ReportPage) -> int:
    return sum(len(re.findall(r"(?m)^#{2,4}\s+", source.path.read_text(encoding="utf-8", errors="replace"))) for source in page.sources)


def _wrap_key_group_sections(fragment: str) -> str:
    """Make each key-group heading an HTML disclosure without touching Markdown."""
    heading_pattern = re.compile(r'<h2(?:\s+id="([^"]+)")?[^>]*>(.*?)</h2>', re.I | re.S)
    matches = list(heading_pattern.finditer(fragment))
    if not matches:
        return fragment
    parts = [fragment[:matches[0].start()]]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(fragment)
        anchor = match.group(1) or f"key-group-{index + 1}"
        title = match.group(2).strip()
        body = fragment[match.end():end].strip()
        open_attribute = " open" if index == 0 else ""
        parts.append(
            f'<details class="key-group-card" id="{escape(anchor)}"{open_attribute}>'
            f'<summary><span class="key-group-title">{title}</span><span class="key-group-hint">点击展开</span></summary>'
            f'<div class="key-group-body">{body}</div></details>'
        )
    return "".join(parts)


def _load_group_matrix(report_dir: Path) -> dict[str, object] | None:
    path = report_dir / "group-daily" / "group_selection_matrix.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    groups = payload.get("groups") if isinstance(payload, dict) else None
    return payload if isinstance(groups, list) else None


def _render_group_selector(payload: dict[str, object]) -> str:
    raw_rows = payload.get("groups")
    rows = raw_rows if isinstance(raw_rows, list) else []
    level_options = ("重点", "雷达观察", "关注", "低优先级", "排除候选")
    raw_dimensions = payload.get("dimensions")
    dimensions = tuple(
        str(item).strip() for item in raw_dimensions
        if str(item).strip()
    ) if isinstance(raw_dimensions, list) else GROUP_VALUE_DIMENSIONS
    row_html: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        group = str(row.get("群聊") or "未命名群聊")
        level = str(row.get("建议关注级别") or "关注")
        tags = [label for label in dimensions if bool(row.get(label))]
        rendered_tags: list[str] = []
        for tag in tags:
            count = int(row.get(f"{tag}消息数") or 0)
            suffix = f" · {count}" if count else ""
            rendered_tags.append(f'<span class="matrix-tag">{escape(tag)}{suffix}</span>')
        tag_html = "".join(rendered_tags) or '<span class="matrix-tag muted-tag">无目标标签</span>'
        options = "".join(
            f'<option value="{escape(option)}"{" selected" if option == level else ""}>{escape(option)}</option>'
            for option in level_options
        )
        row_html.append(
            f'<article class="matrix-row" data-group-row data-group-name="{escape(group.lower())}" '
            f'data-level="{escape(level)}" data-tags="{escape(",".join(tags))}">'
            '<div class="matrix-group"><details class="matrix-detail">'
            f'<summary><strong>{escape(group)}</strong><span class="matrix-expand-hint">展开</span></summary>'
            f'<div class="matrix-detail-body"><p><b>群聊类型：</b>{escape(str(row.get("群聊类型") or "一般信息"))}</p>'
            f'<p><b>主要主题：</b>{escape(str(row.get("主要主题") or "未识别"))}</p>'
            f'<p><b>判断：</b>{escape(str(row.get("判断依据") or ""))}</p></div></details></div>'
            f'<div class="matrix-activity"><strong>{escape(str(row.get("活跃度") or "低"))}</strong>'
            f'<span>{escape(str(row.get("消息数") or 0))} 条 / 有效 {escape(str(row.get("有效讨论数") or 0))}</span></div>'
            f'<div class="matrix-tags">{tag_html}</div>'
            f'<div class="matrix-reason">{escape(str(row.get("判断依据") or ""))}</div>'
            f'<label class="matrix-choice"><span class="sr-only">设置 {escape(group)} 的关注级别</span>'
            f'<select data-group-priority data-suggested="{escape(level)}" data-group="{escape(group)}">{options}</select></label>'
            '</article>'
        )
    basis = escape(str(payload.get("basis") or "建议级别只针对本时段，不等于永久排除。"))
    return (
        '<section class="source-document group-selector" id="group-selection-matrix" data-group-view="selector">'
        '<header class="source-title"><p>群聊管理</p><h2>全部群聊筛选</h2>'
        f'<span class="selector-note">{basis}</span></header>'
        '<div class="matrix-toolbar">'
        '<label class="matrix-search"><span class="sr-only">搜索群名</span><input id="group-matrix-search" type="search" placeholder="搜索群名"></label>'
        '<label><span>关注级别</span><select id="group-level-filter"><option value="all">全部</option><option value="重点">重点</option><option value="雷达观察">雷达观察</option><option value="关注">关注</option><option value="低优先级">低优先级</option><option value="排除候选">排除候选</option></select></label>'
        '<label><span>目标方向</span><select id="group-tag-filter"><option value="all">全部</option>'
        + "".join(f'<option value="{escape(tag)}">{escape(tag)}</option>' for tag in dimensions)
        + '</select></label><button class="matrix-export" id="group-selection-export" type="button">导出选择</button></div>'
        '<div class="matrix-head"><span>群聊（点击展开）</span><span>活跃度</span><span>相关方向</span><span>本时段判断</span><span>我的选择</span></div>'
        f'<div class="matrix-list">{"".join(row_html)}</div><p class="matrix-empty" id="group-matrix-empty" hidden>没有符合当前筛选条件的群聊。</p>'
        '</section>'
    )


def _render_page(
    page: ReportPage,
    fragments: dict[str, str],
    group_matrix: dict[str, object] | None = None,
) -> str:
    sections: list[str] = []
    multiple = len(page.sources) > 1
    for source in page.sources:
        group_view = ""
        if source.relative_path.endswith("group_daily_topics.md"):
            group_view = "topics"
        elif source.relative_path.endswith("group_daily_groups.md"):
            group_view = "groups"
        elif page.route == "groups":
            group_view = "topics"
        heading = (
            f'<header class="source-title"><p>{escape(KIND_LABELS.get(source.kind, "报告"))}</p><h2>{escape(source.title)}</h2><code>{escape(source.relative_path)}</code></header>'
            if multiple else f'<p class="source-origin">完整来源 · {escape(source.relative_path)}</p>'
        )
        fragment = fragments[source.source_id]
        if source.relative_path.endswith("group_daily_groups.md"):
            fragment = _wrap_key_group_sections(fragment)
        sections.append(
            f'<section class="source-document" id="source-{escape(source.source_id)}" data-source="{escape(source.relative_path)}"'
            f'{f" data-group-view={json.dumps(group_view)}" if group_view else ""}>{heading}'
            f'<div class="markdown-body">{fragment}</div></section>'
        )
    if page.route == "groups" and group_matrix:
        sections.append(_render_group_selector(group_matrix))
    switcher = ""
    if page.route == "groups" and len(page.sources) > 1:
        switcher = (
            '<div class="view-switcher" role="tablist" aria-label="群聊日报阅读方式">'
            '<button class="view-button active" type="button" data-group-view-button="topics" role="tab" aria-selected="true">话题日报</button>'
            '<button class="view-button" type="button" data-group-view-button="groups" role="tab" aria-selected="false">重点群聊</button>'
            + ('<button class="view-button" type="button" data-group-view-button="selector" role="tab" aria-selected="false">群聊筛选</button>' if group_matrix else '')
            + '</div>'
        )
    return (
        f'<section class="report-page" data-route="{escape(page.route)}" hidden>'
        f'<header class="page-head"><div><p class="overline">WeChat intelligence report</p><h1>{escape(page.title)}</h1><p>{escape(page.description)}</p></div>'
        f'<div class="page-stat"><strong>{_heading_count(page)}</strong><span>内容节点</span></div></header>'
        f'{switcher}<div class="page-content">{"".join(sections)}</div></section>'
    )


def _replace_tokens(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"__{key}__", value)
    return template


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="微信个人情报库综合交互日报">
  <title>__PAGE_TITLE__</title>
  <style>
    :root { color-scheme: light; --chrome:#20242a; --chrome-2:#2a3037; --canvas:#eef1f4; --paper:#fff; --paper-2:#f6f8fa; --ink:#171b20; --muted:#69737e; --faint:#8b949e; --line:#dce1e6; --line-strong:#cbd1d8; --green:#168c72; --green-soft:#e8f5f1; --blue:#3975c5; --coral:#d96552; --amber:#a56d13; --shadow:0 12px 32px rgba(28,39,49,.06); }
    html[data-theme="dark"] { color-scheme:dark; --canvas:#171b20; --paper:#21262c; --paper-2:#282e35; --ink:#edf1f5; --muted:#afb7c0; --faint:#848e98; --line:#39414a; --line-strong:#4a535e; --green:#75d9c0; --green-soft:#213d37; --coral:#ee806f; --shadow:0 18px 48px rgba(0,0,0,.25); }
    * { box-sizing:border-box; }
    html,body { margin:0; min-height:100%; }
    html { scroll-behavior:smooth; }
    body { background:var(--canvas); color:var(--ink); font:14px/1.7 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; letter-spacing:0; }
    button,input { font:inherit; letter-spacing:0; } button { cursor:pointer; } a { color:var(--green); text-underline-offset:3px; overflow-wrap:anywhere; }
    .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
    .app { min-height:100vh; }
    .sidebar { position:fixed; inset:0 0 auto 0; z-index:30; height:64px; display:flex; align-items:stretch; padding:0 28px; background:var(--chrome); color:#c8ced6; }
    .brand { min-width:250px; display:flex; align-items:center; gap:10px; color:#fff; font-weight:800; }
    .brand-mark { width:26px; height:26px; display:grid; place-items:center; border-radius:5px; background:#75d9c0; color:#10241f; font-size:12px; font-weight:900; }
    .workspace-switch,.nav-label,.sidebar-foot { display:none; }
    .nav-item { display:flex; align-items:center; gap:7px; min-height:64px; padding:0 17px; border-bottom:3px solid transparent; color:#c8ced6; text-decoration:none; font-size:13px; }
    .nav-item:hover { color:#fff; } .nav-item.active { border-color:#75d9c0; background:var(--chrome-2); color:#fff; }
    .nav-glyph { width:14px; display:grid; place-items:center; color:#8f99a4; font-size:10px; } .nav-item.active .nav-glyph { color:#75d9c0; }
    .nav-count { display:none; }
    .fresh-dot { display:inline-block; width:6px; height:6px; margin-right:6px; border-radius:50%; background:#72d29f; }
    .workspace { min-width:0; padding-top:64px; }
    .location-bar { position:sticky; top:64px; z-index:25; height:54px; display:flex; align-items:center; gap:13px; padding:0 30px; border-bottom:1px solid var(--line-strong); background:color-mix(in srgb,var(--paper-2) 94%,transparent); backdrop-filter:blur(18px); }
    .crumbs { min-width:250px; color:var(--muted); font-size:11px; } .crumbs strong { color:var(--ink); }
    .search-wrap { position:relative; width:min(470px,42vw); margin:0 auto; }
    .search-input { width:100%; height:34px; padding:0 58px 0 11px; border:1px solid var(--line-strong); border-radius:6px; background:color-mix(in srgb,var(--paper) 88%,transparent); color:var(--ink); outline:none; }
    .search-input:focus { border-color:var(--green); box-shadow:0 0 0 3px color-mix(in srgb,var(--green) 15%,transparent); }
    .key { position:absolute; right:8px; top:7px; padding:1px 5px; border:1px solid var(--line); border-radius:4px; color:var(--faint); font-size:9px; }
    .toolbar { display:flex; gap:7px; } .icon-button { width:32px; height:32px; padding:0; border:1px solid var(--line-strong); border-radius:6px; background:var(--paper); color:var(--muted); }
    .icon-button:hover { border-color:var(--green); color:var(--green); }
    .mobile-routes { display:none; }
    .report-page { padding:26px 30px 64px; } .report-page[hidden] { display:none!important; }
    .page-head { max-width:1080px; margin:0 auto 25px; display:flex; align-items:end; justify-content:space-between; gap:24px; padding-bottom:22px; border-bottom:1px solid var(--line-strong); }
    .overline { margin:0 0 5px; color:var(--green); font-size:10px; font-weight:800; text-transform:uppercase; }
    .page-head h1 { margin:0; font-size:30px; line-height:1.24; } .page-head p:not(.overline) { margin:7px 0 0; color:var(--muted); font-size:12px; }
    .page-stat { min-width:74px; padding-left:13px; border-left:2px solid var(--coral); } .page-stat strong { display:block; font-size:18px; line-height:1.2; } .page-stat span { color:var(--faint); font-size:9px; }
    .page-content { max-width:1080px; margin:0 auto; } .source-document { min-width:0; padding:22px 24px 28px; border:1px solid var(--line); background:var(--paper); box-shadow:var(--shadow); } .source-document+.source-document { margin-top:16px; }
    .source-document[data-group-view][hidden] { display:none!important; }
    .view-switcher { max-width:1080px; margin:0 auto 16px; display:inline-flex; border:1px solid var(--line-strong); background:var(--paper); }
    .view-button { min-width:132px; padding:8px 16px; border:0; border-right:1px solid var(--line); background:transparent; color:var(--muted); }
    .view-button:last-child { border-right:0; } .view-button.active { background:var(--chrome); color:#fff; font-weight:760; }
    .source-origin { margin:0 0 18px; color:var(--faint); font:10px/1.5 "SFMono-Regular",Consolas,monospace; }
    .source-title { margin-bottom:20px; } .source-title p { margin:0 0 4px; color:var(--coral); font-size:9px; font-weight:800; text-transform:uppercase; } .source-title h2 { margin:0; font-size:22px; } .source-title code { display:inline-block; margin-top:5px; color:var(--faint); font-size:9px; }
    .markdown-body { max-width:860px; color:var(--ink); } .markdown-body h2 { margin:32px 0 12px; padding-top:2px; font-size:20px; line-height:1.35; } .markdown-body h2:first-child { margin-top:0; }
    .markdown-body h3 { margin:25px 0 9px; font-size:16px; } .markdown-body h4 { margin:20px 0 7px; font-size:14px; } .markdown-body p { margin:10px 0; }
    .markdown-body ul,.markdown-body ol { padding-left:22px; } .markdown-body li { margin:7px 0; }
    .markdown-body>ul>li,.markdown-body>ol>li { margin:8px 0; padding:6px 0; }
    .markdown-body blockquote { margin:15px 0; padding:11px 14px; border-left:3px solid var(--green); background:var(--green-soft); color:var(--muted); } .markdown-body blockquote p { margin:0; }
    .markdown-body code { padding:2px 5px; border-radius:3px; background:var(--paper-2); color:var(--coral); font-family:"SFMono-Regular",Consolas,monospace; font-size:.9em; }
    .markdown-body pre { overflow:auto; padding:15px; border:1px solid var(--line); border-radius:6px; background:#171a17; color:#eef0ea; } .markdown-body pre code { padding:0; background:transparent; color:inherit; }
    .markdown-body table { width:100%; display:block; overflow-x:auto; border-collapse:collapse; } .markdown-body th,.markdown-body td { padding:8px 10px; border:1px solid var(--line); text-align:left; white-space:nowrap; } .markdown-body th { background:var(--paper-2); }
    .markdown-body img { max-width:100%; height:auto; }
    .original-link::after { content:" ↗"; font-size:.78em; }
    .key-group-card { margin:0; border-top:1px solid var(--line); background:transparent; }
    .key-group-card:last-child { border-bottom:1px solid var(--line); }
    .key-group-card>summary { display:flex; align-items:center; justify-content:space-between; gap:18px; padding:17px 2px; list-style:none; cursor:pointer; }
    .key-group-card>summary::-webkit-details-marker { display:none; }
    .key-group-card>summary::before { content:"+"; width:22px; height:22px; flex:0 0 22px; display:grid; place-items:center; border:1px solid var(--line-strong); border-radius:4px; color:var(--muted); font-weight:800; }
    .key-group-card[open]>summary::before { content:"−"; color:var(--green); border-color:var(--green); }
    .key-group-title { order:2; flex:1; font-size:17px; font-weight:800; }
    .key-group-hint { order:3; color:var(--faint); font-size:10px; }
    .key-group-card[open] .key-group-hint { color:var(--green); }
    .key-group-body { padding:0 34px 20px; }
    .group-selector { padding-bottom:20px; }
    .selector-note { display:block; max-width:860px; color:var(--muted); font-size:11px; }
    .matrix-toolbar { display:flex; align-items:end; gap:9px; margin:0 0 14px; padding:12px; border:1px solid var(--line); background:var(--paper-2); }
    .matrix-toolbar label { display:grid; gap:4px; color:var(--faint); font-size:9px; font-weight:700; }
    .matrix-toolbar input,.matrix-toolbar select,.matrix-choice select { height:34px; border:1px solid var(--line-strong); border-radius:5px; background:var(--paper); color:var(--ink); padding:0 9px; }
    .matrix-search { flex:1; } .matrix-search input { width:100%; }
    .matrix-export { height:34px; padding:0 12px; border:1px solid var(--green); border-radius:5px; background:var(--green); color:#fff; font-weight:750; }
    .matrix-head,.matrix-row { display:grid; grid-template-columns:minmax(230px,1.35fr) 105px minmax(230px,1.25fr) minmax(210px,1.15fr) 122px; gap:14px; align-items:center; }
    .matrix-head { padding:8px 12px; border-bottom:1px solid var(--line-strong); color:var(--faint); font-size:9px; font-weight:800; }
    .matrix-row { padding:12px; border-bottom:1px solid var(--line); }
    .matrix-row[hidden] { display:none!important; }
    .matrix-row:hover { background:var(--paper-2); }
    .matrix-row[data-level="低优先级"],.matrix-row[data-level="排除候选"] { color:var(--muted); }
    .matrix-group { min-width:0; }
    .matrix-detail>summary { display:flex; align-items:center; gap:7px; list-style:none; cursor:pointer; }
    .matrix-detail>summary::-webkit-details-marker { display:none; }
    .matrix-detail strong { min-width:0; overflow-wrap:anywhere; }
    .matrix-expand-hint { flex:0 0 auto; color:var(--green); font-size:9px; font-weight:700; }
    .matrix-detail[open] .matrix-expand-hint { font-size:0; }
    .matrix-detail[open] .matrix-expand-hint::after { content:"收起"; font-size:9px; }
    .matrix-detail-body { margin-top:8px; padding:8px 10px; border-left:2px solid var(--green); background:var(--green-soft); color:var(--muted); font-size:10px; }
    .matrix-detail-body p { margin:3px 0; }
    .matrix-activity { display:grid; } .matrix-activity strong { font-size:12px; } .matrix-activity span { color:var(--faint); font-size:9px; }
    .matrix-tags { display:flex; flex-wrap:wrap; gap:4px; }
    .matrix-tag { padding:2px 6px; border:1px solid color-mix(in srgb,var(--green) 35%,var(--line)); border-radius:3px; background:var(--green-soft); color:var(--green); font-size:9px; font-weight:700; }
    .muted-tag { border-color:var(--line); background:var(--paper-2); color:var(--faint); }
    .matrix-reason { color:var(--muted); font-size:10px; line-height:1.55; }
    .matrix-choice select { width:100%; }
    .matrix-empty { padding:34px 12px; color:var(--muted); text-align:center; }
    .search-panel { position:fixed; top:60px; left:calc(50% - 235px + 110px); z-index:60; width:min(560px,calc(100vw - 32px)); max-height:min(620px,calc(100vh - 90px)); overflow:auto; border:1px solid var(--line-strong); border-radius:8px; background:var(--paper); box-shadow:0 24px 70px rgba(17,22,18,.2); }
    .search-panel[hidden] { display:none; } .search-head { padding:11px 13px; border-bottom:1px solid var(--line); color:var(--muted); font-size:10px; }
    .search-result { display:block; padding:11px 13px; border-bottom:1px solid var(--line); color:var(--ink); text-decoration:none; } .search-result:hover { background:var(--paper-2); }
    .search-result strong { display:block; font-size:11px; } .search-result p { margin:3px 0 0; color:var(--muted); font-size:10px; line-height:1.55; } .search-empty { padding:28px 14px; color:var(--muted); text-align:center; }
    .bottom-nav { display:none; }
    @media print { .sidebar,.location-bar,.mobile-routes,.bottom-nav { display:none!important; } .app { display:block; } .workspace { grid-column:auto; } .report-page { padding:0; } }
    @media (max-width:900px) {
      .app { display:block; } .sidebar { display:none; } .workspace { padding-top:0; padding-bottom:56px; } .location-bar { top:0; height:50px; padding:0 13px; } .crumbs { min-width:0; flex:1; }
      .search-wrap { width:42px; margin:0; } .search-input { width:42px; padding:0; color:transparent; caret-color:transparent; } .search-input::placeholder { color:transparent; } .search-wrap::before { content:"⌕"; position:absolute; z-index:2; left:13px; top:6px; color:var(--muted); pointer-events:none; }
      .search-wrap:focus-within { position:fixed; inset:8px 12px auto; z-index:70; width:auto; } .search-wrap:focus-within .search-input { width:100%; padding:0 12px; color:var(--ink); caret-color:auto; } .search-wrap:focus-within .search-input::placeholder { color:var(--faint); } .key { display:none; }
      .toolbar .icon-button:nth-child(3) { display:none; } .mobile-routes { position:sticky; top:50px; z-index:20; display:flex; gap:3px; padding:7px 12px; overflow-x:auto; border-bottom:1px solid var(--line); background:var(--canvas); }
      .mobile-routes a { flex:0 0 auto; padding:5px 8px; border-bottom:2px solid transparent; color:var(--muted); text-decoration:none; font-size:10px; } .mobile-routes a.active { border-color:var(--green); color:var(--ink); font-weight:750; }
      .report-page { padding:20px 13px 38px; } .page-head { align-items:start; margin-bottom:18px; padding-bottom:16px; } .page-head h1 { font-size:24px; } .page-head p:not(.overline) { font-size:10px; } .page-stat { min-width:58px; }
      .source-document { padding:18px 15px 22px; } .view-switcher { width:100%; } .view-button { flex:1; min-width:0; }
      .markdown-body { max-width:none; } .markdown-body h2 { font-size:18px; } .markdown-body>ul>li,.markdown-body>ol>li { padding:7px 9px; }
      .key-group-body { padding-left:0; padding-right:0; }
      .matrix-toolbar { align-items:stretch; flex-direction:column; } .matrix-toolbar label,.matrix-export { width:100%; }
      .matrix-head { display:none; } .matrix-row { grid-template-columns:1fr 106px; gap:9px 12px; }
      .matrix-group,.matrix-tags,.matrix-reason { grid-column:1/-1; } .matrix-activity { grid-column:1; } .matrix-choice { grid-column:2; grid-row:2; }
      .search-panel { top:52px; left:12px; right:12px; width:auto; }
      .bottom-nav { position:fixed; inset:auto 0 0; z-index:40; height:54px; display:grid; grid-template-columns:repeat(__BOTTOM_COUNT__,1fr); border-top:1px solid var(--line-strong); background:color-mix(in srgb,var(--paper) 94%,transparent); backdrop-filter:blur(18px); }
      .bottom-nav a { display:grid; place-items:center; align-content:center; gap:1px; color:var(--muted); text-decoration:none; font-size:9px; } .bottom-nav a span { font-size:11px; } .bottom-nav a.active { color:var(--green); font-weight:800; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">W</span><span>WeChat Intelligence</span></div>
      <div class="workspace-switch">Rion · Local workspace</div>
      <div class="nav-label">Report</div>__NAV_HTML__
      <div class="sidebar-foot"><span class="fresh-dot"></span>本地只读 · __GENERATED_AT__<br>__SOURCE_COUNT__ 份源报告 · __LINK_COUNT__ 个原链接 · 完整阅读约 __READING_MINUTES__ 分钟</div>
    </aside>
    <div class="workspace">
      <header class="location-bar">
        <div class="crumbs">Report / <strong id="current-title">今日总览</strong></div>
        <label class="search-wrap"><span class="sr-only">搜索完整报告</span><input class="search-input" id="search-input" type="search" placeholder="搜索联系人、群聊、品牌、项目或链接"><span class="key">⌘K</span></label>
        <div class="toolbar"><button class="icon-button" id="download-button" type="button" title="下载当前分区 Markdown" aria-label="下载当前分区 Markdown">↓</button><button class="icon-button" id="print-button" type="button" title="打印当前分区" aria-label="打印当前分区">▣</button><button class="icon-button" id="theme-button" type="button" title="切换明暗主题" aria-label="切换明暗主题">◐</button></div>
      </header>
      <nav class="mobile-routes" aria-label="移动端报告目录">__MOBILE_NAV_HTML__</nav>
      <main>__PAGES_HTML__</main>
    </div>
  </div>
  <div class="search-panel" id="search-panel" hidden><div class="search-head" id="search-head">输入关键词搜索全部分区</div><div id="search-results"></div></div>
  <nav class="bottom-nav" aria-label="常用分区">__BOTTOM_NAV_HTML__</nav>
  <script>
    const pageMeta=__PAGE_META_JSON__; const markdownByRoute=__MARKDOWN_JSON__;
    const reportPages=[...document.querySelectorAll('.report-page')]; const routeLinks=[...document.querySelectorAll('[data-route-link]')]; const currentTitle=document.getElementById('current-title');
    const groupViewButtons=[...document.querySelectorAll('[data-group-view-button]')]; const groupViews=[...document.querySelectorAll('[data-group-view]')];
    const groupRows=[...document.querySelectorAll('[data-group-row]')]; const groupPrioritySelects=[...document.querySelectorAll('[data-group-priority]')];
    const searchInput=document.getElementById('search-input'); const searchPanel=document.getElementById('search-panel'); const searchHead=document.getElementById('search-head'); const searchResults=document.getElementById('search-results'); const validRoutes=new Set(pageMeta.map(page=>page.route));
    function parseRoute(){const raw=location.hash.startsWith('#/')?location.hash.slice(2):''; const [candidate,...anchorParts]=raw.split('/'); return {route:validRoutes.has(candidate)?candidate:pageMeta[0].route,anchor:decodeURIComponent(anchorParts.join('/'))};}
    function renderRoute(){const {route,anchor}=parseRoute(); const meta=pageMeta.find(page=>page.route===route); reportPages.forEach(page=>{page.hidden=page.dataset.route!==route;}); routeLinks.forEach(link=>link.classList.toggle('active',link.dataset.routeLink===route)); currentTitle.textContent=meta.title; document.title=`${meta.title}｜__PAGE_TITLE__`; if(!location.hash.startsWith('#/'))history.replaceState(null,'',`#/${route}`); requestAnimationFrame(()=>{if(anchor){const target=document.getElementById(anchor); if(target)target.scrollIntoView({behavior:'smooth',block:'start'});}else{window.scrollTo(0,0);}});}
    function setGroupView(view){const available=new Set(groupViewButtons.map(button=>button.dataset.groupViewButton)); const selected=available.has(view)?view:(available.has('topics')?'topics':[...available][0]); groupViewButtons.forEach(button=>{const active=button.dataset.groupViewButton===selected; button.classList.toggle('active',active); button.setAttribute('aria-selected',active?'true':'false');}); groupViews.forEach(section=>{section.hidden=section.dataset.groupView!==selected;}); if(selected)localStorage.setItem('wechat-group-view',selected);}
    function savedGroupPriorities(){try{return JSON.parse(localStorage.getItem('wechat-group-priorities')||'{}')}catch(error){return {};}}
    function persistGroupPriorities(){const values={}; groupPrioritySelects.forEach(select=>{values[select.dataset.group]=select.value;}); localStorage.setItem('wechat-group-priorities',JSON.stringify(values));}
    function filterGroupRows(){const query=(document.getElementById('group-matrix-search')?.value||'').trim().toLowerCase(); const level=document.getElementById('group-level-filter')?.value||'all'; const tag=document.getElementById('group-tag-filter')?.value||'all'; let visible=0; groupRows.forEach(row=>{const select=row.querySelector('[data-group-priority]'); const currentLevel=select?.value||row.dataset.level; const match=(!query||row.dataset.groupName.includes(query))&&(level==='all'||currentLevel===level)&&(tag==='all'||row.dataset.tags.split(',').includes(tag)); row.hidden=!match; if(match)visible+=1;}); const empty=document.getElementById('group-matrix-empty'); if(empty)empty.hidden=visible!==0;}
    function initGroupSelector(){if(!groupRows.length)return; const saved=savedGroupPriorities(); groupPrioritySelects.forEach(select=>{if(saved[select.dataset.group])select.value=saved[select.dataset.group]; const row=select.closest('[data-group-row]'); if(row)row.dataset.level=select.value; select.addEventListener('change',()=>{if(row)row.dataset.level=select.value; persistGroupPriorities(); filterGroupRows();});}); document.getElementById('group-matrix-search')?.addEventListener('input',filterGroupRows); document.getElementById('group-level-filter')?.addEventListener('change',filterGroupRows); document.getElementById('group-tag-filter')?.addEventListener('change',filterGroupRows); document.getElementById('group-selection-export')?.addEventListener('click',()=>{const selections=groupPrioritySelects.map(select=>({group:select.dataset.group,level:select.value,suggested:select.dataset.suggested,changed:select.value!==select.dataset.suggested})); const payload={schema_version:1,exported_at:new Date().toISOString(),note:'排除候选不会自动修改微信或配置；交给 Codex 审核后再写入个人 Profile。',selections}; const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'}); const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; link.download='wechat-group-selection.json'; link.click(); URL.revokeObjectURL(url);}); filterGroupRows();}
    const searchIndex=[]; reportPages.forEach(page=>{const route=page.dataset.route; const pageTitle=pageMeta.find(item=>item.route===route).title; page.querySelectorAll('.markdown-body h2,.markdown-body h3,.markdown-body h4,.markdown-body li,.markdown-body p,.markdown-body summary,.markdown-body blockquote').forEach((node,index)=>{const text=node.textContent.replace(/\s+/g,' ').trim(); if(text.length<4)return; if(!node.id)node.id=`search-${route}-${index}`; const heading=node.matches('h2,h3,h4')?text:(node.closest('details')?.querySelector('summary')?.textContent.trim()||pageTitle); searchIndex.push({route,anchor:node.id,pageTitle,heading,text});});});
    function escapeHtml(value){return value.replace(/[&<>'"]/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'})[character]);}
    function runSearch(){const query=searchInput.value.trim().toLowerCase(); if(!query){searchPanel.hidden=true; searchResults.innerHTML=''; return;} const matches=searchIndex.filter(item=>item.text.toLowerCase().includes(query)).slice(0,36); searchHead.textContent=`全部分区找到 ${matches.length} 条结果`; searchResults.innerHTML=matches.length?matches.map(item=>{const snippet=item.text.length>150?`${item.text.slice(0,150)}…`:item.text; return `<a class="search-result" href="#/${item.route}/${encodeURIComponent(item.anchor)}"><strong>${escapeHtml(item.pageTitle)} · ${escapeHtml(item.heading)}</strong><p>${escapeHtml(snippet)}</p></a>`;}).join(''):'<div class="search-empty">没有找到匹配内容</div>'; searchPanel.hidden=false;}
    window.addEventListener('hashchange',()=>{renderRoute(); searchPanel.hidden=true;}); routeLinks.forEach(link=>link.addEventListener('click',()=>{if(parseRoute().route===link.dataset.routeLink)setTimeout(()=>window.scrollTo(0,0),0);})); groupViewButtons.forEach(button=>button.addEventListener('click',()=>setGroupView(button.dataset.groupViewButton))); searchInput.addEventListener('input',runSearch); searchInput.addEventListener('keydown',event=>{if(event.key==='Escape'){searchInput.value=''; searchPanel.hidden=true; searchInput.blur();}});
    document.addEventListener('keydown',event=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='k'){event.preventDefault(); searchInput.focus();}}); document.addEventListener('click',event=>{if(!event.target.closest('.search-wrap')&&!event.target.closest('.search-panel'))searchPanel.hidden=true;});
    document.getElementById('download-button').addEventListener('click',()=>{const {route}=parseRoute(); const meta=pageMeta.find(page=>page.route===route); const blob=new Blob([markdownByRoute[route]||''],{type:'text/markdown;charset=utf-8'}); const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; link.download=meta.filename; link.click(); URL.revokeObjectURL(url);});
    document.getElementById('print-button').addEventListener('click',()=>window.print()); const savedTheme=localStorage.getItem('wechat-flagship-theme'); if(savedTheme)document.documentElement.dataset.theme=savedTheme; document.getElementById('theme-button').addEventListener('click',()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark'; document.documentElement.dataset.theme=next; localStorage.setItem('wechat-flagship-theme',next);}); initGroupSelector(); if(groupViews.length)setGroupView(localStorage.getItem('wechat-group-view')||'topics'); renderRoute();
  </script>
</body>
</html>'''


def render_report_bundle(
    report_dir: Path,
    *,
    output_path: Path | None = None,
    markdown_output_path: Path | None = None,
    title: str | None = None,
) -> tuple[Path, Path, list[ReportSource]]:
    root = report_dir.expanduser().resolve()
    sources = discover_report_sources(root)
    if not sources:
        raise ValueError(f"报告目录没有 Markdown 文件：{root}")
    pages = build_report_pages(sources)
    pandoc = shutil.which("pandoc")
    if not pandoc:
        try:
            import pypandoc
            pandoc = pypandoc.get_pandoc_path()
        except (ImportError, OSError):
            pass
    if not pandoc:
        raise RuntimeError("生成综合 HTML 需要 pandoc。")

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    page_title = title or "微信个人情报库｜综合日报"
    markdown_path = (markdown_output_path or root / "wechat_daily_full.md").expanduser().resolve()
    html_path = (output_path or root / "wechat_daily_report.html").expanduser().resolve()
    markdown_by_route = write_markdown_site(root, pages, portal_path=markdown_path, title=page_title, generated_at=generated_at)
    source_pages = {source.path.resolve(): page for page in pages for source in page.sources}

    fragments: dict[str, str] = {}
    all_markdown: list[str] = []
    all_urls: set[str] = set()
    visible_sources = [source for page in pages for source in page.sources]
    for source in visible_sources:
        text = source.path.read_text(encoding="utf-8", errors="replace")
        all_markdown.append(text)
        all_urls.update(_external_urls(text))
        fragments[source.source_id] = _rewrite_html_links(_pandoc_fragment(source, pandoc), source=source, source_pages=source_pages)

    nav_html = "".join(
        f'<a class="nav-item" href="#/{escape(page.route)}" data-route-link="{escape(page.route)}"><span class="nav-glyph">{escape(page.glyph)}</span><span>{escape(page.nav_label)}</span><span class="nav-count">{_heading_count(page)}</span></a>'
        for page in pages
    )
    mobile_nav_html = "".join(f'<a href="#/{escape(page.route)}" data-route-link="{escape(page.route)}">{escape(page.nav_label)}</a>' for page in pages)
    bottom_routes = [route for route in ("overview", "groups", "contacts", "radar") if any(page.route == route for page in pages)]
    bottom_nav_html = "".join(
        f'<a href="#/{escape(page.route)}" data-route-link="{escape(page.route)}"><span>{escape(page.glyph)}</span>{escape(page.nav_label)}</a>'
        for route in bottom_routes for page in pages if page.route == route
    )
    page_meta = [{"route": page.route, "title": page.title, "description": page.description, "filename": page.filename} for page in pages]
    full_text = "\n".join(all_markdown)
    html = HTML_TEMPLATE
    group_matrix = _load_group_matrix(root)
    values = {
        "PAGE_TITLE": escape(page_title),
        "NAV_HTML": nav_html,
        "MOBILE_NAV_HTML": mobile_nav_html,
        "BOTTOM_NAV_HTML": bottom_nav_html,
        "BOTTOM_COUNT": str(max(1, len(bottom_routes))),
        "PAGES_HTML": "".join(_render_page(page, fragments, group_matrix) for page in pages),
        "PAGE_META_JSON": json.dumps(page_meta, ensure_ascii=False).replace("</", "<\\/"),
        "MARKDOWN_JSON": json.dumps(markdown_by_route, ensure_ascii=False).replace("</", "<\\/"),
        "GENERATED_AT": escape(generated_at),
        "SOURCE_COUNT": str(len(visible_sources)),
        "LINK_COUNT": str(len(all_urls)),
        "READING_MINUTES": str(_reading_minutes(full_text)),
    }
    html = _replace_tokens(html, values)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return html_path, markdown_path, sources
