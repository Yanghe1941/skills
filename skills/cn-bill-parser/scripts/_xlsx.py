"""Minimal .xlsx reader, standard library only. / 只用标准库的 xlsx 读取器。

Enough for bill exports: shared strings, inline strings, first-level sheets.
足够读取账单导出：共享字符串、内联字符串、各工作表。
"""
import re
import zipfile
from xml.etree import ElementTree as ET

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def load(path):
    """Return (zipfile, shared_strings, [(sheet_name, xml_path), ...])."""
    z = zipfile.ZipFile(path)
    ss = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall(NS + 'si'):
            ss.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = {r.get('Id'): r.get('Target')
            for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheets = []
    for sh in wb.find(NS + 'sheets'):
        tgt = rels[sh.get(RNS + 'id')]
        if not tgt.startswith('xl/'):
            tgt = 'xl/' + tgt.lstrip('/')
        sheets.append((sh.get('name'), tgt))
    return z, ss, sheets


def rows(z, ss, target):
    """Yield (row_number, {column_letter: text_or_None})."""
    root = ET.fromstring(z.read(target))
    for row in root.iter(NS + 'row'):
        cells = {}
        for c in row.findall(NS + 'c'):
            col = re.match(r'[A-Z]+', c.get('r')).group()
            t, v, inline = c.get('t'), c.find(NS + 'v'), c.find(NS + 'is')
            if t == 'inlineStr' and inline is not None:
                val = ''.join(x.text or '' for x in inline.iter(NS + 't'))
            elif v is None:
                val = None
            elif t == 's':
                val = ss[int(v.text)]
            else:
                val = v.text
            cells[col] = val
        yield row.get('r'), cells


def first_sheet_rows(path):
    z, ss, sheets = load(path)
    return list(rows(z, ss, sheets[0][1]))
