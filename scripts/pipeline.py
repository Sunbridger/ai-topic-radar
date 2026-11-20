# -*- coding: utf-8 -*-
"""候选筛选、去重、调用 LLM 生成选题卡。"""

import hashlib
import json
import re
import time
from datetime import date, timedelta

from . import config, llm

SYSTEM_PROMPT = """你是资深 AI 自媒体选题编辑。账号定位：AI 工具评测 / 玩法分享。发布平台：小红书图文。读者：想用 AI 提效的普通用户（非开发者为主）。

任务：从「今日候选热点」里挑出今天最值得写的选题，最多 10 条、最少 1 条；质量不够就少选，不要凑数。按「热度 × 与账号定位的匹配度」排序。

规则：
1. 只写与 AI 工具、AI 应用、AI 玩法、AI 产品、模型发布、AI 硬件、AI 对普通人的影响相关的话题。
2. source 为中文热榜且 kind=trend 的条目是大众热点，本身与 AI 无关：最多选 2 条，且必须能自然落到「AI 工具 / 玩法」上做成借势选题；做不到就不选。
3. 不碰时政、敏感话题；事实和数字只能来自候选项，不得编造；热度只能引用候选里的原文。
4. 每条给 3 个具体可执行的切入角度（能直接开工，不要空话），2 个小红书标题（口语化、带情绪或数字、不超过 20 字、不要夸张失真）。
5. 只输出 JSON，不要输出任何解释或代码块标记。

输出结构：
{"cards":[{"title":"选题标题（中文，贴近事件本身）","source":"来源名","heat":"热度原文","fact":"事实概述，100 字内","why_hot":"为什么火，80 字内","angles":["角度1","角度2","角度3"],"xhs_titles":["标题1","标题2"],"audience":"目标受众与场景，40 字内","url":"候选项里的 url，原样复制"}],"note":"一句话总结今天的选题形势，30 字内"}"""


# ---------------------------------------------------------------- 基础工具

def norm_title(t):
    return re.sub(r"[^\w一-鿿]+", "", (t or "").lower())


def title_key(t):
    return hashlib.sha1(norm_title(t).encode("utf-8")).hexdigest()[:16]


def is_sensitive(title):
    return any(kw in title for kw in config.SENSITIVE_KEYWORDS)


def is_ai(text):
    if config.AI_PATTERN.search(text):
        return True
    return any(kw in text for kw in config.AI_KEYWORDS_CN)


def heat_value(text):
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(亿|万|千)?", text or "")
    if not m:
        return 0.0
    num = float(m.group(1).replace(",", ""))
    return num * {"亿": 1e8, "万": 1e4, "千": 1e3}.get(m.group(2), 1)


# ---------------------------------------------------------------- 去重状态

def load_seen(path):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw.get("entries", {}) if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _cutoff(today):
    return (date.fromisoformat(today) - timedelta(days=config.DEDUPE_DAYS)).isoformat()


def active_seen(entries, today):
    cutoff = _cutoff(today)
    return {k: v for k, v in entries.items() if str(v.get("date", "")) >= cutoff}


def mark_seen(path, cards, today):
    entries = load_seen(path)
    for c in cards:
        key = c.get("key") or title_key(c.get("title", ""))
        entries[key] = {"title": (c.get("title") or "")[:80], "date": today}
    cutoff = _cutoff(today)
    entries = {k: v for k, v in entries.items() if str(v.get("date", "")) >= cutoff}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- 筛选排序

def _score(it):
    if it["source"] == "arXiv" or it["source"].startswith("X ·"):
        return float(it.get("ts") or 0)
    return heat_value(it.get("heat"))


