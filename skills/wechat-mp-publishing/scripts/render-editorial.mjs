// 公众号配图模板库 · 第二套：纸墨社论风。
// 与 render-images.mjs（金-米卡片风）刻意区分——同一个号连续用同一套配图模板，
// 是平台判定「同质化」的要素之一。两套轮换使用。
//
// 用法同 render-images.mjs：
//   const { html } = await import('<skill>/scripts/render-editorial.mjs')
//   await gotoAndWait('data:text/html;charset=utf-8,' + encodeURIComponent(html(spec, W, H)))
//
// 尺寸：封面 900x383（2.35:1），正文图 1080x608。
//
// spec 形状：
// 每个 spec 都可带 `brand`（字符串）在左下角署名，省略则不画。
//
//   { t:'cover', tag, title, sub, no }                    社论头版，no 是右下角期号
//   { t:'table', label, head:[...], rows:[[...],...], foot }  账目表，末列自动高亮
//   { t:'cols',  label, items:[[标题,说明],...] }            2-4 列并置
//   { t:'list',  label, title, items:[[标记,正文],...], foot } 清单/步骤
//   { t:'big',   label, big, sub, foot }                   大字公式或金句
//   { t:'tree',  label, title, lines:[[缩进层级,文字],...], foot } 层级树
//
// title/big/说明 支持 \n。渲染完务必逐张 Read 抽查。

const P = {
  paper:'#F4F1EA', ink:'#16181A', sec:'#575C63', ter:'#8B9097',
  red:'#B4462F', rule:'#CFC8B8', faint:'#E6E1D5'
};
const SERIF = "'Songti SC','STSong','Source Han Serif SC',serif";
const SANS  = "'PingFang SC','Hiragino Sans GB',sans-serif";

const base = (W,H) => `<meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:${W}px;height:${H}px;overflow:hidden}
body{background:${P.paper};font-family:${SANS};color:${P.ink};
-webkit-font-smoothing:antialiased;position:relative}
.wrap{height:100%;padding:48px 60px;display:flex;flex-direction:column;position:relative}
.lab{font-family:${SANS};font-size:20px;font-weight:600;color:${P.red};letter-spacing:4px;
padding-bottom:14px;border-bottom:2px solid ${P.ink};margin-bottom:30px;display:flex;
justify-content:space-between;align-items:flex-end}
.lab b{font-family:${SANS};font-size:17px;font-weight:500;color:${P.ter};letter-spacing:1px}
.brand{position:absolute;left:60px;bottom:26px;font-size:17px;color:${P.ter};letter-spacing:1px}
.serif{font-family:${SERIF}}
</style>`;

const brandOf = (n) => n ? `<div class="brand">${esc(n)}</div>` : "";
const esc = s => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const nl  = s => esc(s).replace(/\n/g,'<br>');

