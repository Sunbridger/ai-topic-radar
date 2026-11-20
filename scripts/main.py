# -*- coding: utf-8 -*-
"""入口：抓取 → 过滤 → LLM 加工 → 生成页面 → 推送飞书。

用法：
    python -m scripts.main                 # 正式运行（需 DEEPSEEK_API_KEY / BARK_ENDPOINT）
    python -m scripts.main --dry-run       # 不调 LLM、不推送，生成占位预览页
    python -m scripts.main --fetch-only    # 只抓取并输出候选 JSON
    python -m scripts.main --no-push       # 正式加工但不推送
    python -m scripts.main --date 2026-11-21
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from . import config, fetch, pipeline, render

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"


def _run_source(name, fn, items, statuses):
    try:
        got = fn()
        statuses[name] = {"ok": True, "count": len(got)}
        items.extend(got)
    except Exception as exc:
        statuses[name] = {"ok": False, "count": 0, "error": f"{type(exc).__name__}: {exc}"}
        print(f"[warn] {name} 抓取失败：{statuses[name]['error']}")


def fetch_all():
    items, statuses = [], {}
    for key, (label, _) in config.TOPHUB_NODES.items():
        _run_source(label, lambda k=key: fetch.fetch_tophub(k), items, statuses)
    _run_source("知乎直连", fetch.fetch_zhihu, items, statuses)
    _run_source("B站直连", fetch.fetch_bilibili, items, statuses)
    _run_source("Hacker News", fetch.fetch_hn, items, statuses)
    _run_source("GitHub Trending", fetch.fetch_github_trending, items, statuses)
    _run_source("arXiv", fetch.fetch_arxiv, items, statuses)
    _run_source("X / FxTwitter", fetch.fetch_x, items, statuses)
    return items, statuses


def page_base():
    explicit = os.environ.get("PAGES_BASE_URL", "").rstrip("/")
    if explicit:
        return explicit
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{name}"
    return ""


def _bark_base(endpoint):
    """支持两种写法：https://api.day.app/<key> 或带 /title/body?group=... 的示例地址。"""
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(endpoint.strip())
    segs = [s for s in parts.path.split("/") if s]
    key = segs[0] if segs else ""
    return urlunsplit((parts.scheme or "https", parts.netloc or "api.day.app", f"/{key}", "", ""))


def attach_images(cards, date_str):
    """下载封面并压缩到 docs/img/<date>/，让页面不依赖外链图片。"""
    try:
        from io import BytesIO

        from PIL import Image
    except Exception as exc:
        print(f"[warn] Pillow 不可用，跳过图片：{exc}")
        return
    from urllib.parse import urlsplit

    outdir = DOCS / "img" / date_str
    if outdir.exists():
        for old in outdir.glob("*.jpg"):
            old.unlink(missing_ok=True)
    saved = 0
    for i, c in enumerate(cards, 1):
        url = (c.get("image") or "").strip()
        if not url.startswith("http"):
            continue
        try:
            host = urlsplit(url).netloc
            r = requests.get(url, headers={
                "User-Agent": fetch.HEADERS["User-Agent"],
                "Referer": f"https://{host}/",
            }, timeout=25)
            r.raise_for_status()
            if not r.headers.get("Content-Type", "").startswith("image/"):
                continue
            if len(r.content) > 6 * 1024 * 1024:
                continue
            image = Image.open(BytesIO(r.content))
            image = image.convert("RGB")
            image.thumbnail((900, 900))
            outdir.mkdir(parents=True, exist_ok=True)
            name = f"{i:02d}.jpg"
            image.save(outdir / name, "JPEG", quality=82, optimize=True, progressive=True)
            c["image_local"] = f"img/{date_str}/{name}"
            saved += 1
        except Exception as exc:
            print(f"[warn] 图片失败 {i} {url[:70]}：{exc}")
            c["image_local"] = ""
    prune_images()
    print(f"[img] 保存 {saved} 张封面")