def select_candidates(items, seen, now_ts=None):
    """过滤敏感/已推/重复，按来源配额组装候选池。"""
    now_ts = now_ts or time.time()
    stats = {"in": len(items), "sensitive": 0, "seen": 0, "dup": 0,
             "stale": 0, "ai": 0, "trend": 0}
    per_source, background, local_keys = {}, [], set()

    for it in items:
        title = it.get("title") or ""
        if not title:
            continue
        if is_sensitive(title):
            stats["sensitive"] += 1
            continue
        key = title_key(title)
        if key in seen:
            stats["seen"] += 1
            continue
        if key in local_keys:
            stats["dup"] += 1
            continue
        ts = it.get("ts")
        if it["source"] == "arXiv" and ts and now_ts - ts > config.ARXIV_HOURS * 3600:
            stats["stale"] += 1
            continue
        if it["source"].startswith("X ·") and ts and now_ts - ts > config.X_HOURS * 3600:
            stats["stale"] += 1
            continue
        local_keys.add(key)
        it["key"] = key

        trusted = it["source"] == "arXiv" or it["source"].startswith("X ·")
        # 中文热榜只看标题：摘要里的顺带提及会引入财经/娱乐噪音
        relevance_text = title if it["source"] in config.CN_HOT_SOURCES else f"{title} {it.get('snippet', '')}"
        if trusted or is_ai(relevance_text):
            it["kind"] = "ai"
            stats["ai"] += 1
            per_source.setdefault(it["source"], []).append(it)
        elif it["source"] in config.CN_HOT_SOURCES:
            it["kind"] = "trend"
            stats["trend"] += 1
            background.append(it)
        # 海外非 AI 条目（HN / GitHub）直接丢弃

    candidates = []
    for src, lst in per_source.items():
        quota = config.X_QUOTA_PER_ACCOUNT if src.startswith("X ·") else config.SOURCE_QUOTA.get(src, 6)
        lst.sort(key=_score, reverse=True)
        candidates.extend(lst[:quota])
    background.sort(key=_score, reverse=True)
    candidates.extend(background[:config.BACKGROUND_QUOTA])
    return candidates[:config.CANDIDATE_CAP], stats


# ---------------------------------------------------------------- 生成选题卡

def build_cards(candidates, today):
    payload = [
        {
            "id": i,
            "source": c["source"],
            "kind": c["kind"],
            "title": c["title"],
            "heat": c.get("heat", ""),
            "snippet": (c.get("snippet") or "")[:160],
            "url": c["url"],
        }
        for i, c in enumerate(candidates, 1)
    ]
    user = (
        "今日候选热点（JSON）：\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\n请按要求输出选题卡 JSON。"
    )
    data = llm.chat_json(SYSTEM_PROMPT, user)
    cards = _validate(data.get("cards") or [], candidates)
    note = str(data.get("note") or "").strip()
    return cards, note


def _validate(raw, candidates):
    by_url = {c["url"]: c for c in candidates if c.get("url")}
    by_title = {title_key(c["title"]): c["url"] for c in candidates}
    cards = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        title = str(r.get("title") or "").strip()
        if not title:
            continue
        url = str(r.get("url") or "").strip()
        if url not in by_url:
            url = by_title.get(title_key(title), "")
        cand = by_url.get(url) or {}
        angles = [str(a).strip() for a in (r.get("angles") or []) if str(a).strip()][:3]
        xhs = [str(a).strip() for a in (r.get("xhs_titles") or []) if str(a).strip()][:2]
        cards.append({
            "title": title,
            "source": str(r.get("source") or cand.get("source") or ""),
            "heat": str(r.get("heat") or cand.get("heat") or ""),
            "kind": cand.get("kind", "ai"),
            "fact": str(r.get("fact") or "").strip(),
            "why_hot": str(r.get("why_hot") or "").strip(),
            "angles": angles,
            "xhs_titles": xhs,
            "audience": str(r.get("audience") or "").strip(),
            "url": url,
            "key": cand.get("key") or title_key(title),
            "image": cand.get("image", ""),
        })
        if len(cards) >= config.CARDS_MAX:
            break
    return cards


def stub_cards(candidates):
    """本地预览用：不调用 LLM，用候选生成占位卡片。"""
    cards = []
    for c in candidates[:8]:
        cards.append({
            "title": c["title"],
            "source": c["source"],
            "heat": c.get("heat", ""),
            "kind": c["kind"],
            "fact": (c.get("snippet") or "（预览模式，未调用 DeepSeek）")[:120],
            "why_hot": f"热度：{c.get('heat') or '未知'}",
            "angles": ["预览角度 1", "预览角度 2", "预览角度 3"],
            "xhs_titles": [f"「{c['title'][:12]}」这个 AI 玩法值得写"],
            "audience": "预览受众",
            "url": c["url"],
            "key": c.get("key", ""),
            "image": c.get("image", ""),
        })
    return cards
