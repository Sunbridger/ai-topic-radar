# -*- coding: utf-8 -*-
"""渲染：GitHub Pages 的 HTML 日报页 + 飞书消息卡片。"""

import html
from datetime import date

from . import config

CSS = """
:root{--bg:#faf7f2;--ink:#191714;--muted:#7a736b;--line:#e4ddd3;--accent:#c9442a;--card:#fffdf9}
@media (prefers-color-scheme:dark){:root{--bg:#121110;--ink:#ece7df;--muted:#948d84;--line:#2b2825;--accent:#ff6a48;--card:#191715}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.75 "PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
main{max-width:700px;margin:0 auto;padding:44px 22px 90px}
.kicker{font:600 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.18em;color:var(--accent);margin:0 0 16px}
h1{font-size:32px;line-height:1.25;margin:0 0 10px;letter-spacing:-.01em}
.lede{color:var(--muted);margin:0 0 38px;font-size:16px}
.card{border-top:1px solid var(--line);padding:30px 0}
.meta{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--muted);margin-bottom:12px}
.rank{color:var(--accent);font-weight:700;font-size:13px}
.chip{border:1px solid var(--line);border-radius:999px;padding:2px 9px}
h2{font-size:22px;line-height:1.45;margin:0 0 12px;letter-spacing:-.005em}
.fact{margin:0 0 16px}
.block{margin:16px 0}
.block h3{font:600 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.14em;color:var(--muted);margin:0 0 9px}
.angles{list-style:none;margin:0;padding:0;counter-reset:a}
.angles li{counter-increment:a;padding-left:28px;position:relative;margin:7px 0}
.angles li:before{content:counter(a,decimal-leading-zero);position:absolute;left:0;top:4px;font:11px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent)}
.titles{list-style:none;margin:0;padding:0}
.titles li{margin:7px 0;padding-left:14px;border-left:2px solid var(--accent)}
.audience{color:var(--muted);font-size:15px;margin:18px 0 10px}
.src{font:13px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent);text-decoration:none;border-bottom:1px solid currentColor;padding-bottom:1px}
.empty{padding:44px 0;color:var(--muted)}
footer{margin-top:60px;border-top:1px solid var(--line);padding-top:20px;color:var(--muted);font-size:13px;line-height:2}
footer a{color:var(--muted)}
"""


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _pretty_date(d):
    dt = date.fromisoformat(d)
    wd = "一二三四五六日"[dt.weekday()]
    return f"{dt.year} 年 {dt.month} 月 {dt.day} 日 · 周{wd}"


def _archive_html(archive, current):
    days = [d for d in archive if d != current][:14]
    if not days:
        return ""
    links = " · ".join(f'<a href="{_esc(d)}.html">{_esc(d[5:])}</a>' for d in days)
    return f"<p>往期：{links}</p>"


def _card_html(i, c):
    angles = "".join(f"<li>{_esc(a)}</li>" for a in (c.get("angles") or []))
    titles = "".join(f"<li>{_esc(t)}</li>" for t in (c.get("xhs_titles") or []))
    meta = "".join(f'<span class="chip">{_esc(x)}</span>' for x in (c.get("source"), c.get("heat")) if x)
    blocks = []
    if c.get("fact"):
        blocks.append(f'<p class="fact">{_esc(c["fact"])}</p>')
    if c.get("why_hot"):
        blocks.append(f'<div class="block"><h3>为什么火</h3><p>{_esc(c["why_hot"])}</p></div>')
    if angles:
        blocks.append(f'<div class="block"><h3>切入角度</h3><ol class="angles">{angles}</ol></div>')
    if titles:
        blocks.append(f'<div class="block"><h3>小红书标题</h3><ul class="titles">{titles}</ul></div>')
    if c.get("audience"):
        blocks.append(f'<p class="audience">适合：{_esc(c["audience"])}</p>')
    src = ""
    if c.get("url"):
        src = f'<a class="src" href="{_esc(c["url"])}" target="_blank" rel="noopener">原文 ↗</a>'
    return (
        '<article class="card">'
        f'<div class="meta"><span class="rank">{i:02d}</span>{meta}</div>'
        f"<h2>{_esc(c['title'])}</h2>"
        + "".join(blocks)
        + src
        + "</article>"
    )


def build_page(cards, date_str, note="", archive=None, latest=False):
    archive = archive or []
    body = "".join(_card_html(i, c) for i, c in enumerate(cards, 1))
    if not body:
        body = '<p class="empty">今天没有达到质量标准的选题。宁缺勿滥，明天见。</p>'
    lede = f'<p class="lede">{_esc(note)}</p>' if note else ""
    footer_archive = _archive_html(archive, date_str)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>AI 选题日报 · {_esc(date_str)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<header>
<p class="kicker">AI 选题日报</p>
<h1>{_pretty_date(date_str)}</h1>
{lede}
</header>
<section>
{body}
</section>
<footer>
<p>每天 06:45 抓取 · 数据源：tophub 热榜 / Hacker News / arXiv / GitHub Trending / X</p>
{footer_archive}
</footer>
</main>
</body>
</html>
"""


# ---------------------------------------------------------------- Bark 推送

def build_bark_payload(cards, date_str, page_url="", note=""):
    """Bark 通知：标题显示条数，正文列选题，点击跳全文页。"""
    title = f"AI 选题日报 {date_str[5:]} · {len(cards)} 条"
    if not cards:
        body = "今日没有达到质量标准的选题。宁缺勿滥，明天见。"
    else:
        lines = [f"{i}. {c['title']}" for i, c in enumerate(cards, 1)]
        if len(cards) < config.CARDS_MIN:
            lines.append("")
            lines.append(f"今日热点较少，仅 {len(cards)} 条达到标准。")
        if note:
            lines.append("")
            lines.append(note)
        body = "\n".join(lines)
    payload = {
        "title": title,
        "body": body,
        "group": config.BARK_GROUP,
        "ttl": config.BARK_TTL,
    }
    if page_url:
        payload["url"] = page_url
    return payload
