# WeChat MP Publishing — Ship Posts Without Killing the Account

**[English]**

An agent skill for the WeChat Official Account pipeline: review backend stats, render article images locally, create rich-text drafts in bulk, and check everything before it goes out. It prepares and it checks — **it never presses Publish.**

The first version of this pipeline killed an account. That's why half of this skill is about slowing you down.

# 公众号发布 — 发文，但别把账号做死

**[中文]**

一个覆盖公众号内容流水线的 Agent 技能：复盘后台数据、本地渲染配图、批量建图文草稿、发出前逐项把关。它只做准备和检查——**绝不替你点发表。**

这套流水线的第一版把一个账号做死过。所以这个技能有一半内容，是在拦着你少发。

## What it does / 功能

| | EN | 中文 |
|---|---|---|
| **Review** | Pulls every published post and ranks by **share rate**, not reads; reports cadence and open rate | 拉取全部已发文章，按**分享率**而非阅读量排序，给出发文节奏与开封率 |
| **Images** | Two local HTML template sets, 14 layouts — rotate them so posts don't look mass-produced | 两套本地 HTML 配图模板、14 种版式，轮换使用，避免看起来像批量生产 |
| **Drafts** | Markdown import → title / author / digest → cover → original declaration → creation source | Markdown 导入 → 标题/作者/摘要 → 封面 → 原创声明 → 创作来源 |
| **Pre-publish gate** | Blocks over-posting, then checks each draft: cover, declarations, image count, duplicate images | 先拦过度发文，再逐篇核对：封面、声明、图片数、重复图 |

## Why half of it tells you to post less / 为什么一半内容在劝你少发

**[English]**

After 23 near-identical posts published daily, the account was flagged **"low-effort content"** and recommendation traffic dropped to **zero**: 4–5 reads per post for days, −94% week over week, followers net negative. Each of those 23 posts had real detail and concrete numbers. **The platform judges the account-level pattern, not the single post.**

The sequel matters more. Once the flag cleared, changing the content type, reader angle, image style and CTA made reads *worse* — 1, 4, 4. **When recommendation is at zero, content is not the variable.**

So the skill ships hard limits — a frequency cap, a drafts-per-batch cap, no template reuse — and `scripts/preflight.mjs` stops you when you try to post too often.

**[中文]**

连续日更 23 篇高度同构的文章后，账号被判定**「低创作度内容」**，推荐流量**直接归零**：此后连续多日每篇 4–5 阅读，同比上周 −94%，粉丝净减。那 23 篇每篇都有真实细节和具体数字。**平台判的是账号级的模式，不是单篇质量。**

后续更值得记住。判定解除后，把内容类型、读者视角、配图风格、CTA 全部换掉重写，阅读反而更低——1、4、4。**推荐归零时，内容不是变量。**

所以技能里带了硬约束——频率上限、单批草稿数上限、模板不许复用——`scripts/preflight.mjs` 会在你想连发时直接拦下来。

Full post-mortem / 完整复盘：[`references/content-rules.md`](references/content-rules.md)

## Example / 效果

> **You:** Turn these three articles into drafts and get them ready to publish.
>
> **AI:** Drafts are done — 3 created, covers, original declaration and creation source all set. But the cadence gate blocks publishing: you've posted 2 times in the last 7 days (limit 2). Earliest safe date is Tuesday. Want me to hold them until then?

> **你：** 把这三篇做成草稿，准备发布。
>
> **AI：** 草稿建好了——3 篇，封面、原创声明、创作来源都已配好。但节奏闸门拦下了发布：最近 7 天已发 2 篇（上限 2 篇），最早可以周二发。要不要先放着，到时候再发？

## Installation / 安装

```bash
npx skills add Yanghe1941/skills --skill wechat-mp-publishing
```

