"""End-to-end tests on synthetic exports (no real data). / 用合成账单做端到端测试，不含真实数据。

Run / 运行:  python3 tests/test_bills.py
"""
import csv
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from parsers import wechat_refund  # noqa: E402
from decimal import Decimal  # noqa: E402


def excel_serial(ts):
    import datetime as dt
    t = dt.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
    return (t - dt.datetime(1899, 12, 30)).total_seconds() / 86400


def write_xlsx(path, rows):
    """Minimal xlsx: numbers as <v>, strings as inline strings."""
    def cell(ref, v):
        if isinstance(v, float):
            return f'<c r="{ref}"><v>{v!r}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
    body = ''.join(
        f'<row r="{i}">' + ''.join(cell(f'{"ABCDEFGHIJK"[j]}{i}', v) for j, v in enumerate(r) if v != '')
        + '</row>' for i, r in enumerate(rows, 1))
    ns = 'http://schemas.openxmlformats.org'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', f'<Types xmlns="{ns}/package/2006/content-types"/>')
        z.writestr('xl/workbook.xml',
                   f'<workbook xmlns="{ns}/spreadsheetml/2006/main" xmlns:r="{ns}/officeDocument/2006/relationships">'
                   '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels',
                   f'<Relationships xmlns="{ns}/package/2006/relationships">'
                   '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',
                   f'<worksheet xmlns="{ns}/spreadsheetml/2006/main"><sheetData>{body}</sheetData></worksheet>')


WECHAT_TX = [  # 交易时间, 类型, 对方, 商品, 收支, 金额, 方式, 状态
    ('2023-03-01 12:00:00', '商户消费', '示例便利店', '零食', '支出', '¥30.50', '零钱', '支付成功'),
    ('2023-03-02 09:00:00', '转账', '张三', '/', '支出', '¥300.00', '零钱', '已全额退款'),
    ('2023-03-05 10:00:00', '转账', '李四', '/', '支出', '¥50.00', '零钱', '已退款(¥20.00)'),
    ('2023-03-05 18:00:00', '转账', '赵六', '/', '收入', '¥50.00', '/', '已存入零钱'),
    ('2023-03-05 20:00:00', '转账', '李四', '/', '收入', '¥100.00', '/', '已存入零钱'),
    ('2023-03-10 08:00:00', '转账', '王五', '/', '支出', '¥200.00', '零钱', '对方已收钱'),
    ('2023-03-20 08:00:00', '转账', '王五', '/', '收入', '¥200.00', '/', '已存入零钱'),
]


def make_wechat(path, expense_total='580.50'):
    head = [['微信支付账单明细'], ['起始时间：[2023-03-01 00:00:00] 终止时间：[2023-03-31 23:59:59]'],
            ['导出时间：[2023-04-01 10:00:00]'], [''], [f'共{len(WECHAT_TX)}笔记录'],
            ['收入：3笔 350.00元'], [f'支出：4笔 {expense_total}元'], ['中性交易：0笔 0.00元'],
            ['----------------------微信支付账单明细列表--------------------'],
            ['交易时间', '交易类型', '交易对方', '商品', '收/支', '金额(元)', '支付方式', '当前状态',
             '交易单号', '商户单号', '备注']]
    body = [[excel_serial(t[0]), *t[1:], f'W{i:04d}', '', '/'] for i, t in enumerate(WECHAT_TX)]
    write_xlsx(path, head + body)


def make_jd(path):
    text = ('导出信息：\n京东账号名：demo\n日期区间：2023-03-01 至 2023-03-31\n导出时间：2023-04-01 10:00:00\n'
            '共：2笔记录\n收入：0笔，0.00元\n支出：2笔，69.40元\n不计收支：0笔，0.00元\n\n'
            '交易时间,商户名称,交易说明,金额,支付方式,交易状态,收/支,交易分类,交易订单号,商家订单号,备注\n'
            '2023-03-01 12:05:00,示例商城,零食,30.50,银行卡,交易成功,支出,食品,J001,,\n'
            '2023-03-08 15:00:00,示例商城,日用品,44.00(已退款5.10),京东余额,交易成功,支出,日用,J002,,\n')
    Path(path).write_bytes(text.encode('utf-8-sig'))


