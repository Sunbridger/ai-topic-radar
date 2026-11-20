# -*- coding: utf-8 -*-
"""渲染：微信公众号风格的 Pages 日报页 + Bark 推送。"""

import html
from datetime import date

from . import config

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#fff;color:#3f3f3f;font:16px/1.9 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;letter-spacing:.4px;-webkit-font-smoothing:antialiased}
main{width:80%;max-width:1080px;margin:0 auto;padding:44px 0 80px}
.masthead{text-align:center}
.kicker{display:inline-block;font-size:12px;letter-spacing:2px;color:#d4472a;border:1px solid #f0cfc6;background:#fdf5f2;padding:3px 12px;border-radius:2px}
h1{font-size:24px;line-height:1.5;color:#1a1a1a;font-weight:700;margin:18px 0 6px}
.masthead .meta{font-size:13px;color:#999;margin:0}
.lede{font-size:15px;color:#8a8a8a;text-align:center;margin:14px 0 0}
.orn{display:flex;align-items:center;gap:12px;margin:30px 0;color:#d8d8d8;font-size:10px;line-height:1}
.orn:before,.orn:after{content:"";flex:1;height:1px;background:#eee}
.section{margin:38px 0 0}
.no{display:inline-block;background:#d4472a;color:#fff;font-size:12px;font-weight:600;line-height:1;padding:5px 8px;border-radius:3px;margin-right:9px;vertical-align:3px;letter-spacing:1px}
h2{font-size:19px;line-height:1.65;color:#1a1a1a;font-weight:700;margin:0 0 8px}
.meta-line{font-size:13px;color:#9b9b9b;margin:0 0 16px;padding-left:2px}
.fig{display:block;width:100%;height:auto;border-radius:4px;margin:2px 0 16px;background:#f4f4f4}
p{margin:14px 0}
.fact{color:#3f3f3f}
.sub{font-size:15px;font-weight:700;color:#222;margin:24px 0 10px;padding-left:9px;border-left:3px solid #d4472a;line-height:1.5}
.angles{list-style:none;margin:0;padding:0;counter-reset:a}
.angles li{counter-increment:a;position:relative;padding-left:26px;margin:8px 0;color:#3f3f3f}
.angles li:before{content:counter(a);position:absolute;left:0;top:0;color:#d4472a;font-weight:600;font-size:14px;line-height:1.9}
.quote{background:#f7f7f7;padding:14px 16px;border-radius:4px;margin:0}
.quote p{margin:4px 0;font-size:15px;color:#444;line-height:1.8}
.audience{font-size:14px;color:#9b9b9b;margin:16px 0 8px}
.src{font-size:14px;color:#576b95;text-decoration:none}
.src:hover{text-decoration:underline}
.empty{text-align:center;color:#9b9b9b;padding:48px 0}
footer{margin-top:56px;text-align:center;color:#b0b0b0;font-size:12px;line-height:2.2}
footer a{color:#8a9bbf;text-decoration:none}
@media (max-width:760px){main{width:auto;padding:32px 20px 64px}}
@media (min-width:1200px){body{font-size:17px}h1{font-size:28px}h2{font-size:21px}.fact,.angles li{font-size:17px}}
"""


def _esc(s):
    return html.escape(str(s or ""), quote=True)


def _pretty_date(d):
    dt = date.fromisoformat(d)
    wd = "一二三四五六日"[dt.weekday()]
    return f"{dt.month} 月 {dt.day} 日 · 周{wd}"


def _archive_html(archive, current):
    days = [d for d in archive if d != current][:14]
    if not days:
        return ""
    links = " ｜ ".join(f'<a href="{_esc(d)}.html">{_esc(d[5:])}</a>' for d in days)
    return f"<p>往期：{links}</p>"


def _card_html(i, c):
    meta_parts = [x for x in (c.get("source"), c.get("heat")) if x]
    meta = ""
    if meta_parts:
        meta = '<p class="meta-line">' + " ｜ ".join(_esc(x) for x in meta_parts) + "</p>"
    parts = [
        '<section class="section">',
        f'<h2><span class="no">{i:02d}</span>{_esc(c["title"])}</h2>',
        meta,
    ]
    if c.get("image_local"):
        parts.append(
            f'<img class="fig" src="{_esc(c["image_local"])}" alt="{_esc(c["title"])}" loading="lazy">'
        )
    if c.get("fact"):
        parts.append(f'<p class="fact">{_esc(c["fact"])}</p>')
    if c.get("why_hot"):
        parts.append(f'<p class="sub">为什么火</p><p>{_esc(c["why_hot"])}</p>')
    if c.get("angles"):
        lis = "".join(f"<li>{_esc(a)}</li>" for a in c["angles"])
        parts.append(f'<p class="sub">切入角度</p><ol class="angles">{lis}</ol>')
    if c.get("xhs_titles"):
        ps = "".join(f"<p>{_esc(t)}</p>" for t in c["xhs_titles"])
        parts.append(f'<p class="sub">小红书标题</p><div class="quote">{ps}</div>')
    if c.get("audience"):
        parts.append(f'<p class="audience">适合：{_esc(c["audience"])}</p>')
    if c.get("url"):
        parts.append(
            f'<p><a class="src" href="{_esc(c["url"])}" target="_blank" rel="noopener">查看原文 ↗</a></p>'
        )
    parts.append("</section>")
    return "".join(parts)


def build_page(cards, date_str, note="", archive=None):
    archive = archive or []
    sections = [_card_html(i, c) for i, c in enumerate(cards, 1)]
    if sections:
        body = '<div class="orn"><span>◆</span></div>'.join(sections)
    else:
        body = '<p class="empty">今天没有达到质量标准的选题。宁缺勿滥，明天见。</p>'
    lede = f'<p class="lede">{_esc(note)}</p>' if note else ""
    dt = date.fromisoformat(date_str)
    footer_archive = _archive_html(archive, date_str)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 选题日报 · {_esc(date_str)}</title>
<style>{CSS}</style>
</head>
<body>
<main>
<header class="masthead">
<span class="kicker">AI 选题日报</span>
<h1>{dt.month} 月 {dt.day} 日 · {len(cards)} 条选题</h1>
<p class="meta">{_esc(date_str)} · 周{"一二三四五六日"[dt.weekday()]} · 每天 06:45 更新</p>
{lede}
</header>
<div class="orn"><span>◆</span></div>
{body}
<footer>
<p>数据源：tophub 热榜 ｜ Hacker News ｜ arXiv ｜ GitHub Trending ｜ X</p>
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
