#!/usr/bin/env python3
"""Parse Chinese bill exports, prove the parse against the platform's own totals,
and export one normalized CSV. Read-only on the source files.
解析国内账单导出，用平台自带合计证明解析完整，再导出统一格式 CSV。不修改源文件。

Usage / 用法:
  python3 bills.py check  <file-or-dir> ...            # reconcile only / 只对账
  python3 bills.py export <file-or-dir> ... -o all.csv # normalized CSV / 导出统一 CSV

Supported / 支持: WeChat Pay .xlsx · Alipay PC .csv (GBK) · JD .csv · CMB bank statement .pdf
Exit code 1 if any file fails reconciliation. / 任一文件对账失败时退出码为 1。
"""
import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parsers import EXPENSE, FIELDS, PARSERS, detect, has_pdfplumber  # noqa: E402

EXTS = {'.xlsx', '.csv', '.pdf'}


def expand(paths):
    for p in map(Path, paths):
        if p.is_dir():
            yield from sorted(f for f in p.rglob('*') if f.suffix.lower() in EXTS)
        else:
            yield p


def run(paths):
    results, failed, skipped = [], False, []
    for f in expand(paths):
        kind = detect(f)
        if not kind:
            skipped.append(f)
            continue
        parse, check = PARSERS[kind]
        try:
            recs, official = parse(f)
        except StopIteration:
            print(f'✗  {f.name}: 找不到表头 / header row not found', file=sys.stderr)
            failed = True
            continue
        checks = check(recs, official)
        ok = all(o is not None and abs(Decimal(p) - Decimal(o)) < Decimal('0.02')
                 for _, p, o in checks)
        failed |= not ok
        results.append((f, kind, recs, official, checks, ok))
    if skipped:
        pdfs = [f for f in skipped if f.suffix.lower() == '.pdf']
        print(f'·  跳过 {len(skipped)} 个不是受支持账单的文件（如记账 App 导出、其他文件）/ '
              f'skipped {len(skipped)} file(s) that are not a supported bill export', file=sys.stderr)
        for f in skipped:
            print(f'     - {f.name}', file=sys.stderr)
        if pdfs and not has_pdfplumber():
            print(f'·  其中 {len(pdfs)} 个 PDF 未识别：招行流水需先 pip install pdfplumber / '
                  f'{len(pdfs)} PDF(s) unchecked — CMB statements need pdfplumber', file=sys.stderr)
    if not results:
        print('✗  没有找到任何受支持的账单文件 / no supported bill export found', file=sys.stderr)
        failed = True
    return results, failed


def report(results, out):
    for f, kind, recs, official, checks, ok in results:
        rng = official.get('range')
        span = f'{rng[0]} → {rng[1]}' if rng else (
            f"{recs[0]['time'][:10]} → {recs[-1]['time'][:10]}" if recs else '')
        print(f"{'✓' if ok else '⚠'}  [{kind}] {f.name}  {len(recs)} 笔  {span}", file=out)
        for label, parsed, off in checks:
            mark = '' if off is not None and abs(Decimal(parsed) - Decimal(off)) < Decimal('0.02') else '  ⚠'
            print(f"     {label:<28} 解析 {parsed}  官方 {'缺失 missing' if off is None else off}{mark}", file=out)
        refunded = [r for r in recs if r['direction'] == EXPENSE and r['refund'] > 0]
        if refunded:
            gross = sum((r['amount'] for r in recs if r['direction'] == EXPENSE), Decimal('0'))
            ref = sum((r['refund'] for r in refunded), Decimal('0'))
            share = f'{ref / gross * 100:.1f}%' if gross else '-'
            print(f"     退款 refunds                  {len(refunded)} 笔 {ref}（占支出口径 {share}）"
                  f" — 分析时用 amount − refund / use amount − refund for analysis", file=out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['check', 'export'])
    ap.add_argument('paths', nargs='+')
    ap.add_argument('-o', '--out', help='export 目标 CSV（默认输出到 stdout）')
    a = ap.parse_args()

    results, failed = run(a.paths)
    report(results, sys.stdout if a.cmd == 'check' else sys.stderr)

    if a.cmd == 'export':
        if failed:
            print('⚠ 有文件未通过对账，仍然导出——请先看上面的 ⚠ 行 / '
                  'some files failed reconciliation; exported anyway, review ⚠ lines first',
                  file=sys.stderr)
        fh = open(a.out, 'w', newline='', encoding='utf-8-sig') if a.out else sys.stdout
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        allrecs = sorted((r for res in results for r in res[2]), key=lambda r: r['time'])
        for r in allrecs:
            w.writerow(r)
        if a.out:
            fh.close()
            print(f'→ {a.out}  {len(allrecs)} 笔', file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
