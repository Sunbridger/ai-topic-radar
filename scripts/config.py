# -*- coding: utf-8 -*-
"""全局配置：数据源、过滤词、账号定位与限额。"""

import re

TIMEZONE = "Asia/Shanghai"
DEDUPE_DAYS = 7
CARDS_MAX = 10
CARDS_MIN = 5  # 低于该数量照常推送，卡片里会注明「今日热点较少」

# ---- 中文热榜（tophub 聚合，每天只抓一次；节点 ID 见 tophub.today） ----
TOPHUB_BASE = "https://tophub.today"
TOPHUB_NODES = {
    "weibo": ("微博热搜", "KqndgxeLl9"),
    "zhihu": ("知乎热榜", "mproPpoq6O"),
    "bilibili": ("B站日榜", "74KvxwokxM"),
    "douyin": ("抖音热榜", "DpQvNABoNE"),
}

# ---- 海外源 ----
X_ACCOUNTS = ["OpenAI", "AnthropicAI", "karpathy", "_akhaliq", "sama"]
HN_MIN_POINTS = 80
ARXIV_URL = (
    "https://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL"
    "&sortBy=submittedDate&sortOrder=descending&max_results=40"
)
ARXIV_HOURS = 24
X_HOURS = 24
GITHUB_TRENDING_URL = "https://github.com/trending?since=daily"

# ---- 相关性：命中即视为 AI/科技话题 ----
AI_KEYWORDS_CN = [
    "人工智能", "大模型", "智能体", "生成式", "文生图", "文生视频", "文生音乐",
    "算力", "英伟达", "芯片", "机器人", "具身智能", "自动驾驶", "数字人", "虚拟人",
    "提示词", "多模态", "微调", "开源模型", "AI绘画", "AI写作", "AI视频", "AI编程",
    "AI手机", "AI眼镜", "智能眼镜", "AI应用", "AI工具", "AIGC", "OpenAI", "Anthropic",
    "ChatGPT", "DeepSeek", "Sora", "Midjourney", "Claude", "Gemini", "Llama", "Qwen",
    "豆包", "通义", "文心", "Kimi", "智谱", "月之暗面", "Copilot",
]
AI_PATTERN = re.compile(
    r"(?<![a-z0-9])(ai|aigc|llm|gpt|chatgpt|claude|anthropic|gemini|openai|deepseek|sora|"
    r"midjourney|nvidia|gpu|tpu|npu|agent|agents|chatbot|copilot|cursor|ollama|llama|qwen|"
    r"hugging\s?face|transformer|diffusion|multimodal|machine\s+learning|neural|rag|mcp|vlm)"
    r"(?![a-z])",
    re.I,
)

# ---- 敏感/时政：标题命中即剔除（先过滤，不交给 LLM 判断） ----
SENSITIVE_KEYWORDS = [
    "习近平", "李强", "台独", "港独", "疆独", "藏独", "六四", "法轮", "导弹", "核武",
    "军演", "开战", "战争", "中美元首", "总统", "特朗普", "拜登", "白宫", "五角大楼",
    "国会", "参议院", "众议院", "选举", "制裁", "关税", "外交", "APEC", "央视新闻",
    "媒体原创", "外交部", "国防部", "人民日报", "新华社",
]

# 中文热榜源（用于区分「可借势」候选）
CN_HOT_SOURCES = ("微博热搜", "知乎热榜", "B站日榜", "B站热门", "抖音热榜")

# 每源进入候选池的条数上限
SOURCE_QUOTA = {
    "微博热搜": 8,
    "知乎热榜": 8,
    "B站日榜": 5,
    "B站热门": 5,
    "抖音热榜": 5,
    "Hacker News": 12,
    "GitHub Trending": 8,
    "arXiv": 6,
}
X_QUOTA_PER_ACCOUNT = 3
BACKGROUND_QUOTA = 12
CANDIDATE_CAP = 70
