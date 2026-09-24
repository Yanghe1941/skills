#!/usr/bin/env python3
"""Build a single local HTML report from bill exports. / 从账单生成一个本地 HTML 报表。

Privacy by construction / 隐私保障写在代码里:
  - One self-contained file: no CDN, no web fonts, no network. A Content-Security-Policy
    blocks every outbound request, so the page cannot send data anywhere.
    单文件、无外链；CSP 禁止一切外部请求，页面无法把数据发出去。
  - Only what the report needs: time, amount, direction, counterparty. No order ids,
    item names, notes, payment methods or balances.
    只含必要字段；不含订单号、商品名、备注、支付方式、余额。
  - --mask hides counterparty and file names (张** / wechat-1) for screenshots.
    --mask 给交易对方和文件名打码，便于截图分享。
  - Never publish the output. Open it locally. / 生成的文件只在本机打开，不要上传发布。

Usage / 用法:
  python3 report.py <files-or-dirs> ... -o report.html [--confirmed pairs.csv] [--mask]
  --confirmed: CSV exported from the report's own "导出确认结果" button (or roundtrip.py
  --csv with a `verdict` column). Confirmed pairs are removed from the totals and charts.
"""
import argparse
import csv
import datetime as dt
import html
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bills import run  # noqa: E402
from parsers import EXPENSE, INCOME  # noqa: E402
from roundtrip import find_all, pair_id, prepare  # noqa: E402

YES = {'y', 'yes', '1', 'true', '确认', '是', 'confirmed'}
ZERO = Decimal('0')
SOURCE_NAME = {'wechat': '微信支付', 'alipay': '支付宝', 'jd': '京东', 'cmb': '招商银行'}
SOURCE_ORDER = ['wechat', 'alipay', 'jd', 'cmb']
TYPE_INFO = {
    '3': ('跨源重复', '同一笔钱在两个平台各记一次', '同方向、同金额、来源不同，间隔 ≤10 分钟（银行按日期 ±1 天）'),
    '2': ('原路返回', '转出去又原额转回来，是周转不是消费', '先转给 X、再从 X 收回同额，≤30 天'),
    '1': ('一收一支', '代付、平账或退款另记', '同额一收一支，≤24 小时，对方不限'),
}


def esc(s):
    return html.escape(str(s), quote=True)


def clean_party(s):
    """Platforms write '/' for 'no counterparty'. / 平台用 / 表示无交易对方。"""
    s = (s or '').strip()
    return '' if s in ('/', '-', '—') else s


def mask_name(s):
    s = clean_party(s)
    if not s:
        return s
    return s[0] + '*' * min(max(len(s) - 1, 1), 3)


def money(d, sign=''):
    return f'{sign}¥{d:,.2f}'


def short_money(d):
    d = float(d)
    if abs(d) >= 1e8:
        return f'{d / 1e8:.2f}亿'
    if abs(d) >= 1e4:
        return f'{d / 1e4:,.1f}万'
    return f'{d:,.0f}'


def net(r):
    return r['_a'] - Decimal(str(r.get('refund') or 0)) if r['direction'] == EXPENSE else r['_a']


def read_confirmed(path):
    if not path:
        return set()
    with open(path, newline='', encoding='utf-8-sig') as fh:
        return {r['id'] for r in csv.DictReader(fh)
                if (r.get('verdict') or '').strip().lower() in YES and r.get('id')}


def savings(code, a, b):
    """What confirming this pair removes: (expense rows, income rows)."""
    legs = [b] if code == '3' else [a, b]
    return [r for r in legs if r['direction'] == EXPENSE], [r for r in legs if r['direction'] == INCOME]


def nice_max(v):
    """Round an axis maximum up to 1/2/2.5/5 × 10^n."""
    v = float(v) or 1.0
    exp = 10 ** (len(str(int(v))) - 1)
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


# ------------------------------------------------------------------ SVG pieces

def svg_waterfall(steps):
    """steps: [(label, value, kind)] kind in total|minus|result|pending."""
    top = max((v for _, v, _ in steps), default=ZERO) or Decimal('1')
    W, row, lab, right = 760, 46, 132, 150
    span = W - lab - right
    sx = lambda d: lab + float(d / top) * span  # noqa: E731
    h = row * len(steps) + 6
    out = [f'<svg viewBox="0 0 {W} {h}" class="chart" role="img" aria-label="支出口径调整">']
    run_total, prev_edge = ZERO, None
    for i, (label, v, kind) in enumerate(steps):
        y = 6 + i * row
        if kind == 'total':
            x0, x1 = ZERO, v
            run_total = v
        elif kind == 'minus':
            x0, x1 = run_total - v, run_total
            run_total -= v
        elif kind == 'result':
            x0, x1 = ZERO, v
        else:
            x0, x1 = run_total - v, run_total
        x, w = sx(x0), max(sx(x1) - sx(x0), 2)
        sign = '−' if kind in ('minus', 'pending') else ''
        if prev_edge is not None:
            out.append(f'<line x1="{prev_edge:.1f}" x2="{prev_edge:.1f}" y1="{y - row + 28}" y2="{y + 6}" class="wf-link"/>')
        strong = kind in ('total', 'result')
        out.append(f'<text x="{lab - 14}" y="{y + 21}" class="wf-lbl{" strong" if strong else ""}" '
                   f'text-anchor="end">{esc(label)}</text>')
        tip = f'{label}　{money(v, sign)}'
        out.append(f'<rect x="{x:.1f}" y="{y + 6}" width="{w:.1f}" height="22" rx="3" class="wf-{kind}" '
                   f'data-tip="{esc(tip)}"/>')
        out.append(f'<text x="{x + w + 10:.1f}" y="{y + 22}" class="wf-val{" strong" if kind == "result" else ""}">'
                   f'{money(v, sign)}</text>')
        if kind != 'pending':
            prev_edge = sx(run_total)
    out.append('</svg>')
    return ''.join(out)


