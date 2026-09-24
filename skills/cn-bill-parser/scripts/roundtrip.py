#!/usr/bin/env python3
"""Find money that looks like it moved but didn't. Read-only.
找出「看起来发生了、其实没有」的钱。只读。

Input: the normalized CSV from `bills.py export` (or any CSV with the same columns —
map your bookkeeping app's export to them). Three pair types, matched in this order:
输入：`bills.py export` 生成的统一 CSV（或任何同列名的 CSV，记账 App 导出可自行映射）。

  3  cross-source duplicate  same direction, same amount, different source, ≤10 min apart
     跨源重复               同方向同金额、来源不同、间隔 ≤10 分钟（日期精度的源按同日±1天）
                            e.g. a JD order paid by bank card shows up in JD *and* the bank
  2  round trip             out to X, then back from X, same amount, ≤30 days
     原路返回               转给 X 后 X 原额转回，≤30 天 → 多为真实资金周转，不是消费/收入
  1  offset pair            one expense + one income, same amount, ≤24 h, any counterparty
     一收一支               同额一收一支，≤24 小时 → 多为代付、平账、退款另记

Each record is used by at most one pair. Pairs are candidates, not verdicts.
每条记录最多进一组。配对是候选，不是结论——逐组人工确认。

Usage / 用法:
  python3 roundtrip.py all.csv [more.csv ...] [--csv pairs.csv]
"""
import argparse
import csv
import datetime as dt
import hashlib
import sys
from decimal import Decimal

EXPENSE, INCOME = '支出', '收入'
DUP_WINDOW = dt.timedelta(minutes=10)
OFFSET_WINDOW = dt.timedelta(hours=24)
TRIP_WINDOW = dt.timedelta(days=30)


def prepare(records):
    """Keep income/expense rows and add parsed time/amount. Works on CSV rows or parser output."""
    out = []
    for r in records:
        if r.get('direction') not in (EXPENSE, INCOME):
            continue
        r = dict(r)
        t = str(r.get('time') or '').strip()
        try:
            r['_t'] = dt.datetime.strptime(t, '%Y-%m-%d %H:%M:%S')
            r['_dateonly'] = False
        except ValueError:
            try:
                r['_t'] = dt.datetime.strptime(t[:10], '%Y-%m-%d')
                r['_dateonly'] = True
            except ValueError:
                continue
        r['_a'] = Decimal(str(r['amount']))
        r['currency'] = r.get('currency') or 'CNY'
        out.append(r)
    out.sort(key=lambda r: r['_t'])
    return out


def load(paths):
    rows = []
    for p in paths:
        with open(p, newline='', encoding='utf-8-sig') as fh:
            rows.extend(csv.DictReader(fh))
    return prepare(rows)


def pair_id(a, b):
    """Stable id so a confirmation survives re-runs. / 稳定 id，重跑后确认结果仍可对上。"""
    key = '|'.join(f"{r.get('source')}/{r.get('time')}/{r['_a']}/{r.get('order_id') or ''}" for r in (a, b))
    return hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]


def _close(a, b, window):
    if a['_dateonly'] or b['_dateonly']:
        return abs((a['_t'].date() - b['_t'].date()).days) <= max(1, window.days)
    return abs(a['_t'] - b['_t']) <= window


def _pairs(data, used, want, window):
    """Greedy nearest-first matching within a time window."""
    pairs = []
    horizon = max(window, dt.timedelta(days=2))  # 日期精度的记录按 ±1 天比
    for i, a in enumerate(data):
        if i in used:
            continue
        best = None
        for j in range(i + 1, len(data)):
            b = data[j]
            if b['_t'] - a['_t'] > horizon:
                break
            if j in used or b['_a'] != a['_a'] or b['currency'] != a['currency']:
                continue
            if want(a, b) and _close(a, b, window):
                best = j
                break
        if best is not None:
            used.update((i, best))
            pairs.append((a, data[best]))
    return pairs


def find_all(data):
    used = set()
    dup = _pairs(data, used, lambda a, b: a['direction'] == b['direction']
                 and a.get('source') != b.get('source'), DUP_WINDOW)
    trip = _pairs(data, used, lambda a, b: a['direction'] != b['direction']
                  and a.get('counterparty') and a.get('counterparty') == b.get('counterparty')
                  and a['direction'] == EXPENSE, TRIP_WINDOW)
    offset = _pairs(data, used, lambda a, b: {a['direction'], b['direction']} == {EXPENSE, INCOME},
                    OFFSET_WINDOW)
    return [('3', '跨源重复 cross-source duplicate', dup),
            ('2', '原路返回 round trip', trip),
            ('1', '一收一支 offset pair', offset)]


def _gap(a, b):
    if a['_dateonly'] or b['_dateonly']:
        return f"{(b['_t'].date() - a['_t'].date()).days}天"
    s = (b['_t'] - a['_t']).total_seconds()
    return f'{s:.0f}s' if s < 3600 else (f'{s / 3600:.1f}h' if s < 86400 * 2 else f'{s / 86400:.0f}天')


def _side(r):
    return f"{r.get('source', '')}:{r['direction']} {(r.get('counterparty') or '')[:14]}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--csv', help='把配对写入 CSV 以便逐组确认 / write pairs to CSV for review')
    a = ap.parse_args()

    data = load(a.paths)
    groups = find_all(data)
    print(f'记录 {len(data)} 笔（仅收入/支出）\n')
    rows = []
    for code, title, pairs in groups:
        total = sum((x['_a'] for x, _ in pairs), Decimal('0'))
        print(f'【类型{code}】{title}：{len(pairs)} 组，单边合计 {total}')
        for n, (x, y) in enumerate(sorted(pairs, key=lambda p: -p[0]['_a']), 1):
            print(f"{n:>4} {x['time'][:16]:<16} {x['_a']:>12} {x['currency']:<4} {_gap(x, y):>6}  "
                  f"{_side(x)}  ⇄  {_side(y)}")
            rows.append({'id': pair_id(x, y), 'type': code, 'amount': x['_a'], 'currency': x['currency'], 'gap': _gap(x, y),
                         'a_time': x['time'], 'a_source': x.get('source'), 'a_direction': x['direction'],
                         'a_counterparty': x.get('counterparty'), 'a_order_id': x.get('order_id'),
                         'b_time': y['time'], 'b_source': y.get('source'), 'b_direction': y['direction'],
                         'b_counterparty': y.get('counterparty'), 'b_order_id': y.get('order_id'),
                         'verdict': ''})
        print()
    print('配对只是候选：请逐组确认后再从收支分析中剔除。/ Pairs are candidates — confirm each before excluding.')
    if a.csv and rows:
        with open(a.csv, 'w', newline='', encoding='utf-8-sig') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f'→ {a.csv}', file=sys.stderr)


if __name__ == '__main__':
    main()
