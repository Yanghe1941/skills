# 公众号后台接口与踩坑

所有请求都要**在页面内 `fetch`（`credentials:'include'`）**，Node 侧的 `serverFetch` 没有 cookie。

## 凭证

编辑页 `window.wx.data` → `{ ticket, user_name, uin, time }`；`token` 从 URL 的 `?token=` 取。
`fingerprint` 可复用页面自带的值，不是必需。

## 取发布数据

```
GET /cgi-bin/appmsgpublish?sub=list&begin=<n>&count=20&token=&lang=zh_CN&f=json&ajax=1
```
`publish_page` → JSON.parse → `publish_list[].publish_info` → JSON.parse → `appmsg_info[]`
字段：`title / read_num / like_num / share_num / comment_num / content_url / copyright_type`
时间：`sent_info.time`（秒级时间戳）

`/misc/appmsganalysis?action=all&...` 返回 `total_num: 0`，**不可用**。

## 素材库

**上传**（返回 `content` = file_id，`cdn_url` = 可直接用在正文的地址）：
```
POST /cgi-bin/filetransfer?action=upload_material&f=json&scene=8&writetype=doublewrite
     &groupid=1&ticket_id=<user_name>&ticket=<ticket>&svr_time=<time>&token=<token>&lang=zh_CN
FormData: type=image/jpeg, id=WU_FILE_0, name, lastModifiedDate, size, file=<Blob>
```
Node 读文件 → base64 → 注入到 `js()` 里 `atob` 还原成 Uint8Array → Blob。单张 ~110KB base64 没问题。

`/cgi-bin/uploadimg2cdn` 返回 `ret: 200009 not found`，**不可用**。

**列表**：`GET /cgi-bin/filepage?begin=0&count=8&type=2&token=&lang=zh_CN&f=json&ajax=1`
→ `page_info.file_item[]`，含 `file_id / name / cdn_url`

**删除**：`POST /cgi-bin/modifyfile?t=ajax-response&token=&lang=zh_CN`，body `oper=del&fileid=<id>`

## 草稿

**删除**：`POST /cgi-bin/operate_appmsg?t=ajax-response&sub=del&type=77&token=&lang=zh_CN`，body 含 `AppMsgId=<id>`

**列表**：`GET /cgi-bin/appmsg?begin=0&count=30&type=77&action=list&token=&lang=zh_CN&f=json&ajax=1`
→ `app_msg_info.item[].multi_item[0].title`。分页每页 7 条左右，`count` 不完全生效，要翻 `begin`。

**创建/更新走 UI，不要走 API。** `POST /cgi-bin/operate_appmsg?sub=update` 设封面（`fileid0` / `cdn_url0`）返回 `ret: 0` 但封面不生效，响应里带 `cover_check_info: {err_format:"2.35:1"}`。这条路已验证走不通。

## 编辑器 DOM

| 元素 | 选择器 |
|---|---|
| 标题 | `#title`（textarea） |
| 作者 | `#author` |
| 摘要 | `#js_description` |
| 文档导入 | `#js_import_file` → `input[accept*="markdown"]` |
| 正文 | `[contenteditable="true"].ProseMirror`（取有 img 的那个） |
| 封面区 | `.js_cover_btn_area` |
| 保存为草稿 | `#js_submit button` |

新建编辑页：
```
/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&createType=0&token=&lang=zh_CN
```
保存后 URL 变成 `...&appmsgid=<新ID>...`，从这里取 ID。

## 坑

- **设 input 值**必须用 `Object.getOwnPropertyDescriptor(proto,'value').set.call(el, v)` 再派发 `input`/`change`/`blur`；直接赋 `.value` 前端不认
- **文档导入会把标题设成文件名**，导入后要覆盖 `#title`
- **正文无首图时导入会自动配 AI 封面**，且接口覆盖不掉。放首图即可避免
- **Markdown 导入偶尔会把正文图片插两遍**（2026-09-15 实测，7 篇里中 1 篇）。特征很明确：
  正常图片的父节点是 `SECTION`，多出来的那份父节点是 `SPAN`，两份都可见、都是真图。
  导入那一刻计数还是对的，**存完再读才变多**，所以「导入后校验图片数」拦不住它。
  和 blockquote、代码块都无关——同样带这两种语法的其他篇没事，别往那边查。
  处理办法是存草稿后重新加载编辑页，按下面这条规则去重再存一次（已验证能持久化）：

  ```js
  // 同一张图既在 SECTION 又在 SPAN 里 → 删掉 SPAN 那份。
  // 只出现在 SPAN 里的不能删（正常图也可能是 SPAN）。
  const key = s => (s.match(/mmbiz[^/]*\/([^/]{20,})\//) || [])[1]?.slice(-16)
  const imgs = [...ed.querySelectorAll('img')].filter(i => key(i.src) && i.offsetParent)
  const inSection = new Set(imgs.filter(i => i.parentElement.tagName === 'SECTION').map(i => key(i.src)))
  for (const i of imgs)
    if (i.parentElement.tagName === 'SPAN' && inSection.has(key(i.src)))
      (i.parentElement.childElementCount === 1 && !i.parentElement.textContent.trim()
        ? i.parentElement : i).remove()
  ```

