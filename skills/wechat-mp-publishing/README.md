# WeChat MP Publishing — Ship Posts Without Killing the Account

**[English]**

An agent skill for the WeChat Official Account pipeline: pull backend stats for review, render article images locally, create rich-text drafts in bulk, and run a pre-publish check. It builds drafts and checks them — **it never presses Publish.**

The first version of this pipeline killed an account. That's why half the skill is about slowing you down.

# 公众号发布 — 别把账号做死

**[中文]**

一个覆盖公众号内容流水线的 Agent 技能：拉后台数据复盘、本地渲染配图、批量建图文草稿、发布前检查。它只建草稿和把关，**绝不替你点发表**。

这套流水线的第一版把一个账号做死过。所以其中一半内容是在拦着你少发。

## What it does / 功能

| | EN | 中文 |
|---|---|---|
| Review | Pulls all published posts, ranks by **share rate** (not reads), computes cadence and open rate | 拉全量发布记录，按**分享率**排序（不是阅读量），算节奏与开封率 |
| Images | Two local HTML template sets, 14 layouts, rotated to avoid looking mass-produced | 两套本地 HTML 配图模板、14 种版式，轮换使用避免同质化 |
| Drafts | Markdown import → title/author/digest → cover → original declaration → creation source | Markdown 导入 → 标题/作者/摘要 → 封面 → 原创声明 → 创作来源 |
| Pre-publish | Cadence gate + per-draft readiness check (cover / original / source / image count / duplicates) | 节奏闸门 + 逐篇齐备性核对（封面/原创/来源/图片数/重复图） |

## Why a whole section tells you to post less / 为什么有一整节在劝你少发

**[English]** After 23 near-identical posts published daily, the account was flagged **"low-effort content"** and recommendation traffic went to **zero** — 4–5 reads per post for days afterwards, week-over-week **−94%**, followers net negative. Every one of those 23 had real detail and concrete numbers. **The platform judges the account-level pattern, not the single post.**

The sequel matters more: once the flag cleared, switching content type, reader angle, image style and CTA made it *worse* (1 / 4 / 4 reads). **When recommendation is zero, content is not the variable.**

**[中文]** 连续日更 23 篇高度同构的文章后，账号被判定**「低创作度内容」**，推荐流量**直接归零**——之后连续多日每篇 4–5 阅读，同比上周 **−94%**，粉丝净减。那 23 篇每篇都有真实细节和具体数字。**平台判的是账号级模式，不是单篇质量。**

后续更值得记：判定解除后，把内容类型、读者视角、配图风格、CTA 全部换掉重写，阅读反而更低（1 / 4 / 4）。**推荐归零时，内容是无效变量。**

So the skill ships hard limits (frequency cap, drafts-per-batch cap, no template reuse), and `scripts/preflight.mjs` blocks you when you try to post too often.
所以技能里带了硬约束（频率上限、单批草稿数上限、模板不许复用），`scripts/preflight.mjs` 的节奏闸门会在你想连发时直接拦下来。

Full post-mortem: [`references/content-rules.md`](references/content-rules.md)

## Requirements / 依赖

Node.js and **ego-browser** (Chromium that reuses your logged-in session). No other dependencies — the image templates are plain HTML + CSS.
Node.js 和 **ego-browser**（复用你已登录会话的 Chromium）。无其他依赖，配图模板是纯 HTML + CSS。

## Configure / 配置

Nothing about any account is hardcoded. Pass it in:
技能不硬编码任何账号信息，调用时传入：

```js
await publishDraft(page, {
  token,                // ?token= from the backend URL / 后台 URL 里的 token
  mdPath,               // local Markdown; first image becomes the cover / 第一张图会成为封面
  title, digest,
  author: 'your pen name',
  original: true,       // declare original — irreversible once published / 发表后不可撤销
  claimSourceType: 1,   // 1 = AI-generated, 0 = none, null = skip / 1 = 内容由AI生成
  expectImgs: 4,
})
```

## Layout / 目录

```
SKILL.md                    main doc, the agent reads this / 主文档
references/backend-api.md   endpoints, DOM selectors, a dozen verified gotchas / 接口、选择器与踩过的坑
references/content-rules.md content rules and the full post-mortem / 内容规律与事故复盘
scripts/render-cards.mjs    image template A: warm cards, 8 layouts / 配图模板 A：暖色卡片
scripts/render-editorial.mjs image template B: ink-on-paper, 6 layouts / 配图模板 B：纸墨社论
scripts/publish-draft.mjs   create a draft, fully configured / 建草稿
scripts/preflight.mjs       cadence gate + readiness check / 发布前检查
```

## Gotchas already paid for / 已经踩过的坑

All verified; details in `references/backend-api.md`.
全部实测过，细节见 `references/backend-api.md`。

- `/cgi-bin/uploadimg2cdn` returns `200009` — use `filetransfer?action=upload_material&scene=8`
- Setting the cover via API returns `ret: 0` but **silently does nothing**; only the UI path works
- With no leading image, the importer attaches an AI-generated cover **you cannot override**
- Markdown import occasionally **duplicates body images** — and the count is correct at import time, only wrong after saving
- Drafts can vanish (`System error (320003)`), so re-count via the list API after creating them
- The backend UI may render in English — every selector needs both languages

## Caveats / 声明

- These are **observations of undocumented backend endpoints**, not an official API. WeChat can change them anytime.
  这些是**对后台内部接口的观察**，不是官方 API，微信随时可以改。
- The content rules come from **one account, two months, ~55 posts**. Don't copy the numbers; the causal structure probably generalises.
  内容规律来自**单个账号两个月约 55 篇**的实测。数字不必照搬，因果结构大概率通用。
- This writes into your own account. **Try it on a test account first.**
  它会往你自己的账号里写内容。**先在测试账号上跑一遍。**