export function html(sp, W, H){

  if (sp.t === 'cover') return base(W,H) + `
<div class="wrap" style="padding:40px 58px 52px;justify-content:center">
  <div style="display:flex;align-items:center;gap:14px;margin-bottom:18px">
    <span style="width:30px;height:3px;background:${P.red}"></span>
    <span style="font-size:19px;font-weight:600;color:${P.red};letter-spacing:4px">${esc(sp.tag)}</span>
  </div>
  <div class="serif" style="font-size:${String(sp.title).replace(/\n/g,'').length>18?42:48}px;font-weight:700;
  line-height:1.32;letter-spacing:1px">${nl(sp.title)}</div>
  <div style="height:1px;background:${P.rule};margin:22px 0 16px"></div>
  <div style="font-size:20px;color:${P.sec};line-height:1.6">${nl(sp.sub)}</div>
</div>
<div class="serif" style="position:absolute;right:52px;bottom:34px;font-size:64px;font-weight:700;
color:${P.faint};line-height:1">${esc(sp.no ?? '')}</div>` + brandOf(sp.brand);

  if (sp.t === 'table') return base(W,H) + `
<div class="wrap">
  <div class="lab">${esc(sp.label)}${sp.note?`<b>${esc(sp.note)}</b>`:''}</div>
  <table style="width:100%;border-collapse:collapse;font-size:25px">
    <tr>${sp.head.map((h,i)=>`<th style="text-align:${i===0?'left':'right'};padding:0 0 12px;
    font-size:19px;font-weight:600;color:${P.ter};letter-spacing:1px">${esc(h)}</th>`).join('')}</tr>
    ${sp.rows.map(r=>`<tr>${r.map((c,i)=>`<td style="text-align:${i===0?'left':'right'};
    padding:17px 0;border-top:1px solid ${P.rule};
    ${i===0?`font-weight:600;`:''}
    ${i===r.length-1?`font-family:${SERIF};font-size:31px;font-weight:700;color:${P.red}`:`color:${i===0?P.ink:P.sec}`}
    ">${nl(c)}</td>`).join('')}</tr>`).join('')}
  </table>
  ${sp.foot?`<div style="margin-top:auto;padding-top:20px;font-size:21px;color:${P.sec};
  line-height:1.6;border-top:2px solid ${P.ink};padding-bottom:14px">${nl(sp.foot)}</div>`:''}
</div>` + brandOf(sp.brand);

  if (sp.t === 'cols'){
    const n = sp.items.length;
    return base(W,H) + `
<div class="wrap">
  <div class="lab">${esc(sp.label)}${sp.note?`<b>${esc(sp.note)}</b>`:''}</div>
  <div style="margin:auto 0;display:grid;grid-template-columns:repeat(${n},1fr);gap:0;padding-bottom:34px">
  ${sp.items.map(([t,d],i)=>`
    <div style="padding:6px ${i===n-1?0:34}px 6px ${i===0?0:34}px;
    ${i<n-1?`border-right:1px solid ${P.rule}`:''}">
      <div class="serif" style="font-size:56px;font-weight:700;color:${P.faint};line-height:1;
      margin-bottom:14px">${i+1}</div>
      <div class="serif" style="font-size:${n>=3?30:34}px;font-weight:700;line-height:1.3;
      margin-bottom:14px">${nl(t)}</div>
      <div style="font-size:${n>=3?20:22}px;color:${P.sec};line-height:1.62">${nl(d)}</div>
    </div>`).join('')}
  </div>
</div>` + brandOf(sp.brand);
  }

  if (sp.t === 'list') return base(W,H) + `
<div class="wrap">
  <div class="lab">${esc(sp.label)}${sp.note?`<b>${esc(sp.note)}</b>`:''}</div>
  ${sp.title?`<div class="serif" style="font-size:34px;font-weight:700;margin-bottom:24px;
  line-height:1.35">${nl(sp.title)}</div>`:''}
  <div style="display:flex;flex-direction:column;gap:${sp.items.length>3?16:22}px;flex:1;
  ${sp.title?'':'justify-content:center;'}padding-bottom:30px">
  ${sp.items.map(([m,txt])=>`
    <div style="display:flex;gap:20px;align-items:flex-start">
      <div class="serif" style="min-width:42px;font-size:27px;font-weight:700;color:${P.red};
      line-height:1.45">${esc(m)}</div>
      <div style="font-size:${sp.items.length>3?24:27}px;line-height:1.5;flex:1">${nl(txt)}</div>
    </div>`).join('')}
  </div>
  ${sp.foot?`<div style="font-size:21px;color:${P.sec};line-height:1.6;border-top:1px solid ${P.rule};
  padding:18px 0 14px">${nl(sp.foot)}</div>`:''}
</div>` + brandOf(sp.brand);

  if (sp.t === 'big') return base(W,H) + `
<div class="wrap">
  <div class="lab">${esc(sp.label)}</div>
  <div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding-bottom:34px">
    <div class="serif" style="font-size:${String(sp.big).replace(/\n/g,'').length>20?44:58}px;
    font-weight:700;line-height:1.4;letter-spacing:1px">${nl(sp.big)}</div>
    ${sp.sub?`<div style="font-size:26px;color:${P.red};margin-top:22px;font-weight:600;
    line-height:1.5">${nl(sp.sub)}</div>`:''}
    ${sp.foot?`<div style="font-size:22px;color:${P.sec};margin-top:26px;line-height:1.62;
    max-width:880px;border-top:1px solid ${P.rule};padding-top:22px">${nl(sp.foot)}</div>`:''}
  </div>
</div>` + brandOf(sp.brand);

  if (sp.t === 'tree') return base(W,H) + `
<div class="wrap">
  <div class="lab">${esc(sp.label)}${sp.note?`<b>${esc(sp.note)}</b>`:''}</div>
  ${sp.title?`<div class="serif" style="font-size:32px;font-weight:700;margin-bottom:22px">${nl(sp.title)}</div>`:''}
  <div style="flex:1;padding-bottom:30px">
  ${sp.lines.map(([lv,txt,hi])=>`
    <div style="display:flex;align-items:center;height:${sp.lines.length>6?52:60}px;
    padding-left:${lv*46}px">
      ${lv>0?`<span style="width:26px;height:1px;background:${P.rule};margin-right:14px"></span>`:''}
      <span style="font-size:${hi?28:25}px;${hi?`font-weight:700;color:${P.red}`:`color:${lv===0?P.ink:P.sec}`};
      ${lv===0?'font-weight:600':''}">${esc(txt)}</span>
    </div>`).join('')}
  </div>
  ${sp.foot?`<div style="font-size:21px;color:${P.sec};line-height:1.6;border-top:2px solid ${P.ink};
  padding:18px 0 14px">${nl(sp.foot)}</div>`:''}
</div>` + brandOf(sp.brand);

  throw new Error('unknown template: ' + sp.t);
}