- **草稿可能凭空消失**：2026-09-15 建的 7 篇里，最早建的两篇过一阵再开就是
  `System error (320003)`，草稿列表里也没有。原因不明，重建即可。
  **所以全部建完之后要用草稿列表 API 点一次数**，别只信 `publishOne` 的返回值——
  它是存完立刻读的，那时候草稿还在。

- **封面选择器（从图片库选择）的搜索框和翻页输入框对 `fillInput`/`pressKey` 完全不响应**，别在这上面浪费时间，走「从正文选择」
- **「从正文选择」的图片要先 hover 再 click** 才选得中；「下一步」和「确认」两步都需要轮询重试，单次点击经常不生效
- **「确认」按钮在弹窗下方视口外**，要先 `scrollIntoView({block:'center'})` 再按坐标点
- 页面有多个 iframe，`document.querySelector('iframe')` 抓到的是脚本 iframe 不是编辑器
- `cliLog` 里对 `js()` 结果 slice 太短会把正常数据误判成缺失

## 原创声明 + 创作来源（已在编辑页验证）

> 这两步已由 `scripts/publish-draft.mjs` 的 `declareOriginal()` / `setClaimSource()` 自动化。
> 下面是它们依赖的点击路径，改脚本前先读。

两个入口都在右侧设置区，**必须先 `scrollIntoView` 再取坐标点击**——用滚动前的旧坐标会点空，这是最容易浪费时间的坑。

### 声明原创

1. `.js_original_apply`（未声明时可见；已声明后它会被隐藏，改由 `.js_original_title` 可见）
2. 弹窗里 Declaration type 默认已选「Text Originality」，Author 已是编辑页填的作者
3. **必须勾底部的「我已阅读并同意…」复选框**（`input[type=checkbox].weui-desktop-form__checkbox`，是弹窗里最后一个）。不勾的话 Confirm 点了没反应
4. Confirm

判断是否成功：`.js_original_apply` 变为 `offsetParent === null`，行文案变成
`Text Originality · Author: <你的作者名> · Quick repost enabled`

### 创作来源

1. 设置区最后一组里的 `.js_claim_source_desc`（显示「未添加 / Not added」那块）
2. 弹窗标题「创作来源 / Creation Source」，Declaration type 是一组 radio：

   | value | 含义 |
   |---|---|
   | **1** | **内容由AI生成** |
   | 2 | 素材来源官方媒体/网络新闻 |
   | 3 | 内容剧情演绎，仅供娱乐 |
   | 4 | 个人观点，仅供参考 |
   | 5 | 健康医疗分享，仅供参考 |
   | 6 | 投资观点，仅供参考 |
   | 0 | 无需声明 |

   radio 的 `value` 就是 `claim_source_type`，和 `user_info.claim_source_list` 里的 type 一致。
   选中判断用 `input[type=radio][value="1"].checked`，别匹配文案（后台可能是英文界面）。
3. Confirm（按钮在弹窗下方视口外，同样要先 `scrollIntoView`）

### 备注

- 这两项都是草稿级设置，存草稿阶段可以反复改
- **原创声明随文章发表后不可撤销**，所以发表这一步始终留给用户

## 自动回复：两条路都堵（2026-09-06 实测）

**关键词自动回复**：总开关 `label.weui-desktop-switch` 常驻 `weui-desktop-switch_loading` 类，点击无响应，试了 3 次都打不开。`action=keywords` 直接进 URL 返回空页面。这个功能在实测的那个账号上用不了（可能与账号类型/权限有关），**别把「后台回复关键词领取」写进文章 CTA**。

**关注后自动回复**：开关是开的、`Edit Reply` 能打开编辑器，但编辑器是 **ProseMirror**，程序化改内容不可靠：
- `Cmd+A` 选不全（只选中当前段落块）
- `cdp('Input.insertText')` 的插入位置会错乱，`\n` 不产生换行
- `Cmd+Z` 撤销无效

结论：**这个编辑器只能人工改**。如果试坏了，**不要点 Save**，直接重新 `gotoAndWait` 加载页面丢弃即可，后台配置不受影响（已验证）。

CTA 因此应设计成**不依赖自动回复**的形式，比如「留言区索取」。
