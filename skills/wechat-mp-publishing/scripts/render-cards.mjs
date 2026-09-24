// 公众号配图模板库。七种版式，金-米色调（沿用 App 小组件配色）。
//
//   const { html } = await import('<skill>/scripts/render-images.mjs')
//   await gotoAndWait('data:text/html;charset=utf-8,' + encodeURIComponent(html(spec, W, H)))
//   await cdp('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 2, mobile: false })
//   const shot = await cdp('Page.captureScreenshot', { format: 'jpeg', quality: 92 })
//   fs.writeFileSync(out, Buffer.from(shot.data, 'base64'))
//
// 尺寸：封面 900x383（2.35:1），正文图 1080x608。
//
// spec 形状：
//   { t:'cover',   kicker, title, sub, mark }              大标题横幅，mark 是右侧巨型水印字符
//   { t:'quote',   label, big, foot }                      场景金句
//   { t:'steps',   label, items:[[序号,标题,说明],...] }      流程，3-4 条最佳
//   { t:'rows',    label, title, items:[[左键,右说明],...] }  清单，3-4 条最佳
//   { t:'compare', label, left:{h,s,b,f}, right:{h,s,b,f} } 左右对比，右侧高亮
//   { t:'stat',    label, value, unit, note, value2, unit2, note2 }  两个大数字
//   { t:'term',    label, lines:[['$',命令],['',输出]], foot }        终端窗口
//
// title/big/b 支持 \n 换行。渲染完务必逐张 Read 抽查，文字溢出只有肉眼看得出来。

const P = {
  bg:'linear-gradient(135deg,#FFFBF0 0%,#F8EACA 52%,#EFD79A 100%)',
  ink:'#1E1A12', sec:'#6D5E42', ter:'#8A7A59', gold:'#B98A15', goldD:'#8F6A08',
  card:'rgba(255,255,255,.72)', line:'rgba(200,170,90,.42)'
};
const base = (W,H) => `<meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:${W}px;height:${H}px;overflow:hidden}
body{background:${P.bg};font-family:"PingFang SC","Hiragino Sans GB","Heiti SC",sans-serif;
color:${P.ink};-webkit-font-smoothing:antialiased;position:relative}
body:after{content:"";position:absolute;right:-120px;top:-140px;width:420px;height:420px;border-radius:50%;
background:radial-gradient(circle,rgba(185,138,21,.16),transparent 68%);pointer-events:none}
.wrap{position:relative;z-index:2;height:100%;padding:56px 64px;display:flex;flex-direction:column}
.kick{font-size:21px;font-weight:700;color:${P.goldD};letter-spacing:3px}
.lab{font-size:22px;font-weight:700;color:${P.goldD};letter-spacing:2px;margin-bottom:26px;
display:flex;align-items:center;gap:12px}
.lab:before{content:"";width:26px;height:4px;border-radius:2px;background:${P.gold}}
.brand{position:absolute;left:64px;bottom:34px;font-size:19px;color:${P.ter};font-weight:600;
display:flex;align-items:center;gap:9px;z-index:3}
.brand i{width:11px;height:11px;border-radius:50%;background:${P.gold};display:block}
.card{background:${P.card};border:1px solid ${P.line};border-radius:20px}
</style>`;

const brandOf = (n) => n ? `<div class="brand"><i></i>${esc(n)}</div>` : "";

const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const nl = s => esc(s).replace(/\n/g,'<br>');