def make_alipay(path):
    cols = ('交易号                  ,商家订单号               ,交易创建时间,付款时间,最近修改时间,交易来源地,类型,交易对方,商品名称,'
            '金额（元）,收/支,交易状态,服务费（元）,成功退款（元）,备注,资金状态,')
    rows = ['A001,M1,2023-03-03 11:00:00,2023-03-03 11:00:05,2023-03-03 11:00:05,其他（包括阿里巴巴和外部商家）,'
            '即时到账交易,示例餐厅,午餐,88.00,支出,交易成功,0.00,0.00,,已支出,',
            'A002,,2023-03-04 09:00:00,,2023-03-04 09:00:00,支付宝网站,支付宝担保交易,余额宝,转入,'
            '12.00,,交易成功,0.00,0.00,,资金转移,']
    lines = ['支付宝交易记录明细查询', '账号:[demo]',
             '起始日期:[2023-03-01 00:00:00]    终止日期:[2023-04-01 00:00:00]',
             '---------------------------------交易记录明细列表------------------------------------',
             cols, *rows,
             '------------------------------------------------------------------------------------',
             '共2笔记录', '已收入:0笔,0.00元', '待收入:0笔,0.00元', '已支出:1笔,88.00元', '待支出:0笔,0.00元',
             '导出时间:[2023-04-01 10:00:00]', '']
    Path(path).write_bytes('\r\n'.join(lines).encode('gbk'))


