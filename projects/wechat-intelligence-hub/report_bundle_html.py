#!/usr/bin/env python3
"""Build a standalone interactive reader from a WeChat report directory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote, urlsplit


GENERATED_NAMES = {
    "wechat_daily_full.md",
    "wechat_daily_report.md",
}


@dataclass(frozen=True)
class ReportSource:
    path: Path
    relative_path: str
    source_id: str
    title: str
    kind: str
    priority: int
    collapsed: bool = False


SOURCE_RULES: tuple[tuple[str, str, str, int, bool], ...] = (
    ("final_report.md", "执行总览", "overview", 10, False),
    ("group-daily/group_daily_brief.md", "群聊精编", "groups", 20, False),
    ("contact-daily/contact_daily_brief.md", "重点私信与回复建议", "contacts", 30, False),
    ("action_overview.md", "行动与商机总览", "actions", 40, False),
    ("group-daily/cross_group_links.md", "跨群重复链接", "links", 50, False),
    ("group-daily/group_daily_appendix.md", "群聊证据附录", "evidence", 70, True),
    ("group-daily/group_daily_digest.md", "群聊机器初筛", "audit", 80, True),
    ("contact-daily/contact_daily_digest.md", "私信机器初筛", "audit", 90, True),
)


KIND_LABELS = {
    "overview": "总览",
    "groups": "群聊",
    "contacts": "私信",
    "actions": "行动",
    "links": "链接",
    "evidence": "证据",
    "audit": "审计",
    "other": "其他",
}


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
    """Return all Markdown report files in a stable editorial order."""
    root = report_dir.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"找不到报告目录：{root}")

    used_ids: set[str] = set()
    sources: list[ReportSource] = []
    for path in sorted(root.rglob("*.md")):
        relative_path = path.relative_to(root).as_posix()
        if (
            path.name in GENERATED_NAMES
            or path.name.startswith(".")
            or relative_path.startswith("wechat-report/")
        ):
            continue
        rule = _source_rule(relative_path)
        text = path.read_text(encoding="utf-8", errors="replace")
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
        sources.append(
            ReportSource(
                path=path,
                relative_path=relative_path,
                source_id=source_id,
                title=title,
                kind=kind,
                priority=priority,
                collapsed=collapsed,
            )
        )
    return sorted(sources, key=lambda item: (item.priority, item.relative_path))


def _strip_first_h1(markdown_text: str) -> str:
    return re.sub(r"(?m)^#\s+.+?\s*\n+", "", markdown_text, count=1).strip()


def build_combined_markdown(
    sources: list[ReportSource],
    *,
    title: str,
    generated_at: str,
) -> str:
    parts = [
        f"# {title}",
        "",
        f"> 综合 {len(sources)} 份本轮 Markdown 报告｜生成时间：{generated_at}",
        "",
    ]
    for source in sources:
        text = source.path.read_text(encoding="utf-8", errors="replace")
        parts.extend(
            [
                f"## {source.title}",
                "",
                f"> 来源文件：`{source.relative_path}`",
                "",
                _strip_first_h1(text),
                "",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def _pandoc_fragment(source: ReportSource, pandoc: str) -> str:
    command = [
        pandoc,
        str(source.path),
        "--from=gfm",
        "--to=html5",
        f"--id-prefix={source.source_id}-",
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Pandoc 转换失败").strip()
        raise RuntimeError(f"{source.relative_path}: {detail}")
    fragment = re.sub(r"(?s)^.*?<h1[^>]*>.*?</h1>", "", result.stdout, count=1)
    return fragment.strip()


def _rewrite_links(
    fragment: str,
    *,
    source: ReportSource,
    source_ids: dict[Path, str],
) -> str:
    def replace(match: re.Match[str]) -> str:
        before, href, after = match.group(1), match.group(2), match.group(3)
        try:
            parsed = urlsplit(href)
        except ValueError:
            return match.group(0)
        if parsed.scheme in {"http", "https"}:
            return f'<a{before}href="{href}"{after} target="_blank" rel="noopener noreferrer" class="original-link">'
        if parsed.scheme or href.startswith("#"):
            return match.group(0)
        candidate = (source.path.parent / unquote(parsed.path)).resolve()
        target_id = source_ids.get(candidate)
        if target_id:
            target = f"#{target_id}-{parsed.fragment}" if parsed.fragment else f"#source-{target_id}"
            return f'<a{before}href="{target}"{after} class="internal-link">'
        return match.group(0)

    return re.sub(r'<a([^>]*?)href="([^"]+)"([^>]*)>', replace, fragment)


def _external_urls(text: str) -> set[str]:
    urls = set(re.findall(r"https?://[^\s<>()\]\[\"']+", text))
    return {url.rstrip(".,;:!?，。；：！？") for url in urls}


def _reading_minutes(text: str) -> int:
    chinese = len(re.findall(r"[\u3400-\u9fff]", text))
    latin = len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", text))
    return max(1, round(chinese / 500 + latin / 250))


def _render_source_panel(source: ReportSource, fragment: str) -> str:
    kind_label = KIND_LABELS.get(source.kind, "其他")
    body = (
        f'<details class="source-disclosure" data-source-details {"" if source.collapsed else "open"}>'
        f'<summary>展开完整内容</summary><div class="source-content">{fragment}</div></details>'
        if source.collapsed
        else f'<div class="source-content">{fragment}</div>'
    )
    return f"""
    <section class="source-panel" id="source-{escape(source.source_id)}"
      data-kind="{escape(source.kind)}" data-title="{escape(source.title)}">
      <header class="source-heading">
        <div>
          <p class="source-kicker">{escape(kind_label)}</p>
          <h2>{escape(source.title)}</h2>
          <p class="source-path">{escape(source.relative_path)}</p>
        </div>
        <button class="bookmark-button" type="button" data-bookmark="{escape(source.source_id)}"
          aria-pressed="false" title="收藏这个栏目" aria-label="收藏这个栏目">☆</button>
      </header>
      {body}
    </section>
    """


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
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError("生成综合 HTML 需要 pandoc。")

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    page_title = title or "微信个人情报库｜综合日报"
    markdown_path = (markdown_output_path or root / "wechat_daily_full.md").expanduser().resolve()
    html_path = (output_path or root / "wechat_daily_report.html").expanduser().resolve()
    combined_markdown = build_combined_markdown(
        sources,
        title=page_title,
        generated_at=generated_at,
    )
    markdown_path.write_text(combined_markdown, encoding="utf-8")

    source_ids = {source.path.resolve(): source.source_id for source in sources}
    panels: list[str] = []
    all_markdown: list[str] = []
    all_urls: set[str] = set()
    for source in sources:
        text = source.path.read_text(encoding="utf-8", errors="replace")
        all_markdown.append(text)
        all_urls.update(_external_urls(text))
        fragment = _rewrite_links(
            _pandoc_fragment(source, pandoc),
            source=source,
            source_ids=source_ids,
        )
        panels.append(_render_source_panel(source, fragment))

    nav_html = "".join(
        f'<a href="#source-{escape(source.source_id)}" data-nav-kind="{escape(source.kind)}">'
        f'<span>{escape(KIND_LABELS.get(source.kind, "其他"))}</span>{escape(source.title)}</a>'
        for source in sources
    )
    filter_options = "".join(
        f'<option value="{escape(kind)}">{escape(label)}</option>'
        for kind, label in KIND_LABELS.items()
        if any(source.kind == kind for source in sources)
    )
    full_text = "\n".join(all_markdown)
    markdown_json = json.dumps(combined_markdown, ensure_ascii=False).replace("</", "<\\/")
    metrics = {
        "files": len(sources),
        "links": len(all_urls),
        "minutes": _reading_minutes(full_text),
        "sections": sum(len(re.findall(r"(?m)^##\s+", text)) for text in all_markdown),
    }

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="description" content="微信个人情报库综合交互日报">
  <title>{escape(page_title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3f5f2; --surface: #ffffff; --surface-soft: #e9eeea;
      --ink: #161a17; --muted: #626a64; --line: #d2d9d3;
      --accent: #087b67; --accent-strong: #055c4d; --signal: #d84d3f;
      --warning: #a96600; --marker: #d9f26b; --shadow: 0 14px 34px rgba(25, 35, 29, .09);
    }}
    html[data-theme="dark"] {{
      color-scheme: dark;
      --bg: #141815; --surface: #1d231f; --surface-soft: #28302a;
      --ink: #edf2ed; --muted: #abb5ad; --line: #3a443d;
      --accent: #5bd0b9; --accent-strong: #8ce5d3; --signal: #ff786a;
      --warning: #efb55e; --marker: #bdd553; --shadow: 0 16px 38px rgba(0, 0, 0, .28);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; scroll-padding-top: 92px; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.72 Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; letter-spacing: 0; }}
    button, input, select {{ font: inherit; letter-spacing: 0; }}
    button, select {{ cursor: pointer; }}
    a {{ color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; overflow-wrap: anywhere; }}
    a:hover {{ color: var(--accent-strong); }}
    .progress {{ position: fixed; inset: 0 0 auto; z-index: 110; height: 3px; background: var(--surface-soft); }}
    .progress span {{ display: block; width: 0; height: 100%; background: var(--signal); }}
    .topbar {{ position: sticky; top: 0; z-index: 100; border-bottom: 1px solid var(--line); background: color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter: blur(16px); }}
    .topbar-inner {{ max-width: 1480px; min-height: 68px; margin: 0 auto; padding: 10px 24px; display: flex; align-items: center; gap: 12px; }}
    .brand {{ min-width: 230px; display: flex; align-items: center; gap: 10px; font-weight: 760; }}
    .brand-mark {{ width: 30px; height: 30px; display: grid; place-items: center; border: 2px solid var(--ink); border-radius: 4px; background: var(--marker); color: #151714; font-weight: 850; }}
    .search {{ position: relative; flex: 1; max-width: 640px; }}
    .search input {{ width: 100%; height: 42px; padding: 0 70px 0 13px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--ink); outline: none; }}
    .search input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 18%, transparent); }}
    .search span {{ position: absolute; right: 11px; top: 9px; color: var(--muted); font-size: 13px; }}
    .icon-button {{ width: 40px; height: 40px; padding: 0; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--ink); font-size: 18px; }}
    .icon-button:hover {{ border-color: var(--accent); color: var(--accent-strong); }}
    .shell {{ max-width: 1480px; margin: 0 auto; padding: 0 24px 76px; }}
    .report-head {{ padding: 46px 0 30px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 28px; align-items: end; border-bottom: 1px solid var(--line); }}
    .eyebrow {{ margin: 0 0 8px; color: var(--signal); font-size: 13px; font-weight: 780; text-transform: uppercase; }}
    .report-head h1 {{ margin: 0; max-width: 920px; font-size: 42px; line-height: 1.18; letter-spacing: 0; }}
    .report-head p {{ max-width: 780px; margin: 12px 0 0; color: var(--muted); }}
    .metrics {{ display: grid; grid-template-columns: repeat(2, 118px); gap: 8px; }}
    .metric {{ padding: 8px 10px; border-left: 3px solid var(--accent); background: var(--surface); }}
    .metric:nth-child(2) {{ border-color: var(--signal); }} .metric:nth-child(3) {{ border-color: var(--warning); }} .metric:nth-child(4) {{ border-color: var(--marker); }}
    .metric strong {{ display: block; font-size: 21px; line-height: 1.2; }} .metric span {{ color: var(--muted); font-size: 12px; }}
    .filterbar {{ min-height: 66px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; border-bottom: 1px solid var(--line); }}
    .filterbar label {{ color: var(--muted); font-size: 13px; font-weight: 650; }}
    .filterbar select {{ height: 38px; min-width: 140px; padding: 0 30px 0 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--ink); }}
    .text-button {{ min-height: 38px; padding: 0 12px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); color: var(--ink); font-weight: 650; }}
    .text-button:hover, .text-button[aria-pressed="true"] {{ border-color: var(--accent); color: var(--accent-strong); }}
    .filter-status {{ margin-left: auto; color: var(--muted); font-size: 13px; }}
    .layout {{ display: grid; grid-template-columns: 240px minmax(0, 900px); gap: 52px; align-items: start; justify-content: center; }}
    .nav {{ position: sticky; top: 94px; max-height: calc(100vh - 112px); padding: 28px 0; overflow: auto; }}
    .nav strong {{ display: block; margin: 0 0 10px; color: var(--muted); font-size: 13px; }}
    .nav a {{ display: block; margin: 2px 0; padding: 8px 10px; border-left: 2px solid transparent; color: var(--muted); text-decoration: none; font-size: 14px; line-height: 1.35; }}
    .nav a span {{ display: block; color: var(--signal); font-size: 11px; font-weight: 760; }}
    .nav a:hover, .nav a.active {{ border-color: var(--signal); background: var(--surface-soft); color: var(--ink); }}
    main {{ min-width: 0; }}
    .source-panel {{ padding: 38px 0 30px; border-bottom: 1px solid var(--line); }}
    .source-panel[hidden] {{ display: none !important; }}
    .source-heading {{ display: flex; align-items: start; justify-content: space-between; gap: 20px; margin-bottom: 22px; }}
    .source-kicker {{ margin: 0 0 5px; color: var(--signal); font-size: 12px; font-weight: 800; }}
    .source-heading h2 {{ margin: 0; font-size: 28px; line-height: 1.25; }}
    .source-path {{ margin: 7px 0 0; color: var(--muted); font: 12px/1.4 "SFMono-Regular", Consolas, monospace; overflow-wrap: anywhere; }}
    .bookmark-button {{ width: 38px; height: 38px; flex: 0 0 38px; padding: 0; border: 1px solid var(--line); border-radius: 5px; background: var(--surface); color: var(--muted); font-size: 22px; }}
    .bookmark-button[aria-pressed="true"] {{ border-color: #849a1d; background: var(--marker); color: #151714; }}
    .source-content h2 {{ margin: 32px 0 14px; font-size: 24px; }}
    .source-content h3 {{ margin: 27px 0 10px; font-size: 19px; }}
    .source-content h4 {{ margin: 23px 0 8px; font-size: 16px; }}
    .source-content p {{ margin: 10px 0; }}
    .source-content blockquote {{ margin: 16px 0; padding: 12px 16px; border-left: 4px solid var(--accent); background: var(--surface-soft); color: var(--muted); }}
    .source-content blockquote p {{ margin: 0; }}
    .source-content ul, .source-content ol {{ padding-left: 22px; }}
    .source-content li {{ margin: 7px 0; }}
    .source-content > ul > li, .source-content > ol > li {{ margin: 9px 0; padding: 10px 12px; border-left: 3px solid var(--line); background: var(--surface); }}
    .source-content li.search-hidden {{ display: none; }}
    .source-content code {{ padding: 2px 5px; border-radius: 3px; background: var(--surface-soft); color: var(--signal); font-family: "SFMono-Regular", Consolas, monospace; font-size: .9em; }}
    .source-content pre {{ position: relative; overflow: auto; padding: 17px; border: 1px solid var(--line); border-radius: 6px; background: #171a17; color: #eef0ea; }}
    .source-content pre code {{ padding: 0; background: transparent; color: inherit; }}
    .source-content table {{ width: 100%; border-collapse: collapse; display: block; overflow-x: auto; }}
    .source-content th, .source-content td {{ padding: 9px 11px; border: 1px solid var(--line); text-align: left; white-space: nowrap; }}
    .source-content th {{ background: var(--surface-soft); }}
    .source-content img {{ max-width: 100%; height: auto; }}
    .source-content details, .source-disclosure {{ margin: 12px 0; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }}
    .source-content summary, .source-disclosure > summary {{ padding: 12px 14px; cursor: pointer; font-weight: 720; }}
    .source-content details > :not(summary), .source-disclosure > .source-content {{ margin-left: 14px; margin-right: 14px; }}
    .source-content details > :last-child, .source-disclosure > .source-content {{ margin-bottom: 14px; }}
    .original-link::after {{ content: " ↗"; font-size: .78em; }}
    .empty {{ display: none; padding: 70px 0; text-align: center; color: var(--muted); }}
    .empty.visible {{ display: block; }}
    .sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }}
    @media print {{ .topbar, .filterbar, .nav, .bookmark-button {{ display: none !important; }} .shell {{ max-width: none; padding: 0; }} .layout {{ display: block; }} .source-panel {{ break-inside: avoid; }} }}
    @media (max-width: 1000px) {{
      .topbar-inner {{ flex-wrap: wrap; }} .brand {{ min-width: 0; }} .search {{ order: 3; flex-basis: 100%; max-width: none; }}
      .report-head {{ grid-template-columns: 1fr; }} .metrics {{ grid-template-columns: repeat(4, minmax(92px, 1fr)); }}
      .layout {{ display: block; }} .nav {{ position: sticky; top: 121px; z-index: 80; display: flex; gap: 4px; max-height: none; margin: 0 -24px; padding: 9px 24px; overflow-x: auto; border-bottom: 1px solid var(--line); background: var(--bg); }}
      .nav strong {{ display: none; }} .nav a {{ flex: 0 0 auto; border-left: 0; border-bottom: 2px solid transparent; white-space: nowrap; }} .nav a span {{ display: none; }} .nav a.active {{ border-bottom-color: var(--signal); }}
    }}
    @media (max-width: 650px) {{
      body {{ font-size: 15px; }} .topbar-inner, .shell {{ padding-left: 16px; padding-right: 16px; }} .brand span:last-child {{ display: none; }}
      .report-head {{ padding-top: 34px; }} .report-head h1 {{ font-size: 31px; }} .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .filter-status {{ width: 100%; margin-left: 0; }} .nav {{ margin-left: -16px; margin-right: -16px; padding-left: 16px; padding-right: 16px; }}
      .source-heading h2 {{ font-size: 24px; }}
    }}
  </style>
</head>
<body>
  <div class="progress" aria-hidden="true"><span id="progress-bar"></span></div>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand"><span class="brand-mark">W</span><span>WeChat Intelligence Hub</span></div>
      <label class="search"><span class="sr-only">搜索全文</span><input id="search-input" type="search" placeholder="搜索联系人、群聊、品牌、项目或链接"><span>⌘K</span></label>
      <button class="icon-button" id="expand-button" type="button" title="展开或收起全部" aria-label="展开或收起全部">↕</button>
      <button class="icon-button" id="download-button" type="button" title="下载完整 Markdown" aria-label="下载完整 Markdown">↓</button>
      <button class="icon-button" id="print-button" type="button" title="打印或导出 PDF" aria-label="打印或导出 PDF">▣</button>
      <button class="icon-button" id="theme-button" type="button" title="切换明暗主题" aria-label="切换明暗主题">◐</button>
    </div>
  </header>
  <div class="shell">
    <header class="report-head">
      <div>
        <p class="eyebrow">Local, read-only intelligence report</p>
        <h1>{escape(page_title)}</h1>
        <p>一个页面整合行动总览、群聊话题、重点私信、回复建议、跨群投放链接与完整证据。外部原链接可直接打开，机器初筛默认折叠。</p>
      </div>
      <div class="metrics" aria-label="报告统计">
        <div class="metric"><strong>{metrics['files']}</strong><span>Markdown 文件</span></div>
        <div class="metric"><strong>{metrics['links']}</strong><span>外部原链接</span></div>
        <div class="metric"><strong>{metrics['sections']}</strong><span>内容栏目</span></div>
        <div class="metric"><strong>{metrics['minutes']}</strong><span>分钟完整阅读</span></div>
      </div>
    </header>
    <div class="filterbar">
      <label for="kind-filter">内容范围</label>
      <select id="kind-filter"><option value="all">全部内容</option>{filter_options}</select>
      <button class="text-button" id="saved-only" type="button" aria-pressed="false">只看收藏</button>
      <span class="filter-status" id="filter-status">显示 {len(sources)} / {len(sources)} 个栏目</span>
    </div>
    <div class="layout">
      <nav class="nav" aria-label="报告目录"><strong>报告目录</strong>{nav_html}</nav>
      <main id="report-main">{''.join(panels)}<div class="empty" id="empty-state">没有找到匹配内容。</div></main>
    </div>
  </div>
  <script>
    const markdownSource = {markdown_json};
    const searchInput = document.getElementById('search-input');
    const kindFilter = document.getElementById('kind-filter');
    const savedOnlyButton = document.getElementById('saved-only');
    const status = document.getElementById('filter-status');
    const emptyState = document.getElementById('empty-state');
    const panels = [...document.querySelectorAll('.source-panel')];
    const bookmarksKey = 'wechat-report-bookmarks-v1';
    let bookmarks = new Set(JSON.parse(localStorage.getItem(bookmarksKey) || '[]'));

    function refreshBookmarkButtons() {{
      document.querySelectorAll('[data-bookmark]').forEach((button) => {{
        const saved = bookmarks.has(button.dataset.bookmark);
        button.setAttribute('aria-pressed', String(saved));
        button.textContent = saved ? '★' : '☆';
      }});
    }}

    function applyFilters() {{
      const query = searchInput.value.trim().toLowerCase();
      const kind = kindFilter.value;
      const savedOnly = savedOnlyButton.getAttribute('aria-pressed') === 'true';
      let visible = 0;
      panels.forEach((panel) => {{
        const kindMatch = kind === 'all' || panel.dataset.kind === kind;
        const savedMatch = !savedOnly || bookmarks.has(panel.id.replace('source-', ''));
        const textMatch = !query || panel.textContent.toLowerCase().includes(query);
        const show = kindMatch && savedMatch && textMatch;
        panel.hidden = !show;
        if (show) {{
          visible += 1;
          if (query) panel.querySelectorAll('details').forEach((details) => details.open = true);
        }}
        panel.querySelectorAll('.source-content li').forEach((item) => {{
          item.classList.toggle('search-hidden', Boolean(query) && !item.textContent.toLowerCase().includes(query));
        }});
      }});
      status.textContent = `显示 ${{visible}} / ${{panels.length}} 个栏目`;
      emptyState.classList.toggle('visible', visible === 0);
    }}

    document.querySelectorAll('[data-bookmark]').forEach((button) => button.addEventListener('click', () => {{
      const id = button.dataset.bookmark;
      bookmarks.has(id) ? bookmarks.delete(id) : bookmarks.add(id);
      localStorage.setItem(bookmarksKey, JSON.stringify([...bookmarks]));
      refreshBookmarkButtons(); applyFilters();
    }}));
    searchInput.addEventListener('input', applyFilters);
    kindFilter.addEventListener('change', applyFilters);
    savedOnlyButton.addEventListener('click', () => {{
      const next = savedOnlyButton.getAttribute('aria-pressed') !== 'true';
      savedOnlyButton.setAttribute('aria-pressed', String(next)); applyFilters();
    }});
    document.addEventListener('keydown', (event) => {{
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {{ event.preventDefault(); searchInput.focus(); }}
    }});
    document.getElementById('expand-button').addEventListener('click', () => {{
      const details = [...document.querySelectorAll('details')];
      const shouldOpen = details.some((item) => !item.open);
      details.forEach((item) => item.open = shouldOpen);
    }});
    document.getElementById('download-button').addEventListener('click', () => {{
      const blob = new Blob([markdownSource], {{type: 'text/markdown;charset=utf-8'}});
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = 'wechat_daily_full.md'; link.click(); URL.revokeObjectURL(url);
    }});
    document.getElementById('print-button').addEventListener('click', () => window.print());
    const themeButton = document.getElementById('theme-button');
    const savedTheme = localStorage.getItem('wechat-report-theme');
    if (savedTheme) document.documentElement.dataset.theme = savedTheme;
    themeButton.addEventListener('click', () => {{
      const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next; localStorage.setItem('wechat-report-theme', next);
    }});
    window.addEventListener('scroll', () => {{
      const max = document.documentElement.scrollHeight - window.innerHeight;
      document.getElementById('progress-bar').style.width = `${{max > 0 ? (window.scrollY / max) * 100 : 0}}%`;
    }}, {{passive: true}});
    const navLinks = [...document.querySelectorAll('.nav a')];
    const observer = new IntersectionObserver((entries) => {{
      entries.filter((entry) => entry.isIntersecting).forEach((entry) => {{
        navLinks.forEach((link) => link.classList.toggle('active', link.getAttribute('href') === `#${{entry.target.id}}`));
      }});
    }}, {{rootMargin: '-20% 0px -68% 0px'}});
    panels.forEach((panel) => observer.observe(panel));
    refreshBookmarkButtons(); applyFilters();
  </script>
</body>
</html>"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    return html_path, markdown_path, sources


# Keep the established import path while the complete sectioned renderer lives in
# its own module. Older helpers above remain available to downstream callers.
from report_bundle_flagship import render_report_bundle as render_report_bundle