Requires Node.js and [**ego lite**](https://github.com/citrolabs/ego-lite) — a Chromium built for AI agents that reuses your logged-in session (`npx skills add citrolabs/ego-lite`). Nothing else: the image templates are plain HTML + CSS.
需要 Node.js 和 [**ego lite**](https://github.com/citrolabs/ego-lite)——专为 AI Agent 打造、能复用你已登录会话的 Chromium（`npx skills add citrolabs/ego-lite`）。没有其他依赖，配图模板是纯 HTML + CSS。

## Configuration / 配置

Nothing about any account is hardcoded — pass it in:
不硬编码任何账号信息，调用时传入：

```js
await publishDraft(page, {
  token,                // ?token= from the backend URL / 后台地址里的 token
  mdPath,               // local Markdown; the first image becomes the cover / 本地 Markdown，第一张图作封面
  title, digest,
  author: 'your pen name',
  original: true,       // declare original — irreversible once published / 声明原创，发表后不可撤销
  claimSourceType: 1,   // 1 = AI-generated, 0 = none, null = skip / 1 = 内容由AI生成
  expectImgs: 4,
})
```

## Layout / 目录

```
SKILL.md                      the agent reads this / Agent 读取的主文档
references/backend-api.md     endpoints, DOM selectors, verified gotchas / 接口、选择器与踩过的坑
references/content-rules.md   content rules and the full post-mortem / 内容规律与完整复盘
scripts/render-cards.mjs      image template A: warm cards, 8 layouts / 配图模板 A：暖色卡片
scripts/render-editorial.mjs  image template B: ink on paper, 6 layouts / 配图模板 B：纸墨社论
scripts/publish-draft.mjs     create one fully configured draft / 建一篇配置齐全的草稿
scripts/preflight.mjs         cadence gate + readiness check / 节奏闸门 + 齐备性核对
```

## Gotchas already paid for / 已经替你踩过的坑

Every one verified — details in [`references/backend-api.md`](references/backend-api.md).
全部实测过，细节见 [`references/backend-api.md`](references/backend-api.md)。

| EN | 中文 |
|---|---|
| `/cgi-bin/uploadimg2cdn` returns `200009` — use `filetransfer?action=upload_material&scene=8` | `uploadimg2cdn` 返回 `200009`，要改用 `filetransfer` 上传 |
| Setting the cover via API returns `ret: 0` but **does nothing**; only the UI path works | 用接口设封面返回 `ret: 0` 却**不生效**，只能走界面 |
| With no leading image, the importer attaches an AI cover **you can't override** | 正文没有首图时，导入会自动配一张 AI 封面，且**无法覆盖** |
| Markdown import sometimes **duplicates body images** — correct at import, wrong after save | Markdown 导入偶尔**把正文图插两遍**——导入时计数正常，存完才变多 |
| Drafts can vanish (`System error (320003)`) — re-count via the list API afterwards | 草稿会凭空消失（`320003`），建完要用列表接口再点一次数 |
| The backend may render in English — every selector needs both languages | 后台可能是英文界面，所有按钮匹配都要中英双语 |

## Caveats / 声明

- These are **observations of undocumented backend endpoints**, not an official API — WeChat can change them at any time.
  这些是**对后台内部接口的观察**，不是官方 API，微信随时可能改动。
- The content rules come from **one account, two months, about 55 posts**. Don't copy the numbers; the causal structure likely generalizes.
  内容规律来自**单个账号两个月约 55 篇**的实测。数字不必照搬，因果结构大概率通用。
- The publish click path itself is **unverified** and deliberately not automated.
  发表按钮的点击路径**未经验证**，也刻意没有自动化。
- This writes into your own account. **Try it on a test account first.**
  它会往你自己的账号里写内容，**请先在测试账号上跑一遍。**

## Changelog / 更新记录

**0.1.0**
- Initial release: review, image templates, draft creation, pre-publish gate. / 首次发布：复盘、配图模板、建草稿、发布前闸门。
- Fix: the frontmatter description contained an unquoted `: `, so YAML parsing failed and installers skipped the skill. / 修复：description 中未加引号的 `: ` 导致 YAML 解析失败，安装器会跳过该技能。