def svg_years(years):
    """years: [(YYYY, expense, income)] grouped bars, one axis."""
    if not years:
        return '<p class="empty">没有可画的数据。</p>'
    n = len(years)
    W, H, top, bottom, left, right = 760, 280, 18, 34, 52, 8
    ph, pw = H - top - bottom, W - left - right
    peak = nice_max(max(max(e, i) for _, e, i in years))
    y = lambda d: top + ph - float(d) / peak * ph  # noqa: E731
    slot = pw / n
    bw = max(min(slot * 0.32, 22), 3)
    gap = 2
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="年度真实支出与收入">']
    for k in range(5):
        v = peak * k / 4
        yy = y(v)
        out.append(f'<line x1="{left}" x2="{W - right}" y1="{yy:.1f}" y2="{yy:.1f}" class="grid"/>')
        out.append(f'<text x="{left - 8}" y="{yy + 4:.1f}" class="axis" text-anchor="end">{short_money(v)}</text>')
    label_every = 1 if n <= 14 else 2
    for k, (yr, e, i) in enumerate(years):
        cx = left + slot * (k + .5)
        for j, (v, cls) in enumerate(((e, 'bar-exp'), (i, 'bar-inc'))):
            x = cx - bw - gap / 2 if j == 0 else cx + gap / 2
            hh = max(top + ph - y(v), 0)
            if hh > 0:
                r = min(3, bw / 2, hh)
                out.append(f'<path d="M{x:.1f},{top + ph} v{-(hh - r):.1f} q0,{-r} {r},{-r} h{bw - 2 * r:.1f} '
                           f'q{r},0 {r},{r} v{hh - r:.1f} z" class="{cls}"/>')
        tip = f'{yr} 年　真实支出 {money(e)}　收入 {money(i)}'
        out.append(f'<rect x="{left + slot * k:.1f}" y="{top}" width="{slot:.1f}" height="{ph}" class="hit" '
                   f'data-tip="{esc(tip)}"/>')
        if k % label_every == 0:
            out.append(f'<text x="{cx:.1f}" y="{H - 12}" class="axis" text-anchor="middle">{yr}</text>')
    out.append(f'<line x1="{left}" x2="{W - right}" y1="{top + ph}" y2="{top + ph}" class="baseline"/>')
    out.append('</svg>')
    return ''.join(out)


def heatmap(months):
    """months: {YYYY-MM: expense}. Year × month grid, quantile-binned single hue."""
    vals = sorted(v for v in months.values() if v > 0)
    if not vals:
        return '<p class="empty">没有支出。</p>'
    cuts = [vals[min(int(len(vals) * q), len(vals) - 1)] for q in (.2, .4, .6, .8)]
    level = lambda v: 0 if v <= 0 else 1 + sum(v > c for c in cuts)  # noqa: E731
    years = sorted({k[:4] for k in months})
    head = ''.join(f'<span class="hm-m">{m}</span>' for m in range(1, 13))
    rows = []
    for yr in years:
        cells = []
        for m in range(1, 13):
            key = f'{yr}-{m:02d}'
            if key not in months:
                cells.append(f'<span class="hm-c none" data-tip="{key}　无数据"></span>')
                continue
            v = months[key]
            cells.append(f'<span class="hm-c l{level(v)}" data-tip="{key}　真实支出 {money(v)}"></span>')
        total = sum((months.get(f'{yr}-{m:02d}', ZERO) for m in range(1, 13)), ZERO)
        rows.append(f'<div class="hm-row"><span class="hm-y">{yr}</span>{"".join(cells)}'
                    f'<span class="hm-t">{short_money(total)}</span></div>')
    legend = ''.join(f'<span class="hm-c l{k}"></span>' for k in range(1, 6))
    return (f'<div class="hm"><div class="hm-row hm-head"><span class="hm-y"></span>{head}'
            f'<span class="hm-t">全年</span></div>{"".join(rows)}</div>'
            f'<div class="hm-legend"><span>少</span>{legend}<span>多</span>'
            f'<span class="hm-note">按月份五分位着色 · 单月 {short_money(vals[0])} – {short_money(vals[-1])} · '
            f'斜纹格为无数据月份</span></div>')


def hbars(items):
    if not items:
        return '<p class="empty">没有可画的数据。</p>'
    peak = items[0][1] or Decimal('1')
    total = sum((v for _, v in items), ZERO)
    rows = []
    for k, (label, v) in enumerate(items, 1):
        pct = float(v / peak) * 100
        rows.append(f'<div class="hb" data-tip="{esc(label)}　{money(v)}"><span class="hb-k">{k:02d}</span>'
                    f'<span class="hb-l">{esc(label)}</span><span class="hb-track"><i style="width:{pct:.2f}%"></i></span>'
                    f'<span class="hb-v">{money(v)}</span></div>')
    return f'<div class="hbars">{"".join(rows)}</div><p class="foot">前 {len(items)} 名合计 {money(total)}</p>'


def share_bar(parts):
    """parts: [(source, value)] → 100% stacked bar with legend."""
    total = sum((v for _, v in parts), ZERO)
    if not total:
        return '<p class="empty">没有可画的数据。</p>'
    segs, legend = [], []
    for k, (src, v) in enumerate(parts):
        pct = float(v / total) * 100
        nm = SOURCE_NAME.get(src, src)
        segs.append(f'<i class="s{k + 1}" style="width:{pct:.3f}%" data-tip="{nm}　{money(v)}（{pct:.1f}%）"></i>')
        legend.append(f'<div class="sl"><b class="s{k + 1}"></b><span>{nm}</span><em>{pct:.1f}%</em>'
                      f'<strong>{money(v)}</strong></div>')
    return f'<div class="share">{"".join(segs)}</div><div class="share-legend">{"".join(legend)}</div>'


# ------------------------------------------------------------------ page chrome

