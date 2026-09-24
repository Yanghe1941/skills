"""Parsers for Chinese bill exports. Read-only. / 国内账单导出解析器，只读。

Every parser returns (records, official) where
  records  = list of normalized dicts (see FIELDS)
  official = totals printed by the platform itself in the file header/footer,
             used by `bills.py check` to prove the parse is complete.
每个解析器返回 (记录, 官方合计)。官方合计取自文件自带的页眉/页脚，用来证明解析完整。
"""
import csv
import datetime as dt
import io
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from _xlsx import first_sheet_rows

FIELDS = ['source', 'file', 'time', 'direction', 'amount', 'refund', 'currency',
          'counterparty', 'item', 'method', 'status', 'order_id', 'note', 'balance']

EXPENSE, INCOME, NEUTRAL = '支出', '收入', '不计收支'


def _dec(s):
    s = re.sub(r'[¥￥,\s]', '', s or '')
    try:
        return Decimal(s) if s else None
    except InvalidOperation:
        return None


def _rec(**kw):
    r = {k: '' for k in FIELDS}
    r.update(kw)
    r.setdefault('currency', 'CNY')
    r['currency'] = r['currency'] or 'CNY'
    r['refund'] = r['refund'] or Decimal('0')
    return r


# ---------------------------------------------------------------- WeChat Pay
# 微信支付 · 账单中心导出的 xlsx。页眉含「共N笔记录 / 收入 / 支出 / 中性交易」。
# 日期是 Excel 序列数。⚠ 官方「支出」合计包含已退款交易——见 refund 字段。

WECHAT_COLS = ['交易时间', '交易类型', '交易对方', '商品', '收支', '金额', '支付方式',
               '当前状态', '交易单号', '商户单号', '备注']
_EXCEL_EPOCH = dt.datetime(1899, 12, 30)
_REFUND_ANY = re.compile(r'退款|已退还')
_REFUND_PART = re.compile(r'已退款\s*[(（]\s*[¥￥]?([\d,.]+)\s*[)）]')


