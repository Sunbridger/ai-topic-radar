# AI 选题雷达

每天 06:45 抓取中文热榜与海外 AI 一手源，用 DeepSeek 加工成 8–10 条小红书向选题卡，通过 Bark 推送到 iPhone，全文发布到 GitHub Pages。

## 产出

- **Bark 通知**：标题带条数，正文列选题标题，点击跳转全文页
- **日报页**：`https://<owner>.github.io/ai-topic-radar/<YYYY-MM-DD>.html`，公众号风格排版，含封面图、事实、为什么火、3 个角度、2 个小红书标题、受众

封面图取自各源（B站/知乎/抖音封面、GitHub OG 图、X 配图），运行时下载压缩到 `docs/img/<date>/` 并随页面发布，不依赖外链；超过 60 天的图片会自动清理。

## 数据源

| 层 | 来源 | 方式 |
|---|---|---|
| 中文热榜 | 微博热搜 / 知乎热榜 / B站日榜 / 抖音热榜 | tophub.today 节点页（每天一次） |
| 中文热榜补充 | B站热门、知乎热榜 | 官方免签接口直连 |
| 海外 | Hacker News | Algolia API（24h 内 ≥ 80 分） |
| 海外 | GitHub Trending | daily 页解析 |
| 海外 | arXiv cs.AI / cs.CL | 官方 Atom API（24h 内） |
| 海外 | X：OpenAI / AnthropicAI / karpathy / _akhaliq / sama | FxTwitter RSS |

## 规则

- 只保留 AI 相关话题；中文热榜中的破圈热点最多借势 2 条
- 时政 / 敏感关键词直接剔除
- 7 天 `data/seen.json` 去重，持续发酵的话题以新进展重入
- 每天最多 10 条；合格不足 5 条照发并注明，宁缺勿滥

## 部署步骤

1. 新建 public 仓库并推送本目录（或直接 fork）。
2. **Settings → Pages**：Source 选 `Deploy from a branch`，分支 `main`，目录 `/docs`。
3. **Settings → Secrets and variables → Actions**：添加
   - `DEEPSEEK_API_KEY`：DeepSeek 平台创建的 API Key
   - `BARK_ENDPOINT`：Bark App 里「服务器」页的推送地址，形如 `https://api.day.app/<key>`（带 `/title/body?…` 的示例地址也可直接粘贴）
4. **Actions → daily-topics → Run workflow** 手动跑一次验证。
5. 之后每天 06:45（北京时间）自动运行，7:00 前送达。

> 首次启用 Pages 后，日报页 URL 形如 `https://<owner>.github.io/ai-topic-radar/2026-11-21.html`。
> 仓库每天有一次自动提交（`seen.json` + 页面），同时避免公开仓库 60 天无活动导致定时任务被停用。

## 本地运行

```bash
uv venv
uv pip install -r requirements.txt

# 只看抓取结果
.venv/bin/python -m scripts.main --fetch-only

# 生成占位预览页（不调 LLM、不推送）
.venv/bin/python -m scripts.main --dry-run

# 完整运行（需要 key 与 Bark 地址）
DEEPSEEK_API_KEY=sk-xxx BARK_ENDPOINT=https://api.day.app/<key> \
  .venv/bin/python -m scripts.main
```

## 配置

账号定位、关键词、敏感词、每源配额、X 账号列表、Bark 分组与 TTL 都在 `scripts/config.py`；LLM 提示词在 `scripts/pipeline.py` 的 `SYSTEM_PROMPT`。

## 已知限制

- tophub 页面结构或节点 ID 变更会导致解析失败（日志里会标出「解析为空」）
- GitHub Actions 定时可能有 5–30 分钟延迟
- FxTwitter 为第三方免费服务，可能限流或停服
- 数据源合规：tophub 属聚合站，日更一次、低频率使用
- 成本：DeepSeek 每天约 ¥1；Actions 公开仓库免费