CSS = r"""
:root{
  --ground:#f3f4f1;--surface:#fff;--sunk:#f7f8f6;
  --ink:#17202a;--ink2:#3d4852;--muted:#66727d;--rule:#dfe3e0;--rule2:#eceee9;
  --accent:#1f3a5f;--accent-soft:#e7edf4;--brass:#9a6b1f;
  --bad:#b42318;--bad-soft:#fbeceb;--bad-line:#f1c9c4;
  --ok:#0b7446;--ok-soft:#e8f4ed;--ok-line:#bfdfcc;
  --exp:#1f3a5f;--inc:#b0813a;--minus:#c9ced2;--cut:#c7847a;
  --h0:#eceee9;--h1:#dbe5f0;--h2:#b3c8e0;--h3:#7f9fc6;--h4:#4f7cac;--h5:#1f3a5f;
  --s1:#1f3a5f;--s2:#4f7cac;--s3:#b0813a;--s4:#a9c1dc;
  --serif:"Songti SC","Noto Serif SC","Source Han Serif SC","STSong",serif;
  --sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  --mono:"SF Mono",ui-monospace,Menlo,Consolas,monospace;--r:8px;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
  --ground:#0f1318;--surface:#161b22;--sunk:#1b222a;
  --ink:#e7ebef;--ink2:#c3cbd3;--muted:#8e99a4;--rule:#2a333d;--rule2:#222a33;
  --accent:#9dbbe0;--accent-soft:#1c2837;--brass:#d2a55a;
  --bad:#f07a6c;--bad-soft:#2a1715;--bad-line:#5a2a25;
  --ok:#5cc28c;--ok-soft:#13261c;--ok-line:#23513a;
  --exp:#7fa6d6;--inc:#d2a55a;--minus:#3a434d;--cut:#a4574c;
  --h0:#1b222a;--h1:#1c2837;--h2:#27405e;--h3:#34608f;--h4:#5f8cc0;--h5:#9dbbe0;
  --s1:#9dbbe0;--s2:#5f8cc0;--s3:#d2a55a;--s4:#34506f}}
:root[data-theme="dark"]{color-scheme:dark;
  --ground:#0f1318;--surface:#161b22;--sunk:#1b222a;
  --ink:#e7ebef;--ink2:#c3cbd3;--muted:#8e99a4;--rule:#2a333d;--rule2:#222a33;
  --accent:#9dbbe0;--accent-soft:#1c2837;--brass:#d2a55a;
  --bad:#f07a6c;--bad-soft:#2a1715;--bad-line:#5a2a25;
  --ok:#5cc28c;--ok-soft:#13261c;--ok-line:#23513a;
  --exp:#7fa6d6;--inc:#d2a55a;--minus:#3a434d;--cut:#a4574c;
  --h0:#1b222a;--h1:#1c2837;--h2:#27405e;--h3:#34608f;--h4:#5f8cc0;--h5:#9dbbe0;
  --s1:#9dbbe0;--s2:#5f8cc0;--s3:#d2a55a;--s4:#34506f}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:24px}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{font-family:var(--sans);font-size:14px;line-height:1.65;background:var(--ground);color:var(--ink);
  -webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums}
button,input{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
code{font-family:var(--mono);font-size:.86em;background:var(--sunk);border:1px solid var(--rule2);padding:0 5px;border-radius:4px}

.shell{max-width:1320px;margin:0 auto;padding-inline:24px;display:grid;grid-template-columns:196px minmax(0,1fr);gap:44px}
.rail{position:sticky;top:0;align-self:start;height:100vh;overflow-y:auto;padding-block:32px 24px;
  display:flex;flex-direction:column;gap:24px;scrollbar-width:none}
.rail::-webkit-scrollbar{display:none}
.brand .mark{font-family:var(--serif);font-size:19px;font-weight:700;letter-spacing:.5px}
.brand .sub{font-size:11px;color:var(--muted);letter-spacing:1.2px;text-transform:uppercase}
.toc{display:flex;flex-direction:column;gap:1px;border-left:1px solid var(--rule)}
.toc a{display:flex;gap:10px;align-items:baseline;padding:5px 0 5px 14px;margin-left:-1px;border-left:2px solid transparent;
  color:var(--muted);text-decoration:none;font-size:13px;white-space:nowrap}
.toc a .no{font-family:var(--mono);font-size:10.5px;color:var(--brass);min-width:18px}
.toc a:hover{color:var(--ink);border-left-color:var(--rule)}
.toc a.on{color:var(--ink);font-weight:600;border-left-color:var(--accent)}
.meta{display:flex;flex-direction:column;gap:6px;font-size:11.5px;color:var(--muted)}
.meta span{display:flex;align-items:center;gap:7px}
.meta span::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--rule);flex:none}
.meta .good{color:var(--ok)}.meta .good::before{background:var(--ok)}
.meta .bad{color:var(--bad);font-weight:600}.meta .bad::before{background:var(--bad)}
.theme{display:flex;border:1px solid var(--rule);border-radius:6px;overflow:hidden;width:max-content}
.theme button{border:0;background:var(--surface);padding:3px 11px;font-size:11.5px;color:var(--muted);cursor:pointer}
.theme button+button{border-left:1px solid var(--rule)}
.theme button[aria-pressed="true"]{background:var(--accent-soft);color:var(--ink);font-weight:600}
.lock{font-size:11.5px;color:var(--muted);line-height:1.6;border-top:1px solid var(--rule);padding-top:14px}
.lock b{display:block;color:var(--ink2);font-weight:600;margin-bottom:2px}

main{min-width:0;padding-block:34px 120px}
.masthead{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px 24px;align-items:end;
  padding-bottom:22px;border-bottom:1px solid var(--rule)}
.eyebrow{font-size:11px;letter-spacing:2px;color:var(--brass);font-weight:600}
.masthead h1{font-family:var(--serif);font-size:34px;line-height:1.2;font-weight:700;margin-top:6px;text-wrap:balance}
.masthead .sub{grid-column:1/-1;font-size:14.5px;color:var(--ink2);max-width:74ch;line-height:1.75}
.masthead .sub b{color:var(--ink);font-family:var(--mono);font-weight:600;font-size:.96em}
.asof{text-align:right;font-size:11.5px;color:var(--muted);line-height:1.5;letter-spacing:.3px}
.asof b{display:block;font-family:var(--mono);font-size:15px;color:var(--ink);font-weight:600;letter-spacing:0}
.banner{margin-top:18px;border:1px solid var(--bad-line);background:var(--bad-soft);color:var(--bad);border-radius:var(--r);
  padding:11px 14px;font-weight:600;font-size:13.5px}

.strip{display:grid;grid-template-columns:1.45fr repeat(4,minmax(0,1fr));gap:1px;background:var(--rule);
  border:1px solid var(--rule);border-radius:var(--r);overflow:hidden;margin-top:24px}
.strip .t{background:var(--surface);padding:15px 16px 14px;min-width:0}
.strip .k{font-size:11.5px;font-weight:600;letter-spacing:.6px;color:var(--muted);display:flex;gap:7px;align-items:center}
.strip .k i{width:8px;height:8px;border-radius:2px;display:inline-block}
.strip .v{font-family:var(--mono);font-size:18px;font-weight:600;letter-spacing:-.4px;margin-top:5px;overflow-wrap:anywhere}
.strip .d{font-size:11.5px;color:var(--muted);margin-top:3px}
.strip .hero{background:var(--accent-soft)}
.strip .hero .k{color:var(--accent)}
.strip .hero .v{font-size:28px;letter-spacing:-.8px}
.strip .neg .v{color:var(--ink2)}

section{padding-block:44px 4px}
h2{font-family:var(--serif);font-size:21px;font-weight:700;display:flex;align-items:baseline;gap:12px;line-height:1.35}
h2 .n{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--brass);letter-spacing:.5px;min-width:30px}
h2 .n::before{content:"§"}
.lede{font-size:13.5px;color:var(--muted);margin:6px 0 18px 42px;max-width:80ch}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);padding:18px 20px 16px;margin-bottom:16px}
.card h3{font-size:14.5px;font-weight:650;line-height:1.4}
.card .h3note{font-size:12.5px;color:var(--muted);margin:2px 0 14px}
.grid{display:grid;gap:16px;margin-bottom:16px}.grid>.card{margin-bottom:0}
.g2{grid-template-columns:minmax(0,1.55fr) minmax(0,1fr)}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.empty{color:var(--muted);font-size:13px}.foot{font-size:12px;color:var(--muted);margin-top:10px}

.src{display:flex;flex-direction:column;gap:5px}
.src .top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.src .name{font-weight:650;font-size:14.5px}
.pill{font-size:10.5px;font-weight:700;letter-spacing:.5px;padding:2px 8px;border-radius:999px;white-space:nowrap}
.pill.ok{background:var(--ok-soft);color:var(--ok);border:1px solid var(--ok-line)}
.pill.bad{background:var(--bad-soft);color:var(--bad);border:1px solid var(--bad-line)}
.src .big{font-family:var(--mono);font-size:22px;font-weight:600;letter-spacing:-.4px;margin-top:4px}
.src .big small{font-family:var(--sans);font-size:12px;color:var(--muted);font-weight:400;margin-left:6px;letter-spacing:0}
.src .range{font-size:12px;color:var(--muted);font-family:var(--mono)}
.ticks{display:flex;gap:3px;margin-top:8px}.ticks i{height:6px;flex:1;border-radius:1px;background:var(--ok)}
.ticks i.x{background:var(--bad)}
details.files summary{cursor:pointer;font-size:13px;color:var(--accent);font-weight:600}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:12px}
.tbl th,.tbl td{padding:8px 10px;border-bottom:1px solid var(--rule2);text-align:left;white-space:nowrap}
.tbl th{font-size:11.5px;font-weight:600;color:var(--muted);letter-spacing:.3px;background:var(--sunk)}
.tbl td.n,.tbl th.n{text-align:right;font-family:var(--mono)}
.tbl .ok{color:var(--ok);font-weight:600}.tbl .bad{color:var(--bad);font-weight:600}
.scroll{overflow-x:auto}

.chart{display:block;width:100%;height:auto}
.chart text{font-family:var(--sans)}
.axis{fill:var(--muted);font-size:11px;font-family:var(--mono)!important}
.chart .grid{stroke:var(--rule2);stroke-width:1}.baseline{stroke:var(--ink2);stroke-width:1}
.hit{fill:transparent;cursor:crosshair}.hit:hover{fill:var(--ink);fill-opacity:.05}
.bar-exp{fill:var(--exp)}.bar-inc{fill:var(--inc)}
.wf-lbl{fill:var(--ink2);font-size:13px}.wf-lbl.strong{fill:var(--ink);font-weight:650}
.wf-val{fill:var(--ink2);font-size:13px;font-family:var(--mono)!important}.wf-val.strong{fill:var(--ink);font-weight:700}
.wf-total{fill:var(--minus)}.wf-minus{fill:var(--cut)}.wf-result{fill:var(--exp)}
.wf-pending{fill:none;stroke:var(--muted);stroke-width:1.5;stroke-dasharray:4 3}
.wf-link{stroke:var(--muted);stroke-width:1;stroke-dasharray:2 3}
.legend{display:flex;gap:18px;font-size:12.5px;color:var(--ink2);margin-bottom:6px;flex-wrap:wrap}
.legend span{display:flex;align-items:center;gap:6px}.legend i{width:10px;height:10px;border-radius:2px}

.hm{display:grid;gap:3px;overflow-x:auto;padding-bottom:4px}
.hm-row{display:grid;grid-template-columns:44px repeat(12,minmax(20px,1fr)) 64px;gap:3px;align-items:center;min-width:420px}
.hm-y{font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.hm-m{font-family:var(--mono);font-size:10.5px;color:var(--muted);text-align:center}
.hm-t{font-family:var(--mono);font-size:11.5px;color:var(--ink2);text-align:right}
.hm-head .hm-t{color:var(--muted);font-family:var(--sans)}
.hm-c{height:26px;border-radius:3px;background:var(--h0)}
.hm-c.none{background:repeating-linear-gradient(135deg,var(--sunk) 0 3px,var(--rule2) 3px 5px)}
.hm-c.l1{background:var(--h1)}.hm-c.l2{background:var(--h2)}.hm-c.l3{background:var(--h3)}
.hm-c.l4{background:var(--h4)}.hm-c.l5{background:var(--h5)}
.hm-row .hm-c:hover{outline:2px solid var(--ink);outline-offset:1px}
.hm-legend{display:flex;align-items:center;gap:4px;margin-top:14px;font-size:11.5px;color:var(--muted);flex-wrap:wrap}
.hm-legend .hm-c{width:18px;height:12px}.hm-legend .hm-note{margin-left:12px}

.hbars{display:flex;flex-direction:column;gap:1px}
.hb{display:grid;grid-template-columns:22px minmax(0,140px) minmax(0,1fr) 112px;gap:10px;align-items:center;
  padding:5px 6px;border-radius:5px;font-size:13px}
.hb:hover{background:var(--sunk)}
.hb-k{font-family:var(--mono);font-size:11px;color:var(--brass)}
.hb-l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hb-track{height:10px;background:var(--rule2);border-radius:2px;overflow:hidden}
.hb-track i{display:block;height:100%;background:var(--exp);border-radius:2px}
.hb-v{font-family:var(--mono);text-align:right;font-size:12.5px}
.share{display:flex;height:16px;border-radius:3px;overflow:hidden;gap:2px;margin-top:6px}
.share i{display:block;height:100%}
.s1{background:var(--s1)}.s2{background:var(--s2)}.s3{background:var(--s3)}.s4{background:var(--s4)}
.share-legend{display:flex;flex-direction:column;margin-top:16px}
.sl{display:grid;grid-template-columns:12px 1fr auto;gap:2px 10px;align-items:center;padding:9px 0;border-bottom:1px solid var(--rule2)}
.sl b{width:10px;height:10px;border-radius:2px}.sl span{font-size:13px}
.sl em{font-style:normal;font-family:var(--mono);font-size:13px;font-weight:600;text-align:right}
.sl strong{grid-column:2/-1;font-family:var(--mono);font-size:11.5px;color:var(--muted);font-weight:400}

.ptype{display:flex;flex-direction:column;gap:4px;border-top:3px solid var(--accent)}
.ptype .code{font-family:var(--mono);font-size:10.5px;color:var(--brass);letter-spacing:1px}
.ptype .name{font-weight:650;font-size:15px}
.ptype .num{font-family:var(--mono);font-size:24px;font-weight:600;letter-spacing:-.4px}
.ptype .num small{font-size:12px;color:var(--muted);font-family:var(--sans);font-weight:400;margin-left:6px;letter-spacing:0}
.ptype .why{font-size:12.5px;color:var(--ink2)}
.ptype .rule{font-size:11.5px;color:var(--muted)}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.chip{border:1px solid var(--rule);background:var(--surface);border-radius:999px;padding:4px 12px;font-size:12.5px;cursor:pointer;color:var(--ink2)}
.chip:hover{border-color:var(--ink2)}
.chip[aria-pressed="true"]{background:var(--ink);color:var(--surface);border-color:var(--ink)}
.chip em{font-style:normal;font-family:var(--mono);opacity:.7;margin-left:5px}
.btn{border:1px solid var(--accent);background:var(--accent);color:var(--surface);border-radius:6px;padding:6px 14px;
  font-size:12.5px;font-weight:600;cursor:pointer;margin-left:auto}
.btn:hover{filter:brightness(1.12)}
.ptbl tr.hide{display:none}
.ptbl td.side{white-space:normal;min-width:130px;max-width:260px}
.ptbl .who{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink)}
.ptbl .tag{font-size:11px;padding:1px 7px;border-radius:4px;background:var(--sunk);border:1px solid var(--rule);color:var(--ink2)}
.ptbl .sc{display:block;font-size:11px;color:var(--muted)}
.ptbl input{width:16px;height:16px;accent-color:var(--accent);cursor:pointer}
.ptbl tbody tr:hover td{background:var(--sunk)}
.ptbl tr.on td{background:var(--accent-soft)!important}
.more{display:block;margin:14px auto 0;border:1px solid var(--rule);background:var(--surface);border-radius:6px;padding:6px 16px;font-size:12.5px;cursor:pointer;color:var(--ink2)}
.dock{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:var(--ink);color:var(--surface);
  border-radius:999px;padding:10px 20px;font-size:13px;box-shadow:0 10px 30px rgba(0,0,0,.2);display:none;gap:8px;align-items:center;
  white-space:nowrap;z-index:5;max-width:calc(100vw - 32px);overflow:hidden}
.dock.show{display:flex}.dock b{font-family:var(--mono)}.dock span{opacity:.72}

.notes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.notes ul{margin:8px 0 0 18px;font-size:13px;color:var(--ink2)}.notes li{margin:4px 0}
footer{margin-top:28px;padding-top:16px;border-top:1px solid var(--rule);font-size:12px;color:var(--muted)}

#tip{position:fixed;pointer-events:none;z-index:10;background:var(--ink);color:var(--surface);font-size:12px;
  padding:6px 10px;border-radius:6px;white-space:nowrap;font-family:var(--mono);opacity:0;transition:opacity .08s;
  box-shadow:0 4px 16px rgba(0,0,0,.2)}

@media (max-width:1180px){.strip{grid-template-columns:repeat(2,minmax(0,1fr))}.strip .hero{grid-column:1/-1}
  .g2{grid-template-columns:1fr}}
@media (max-width:760px){.g3{grid-template-columns:1fr}}
@media (max-width:900px){.shell{grid-template-columns:1fr;gap:0}.rail{display:none}.g2,.notes{grid-template-columns:1fr}
  .masthead{grid-template-columns:1fr}.asof{text-align:left}.lede{margin-left:0}
  .hb{grid-template-columns:22px minmax(0,1fr) 104px}.hb-track{grid-column:2/-1;grid-row:2}}
@media (max-width:520px){.shell{padding-inline:16px}.masthead h1{font-size:27px}.strip .hero .v{font-size:24px}
  .dock span:last-child{display:none}}
@media print{.rail,.dock,.btn,#tip,.more{display:none!important}.shell{display:block}body{background:#fff}}
"""

