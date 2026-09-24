// 发布前检查。**只读**，不点任何发布按钮。
//
//   const { cadenceCheck, checkDrafts } = await import('<skill>/scripts/preflight.mjs')
//   console.log(fmtCadence(await cadenceCheck(page, { token })))
//   console.log(fmtDrafts(await checkDrafts(page, { token })))
//
// 两件事：
//   1. cadenceCheck —— 节奏闸门。账号 2026-09 被判过「低创作度内容」，
//      「频繁发布」是判定要素，所以发之前必须先看最近发了多少。
//   2. checkDrafts  —— 逐篇核对草稿是否齐备（封面/原创/作者/创作来源/图片数/重复图）。
//      `publishOne` 的返回值是存完立刻读的，不能当数；草稿还会凭空消失（320003）。

const sleep = (s) => new Promise(r => setTimeout(r, s * 1000));

// ── 节奏闸门 ──────────────────────────────────────────────
// 阈值来自 2026-09-06 那次判定的实际教训，不是拍脑袋：
//   日更 23 篇 → 推荐归零。判定解除后继续日更（09-14/15/16），阅读 1/4/4。
export const CADENCE = { maxPer7Days: 2, minGapDays: 3 };

export async function cadenceCheck(page, { token }) {
  await page.goto(`https://mp.weixin.qq.com/cgi-bin/home?t=home/index&lang=zh_CN&token=${token}`);
  await page.waitForLoadState();
  const rows = await page.evaluate(`(async () => {
    const out = [];
    for (let begin = 0; begin < 60; begin += 20) {
      const r = await fetch('/cgi-bin/appmsgpublish?sub=list&begin='+begin+'&count=20&token=${token}&lang=zh_CN&f=json&ajax=1', {credentials:'include'});
      const j = await r.json();
      let pp; try { pp = JSON.parse(j.publish_page); } catch(e) { break; }
      const list = pp.publish_list || [];
      if (!list.length) break;
      for (const it of list) {
        let pi; try { pi = JSON.parse(it.publish_info); } catch(e) { continue; }
        for (const a of (pi.appmsg_info || []))
          out.push({ t: pi.sent_info?.time, title: a.title, read: a.read_num, share: a.share_num });
      }
      if (list.length < 20) break;
    }
    return out; })()`);

  const now = Date.now() / 1000;
  const valid = rows.filter(r => r.t > 1_700_000_000).sort((a, b) => b.t - a.t);
  const last = valid[0];
  const gapDays = last ? (now - last.t) / 86400 : Infinity;
  const in7 = valid.filter(r => now - r.t < 7 * 86400);
  const in30 = valid.filter(r => now - r.t < 30 * 86400);
  const avgRead = in30.length ? in30.reduce((s, r) => s + (r.read || 0), 0) / in30.length : 0;

  const blockers = [];
  if (gapDays < CADENCE.minGapDays)
    blockers.push(`距上次发表只有 ${gapDays.toFixed(1)} 天（下限 ${CADENCE.minGapDays} 天）`);
  if (in7.length >= CADENCE.maxPer7Days)
    blockers.push(`最近 7 天已发 ${in7.length} 篇（上限 ${CADENCE.maxPer7Days} 篇）`);

  return { last, gapDays, in7: in7.length, in30: in30.length, avgRead, blockers, recent: valid.slice(0, 10) };
}

// ── 草稿核对 ──────────────────────────────────────────────
const PROBE = `(() => {
  const ed=[...document.querySelectorAll('[contenteditable="true"].ProseMirror')].find(e=>e.querySelectorAll('img').length);
  if(!ed) return null;
  const key=s=>(s.match(/mmbiz[^/]*\\/([^/]{20,})\\//)||[])[1]?.slice(-16);
  const imgs=[...ed.querySelectorAll('img')].filter(i=>key(i.src)&&i.offsetParent);
  const keys=imgs.map(i=>key(i.src));
  const dup=keys.filter((k,i)=>keys.indexOf(k)!==i);
  const p=document.querySelector('.js_cover_preview_new'), oa=document.querySelector('.js_original_apply');
  return {
    title:(document.querySelector('#title')||{}).value||'',
    author:(document.querySelector('#author')||{}).value||'',
    digest:((document.querySelector('#js_description')||{}).value||''),
    imgs: imgs.length, uniqueImgs: new Set(keys).size, dupImgs: [...new Set(dup)].length,
    chars: ed.innerText.length,
    cover: p?/mmbiz/.test(String(getComputedStyle(p).backgroundImage)):false,
    original: !!(oa && oa.offsetParent===null),
    source: ((document.querySelector('.js_claim_source_desc')||{}).innerText||'').split('\\n')[0]
  }; })()`;

export async function checkDrafts(page, { token, appmsgids, expectImgs = 4,
  expectAuthor = null, expectSource = null }) {
  const out = [];
  for (const id of appmsgids) {
    await page.goto(`https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=0&type=77&appmsgid=${id}&token=${token}&lang=zh_CN`);
    await page.waitForLoadState();
    let v = null;
    for (let t = 0; t < 8 && !v; t++) { await sleep(3.5); v = await page.evaluate(PROBE); }
    if (!v) { out.push({ id, gone: true, problems: ['打不开（可能已被平台清掉，见 320003）'] }); continue; }

    const problems = [];
    if (!v.cover) problems.push('没有封面');
    if (!v.original) problems.push('没有声明原创');
    if (expectAuthor && v.author !== expectAuthor) problems.push(`作者是「${v.author}」，应为 ${expectAuthor}`);
    if (expectSource && !v.source.includes(expectSource)) problems.push(`创作来源是「${v.source}」，应为 ${expectSource}`);
    if (v.imgs !== expectImgs) problems.push(`图片 ${v.imgs} 张，期望 ${expectImgs}`);
    if (v.dupImgs) problems.push(`有 ${v.dupImgs} 张图重复（导入器的老毛病，见 wechat-backend.md）`);
    if (!v.title.trim()) problems.push('标题为空');
    if (!v.digest.trim()) problems.push('摘要为空');
    else if (v.digest.length > 120) problems.push(`摘要 ${v.digest.length} 字，上限 120`);
    out.push({ id, ...v, problems });
  }
  return out;
}

export const fmtCadence = (c) => [
  `最近 7 天 ${c.in7} 篇 / 30 天 ${c.in30} 篇 / 30 天均阅读 ${c.avgRead.toFixed(0)}`,
  c.last ? `上次发表：${new Date(c.last.t*1000).toISOString().slice(0,10)}「${c.last.title}」，距今 ${c.gapDays.toFixed(1)} 天` : '没有发表记录',
  c.blockers.length ? '⛔ ' + c.blockers.join('；') + ' —— 先别发，把这条告诉用户' : '✓ 节奏没问题',
].join('\n');

export const fmtDrafts = (rows) => rows.map(r =>
  r.problems.length
    ? `✗ ${r.id} ${r.title || ''}\n    ` + r.problems.join('\n    ')
    : `✓ ${r.id} ${r.title}  图${r.imgs} 正文${r.chars}字 摘要${r.digest.length}字`
).join('\n');
