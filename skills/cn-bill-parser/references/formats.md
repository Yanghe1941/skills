# Formats & quirks / 格式与坑

Entry paths inside each app change between versions — treat them as hints.
各 App 的导出入口会随版本变化，下列路径仅供参考。

## Verification status / 验证状态

| Source / 来源 | File / 文件 | Self-check / 自校验 | Verified on real exports / 真实数据验证 |
|---|---|---|---|
| WeChat Pay 微信支付 | `.xlsx` from 账单中心 · 下载账单 · 用于个人对账 | header totals: record count, expense count, expense total | ✓ multi-year real exports, all match |
| Alipay 支付宝 | `.csv` (GBK) from the **PC** 交易记录 download, header row starts with `交易号` | footer 已支出 count + net amount | ✓ multi-year real exports, all match |
| JD 京东 | `.csv` (UTF-8 BOM) 交易流水, header row starts with `交易时间,商户名称` | header record count, expense count, net expense | ✓ multi-year real exports, all match |
| CMB 招商银行 | 交易流水 `.pdf` (一网通 layout) | running balance: `balance[i] == balance[i-1] + amount[i]` | ✓ once (thousands of rows, 0 breaks) with the original script; **the ported version has not been re-run on a real PDF yet** |

**Not supported yet / 暂不支持**: Alipay's mobile "个人对账" export (columns start `交易时间,交易分类`), WeChat CSV exports, other banks. `bills.py` reports them as `?` and skips — it does not guess.
支付宝手机端「个人对账」导出、微信 CSV、其他银行暂不支持，会标 `?` 并跳过，不硬猜。

## Normalized columns / 统一字段

| Column | Meaning |
|---|---|
| `source` | `wechat` / `alipay` / `jd` / `cmb` |
| `time` | `YYYY-MM-DD HH:MM:SS`; CMB is date-only `YYYY-MM-DD` |
| `direction` | `支出` / `收入` / `不计收支` |
| `amount` | gross, always positive / 毛额，恒为正 |
| `refund` | refunded part of this row; real spend = `amount − refund` / 本笔退回部分 |
| `counterparty`, `item`, `method`, `status`, `order_id`, `note` | as exported, lightly cleaned |
| `balance` | CMB only / 仅招行 |

To feed `roundtrip.py` from any other source (e.g. a bookkeeping app), produce a CSV with at least `source, time, direction, amount, currency, counterparty`.
其他来源（如记账 App）只要映射出上述最少字段，也能喂给 `roundtrip.py`。

## Quirks that change the numbers / 会改变结论的坑

| Source | Quirk / 坑 | How it's handled / 处理 |
|---|---|---|
| WeChat | The printed **支出 total includes refunded transactions** — transfers the other side never accepted, orders refunded in full. In one real multi-year ledger this was about a quarter of the printed expense. | Reconcile against the raw gross (so the check still proves completeness), put the refunded part in `refund`. `已退款(¥x)` → partial `x`; `已全额退款` / `对方已退还` / `退款中` → full amount (conservative). |
| WeChat | Dates are Excel serial numbers, not text. | Converted; text dates also accepted. |
| Alipay | GBK encoding, CRLF line ends, page header *and* footer around the table. Printed 已支出 is **net of refunds**. | Split on CRLF only (cells may contain bare `\n`); check against `amount − refund`. |
| JD | Amount cells like `44.00(已退款5.10)`. Printed 支出 is **net of refunds**. | Gross → `amount`, `5.10` → `refund`; check against net. |
| JD | JD itself warns: non-balance payments also appear in your bank statement. | `roundtrip.py` type 3 (cross-source duplicate). |
| CMB | 交易摘要/对手信息 wrap, and wrapped text is vertically centered — it can sit *above* its date. | Rows are cut by date anchors at the midpoint between neighbours, not by text lines. Column x-ranges are tuned to one layout; a new layout will show balance breaks rather than silently mis-parse. |
| CMB | First row picks up page-header text, last row the footer notice. | Fields re-extracted by regex; first-row date back-filled. |
| All | Transfers to a person that come back later look like spending + income. | `roundtrip.py` type 2 (round trip), type 1 (same-day offset). |

## Pair types / 配对类型（`roundtrip.py`）

Matched in this order; each record joins at most one pair.
按此顺序匹配，每条记录最多进一组。

| Type | Rule | Usually means / 通常意味着 |
|---|---|---|
| 3 cross-source duplicate | same direction, same amount, different `source`, ≤10 min (date-only sources: ±1 day) | the same payment seen by two platforms / 同一笔钱在两个平台各记一次 |
| 2 round trip | expense to X, then income from X, same amount, ≤30 days | money lent/parked and returned — cash flow, not consumption / 资金周转，非消费 |
| 1 offset pair | one expense + one income, same amount, ≤24 h, any counterparty | paying on someone's behalf, refund booked as income, balancing entries / 代付、退款另记、平账 |