JS = r"""
(function(){
  var root=document.documentElement,KEY='cn-bill-parser:';
  function get(k){try{return localStorage.getItem(KEY+k);}catch(e){return null;}}
  function set(k,v){try{localStorage.setItem(KEY+k,v);}catch(e){}}
  var btns=[].slice.call(document.querySelectorAll('.theme button'));
  function applyTheme(t){if(t==='auto')root.removeAttribute('data-theme');else root.setAttribute('data-theme',t);
    btns.forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.t===t));});}
  applyTheme(get('theme')||'auto');
  btns.forEach(function(b){b.addEventListener('click',function(){set('theme',b.dataset.t);applyTheme(b.dataset.t);});});
  var tip=document.getElementById('tip');
  document.addEventListener('mousemove',function(e){
    var t=e.target.closest&&e.target.closest('[data-tip]');
    if(!t){tip.style.opacity=0;return;}
    tip.textContent=t.getAttribute('data-tip');tip.style.opacity=1;
    var w=tip.offsetWidth,x=e.clientX+14,y=e.clientY+18;
    if(x+w>window.innerWidth-8)x=e.clientX-w-14;
    tip.style.left=x+'px';tip.style.top=y+'px';});
  var links=[].slice.call(document.querySelectorAll('.toc a'));
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(en){if(en.isIntersecting){
      links.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#'+en.target.id);});}});},
      {rootMargin:'-15% 0px -75% 0px'});
    document.querySelectorAll('main section[id]').forEach(function(s){io.observe(s);});}
  var rows=[].slice.call(document.querySelectorAll('.ptbl tbody tr[data-type]'));
  var boxes=rows.map(function(r){return r.querySelector('input');});
  var base=parseFloat(document.body.dataset.base),filter='all',limit=30,dock=document.getElementById('dock');
  var fmt=function(v){return '¥'+v.toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2});};
  boxes.forEach(function(b){var s=get(b.dataset.pair);if(s!==null&&!b.disabled)b.checked=(s==='1');});
  var more=document.getElementById('more');
  function render(){
    var shown=0,cut=0,n=0,total=0;
    rows.forEach(function(r,i){var ok=(filter==='all'||r.dataset.type===filter);
      if(ok)total++;var vis=ok&&shown<limit;if(vis)shown++;r.classList.toggle('hide',!vis);
      r.classList.toggle('on',boxes[i].checked);
      if(boxes[i].checked&&!boxes[i].disabled){cut+=parseFloat(boxes[i].dataset.save);n++;}});
    if(more){more.style.display=total>limit?'block':'none';more.textContent='显示全部 '+total+' 组';}
    if(dock){dock.classList.toggle('show',n>0);
      dock.innerHTML='<span>本页另确认</span><b>'+n+'</b><span>组 · 真实支出约</span><b>'+fmt(base-cut)+
        '</b><span>· 导出后用 --confirmed 重新生成</span>';}
  }
  boxes.forEach(function(b){b.addEventListener('change',function(){set(b.dataset.pair,b.checked?'1':'0');render();});});
  [].slice.call(document.querySelectorAll('.chip')).forEach(function(c){c.addEventListener('click',function(){
    filter=c.dataset.f;limit=30;document.querySelectorAll('.chip').forEach(function(x){
      x.setAttribute('aria-pressed',String(x===c));});render();});});
  if(more)more.addEventListener('click',function(){limit=1e9;render();});
  render();
  var ex=document.getElementById('export');if(ex)ex.addEventListener('click',function(){
    var out=['id,type,amount,verdict'];
    boxes.forEach(function(b){out.push([b.dataset.pair,b.dataset.type,b.dataset.amount,(b.checked?'确认':'')].join(','));});
    var a=document.createElement('a');
    a.href='data:text/csv;charset=utf-8,'+encodeURIComponent('﻿'+out.join('\n'));
    a.download='pairs-confirmed.csv';document.body.appendChild(a);a.click();a.remove();});
})();
"""


