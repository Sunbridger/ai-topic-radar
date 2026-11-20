# -*- coding: utf-8 -*-
"""各数据源抓取。每个 fetch_* 返回 item dict 列表，失败抛异常由上层记录。"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

from . import config

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _get(url, timeout=20, headers=None):
    r = requests.get(url, headers=headers or HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def _clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _item(source, title, url, heat="", snippet="", ts=None, rank=None, kind="ai", image=""):
    return {
        "source": source,
        "title": _clean(title),
        "url": url or "",
        "heat": _clean(heat),
        "snippet": _clean(snippet)[:300],
        "ts": ts,
        "rank": rank,
        "kind": kind,
        "image": image or "",
    }


def _rfc822(s):
    try:
        return int(parsedate_to_datetime(s).timestamp())
    except Exception:
        return None


def _iso_ts(s):
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


# ---------------------------------------------------------------- 中文热榜

def fetch_tophub(key):
    """解析 tophub 节点页的表格：排名 / 标题链接 / 热度。"""
    name, node = config.TOPHUB_NODES[key]
    r = _get(f"{config.TOPHUB_BASE}/n/{node}")
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for tr in soup.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        rank_txt = _clean(tds[0].get_text()).rstrip(".")
        if not rank_txt.isdigit():
            continue
        # 两种行布局：文字榜（微博）链接在 td[1]；图文榜链接在含封面的 td 内
        a = None
        for td in tds[1:]:
            cand = td.find("a", href=True)
            if cand and _clean(cand.get_text()) and str(cand["href"]).startswith("http"):
                a = cand
                break
        if not a:
            continue
        heat = ""
        ws = tr.select_one("td.ws")
        if ws:
            heat = _clean(ws.get_text())
        else:
            cell = a.find_parent("td")
            desc = cell.select_one(".item-desc") if cell else None
            if desc:
                heat = _clean(desc.get_text())
        title = _clean(a.get_text())
        image = ""
        for td in tds[1:]:
            im = td.find("img")
            if not im:
                continue
            src = im.get("data-src") or im.get("src") or ""
            if src.startswith("http") and "placeholder-lazyload" not in src:
                image = src
            break
        if title:
            items.append(_item(name, title, a["href"], heat, rank=int(rank_txt), image=image))
        if len(items) >= 30:
            break
    if not items:
        raise ValueError(f"{name} 解析为空，可能页面改版")
    return items


def fetch_zhihu():
    """知乎移动端热榜接口（免签，可能限流）。"""
    mobile = {
        **HEADERS,
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
        ),
    }
    r = _get("https://api.zhihu.com/topstory/hot-list?limit=30", headers=mobile)
    data = r.json().get("data") or []
    items = []
    for i, it in enumerate(data, 1):
        t = it.get("target") or {}
        title, qid = t.get("title"), t.get("id")
        if not title or not qid:
            continue
        heat = ""
        if t.get("follower_count"):
            heat = f"{t['follower_count']} 关注 · {t.get('answer_count', 0)} 回答"
        items.append(_item(
            "知乎热榜", title, f"https://www.zhihu.com/question/{qid}", heat,
            t.get("excerpt") or "", rank=i,
        ))
    if not items:
        raise ValueError("知乎热榜解析为空")
    return items


def fetch_bilibili():
    """B 站综合热门（匿名接口，免 WBI 签名）。"""
    r = _get("https://api.bilibili.com/x/web-interface/popular?ps=30&pn=1")
    data = r.json()
    if data.get("code") != 0:
        raise ValueError(f"B站接口 code={data.get('code')}")
    items = []
    for i, v in enumerate(data["data"].get("list", []), 1):
        view = (v.get("stat") or {}).get("view", 0)
        heat = f"{view / 10000:.1f}万播放" if view >= 10000 else f"{view}播放"
        pic = (v.get("pic") or "").replace("http://", "https://")
        items.append(_item(
            "B站热门", v.get("title", ""), f"https://www.bilibili.com/video/{v.get('bvid', '')}",
            heat, v.get("desc", ""), rank=i, image=pic,
        ))
    return items


# ---------------------------------------------------------------- 海外源

def fetch_hn():
    since = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
    url = (
        "https://hn.algolia.com/api/v1/search?tags=story"
        f"&numericFilters=created_at_i%3E{since},points%3E{config.HN_MIN_POINTS}"
        "&hitsPerPage=50"
    )
    hits = _get(url).json().get("hits", [])
    items = []
    for h in hits:
        title = h.get("title") or h.get("story_title") or ""
        if not title:
            continue
        link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        items.append(_item(
            "Hacker News", title, link,
            f"{h.get('points', 0)} 分 · {h.get('num_comments', 0)} 评论",
            h.get("story_text") or "", ts=h.get("created_at_i"),
        ))
    return items


def fetch_github_trending():
    r = _get(config.GITHUB_TRENDING_URL)
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for art in soup.select("article.Box-row"):
        a = art.select_one("h2 a")
        if not a or not a.get("href"):
            continue
        repo = str(a["href"]).strip("/")
        desc_el = art.select_one("p")
        desc = _clean(desc_el.get_text()) if desc_el else ""
        star_el = art.select_one("span.float-sm-right")
        stars = _clean(star_el.get_text()) if star_el else ""
        items.append(_item(
            "GitHub Trending", repo, f"https://github.com/{repo}", stars, desc,
            image=f"https://opengraph.githubassets.com/1/{repo}",
        ))
    if not items:
        raise ValueError("GitHub Trending 解析为空")
    return items


def fetch_arxiv():
    root = ET.fromstring(_get(config.ARXIV_URL, timeout=30).content)
    items = []
    for e in root.findall("a:entry", ATOM):
        title = _clean(e.findtext("a:title", default="", namespaces=ATOM))
        link = e.findtext("a:id", default="", namespaces=ATOM)
        published = e.findtext("a:published", default="", namespaces=ATOM)
        summary = _clean(e.findtext("a:summary", default="", namespaces=ATOM))
        if title:
            items.append(_item(
                "arXiv", title, link, published[:10], summary, ts=_iso_ts(published),
            ))
    return items


def fetch_x():
    """FxTwitter 的 RSS 时间线，每个账号取最近 3 条。"""
    items, errors = [], []
    for handle in config.X_ACCOUNTS:
        try:
            r = _get(f"https://fxtwitter.com/{handle}/feed.xml", timeout=15)
            root = ET.fromstring(r.content)
            got = []
            for it in root.iter("item"):
                title = _clean(it.findtext("title") or "")
                link = _clean(it.findtext("link") or "")
                # FxTwitter 偶尔把纯链接当作标题，丢弃
                if not title or title.startswith("http") or len(title) < 6:
                    continue
                image = ""
                for enc in it.findall("enclosure"):
                    if (enc.get("type") or "").startswith("image/") and enc.get("url"):
                        image = enc.get("url")
                        break
                if not image:
                    thumb = it.find("{http://search.yahoo.com/mrss/}thumbnail")
                    if thumb is not None:
                        image = thumb.get("url") or ""
                got.append(_item(
                    f"X · @{handle}", title, link, "X 账号动态",
                    ts=_rfc822(it.findtext("pubDate") or ""), image=image,
                ))
            got.sort(key=lambda x: x["ts"] or 0, reverse=True)
            items.extend(got[:config.X_QUOTA_PER_ACCOUNT])
        except Exception as exc:  # 单账号失败不影响整体
            errors.append(f"{handle}: {exc}")
    if not items:
        raise ValueError("FxTwitter 全部失败：" + "; ".join(errors))
    return items
