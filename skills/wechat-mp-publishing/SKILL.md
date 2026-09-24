---
name: wechat-mp-publishing
description: Automate the WeChat Official Account pipeline: pull backend stats for review, render article images locally, create rich-text drafts in bulk (cover, original-content declaration and creation-source set automatically), then run a cadence gate and readiness check before publishing. Use when asked to analyse account data, write or illustrate a post, upload drafts to the backend, or get ready to publish. It never presses Publish — that stays with the user. 微信公众号内容流水线：拉后台数据复盘、本地渲染配图、批量建图文草稿、发布前做节奏与齐备性检查；发表按钮始终由用户自己点。
---

# 微信公众号内容生产与投放

覆盖四件事：**拉数据复盘 → 写稿配图 → 建草稿 → 发布前检查**。四步可独立使用。
最后一步只做检查和把关，**发表按钮始终由用户自己点**。

浏览器自动化用 [ego-browser](https://github.com/citrolabs/ego-lite)（Chromium，复用用户已登录的会话）。
所有后台请求都要**在页面内 `fetch`**——Node 侧没有 cookie。

## ⚠️ 先读这一条：批量生产会把账号做死

实测事故：连续日更 23 篇高度同构的文章后，账号被平台判定 **「低创作度内容」**
（账号成长 → 账号检测），**推荐流量直接归零**——断崖后连续多日每篇 4–5 阅读，
昨日阅读同比上周 **−94%**，粉丝净减。

**单篇质量高 ≠ 安全。** 那 23 篇每篇都有真实细节和具体数字，平台判的是**账号级模式**：
母题、结构、配图模板、CTA、发布节奏全都一样。

更要命的后续：判定解除后，把内容类型、读者视角、配图风格、CTA 全部换掉重写，
阅读反而更低（1 / 4 / 4）。**推荐归零时，内容是无效变量。**

完整的约束表、事故经过和恢复策略见 `references/content-rules.md`，**动手写稿之前先读**。

调用这个 skill 之前先问一句：**这次发布的目标是什么？**
如果答案是「拉新」，先把账号的开封率（单篇阅读 ÷ 粉丝数）算出来摆给用户看。

## 0. 配置与登录

这个 skill 不硬编码任何账号信息。开工前先和用户确认：

| 项 | 说明 |
|---|---|
| `author` | 文章署名 |
| `original` | 是否声明原创（默认 true）。**随文章发表后不可撤销**，草稿阶段可反复改 |
| `claimSourceType` | 创作来源。`1` = 内容由AI生成，`0` = 无需声明，`null` = 不设置 |
| `brand` | 配图左下角署名，省略则不画 |

ego-browser 里的公众号会话经常过期（提示「登录超时」）。此时 `handOff()` 让用户扫码，
等用户确认后再 `takeOverTaskSpace()` 继续。**不要自己反复重试。**

登录后从任一后台页取凭证：

```js
const { ticket, user_name, time } = await page.evaluate(() => window.wx.data)
const token = (await page.url()).match(/token=(\d+)/)[1]
```

## 1. 拉阅读数据

**用 `appmsgpublish`，不要用 `appmsganalysis`**（后者返回 `total_num: 0`）：

```
GET /cgi-bin/appmsgpublish?sub=list&begin=0&count=20&token=<token>&lang=zh_CN&f=json&ajax=1
```

`publish_page` 是 JSON 字符串要二次 parse；每条 `publish_info` 再 parse，
`appmsg_info[]` 内含 `read_num / like_num / share_num / comment_num`，
`sent_info.time` 是秒级时间戳。

**复盘按分享率排序，不看阅读量。** 平台推荐能把单篇灌到两千阅读而分享率只有 0.17%，
那是不可复制的。详见 `references/content-rules.md`。

## 2. 写稿与配图

**配图 1+3**：每篇 1 封面 + 3 正文图。本地渲染 HTML 再截图。
**两套模板轮换用，不要连续几批都用同一套**——配图模板一致是同质化判定的要素之一：

| 脚本 | 风格 | 版式 |
|---|---|---|
| `scripts/render-cards.mjs` | 暖色卡片，圆角+渐变 | cover / quote / steps / rows / compare / stat / term / shot |
| `scripts/render-editorial.mjs` | 纸墨社论，米纸底+近黑墨+赭红，宋体标题，细线无渐变 | cover / table / cols / list / big / tree |

两套的 `html(spec, W, H)` 签名一致，可直接替换。每个 spec 可带 `brand` 字符串署名：

```js
const { html } = await import('<skill>/scripts/render-editorial.mjs')
await page.goto('data:text/html;charset=utf-8,' + encodeURIComponent(html(spec, W, H)))
await page.cdp('Emulation.setDeviceMetricsOverride',
  { width: W, height: H, deviceScaleFactor: 2, mobile: false })
const shot = await page.cdp('Page.captureScreenshot', { format: 'jpeg', quality: 92 })
fs.writeFileSync(out, Buffer.from(shot.data, 'base64'))
```

尺寸：封面 **900×383**（2.35:1），正文图 **1080×608**。中文字体用 PingFang SC / Songti SC。

**渲染完逐张肉眼抽查。** 文字溢出、重叠、样式没生效，只有看图才发现得了——
实测踩过：内联 `style="..."` 里的字体栈带双引号会把属性提前截断，整条样式静默失效。

稿件用 Markdown 写，正文留三个插图位。

## 3. 建草稿

```js
const { publishDraft } = await import('<skill>/scripts/publish-draft.mjs')
const r = await publishDraft(page, {
  token, mdPath, title, digest,
  author: '<用户的笔名>', original: true, claimSourceType: 1, expectImgs: 4,
})
// → { appmsgid, title, author, digest, imgs, chars, cover, original, source }
```

一篇一篇顺序调用，不要并发。要点：

- 图片上传用 `/cgi-bin/filetransfer?action=upload_material&scene=8`，
  **必须在页面内 `fetch`**（Node 侧没 cookie）
- 正文用公众号原生的 **Markdown 文档导入**（`#js_import_file`），
  H2 和图片会自动排版，**不要自己拼 HTML**
- md 里图片写 `![](<素材库 cdn_url>)`，**封面图必须是正文第一张**——
  否则导入会自动配一张 AI 生成的封面，而且接口覆盖不掉
- 封面靠「从正文选择」设置，**hover 后再 click**，且必须轮询重试
- **后台 UI 可能是英文的**（取决于登录时的 lang）。按钮匹配都要中英双语，脚本里已处理

完整接口、DOM 选择器和十几个坑见 `references/backend-api.md`。

## 4. 发布

**这一步不要自己点。** 发表不可逆：原创声明随发表永久生效、群发额度每天有限、
发出去删不掉（平台明确说过**删文不算优化项的修复**）。

```js
const { cadenceCheck, checkDrafts, fmtCadence, fmtDrafts } =
  await import('<skill>/scripts/preflight.mjs')
console.log(fmtCadence(await cadenceCheck(page, { token })))
console.log(fmtDrafts(await checkDrafts(page, {
  token, appmsgids: ['...'], expectAuthor: '<笔名>', expectSource: 'AI',
})))
```

1. **节奏闸门** `cadenceCheck` —— 默认 7 天最多 2 篇、两篇间隔至少 3 天。
   命中 blocker 就停下来**把原话告诉用户**，不要自己判断「这次情况特殊可以发」。
2. **逐篇核对** `checkDrafts` —— 查封面 / 原创 / 作者 / 创作来源 / 图片数 /
   **重复图** / 摘要长度。`publishDraft` 的返回值是存完立刻读的，**不能当数**。
3. **一次性汇报**：哪几篇就绪、建议哪天发哪篇、为什么。
4. 用户自己点发表。

**不要逐篇问「可以发了吗」。** 先完成全部草稿与检查，再一次性确认。

### 发布入口（⚠️ 未验证）

这套流程我没跑过，下面只是后台菜单位置，**不是验证过的点击路径**：

- 草稿箱 → 选中某篇 → 「发表」（群发给粉丝，订阅号每天 1 次）
- 「定时发表」可设未来时间

要写自动化，必须先人工走一遍、把真实 DOM 记进 `references/backend-api.md` 再动手。
**不要照着猜的选择器写发布脚本。**

### 发完之后

- **7 天内才能助推**，「仅 7 天内发表且符合规范的内容可助推」，过期作废——
  发完立刻去「账号成长 → 内容助推」看 `Available Impressions`，有额度就推
- 后台会自动生成**贴图草稿**（发布后优先推给非粉丝），很多人从没用过
- 隔几天回来跑一次 `cadenceCheck`，它顺带给出 30 天均阅读

## 边界

- **发表 / 群发 / 定时发表：绝不代点。** 不可逆，原创声明发表后不可撤销
- 建草稿是往用户账号里写内容：可以批量做，做完一次性汇报，
  不要逐篇要用户回「继续」
- 用户说「逐篇」就一篇一篇顺序做，不要在一个草稿里塞多图文
- 清理掉自己产生的测试草稿和测试素材