# ------------------------------------------------------------------ build

def build(paths, confirmed_path=None, masked=False):
    results, failed = run(paths)
    confirmed = read_confirmed(confirmed_path)
    name = mask_name if masked else clean_party
    allrecs = [r for res in results for r in res[2]]
    data = [r for r in prepare(allrecs) if r['currency'] == 'CNY']
    groups = find_all(data)

    excluded, pairs = set(), []
    for code, _title, ps in groups:
        for a, b in ps:
            ex, inc = savings(code, a, b)
            save = sum((net(r) for r in ex), ZERO)
            pid = pair_id(a, b)
            if pid in confirmed:
                excluded.update(id(r) for r in ex + inc)
            pairs.append((code, a, b, pid, save, pid in confirmed))

    exp = [r for r in data if r['direction'] == EXPENSE]
    gross = sum((r['_a'] for r in exp), ZERO)
    refunds = sum((r['_a'] - net(r) for r in exp), ZERO)
    conf_cut = sum((p[4] for p in pairs if p[5]), ZERO)
    open_pairs = [p for p in pairs if not p[5]]
    pending = sum((p[4] for p in open_pairs), ZERO)
    real = gross - refunds - conf_cut
    n_income = sum(1 for r in data if r['direction'] == INCOME)
    income = sum((r['_a'] for r in data if r['direction'] == INCOME and id(r) not in excluded), ZERO)

    months, years = {}, defaultdict(lambda: [ZERO, ZERO])
    by_party, by_source = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    for r in data:
        if id(r) in excluded:
            continue
        m = r['_t'].strftime('%Y-%m')
        months.setdefault(m, ZERO)
        if r['direction'] == EXPENSE:
            v = net(r)
            months[m] += v
            years[m[:4]][0] += v
            by_party[name(r.get('counterparty')) or '（未注明）'] += v
            by_source[r.get('source')] += v
        else:
            years[m[:4]][1] += r['_a']
    top = sorted(((k, v) for k, v in by_party.items() if v > 0), key=lambda kv: -kv[1])[:15]
    year_rows = [(y, v[0], v[1]) for y, v in sorted(years.items())]
    first, last = (data[0]['_t'], data[-1]['_t']) if data else (None, None)
    n_years = len(years)
    n_ok = sum(1 for res in results if res[5])
    refund_pct = float(refunds / gross * 100) if gross else 0.0

    strip = f"""<div class="strip">
<div class="t hero"><div class="k"><i style="background:var(--exp)"></i>真实支出</div><div class="v">{money(real)}</div>
<div class="d">{'已扣退款与已确认配对' if conf_cut else '已扣退款'} · 年均 {short_money(real / max(n_years, 1))}</div></div>
<div class="t"><div class="k">账单支出毛额</div><div class="v">{money(gross)}</div><div class="d">{len(exp):,} 笔支出</div></div>
<div class="t neg"><div class="k">退款</div><div class="v">−{money(refunds)}</div><div class="d">占毛额 {refund_pct:.1f}%</div></div>
<div class="t neg"><div class="k">待确认配对</div><div class="v">−{money(pending)}</div>
<div class="d">{len(open_pairs)} 组候选{f' · 已确认 {len(pairs) - len(open_pairs)} 组' if conf_cut else ''}</div></div>
<div class="t"><div class="k"><i style="background:var(--inc)"></i>收入</div><div class="v">{money(income)}</div>
<div class="d">{n_income:,} 笔</div></div></div>"""

    by_src = defaultdict(list)
    for k, res in enumerate(results, 1):
        by_src[res[1]].append((k, res))
    cards = []
    for src in SOURCE_ORDER:
        if src not in by_src:
            continue
        items = by_src[src]
        recs = [r for _, res in items for r in res[2]]
        ok = all(res[5] for _, res in items)
        times = sorted(r['time'][:10] for r in recs if r['time'])
        ticks = ''.join(f'<i class="{"" if res[5] else "x"}" '
                        f'data-tip="{esc(f"{src}-{k}" if masked else res[0].name)}　{"一致" if res[5] else "不符"}"></i>'
                        for k, res in items)
        cards.append(f"""<div class="card src"><div class="top"><span class="name">{SOURCE_NAME[src]}</span>
<span class="pill {'ok' if ok else 'bad'}">{'全部一致' if ok else '存在不符'}</span></div>
<div class="big">{len(recs):,}<small>笔 · {len(items)} 个文件</small></div>
<div class="range">{times[0] if times else '—'} → {times[-1] if times else '—'}</div>
<div class="ticks">{ticks}</div></div>""")
    file_rows = []
    for k, (f, kind, recs, _off, checks, ok) in enumerate(results, 1):
        fname = f'{kind}-{k}' if masked else f.name
        detail = ' · '.join(f"{lab.split()[0]} {'✓' if o is not None and abs(Decimal(p) - Decimal(o)) < Decimal('0.02') else '✗'}"
                            for lab, p, o in checks)
        file_rows.append(f'<tr><td class="{"ok" if ok else "bad"}">{"✓ 一致" if ok else "⚠ 不符"}</td>'
                         f'<td>{SOURCE_NAME.get(kind, kind)}</td><td>{esc(fname)}</td>'
                         f'<td class="n">{len(recs):,}</td><td>{esc(detail)}</td></tr>')

    steps = [('账单支出毛额', gross, 'total'), ('− 退款', refunds, 'minus')]
    if conf_cut:
        steps.append(('− 已确认配对', conf_cut, 'minus'))
    steps.append(('= 真实支出', real, 'result'))
    if pending:
        steps.append(('待确认配对', pending, 'pending'))

    counts = {c: [0, ZERO] for c in TYPE_INFO}
    for code, _a, _b, _pid, save, _c in pairs:
        counts[code][0] += 1
        counts[code][1] += save
    type_cards = ''.join(
        f"""<div class="card ptype"><span class="code">TYPE {c}</span><span class="name">{TYPE_INFO[c][0]}</span>
<span class="num">{counts[c][0]}<small>组 · 涉及 {money(counts[c][1])}</small></span>
<span class="why">{TYPE_INFO[c][1]}</span><span class="rule">{TYPE_INFO[c][2]}</span></div>""" for c in ('3', '2', '1'))
    def side(r, when=False):
        extra = f' · {r["_t"]:%Y-%m-%d}' if when else ''
        return (f'<span class="who">{esc(name(r.get("counterparty")) or "—")}</span>'
                f'<span class="sc">{esc(SOURCE_NAME.get(r.get("source"), r.get("source")))} · {esc(r["direction"])}{extra}</span>')
    prow = [f'<tr data-type="{code}"><td><input type="checkbox" data-pair="{pid}" data-type="{code}" '
            f'data-amount="{a["_a"]}" data-save="{save}" aria-label="确认这一组"{" checked disabled" if c else ""}></td>'
            f'<td><span class="tag">{TYPE_INFO[code][0]}</span></td><td class="n">{money(a["_a"])}</td>'
            f'<td class="n">{a["_t"]:%Y-%m-%d}</td><td class="side">{side(a)}</td>'
            f'<td class="side">{side(b, True)}</td></tr>'
            for code, a, b, pid, save, c in sorted(pairs, key=lambda p: -p[1]['_a'])]
    chips = (f'<button class="chip" data-f="all" aria-pressed="true">全部<em>{len(pairs)}</em></button>'
             + ''.join(f'<button class="chip" data-f="{c}" aria-pressed="false">{TYPE_INFO[c][0]}<em>{counts[c][0]}</em></button>'
                       for c in ('3', '2', '1')))

    span_txt = f'{first:%Y.%m.%d} — {last:%Y.%m.%d}' if first else '—'
    status_meta = (f'<span class="good">{n_ok}/{len(results)} 个文件对账一致</span>' if not failed
                   else f'<span class="bad">{len(results) - n_ok} 个文件不符</span>')
    banner = ('<div class="banner">⚠ 有文件没有通过对账：下面的数字建立在不完整的解析上，先处理不符的文件再下结论。</div>'
              if failed else '')
    sub = (f'{n_years} 年、{len(data):,} 笔收支，来自 {len(by_src)} 个平台的 {len(results)} 个账单文件。'
           f'账单上的支出是 <b>{money(gross)}</b>，扣掉从未真实发生的退款{"与已确认的配对" if conf_cut else ""}后，'
           f'真实支出是 <b>{money(real)}</b>'
           + (f'；另有 {len(open_pairs)} 组候选配对等你确认，属实的话还会再少 <b>{money(pending)}</b>。'
              if pending else '。'))
    toc = ''.join(f'<a href="#{i}"><span class="no">{n}</span>{t}</a>' for n, i, t in (
        ('01', 's1', '对账'), ('02', 's2', '口径调整'), ('03', 's3', '时间'), ('04', 's4', '结构'),
        ('05', 's5', '候选配对'), ('06', 's6', '口径与隐私')))
    share = share_bar([(s, by_source[s]) for s in SOURCE_ORDER if by_source.get(s)])

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><meta name="robots" content="noindex,nofollow">
<title>账单对账报表</title><style>{CSS}</style></head>
<body data-base="{gross - refunds - conf_cut}"><div class="shell">
<aside class="rail"><div class="brand"><div class="mark">账单对账</div><div class="sub">Bill reconciliation</div></div>
<nav class="toc">{toc}</nav>
<div class="meta"><span>{esc(span_txt)}</span>{status_meta}<span>生成于 {dt.datetime.now():%Y-%m-%d %H:%M}</span>{'<span>已打码</span>' if masked else ''}</div>
<div class="theme" role="group" aria-label="主题"><button data-t="auto">自动</button><button data-t="light">浅</button><button data-t="dark">深</button></div>
<div class="lock"><b>🔒 仅本机</b>页面禁止一切网络请求。请勿上传或转发；截图请用 <code>--mask</code> 重新生成。</div></aside>
<main>
<header class="masthead"><div><div class="eyebrow">PERSONAL LEDGER · RECONCILED</div><h1>账单对账报表</h1></div>
<div class="asof">账单期间<b>{esc(span_txt)}</b></div><p class="sub">{sub}</p></header>
{banner}{strip}