export function html(sp, W, H){
  if (sp.t==='cover') return base(W,H)+`
<div style="position:absolute;right:38px;top:50%;transform:translateY(-50%);font-size:${String(sp.mark).length>2?132:172}px;
font-weight:800;color:rgba(143,106,8,.085);letter-spacing:-4px;z-index:1;white-space:nowrap">${esc(sp.mark)}</div>
<div class="wrap" style="justify-content:center;max-width:660px;padding:40px 56px 76px">
  <div class="kick">${esc(sp.kicker)}</div>
  <div style="font-size:50px;font-weight:800;line-height:1.26;margin-top:14px;letter-spacing:1px">${nl(sp.title)}</div>
  <div style="width:70px;height:5px;border-radius:3px;background:${P.gold};margin:20px 0 14px"></div>
  <div style="font-size:21px;color:${P.sec};line-height:1.55;font-weight:500">${nl(sp.sub)}</div>
</div>`+brandOf(sp.brand);

  if (sp.t==='quote') return base(W,H)+`
<div style="position:absolute;left:44px;top:96px;font-size:200px;font-weight:800;color:rgba(185,138,21,.13);
line-height:1;z-index:1">&ldquo;</div>
<div class="wrap" style="justify-content:center">
  <div class="lab">${esc(sp.label)}</div>
  <div style="font-size:46px;font-weight:800;line-height:1.44;letter-spacing:1px">${nl(sp.big)}</div>
  <div style="width:70px;height:5px;border-radius:3px;background:${P.gold};margin:32px 0 22px"></div>
  <div style="font-size:24px;color:${P.sec};line-height:1.65;max-width:840px;font-weight:500">${nl(sp.foot)}</div>
</div>`+brandOf(sp.brand);

  if (sp.t==='steps') return base(W,H)+`
<div class="wrap">
  <div class="lab">${esc(sp.label)}</div>
  <div style="display:flex;flex-direction:column;gap:16px;flex:1;justify-content:center;padding-bottom:26px">
  ${sp.items.map(([n,t,d])=>`
    <div class="card" style="display:flex;align-items:center;gap:22px;padding:19px 26px">
      <div style="min-width:54px;height:54px;border-radius:15px;background:${P.gold};color:#fff;font-size:22px;
      font-weight:800;display:flex;align-items:center;justify-content:center">${esc(n)}</div>
      <div style="flex:1">
        <div style="font-size:29px;font-weight:800;letter-spacing:.5px">${esc(t)}</div>
        <div style="font-size:21px;color:${P.sec};margin-top:5px;line-height:1.45;font-weight:500">${esc(d)}</div>
      </div>
    </div>`).join('')}
  </div>
</div>`+brandOf(sp.brand);

  if (sp.t==='rows') return base(W,H)+`
<div class="wrap">
  <div class="lab">${esc(sp.label)}</div>
  <div style="font-size:34px;font-weight:800;margin-bottom:26px;letter-spacing:.5px">${esc(sp.title)}</div>
  <div style="display:flex;flex-direction:column;gap:15px;flex:1;justify-content:center;padding-bottom:34px">
  ${sp.items.map(([k,v])=>`
    <div class="card" style="display:flex;align-items:center;gap:26px;padding:20px 28px">
      <div style="min-width:190px;font-size:29px;font-weight:800;color:${P.goldD};letter-spacing:.5px">${esc(k)}</div>
      <div style="flex:1;font-size:23px;color:${P.sec};line-height:1.45;font-weight:500">${esc(v)}</div>
    </div>`).join('')}
  </div>
</div>`+brandOf(sp.brand);

  if (sp.t==='compare'){
    const col = (c,accent)=>`
    <div class="card" style="flex:1;padding:34px 30px;display:flex;flex-direction:column;
    ${accent?`border-color:rgba(185,138,21,.6);background:rgba(255,251,240,.86)`:''}">
      <div style="font-size:34px;font-weight:800;letter-spacing:1px">${esc(c.h)}</div>
      <div style="font-size:22px;color:${P.goldD};font-weight:700;margin-top:7px">${esc(c.s)}</div>
      <div style="height:1px;background:${P.line};margin:20px 0"></div>
      <div style="font-size:25px;line-height:1.5;font-weight:600;flex:1">${nl(c.b)}</div>
      <div style="font-size:20px;color:${P.ter};margin-top:18px;line-height:1.45;font-weight:500">${esc(c.f)}</div>
    </div>`;
    return base(W,H)+`
<div class="wrap">
  <div class="lab">${esc(sp.label)}</div>
  <div style="display:flex;gap:22px;flex:1;padding-bottom:34px">${col(sp.left,false)}${col(sp.right,true)}</div>
</div>`+brandOf(sp.brand);
  }

  if (sp.t==='stat'){
    const blk = (v,u,n)=>`
    <div class="card" style="flex:1;padding:32px 30px;display:flex;flex-direction:column;justify-content:center">
      <div style="display:flex;align-items:baseline;gap:12px">
        <div style="font-size:${String(v).length>5?60:80}px;font-weight:800;color:${P.goldD};letter-spacing:-1px;line-height:1">${esc(v)}</div>
        <div style="font-size:26px;font-weight:700;color:${P.sec}">${esc(u)}</div>
      </div>
      <div style="font-size:21px;color:${P.sec};margin-top:18px;line-height:1.5;font-weight:500">${esc(n)}</div>
    </div>`;
    return base(W,H)+`
<div class="wrap">
  <div class="lab">${esc(sp.label)}</div>
  <div style="display:flex;gap:22px;flex:1;padding-bottom:34px">${blk(sp.value,sp.unit,sp.note)}${blk(sp.value2,sp.unit2,sp.note2)}</div>
</div>`+brandOf(sp.brand);
  }

  if (sp.t==='term') return base(W,H)+`
<div class="wrap">
  <div class="lab">${esc(sp.label)}</div>
  <div style="background:#191510;border-radius:20px;padding:44px 40px;margin:auto 0;
  font-family:"SF Mono",Menlo,Consolas,monospace;display:flex;flex-direction:column;justify-content:center;gap:16px">
  ${sp.lines.map(([p,t])=>`<div style="font-size:27px;line-height:1.5;color:${p==='$'?'#F0DCA6':'#7FDB96'};font-weight:600">
    ${p==='$'?'<span style="color:#B98A15">$</span> ':'&nbsp;&nbsp;'}${esc(t)}</div>`).join('')}
  </div>
  <div style="font-size:22px;color:${P.sec};margin-top:22px;padding-bottom:26px;font-weight:500">${esc(sp.foot)}</div>
</div>`+brandOf(sp.brand);

  if (sp.t==='shot') return base(W,H)+`
<div class="wrap">
  <div class="lab">${esc(sp.label)}</div>
  <div style="display:flex;gap:34px;align-items:center;flex:1;padding-bottom:30px">
    <div style="flex:0 0 258px;height:424px;overflow:hidden;border-radius:22px;
    box-shadow:0 16px 40px rgba(90,66,10,.28);border:1px solid rgba(200,170,90,.5)">
      <img src="${sp.img}" style="width:100%;display:block;object-fit:cover;object-position:top">
    </div>
    <div style="flex:1">
      <div style="font-size:34px;font-weight:800;line-height:1.42;letter-spacing:.5px">${nl(sp.title)}</div>
      <div style="width:60px;height:5px;border-radius:3px;background:${P.gold};margin:22px 0 18px"></div>
      <div style="font-size:22px;color:${P.sec};line-height:1.65;font-weight:500">${nl(sp.note)}</div>
    </div>
  </div>
</div>`+brandOf(sp.brand);

  throw new Error('unknown template: '+sp.t);
}