def make_demo(folder, seed=7):
    """A fake but realistic year of bills for the demo report. / 伪造的一年账单，仅用于演示。"""
    import random
    import datetime as dt
    rnd = random.Random(seed)
    folder = Path(folder)
    tx = []
    shops = [('示例超市', 40, 260), ('示例咖啡', 18, 38), ('示例外卖', 25, 80), ('示例地铁', 3, 8),
             ('示例电商', 60, 600), ('示例健身房', 99, 99), ('示例电影院', 45, 120)]
    d = dt.datetime(2024, 1, 1, 8)
    while d < dt.datetime(2025, 3, 31):
        for _ in range(rnd.randint(1, 3)):
            name, lo, hi = rnd.choice(shops)
            t = d + dt.timedelta(minutes=rnd.randint(0, 780))
            status = '已全额退款' if rnd.random() < 0.03 else '支付成功'
            tx.append((t, '商户消费', name, '支出', f'{rnd.uniform(lo, hi):.2f}', status))
        if d.day == 5:
            tx.append((d + dt.timedelta(hours=2), '转账', '示例房东', '支出', '3200.00', '对方已收钱'))
        if d.day == 10:
            tx.append((d + dt.timedelta(hours=3), '工资', '示例公司', '收入', '15000.00', '已存入零钱'))
        d += dt.timedelta(days=1)
    # round trips and an offset pair / 原路返回与一收一支
    for day, amt, who in ((dt.datetime(2024, 3, 2, 20), '5000.00', '张三'),
                          (dt.datetime(2024, 9, 12, 21), '2000.00', '李四')):
        tx.append((day, '转账', who, '支出', amt, '对方已收钱'))
        tx.append((day + dt.timedelta(days=18), '转账', who, '收入', amt, '已存入零钱'))
    tx.append((dt.datetime(2024, 6, 8, 19), '转账', '王五', '支出', '468.00', '对方已收钱'))
    tx.append((dt.datetime(2024, 6, 8, 23), '转账', '赵六', '收入', '468.00', '已存入零钱'))
    tx.append((dt.datetime(2024, 11, 3, 9), '转账', '钱七', '支出', '1000.00', '已全额退款'))
    tx.sort()

    exp = [x for x in tx if x[3] == '支出']
    inc = [x for x in tx if x[3] == '收入']
    total = lambda xs: f"{sum(Decimal(x[4]) for x in xs):.2f}"  # noqa: E731
    head = [['微信支付账单明细'], ['起始时间：[2024-01-01 00:00:00] 终止时间：[2025-03-31 23:59:59]'],
            [f'共{len(tx)}笔记录'], [f'收入：{len(inc)}笔 {total(inc)}元'],
            [f'支出：{len(exp)}笔 {total(exp)}元'], ['中性交易：0笔 0.00元'],
            ['交易时间', '交易类型', '交易对方', '商品', '收/支', '金额(元)', '支付方式', '当前状态',
             '交易单号', '商户单号', '备注']]
    body = [[excel_serial(f'{t:%Y-%m-%d %H:%M:%S}'), k, who, '/', io, f'¥{a}', '零钱', st, f'D{i:05d}', '', '/']
            for i, (t, k, who, io, a, st) in enumerate(tx)]
    write_xlsx(folder / 'wechat-demo.xlsx', head + body)

    # JD: two orders paid by bank card that WeChat also recorded → cross-source duplicates
    dup = [x for x in exp if x[2] == '示例电商'][:2]
    lines = [f'{(t + dt.timedelta(minutes=2)):%Y-%m-%d %H:%M:%S},示例电商,订单,{a},银行卡,交易成功,支出,购物,J{i},,'
             for i, (t, _k, _w, _io, a, _s) in enumerate(dup)]
    jd = ('日期区间：2024-01-01 至 2025-03-31\n'
          f'共：{len(lines)}笔记录\n收入：0笔，0.00元\n支出：{len(lines)}笔，{total(dup)}元\n不计收支：0笔，0.00元\n'
          '交易时间,商户名称,交易说明,金额,支付方式,交易状态,收/支,交易分类,交易订单号,商家订单号,备注\n'
          + '\n'.join(lines) + '\n')
    (folder / 'jd-demo.csv').write_bytes(jd.encode('utf-8-sig'))


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


class BillsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        make_wechat(self.tmp / 'wechat.xlsx')
        make_jd(self.tmp / 'jd.csv')
        make_alipay(self.tmp / 'alipay.csv')

    def test_check_reconciles_all_formats(self):
        r = run(SCRIPTS / 'bills.py', 'check', self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count('✓'), 3, r.stdout)
        self.assertIn('[wechat]', r.stdout)
        self.assertIn('[alipay]', r.stdout)
        self.assertIn('[jd]', r.stdout)

    def test_unrelated_files_are_skipped_not_misread(self):
        # a bookkeeping-app CSV that mentions 京东 and 交易号, a stray PDF, a random xlsx
        (self.tmp / 'ledger.csv').write_bytes('日期,类型,金额,备注\n2023-03-01,支出,30,京东 交易号123\n'
                                               .encode('utf-8-sig'))
        (self.tmp / 'other.pdf').write_bytes(b'%PDF-1.4\n%%EOF\n')
        write_xlsx(self.tmp / 'notes.xlsx', [['交易时间', '金额'], ['2023-03-01', '1']])
        r = run(SCRIPTS / 'bills.py', 'check', self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.count('✓'), 3, r.stdout)
        for name in ('ledger.csv', 'other.pdf', 'notes.xlsx'):
            self.assertIn(name, r.stderr)
        out = self.tmp / 'r.html'
        self.assertEqual(run(SCRIPTS / 'report.py', self.tmp, '-o', out).returncode, 0)
        self.assertTrue(out.exists())

    def test_check_fails_when_totals_disagree(self):
        make_wechat(self.tmp / 'wechat.xlsx', expense_total='999.99')
        r = run(SCRIPTS / 'bills.py', 'check', self.tmp / 'wechat.xlsx')
        self.assertEqual(r.returncode, 1)
        self.assertIn('⚠', r.stdout)

    def test_export_and_roundtrip(self):
        out = self.tmp / 'all.csv'
        r = run(SCRIPTS / 'bills.py', 'export', self.tmp, '-o', out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with out.open(encoding='utf-8-sig') as fh:
            recs = list(csv.DictReader(fh))
        self.assertEqual(len(recs), 7 + 2 + 2)
        refunds = {x['counterparty']: x['refund'] for x in recs
                   if x['source'] == 'wechat' and x['direction'] == '支出'}
        self.assertEqual(refunds['张三'], '300.00')
        self.assertEqual(refunds['李四'], '20.00')

        pairs = self.tmp / 'pairs.csv'
        r = run(SCRIPTS / 'roundtrip.py', out, '--csv', pairs)
        self.assertEqual(r.returncode, 0, r.stderr)
        with pairs.open(encoding='utf-8-sig') as fh:
            got = {(p['type'], p['amount']) for p in csv.DictReader(fh)}
        self.assertEqual(got, {('3', '30.50'), ('2', '200.00'), ('1', '50.00')})

    def test_report_is_local_and_private(self):
        demo = self.tmp / 'demo'
        demo.mkdir()
        make_demo(demo)
        out = self.tmp / 'r.html'
        r = run(SCRIPTS / 'report.py', demo, '-o', out)
        self.assertEqual(r.returncode, 0, r.stderr)
        page = out.read_text(encoding='utf-8')
        self.assertIn("default-src 'none'", page)
        for bad in ('http://', 'https://', '<link', 'src="', '@import', 'D00001', 'J0'):
            self.assertNotIn(bad, page)
        self.assertIn('✓ 一致', page)
        self.assertIn('张三', page)

        masked = self.tmp / 'm.html'
        run(SCRIPTS / 'report.py', demo, '-o', masked, '--mask')
        page = masked.read_text(encoding='utf-8')
        for name in ('张三', '示例房东', 'wechat-demo.xlsx'):
            self.assertNotIn(name, page)
        self.assertIn('张*', page)

    def test_report_applies_confirmed_pairs(self):
        demo = self.tmp / 'demo'
        demo.mkdir()
        make_demo(demo)
        allcsv, pairs = self.tmp / 'all.csv', self.tmp / 'pairs.csv'
        run(SCRIPTS / 'bills.py', 'export', demo, '-o', allcsv)
        run(SCRIPTS / 'roundtrip.py', allcsv, '--csv', pairs)
        with pairs.open(encoding='utf-8-sig') as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(sorted(p['type'] for p in rows), ['1', '2', '2', '3', '3'])
        for p in rows:
            p['verdict'] = '确认'
        with pairs.open('w', newline='', encoding='utf-8-sig') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        before = run(SCRIPTS / 'report.py', demo, '-o', self.tmp / 'a.html')
        after = run(SCRIPTS / 'report.py', demo, '-o', self.tmp / 'b.html', '--confirmed', pairs)
        self.assertEqual(before.returncode, 0)
        self.assertEqual(after.returncode, 0)
        self.assertIn('− 已确认配对', (self.tmp / 'b.html').read_text(encoding='utf-8'))
        self.assertNotIn('− 已确认配对', (self.tmp / 'a.html').read_text(encoding='utf-8'))

    def test_wechat_refund_parsing(self):
        amt = Decimal('780.42')
        self.assertEqual(wechat_refund('已退款(¥88.00)', amt), Decimal('88.00'))
        self.assertEqual(wechat_refund('已退款（¥88.00）', amt), Decimal('88.00'))
        self.assertEqual(wechat_refund('已全额退款', amt), amt)
        self.assertEqual(wechat_refund('对方已退还', amt), amt)
        self.assertEqual(wechat_refund('支付成功', amt), Decimal('0'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