<section id="s1"><h2><span class="n">01</span>对账：先证明解析完整</h2>
<p class="lede">每个文件都要和平台自己印在文件里的合计逐项一致（银行流水用逐笔余额连续性）。一个文件对不上，后面的数字就都不可信。</p>
<div class="grid g4">{''.join(cards)}</div>
<details class="files card"><summary>查看 {len(results)} 个文件的逐项检查</summary><div class="scroll">
<table class="tbl"><thead><tr><th>结果</th><th>来源</th><th>文件</th><th class="n">笔数</th><th>检查项</th></tr></thead>
<tbody>{''.join(file_rows)}</tbody></table></div></details></section>

<section id="s2"><h2><span class="n">02</span>口径调整：从账单上的支出到真实支出</h2>
<p class="lede">微信页眉的「支出」把已退款交易也算了进去；转出又转回的钱、两个平台各记一次的钱，都会让支出看起来更多。</p>
<div class="card">{svg_waterfall(steps)}</div></section>

<section id="s3"><h2><span class="n">03</span>时间：钱花在了哪些年、哪些月</h2>
<p class="lede">柱图对比每年的真实支出与收入；热力日历一行一年、一格一月，颜色越深花得越多。</p>
<div class="card"><h3>年度真实支出与收入</h3><p class="h3note">同一坐标轴 · 悬停查看金额</p>
<div class="legend"><span><i style="background:var(--exp)"></i>真实支出</span><span><i style="background:var(--inc)"></i>收入</span></div>
{svg_years(year_rows)}</div>
<div class="card"><h3>按月真实支出</h3><p class="h3note">悬停查看每月金额，右侧为全年合计</p>{heatmap(months)}</div></section>