def prune_images(days=60):
    """只保留最近 60 天的图片，控制仓库体积。"""
    root = DOCS / "img"
    if not root.exists():
        return
    import shutil

    cutoff = datetime.now() - timedelta(days=days)
    for d in root.iterdir():
        if not d.is_dir():
            continue
        try:
            dt = datetime.strptime(d.name, "%Y-%m-%d")
        except ValueError:
            continue
        if dt < cutoff:
            shutil.rmtree(d, ignore_errors=True)


def push_bark(payload):
    endpoint = os.environ.get("BARK_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("缺少环境变量 BARK_ENDPOINT")
    r = requests.post(_bark_base(endpoint), json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("code") not in (200, None):
        raise RuntimeError(f"Bark 返回错误：{data}")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description="每日 AI 选题助手")
    ap.add_argument("--fetch-only", action="store_true", help="只抓取，输出候选 JSON")
    ap.add_argument("--dry-run", action="store_true", help="不调 LLM、不推飞书，生成预览页")
    ap.add_argument("--no-push", action="store_true", help="不推送飞书")
    ap.add_argument("--date", help="日期 YYYY-MM-DD，默认今天（北京时间）")
    args = ap.parse_args(argv)

    date_str = args.date or datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d")
    DATA.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)

    items, statuses = fetch_all()
    seen = pipeline.active_seen(pipeline.load_seen(DATA / "seen.json"), date_str)
    candidates, stats = pipeline.select_candidates(items, seen)
    print(f"[fetch] 原始 {len(items)} 条，候选 {len(candidates)} 条，统计 {stats}")
    print("[fetch] 各源状态：" + json.dumps(statuses, ensure_ascii=False))

    if args.fetch_only:
        out = DATA / f"candidates_{date_str}.json"
        out.write_text(json.dumps(
            {"date": date_str, "statuses": statuses, "stats": stats, "candidates": candidates},
            ensure_ascii=False, indent=1,
        ), encoding="utf-8")
        print(f"[fetch-only] 已写入 {out}")
        return 0

    if args.dry_run:
        cards = pipeline.stub_cards(candidates)
        note = "预览模式：未调用 DeepSeek，卡片内容为占位。"
    else:
        if not candidates:
            cards, note = [], "今日没有达到质量标准的选题。"
        else:
            cards, note = pipeline.build_cards(candidates, date_str)
            if not cards:
                note = note or "今日没有达到质量标准的选题。"
            elif len(cards) < config.CARDS_MIN:
                note = (note + " " if note else "") + f"今日热点较少，仅 {len(cards)} 条达到标准。"

    attach_images(cards, date_str)

    archive = sorted(
        f.stem for f in DOCS.glob("*.html") if f.stem != "index"
    ) + [date_str]
    archive = sorted(set(archive), reverse=True)

    page = render.build_page(cards, date_str, note, archive=archive)
    (DOCS / f"{date_str}.html").write_text(page, encoding="utf-8")
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    if not args.dry_run:
        pipeline.mark_seen(DATA / "seen.json", cards, date_str)
        (DATA / "last_cards.json").write_text(json.dumps(
            {"date": date_str, "note": note, "cards": cards},
            ensure_ascii=False, indent=1,
        ), encoding="utf-8")

    url = f"{page_base()}/{date_str}.html" if page_base() else ""
    pushed = False
    if args.dry_run or args.no_push:
        print("[push] 跳过（dry-run / no-push）")
    else:
        payload = render.build_bark_payload(cards, date_str, url, note)
        resp = push_bark(payload)
        pushed = True
        print(f"[push] Bark OK，响应 {resp}")

    (DATA / "last_run.json").write_text(json.dumps({
        "date": date_str,
        "statuses": statuses,
        "stats": stats,
        "cards": len(cards),
        "note": note,
        "pushed": pushed,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[done] {date_str}: {len(cards)} 条选题卡，全文页 docs/{date_str}.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
