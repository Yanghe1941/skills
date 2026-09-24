// 逐篇建图文草稿。只建草稿，**绝不发布**——发布见 SKILL.md 第 4 节。
//
//   const { publishDraft } = await import('<skill>/scripts/publish-draft.mjs')
//   await publishDraft(page, {
//     token,                  // 后台 URL 里的 ?token=
//     mdPath,                 // 本地 Markdown，第一张图会被设成封面
//     title, digest,
//     author: '你的笔名',
//     original: true,         // 是否声明原创
//     claimSourceType: 1,     // 创作来源；1 = 内容由AI生成，null = 不设置
//     expectImgs: 4,
//   })
//
// 自动完成：Markdown 导入 → 标题/作者/摘要 → 封面（从正文选择）→ 原创声明 → 创作来源 → 存草稿。
//
// 两件必须知道的事：
//   · 返回值是存完立刻读的，**不能当数**。草稿事后会凭空消失（320003），
//     导入器也可能把正文图插两遍。建完务必再跑 preflight.mjs 的 checkDrafts。
//   · 逐篇顺序调用，不要并发。

const sleep = (s) => new Promise(r => setTimeout(r, s * 1000));

async function centerOf(page, expr) {
  return page.evaluate(`(() => { const el = (${expr}); if (!el || !el.offsetParent) return null;
    el.scrollIntoView({ block:'center' });
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2) }; })()`);
}

// 弹窗按钮统一按坐标点：这些按钮常在视口外，选择器点击会落空
const DLG = `[...document.querySelectorAll('.weui-desktop-dialog')].filter(e=>e.offsetParent).pop()`;
const btnIn = (re) => `(() => { const d = ${DLG}; if (!d) return null;
  return [...d.querySelectorAll('button,a')].find(x => ${re}.test((x.innerText||'').trim())) || null; })()`;

export async function publishDraft(page, opt) {
  const { token, mdPath, title, digest, author,
    original = true, claimSourceType = null, expectImgs = 4 } = opt;
  const log = (m) => console.log(`   ${m}`);

  await page.goto(`https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&createType=0&token=${token}&lang=zh_CN`);
  await page.waitForLoadState();
  await sleep(6);

  // ── 正文：走公众号原生 Markdown 导入，不要自己拼 HTML
  await page.click('#js_import_file');
  await sleep(2.5);
  await page.setInputFiles('input[accept*="markdown"]', mdPath);
  await sleep(9);

  const imported = await page.evaluate(`(() => { const ed=[...document.querySelectorAll('[contenteditable="true"].ProseMirror')].find(e=>e.querySelectorAll('img').length);
    return ed ? [...ed.querySelectorAll('img')].filter(i=>/mmbiz/.test(i.src)).length : 0; })()`);
  if (imported !== expectImgs) throw new Error(`导入后图片数=${imported}，期望 ${expectImgs}`);

  // ── 标题/作者/摘要。导入会把标题设成文件名，必须在这之后覆盖
  await page.evaluate(`(() => {
    const set=(el,v)=>{ if(!el) return; const p = el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(p,'value').set.call(el,v);
      for (const t of ['input','change','blur']) el.dispatchEvent(new Event(t,{bubbles:true})); };
    set(document.querySelector('#title'), ${JSON.stringify(title)});
    set(document.querySelector('#author'), ${JSON.stringify(author)});
    set(document.querySelector('#js_description'), ${JSON.stringify(digest)});
  })()`);
  await sleep(1);

  await setCoverFromBody(page);
  log('封面 ✓');
  if (original) { await declareOriginal(page); log('原创 ✓'); }
  if (claimSourceType != null) { await setClaimSource(page, claimSourceType); log('创作来源 ✓'); }

  await page.click('#js_submit button');
  await sleep(9);
  const url = await page.url();
  const appmsgid = (url.match(/appmsgid=(\d+)/) || [])[1];
  if (!appmsgid) throw new Error('保存后没拿到 appmsgid: ' + url);

  await sleep(3);
  const v = await page.evaluate(`(() => {
    const ed=[...document.querySelectorAll('[contenteditable="true"].ProseMirror')].find(e=>e.querySelectorAll('img').length);
    const p=document.querySelector('.js_cover_preview_new');
    const oa=document.querySelector('.js_original_apply');
    return { title:(document.querySelector('#title')||{}).value, author:(document.querySelector('#author')||{}).value,
      digest:((document.querySelector('#js_description')||{}).value||'').length,
      imgs: ed?[...ed.querySelectorAll('img')].filter(i=>/mmbiz/.test(i.src)).length:0,
      chars: ed?ed.innerText.length:0,
      cover: p?/mmbiz/.test(String(getComputedStyle(p).backgroundImage)):false,
      original: !!(oa && oa.offsetParent === null),
      source: (document.querySelector('.js_claim_source_desc')||{}).innerText||'' }; })()`);
  return { appmsgid, ...v };
}