<section id="s4"><h2><span class="n">04</span>结构：钱花给了谁、从哪里花出去</h2>
<p class="lede">按交易对方汇总真实支出（已扣退款）。转账对象会和商户一起出现在这里。</p>
<div class="grid g2"><div class="card"><h3>真实支出最多的交易对方</h3><p class="h3note">前 15 名</p>{hbars(top)}</div>
<div class="card"><h3>按平台</h3><p class="h3note">真实支出来自哪个平台</p>{share}</div></div></section>

<section id="s5"><h2><span class="n">05</span>候选配对：逐组确认</h2>
<p class="lede">配对只是候选，两笔无关的同额交易也可能被配上。勾选你确认属实的（只保存在本机浏览器），点「导出确认结果」，再用 <code>--confirmed</code> 重新生成，图表就按确认后的口径更新。</p>
<div class="grid g3">{type_cards}</div>
<div class="card"><div class="bar">{chips}<button class="btn" id="export" type="button">导出确认结果</button></div>
<div class="scroll"><table class="tbl ptbl"><thead><tr><th>确认</th><th>类型</th><th class="n">金额</th><th class="n">日期</th>
<th>A</th><th>B</th></tr></thead>
<tbody>{''.join(prow) or '<tr><td colspan="6" class="empty">没有候选配对。</td></tr>'}</tbody></table></div>
<button class="more" id="more" type="button"></button></div></section>