def _wechat_time(v):
    try:
        return _EXCEL_EPOCH + dt.timedelta(days=float(v))
    except (TypeError, ValueError):
        pass
    try:
        return dt.datetime.strptime((v or '').strip(), '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def wechat_refund(status, amount):
    """How much of this WeChat transaction was refunded. / 本笔被退回多少。

    「已退款(¥88.00)」→ partial, 88.00. 「已全额退款」「对方已退还」→ full amount.
    「退款中」is counted as full too (conservative — it is on its way back).
    """
    status = status or ''
    m = _REFUND_PART.search(status)
    if m:
        return min(_dec(m.group(1)) or Decimal('0'), amount)
    return amount if _REFUND_ANY.search(status) else Decimal('0')


def parse_wechat(path):
    rs = first_sheet_rows(path)
    head = '\n'.join((c.get('A') or '') for _, c in rs[:20])
    official = {}
    m = re.search(r'共(\d+)笔记录', head)
    if m:
        official['count'] = int(m.group(1))
    for k in (INCOME, EXPENSE, '中性交易'):
        m = re.search(rf'{k}[：:]\s*(\d+)笔\s*([\d.,]+)元', head)
        if m:
            official[k] = (int(m.group(1)), _dec(m.group(2)))
    m = re.search(r'起始时间[：:]\[(.+?)\]\s*终止时间[：:]\[(.+?)\]', head)
    if m:
        official['range'] = (m.group(1), m.group(2))

    hi = next(i for i, (_, c) in enumerate(rs) if (c.get('A') or '').strip() == '交易时间')
    recs = []
    for _, c in rs[hi + 1:]:
        d = {n: (c.get(k) or '').strip() for n, k in zip(WECHAT_COLS, 'ABCDEFGHIJK')}
        t, amt = _wechat_time(d['交易时间']), _dec(d['金额'])
        if t is None or amt is None:
            continue
        direction = d['收支'] if d['收支'] in (EXPENSE, INCOME) else NEUTRAL
        recs.append(_rec(
            source='wechat', file=Path(path).name, time=t.strftime('%Y-%m-%d %H:%M:%S'),
            direction=direction, amount=amt,
            refund=wechat_refund(d['当前状态'], amt) if direction == EXPENSE else Decimal('0'),
            counterparty=d['交易对方'], item=f"{d['交易类型']}/{d['商品']}".strip('/'),
            method=d['支付方式'], status=d['当前状态'], order_id=d['交易单号'], note=d['备注']))
    return recs, official


def check_wechat(recs, official):
    exp = [r for r in recs if r['direction'] == EXPENSE]
    return [
        ('记录数 records', len(recs), official.get('count')),
        ('支出笔数 expense count', len(exp), official.get(EXPENSE, (None,))[0]),
        ('支出金额 expense total', sum((r['amount'] for r in exp), Decimal('0')),
         official.get(EXPENSE, (None, None))[1]),
    ]


# ---------------------------------------------------------------- Alipay
# 支付宝 · 电脑版「交易记录」CSV（GBK 编码、CRLF、带页眉页脚，表头以「交易号」开头）。
# 页脚含「已收入/已支出/待收入/待支出:N笔,X元」。

ALIPAY_COLS = ['交易号', '商家订单号', '交易创建时间', '付款时间', '最近修改时间', '交易来源地',
               '类型', '交易对方', '商品名称', '金额', '收支', '交易状态', '服务费', '成功退款',
               '备注', '资金状态']


def parse_alipay(path):
    raw = Path(path).read_bytes().decode('gbk', errors='replace')
    # 只按 CRLF 切：单元格里的裸 \n 属于同一条记录
    lines = raw.split('\r\n') if '\r\n' in raw else raw.split('\n')
    hi = next(i for i, l in enumerate(lines) if l.startswith('交易号'))
    fi = next((i for i, l in enumerate(lines[hi + 1:], hi + 1)
               if l.startswith('---') or l.startswith('已收入:')), len(lines))
    recs = []
    for row in csv.reader(l for l in lines[hi + 1:fi] if l.strip()):
        row = [c.strip() for c in row]
        if len(row) < 16:
            continue
        d = dict(zip(ALIPAY_COLS, row[:16]))
        amt = _dec(d['金额'])
        ts = d['付款时间'] or d['交易创建时间']
        try:
            t = dt.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        if amt is None:
            continue
        direction = d['收支'] if d['收支'] in (EXPENSE, INCOME) else NEUTRAL
        recs.append(_rec(
            source='alipay', file=Path(path).name, time=t.strftime('%Y-%m-%d %H:%M:%S'),
            direction=direction, amount=amt, refund=_dec(d['成功退款']) or Decimal('0'),
            counterparty=d['交易对方'], item=f"{d['类型']}/{d['商品名称']}".strip('/'),
            status=f"{d['交易状态']}/{d['资金状态']}", order_id=d['交易号'], note=d['备注']))
    official = {}
    for l in lines[fi:]:
        m = re.match(r'(已收入|已支出|待收入|待支出):(\d+)笔,([\d.]+)元', l)
        if m:
            official[m.group(1)] = (int(m.group(2)), _dec(m.group(3)))
    m = re.search(r'起始日期:\[(.+?)\]\s+终止日期:\[(.+?)\]', raw)
    if m:
        official['range'] = (m.group(1), m.group(2))
    return recs, official


def check_alipay(recs, official):
    # 官方「已支出」= 收支为支出、资金状态为已支出，金额是扣除成功退款后的净额
    paid = [r for r in recs if r['direction'] == EXPENSE and r['status'].endswith('/已支出')]
    return [
        ('已支出笔数 paid count', len(paid), official.get('已支出', (None,))[0]),
        ('已支出净额 paid net', sum((r['amount'] - r['refund'] for r in paid), Decimal('0')),
         official.get('已支出', (None, None))[1]),
    ]


# ---------------------------------------------------------------- JD
# 京东 · 交易流水 CSV（UTF-8 BOM，页眉含「共：N笔记录 / 支出：N笔，X元」）。
# 金额可能形如 "44.00(已退款5.10)"：毛额进 amount，退款进 refund。
# 页眉「支出」金额是扣除退款后的净额（按毛额对不上）。
# ⚠ 京东官方提示：非余额支付会同时产生银行交易，合并多源时注意重复——见 roundtrip.py 类型3。

JD_COLS = ['交易时间', '商户名称', '交易说明', '金额', '支付方式', '交易状态', '收支', '交易分类',
           '交易订单号', '商家订单号', '备注']


def parse_jd(path):
    raw = Path(path).read_bytes().decode('utf-8-sig')
    lines = raw.splitlines()
    hi = next(i for i, l in enumerate(lines) if l.startswith('交易时间,'))
    head = '\n'.join(lines[:hi])
    official = {}
    m = re.search(r'共[：:]\s*(\d+)笔记录', head)
    if m:
        official['count'] = int(m.group(1))
    for k in (INCOME, EXPENSE, NEUTRAL):
        m = re.search(rf'{k}[：:]\s*(\d+)笔(?:\(含\d+笔[^)]*\))?[，,]\s*([\d.,]+)元', head)
        if m:
            official[k] = (int(m.group(1)), _dec(m.group(2)))
    m = re.search(r'日期区间[：:]\s*(\S+)\s*至\s*(\S+)', head)
    if m:
        official['range'] = (m.group(1), m.group(2))
    recs = []
    for row in csv.reader(io.StringIO('\n'.join(lines[hi + 1:]))):
        if len(row) < 11:
            continue
        d = dict(zip(JD_COLS, [c.strip() for c in row[:11]]))
        m = re.match(r'^([\d.]+)(?:\(已退款([\d.]+)\))?$', re.sub(r'[¥￥,\s]', '', d['金额']))
        try:
            t = dt.datetime.strptime(d['交易时间'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        if not m:
            continue
        direction = d['收支'] if d['收支'] in (EXPENSE, INCOME) else NEUTRAL
        recs.append(_rec(
            source='jd', file=Path(path).name, time=t.strftime('%Y-%m-%d %H:%M:%S'),
            direction=direction, amount=Decimal(m.group(1)), refund=_dec(m.group(2)) or Decimal('0'),
            counterparty=d['商户名称'], item=f"{d['交易分类']}/{d['交易说明']}".strip('/'),
            method=d['支付方式'], status=d['交易状态'], order_id=d['交易订单号'], note=d['备注']))
    return recs, official


def check_jd(recs, official):
    exp = [r for r in recs if r['direction'] == EXPENSE]
    return [
        ('记录数 records', len(recs), official.get('count')),
        ('支出笔数 expense count', len(exp), official.get(EXPENSE, (None,))[0]),
        ('支出净额 expense net', sum((r['amount'] - r['refund'] for r in exp), Decimal('0')),
         official.get(EXPENSE, (None, None))[1]),
    ]


# ---------------------------------------------------------------- CMB (China Merchants Bank)
# 招商银行 · 一网通「交易流水」PDF。需要 pdfplumber（唯一的非标准库依赖）。
# 「交易摘要/对手信息」会折行，且折行文本垂直居中、可能出现在日期行上方——
# 所以不按文本行切，而以左侧日期词为锚点，取相邻锚点纵坐标中点作行边界。
# 自校验：逐笔 余额[i] == 余额[i-1] + 金额[i]。列坐标针对该版式，版式变了会校验失败。

CMB_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
CMB_PAGENO = re.compile(r'^\d+/\d+$')
CMB_COLS = [(30, 95, 'date'), (95, 150, 'cur'), (150, 230, 'amount'),
            (230, 300, 'balance'), (300, 410, 'type'), (410, 600, 'party')]


def _cmb_col(x0):
    return next((n for a, b, n in CMB_COLS if a <= x0 < b), None)


def parse_cmb(path):
    import pdfplumber  # detect() only routes PDFs here when it is installed
    raw = []
    with pdfplumber.open(path) as pdf:
        for pi, pg in enumerate(pdf.pages):
            ws = [w for w in pg.extract_words()
                  if 80 < w['top'] < pg.height - 25 and not CMB_PAGENO.match(w['text'])]
            anchors = sorted((w for w in ws if CMB_DATE.match(w['text']) and w['x0'] < 95),
                             key=lambda w: w['top'])
            if not anchors:
                continue
            tops = [a['top'] for a in anchors]
            bounds = [(80 if i == 0 else (tops[i - 1] + tops[i]) / 2,
                       float('inf') if i == len(tops) - 1 else (tops[i] + tops[i + 1]) / 2)
                      for i in range(len(tops))]
            page = [dict(date='', cur='', amount='', balance='', type='', party='')
                    for _ in anchors]
            for w in ws:
                c = _cmb_col(w['x0'])
                if not c:
                    continue
                for i, (lo, hi) in enumerate(bounds):
                    if lo <= w['top'] < hi:
                        page[i][c] += w['text']
                        break
            raw.extend(page)

    num = re.compile(r'-?[\d,]+\.\d\d')
    recs = []
    for r in raw:  # 首行会粘上页眉、末行会粘上页脚提示，按正则抽回干净字段
        dates = re.findall(r'\d{4}-\d{2}-\d{2}', r['date'])
        amt, bal = num.search(r['amount']), num.search(r['balance'])
        if not (amt and bal):
            continue
        a = Decimal(amt.group(0).replace(',', ''))
        recs.append(_rec(
            source='cmb', file=Path(path).name, time=dates[-1] if dates else '',
            direction=EXPENSE if a < 0 else INCOME, amount=abs(a),
            counterparty=re.sub(r'—+.*', '', r['party']),
            item=re.sub(r'—+.*|^.*(?=代发款项)', '', r['type']),
            balance=Decimal(bal.group(0).replace(',', ''))))
    # 页眉污染只会影响第 1 笔的日期
    if len(recs) > 1 and (not recs[0]['time'] or recs[0]['time'] > recs[1]['time']):
        recs[0]['time'] = recs[1]['time']
    return recs, {}


def _signed(r):
    return -r['amount'] if r['direction'] == EXPENSE else r['amount']


def check_cmb(recs, official):
    bad = 0
    if recs:
        prev = recs[0]['balance'] - _signed(recs[0])
        for r in recs:
            if r['balance'] != prev + _signed(r):
                bad += 1
            prev = r['balance']
    return [('余额连续性失败 balance breaks', bad, 0)]


# ---------------------------------------------------------------- detection

PARSERS = {'wechat': (parse_wechat, check_wechat), 'alipay': (parse_alipay, check_alipay),
           'jd': (parse_jd, check_jd), 'cmb': (parse_cmb, check_cmb)}


def has_pdfplumber():
    try:
        import pdfplumber  # noqa: F401
        return True
    except ImportError:
        return False


def _lines_start(text, prefix):
    # 真实导出的表头常在逗号前补空格（支付宝），比较前去掉所有空白
    return any(re.sub(r'\s+', '', l.lstrip('\ufeff')).startswith(prefix) for l in text.splitlines())


def detect(path):
    """Identify a file by the exact header row its parser needs — never by loose keywords.
    Returns a source key, or None (the caller skips the file). Other bookkeeping exports,
    notes or unrelated PDFs in the same folder must come back as None.
    按解析器所需的表头精确识别，不靠关键词；同目录里的记账 App 导出、其他 PDF 一律返回 None。"""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext == '.pdf':
            if not has_pdfplumber():
                return None
            import pdfplumber
            with pdfplumber.open(p) as pdf:
                first = (pdf.pages[0].extract_text() or '') if pdf.pages else ''
            return 'cmb' if '招商银行' in first else None
        if ext == '.xlsx':
            rs = first_sheet_rows(path)[:40]
            head = ' '.join((c.get('A') or '') for _, c in rs)
            header = any((c.get('A') or '').strip() == '交易时间' and (c.get('B') or '').strip() == '交易类型'
                         for _, c in rs)
            return 'wechat' if header and '微信' in head else None
        if ext == '.csv':
            data = p.read_bytes()[:16384]
            if _lines_start(data.decode('utf-8-sig', errors='ignore'), '交易时间,商户名称,交易说明'):
                return 'jd'
            if _lines_start(data.decode('gbk', errors='ignore'), '交易号,商家订单号'):
                return 'alipay'
    except Exception:  # corrupt, encrypted or not really that format / 损坏、加密或名不副实
        return None
    return None