// ── 封面：只能走「从正文选择」。API 设封面返回 ret:0 但不生效，别再试
async function setCoverFromBody(page) {
  await page.evaluate(`document.querySelector('.js_cover_btn_area').scrollIntoView({block:'center'})`);
  await sleep(1);
  await page.click('.js_cover_btn_area');
  await sleep(2.5);

  const mi = await centerOf(page, `[...document.querySelectorAll('li,div,span')].filter(x=>x.offsetParent && /^(从正文选择|Choose from content)$/.test((x.innerText||'').trim()))[0]`);
  if (!mi) throw new Error('找不到「从正文选择」');
  await page.mouse.click(mi.x, mi.y);
  await sleep(4);

  // 图片要先 hover 再 click 才选得中，且两步都得轮询——单次点击经常不生效
  let card = null;
  for (let t = 0; t < 10 && !card; t++) {
    await sleep(1.2);
    card = await page.evaluate(`(() => { const d=${DLG}; if(!d) return null;
      const el=d.querySelectorAll('.appmsg_content_img.cover')[0]; if(!el) return null;
      const r=el.getBoundingClientRect();
      return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
  }
  if (!card) throw new Error('正文图片选择器没出现');

  const pick = async () => { await page.mouse.move(card.x, card.y); await sleep(0.8); await page.mouse.click(card.x, card.y); await sleep(1.2); };
  await pick();

  let nx = null;
  for (let t = 0; t < 8 && !nx; t++) {
    nx = await page.evaluate(`(() => { const b=${btnIn('/^(下一步|Next)$/')};
      if(!b || b.disabled || /disabled/.test(b.className)) return null;
      const r=b.getBoundingClientRect(); return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
    if (!nx) await pick();
  }
  if (!nx) throw new Error('首图选不中');
  await page.mouse.click(nx.x, nx.y);

  let ok = null;
  for (let t = 0; t < 10 && !ok; t++) {
    await sleep(1.5);
    ok = await page.evaluate(`(() => { const d=${DLG};
      if(!d || !/编辑封面|Edit Cover|Edit cover/.test(d.innerText||'')) return null;
      const b=${btnIn('/^(确认|Confirm|OK|Done)$/')}; if(!b) return null;
      b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect();
      return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
    if (ok) break;
    await pick();
    const again = await page.evaluate(`(() => { const d=${DLG};
      if(!d || /编辑封面|Edit Cover|Edit cover/.test(d.innerText||'')) return null;
      const b=${btnIn('/^(下一步|Next)$/')}; if(!b) return null;
      const r=b.getBoundingClientRect(); return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
    if (again) await page.mouse.click(again.x, again.y);
  }
  if (!ok) throw new Error('等不到「编辑封面」的确认按钮');

  for (let t = 0; t < 6; t++) {
    const b = await page.evaluate(`(() => { const b=${btnIn('/^(确认|Confirm|OK|Done)$/')}; if(!b) return null;
      b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect();
      return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
    if (!b) break;
    await sleep(1.2);
    await page.mouse.click(b.x, b.y);
    await sleep(3);
  }
  const set = await page.evaluate(`(() => { const p=document.querySelector('.js_cover_preview_new');
    return p ? /mmbiz/.test(String(getComputedStyle(p).backgroundImage)) : false; })()`);
  if (!set) throw new Error('封面未设置成功');
}

// ── 声明原创。随文章发表后不可撤销，但草稿阶段可反复改
async function declareOriginal(page) {
  const done = async () => page.evaluate(`(() => { const e=document.querySelector('.js_original_apply'); return !!e && e.offsetParent===null; })()`);
  if (await done()) return;

  const entry = await centerOf(page, `document.querySelector('.js_original_apply')`);
  if (!entry) throw new Error('找不到原创声明入口');
  await sleep(0.8);
  await page.mouse.click(entry.x, entry.y);
  await sleep(3);

  // 不勾底部那个同意框，Confirm 点了没反应
  const checked = await page.evaluate(`(() => { const d=${DLG}; if(!d) return false;
    const cs=[...d.querySelectorAll('input[type=checkbox]')].filter(c=>c.offsetParent||c.parentElement);
    const c=cs[cs.length-1]; if(!c) return false;
    if(!c.checked){ c.scrollIntoView({block:'center'}); c.click(); }
    return c.checked; })()`);
  if (!checked) throw new Error('原创弹窗：同意复选框没勾上');
  await sleep(1);

  for (let t = 0; t < 5 && !(await done()); t++) {
    const b = await page.evaluate(`(() => { const b=${btnIn('/^(确认|确定|Confirm|OK|Done)$/')}; if(!b) return null;
      b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect();
      return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
    if (!b) break;
    await sleep(1);
    await page.mouse.click(b.x, b.y);
    await sleep(2.5);
  }
  if (!(await done())) throw new Error('原创声明没生效');
}

// ── 创作来源。type=1 是「内容由AI生成」，按 radio 的 value 选，不要匹配文案（后台可能是英文）
async function setClaimSource(page, type) {
  const entry = await centerOf(page, `document.querySelector('.js_claim_source_desc')`);
  if (!entry) throw new Error('找不到创作来源入口');
  await sleep(0.8);
  await page.mouse.click(entry.x, entry.y);
  await sleep(3);

  const picked = await page.evaluate(`(() => { const d=${DLG}; if(!d) return false;
    const r=d.querySelector('input[type=radio][value="${type}"]'); if(!r) return false;
    if(!r.checked){ r.scrollIntoView({block:'center'}); r.click(); }
    return r.checked; })()`);
  if (!picked) throw new Error('创作来源：选不中 type=' + type);
  await sleep(1);

  for (let t = 0; t < 5; t++) {
    const b = await page.evaluate(`(() => { const b=${btnIn('/^(确认|确定|Confirm|OK|Done)$/')}; if(!b) return null;
      b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect();
      return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; })()`);
    if (!b) break;
    await sleep(1);
    await page.mouse.click(b.x, b.y);
    await sleep(2.5);
  }
}