<section id="s6"><h2><span class="n">06</span>口径与隐私</h2>
<div class="notes"><div class="card"><h3>口径</h3><ul>
<li>真实支出 = 支出金额 − 退款部分；「不计收支」不计入。</li>
<li>只统计人民币；已确认的配对从支出和收入两侧同时剔除。</li>
<li>跨源重复只剔除后一条记录；原路返回与一收一支两条都剔除。</li>
<li>本报表描述资金发生了什么，不构成财务、税务或信贷建议。</li></ul></div>
<div class="card"><h3>隐私</h3><ul>
<li>单文件、零外链；内容安全策略禁止一切网络请求。</li>
<li>只含时间、金额、方向、交易对方；不含订单号、商品、备注、支付方式、余额。</li>
<li>勾选状态只存在本机浏览器的本地存储里。</li>
<li>要截图分享，请用 <code>--mask</code> 重新生成打码版。</li></ul></div></div>
<footer>由 cn-bill-parser 在本机生成。</footer></section>
</main></div>
<div class="dock" id="dock" aria-live="polite"></div><div id="tip" role="tooltip"></div>
<script>{JS}</script></body></html>"""


def warn_if_tracked(out):
    """Warn when the report lands inside a git repo and is not ignored."""
    try:
        d = out.resolve().parent
        inside = subprocess.run(['git', '-C', str(d), 'rev-parse', '--is-inside-work-tree'],
                                capture_output=True, text=True).stdout.strip() == 'true'
        ignored = subprocess.run(['git', '-C', str(d), 'check-ignore', '-q', str(out.resolve())],
                                 capture_output=True).returncode == 0
        if inside and not ignored:
            print(f'⚠ {out} 在 git 仓库里且未被忽略——小心不要提交它 / inside a git repo and not ignored; '
                  f'do not commit it', file=sys.stderr)
    except (OSError, FileNotFoundError):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='+')
    ap.add_argument('-o', '--out', default='bill-report.html')
    ap.add_argument('--confirmed', help='确认结果 CSV（id, verdict）')
    ap.add_argument('--mask', action='store_true', help='交易对方与文件名打码')
    a = ap.parse_args()
    out = Path(a.out)
    out.write_text(build(a.paths, a.confirmed, a.mask), encoding='utf-8')
    print(f'→ {out}  （仅本机打开，勿上传 / open locally, do not upload）', file=sys.stderr)
    warn_if_tracked(out)


if __name__ == '__main__':
    main()
