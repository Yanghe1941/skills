# CN Bill Parser — Reconcile Before You Analyze

**[English]**

An agent skill for Chinese bill exports — **WeChat Pay, Alipay, JD and China Merchants Bank**. It parses each file, proves the parse against the totals the platform printed in the file itself, exports one normalized CSV, and flags money that only *looks* like it moved.

It exists because asking an agent "how much did I spend?" over raw bill exports gives a confident, wrong answer.

# 国内账单解析 — 先对账，再分析

**[中文]**

一个处理国内账单导出的 Agent 技能——**微信支付、支付宝、京东、招商银行**。逐个文件解析，用平台自己印在文件里的合计证明解析完整，导出统一格式 CSV，再找出那些「看起来发生了、其实没有」的钱。

做它，是因为直接让 AI 读原始账单回答「我花了多少钱」，会得到一个很自信的错误答案。

## What it does / 功能

| | EN | 中文 |
|---|---|---|
| **Parse** | WeChat `.xlsx`, Alipay PC `.csv` (GBK), JD `.csv`, CMB statement `.pdf` → one schema | 四种导出 → 统一字段 |
| **Reconcile** | Every file checked against its own header/footer totals (or, for the bank, a running-balance check). Any mismatch → exit 1, analysis stops | 每个文件都与自带合计对账（银行流水用逐笔余额连续性）。对不上就退出码 1，分析暂停 |
| **Refunds** | Separates the refunded part of each row so real spend = `amount − refund` | 拆出每笔的退款部分，真实支出 = `amount − refund` |
| **Report** | One local HTML file: reconciliation status, gross → refunds → confirmed pairs → real spend, monthly chart, top counterparties, pairs you tick off in the page | 一个本地 HTML 文件：对账状态、从毛额到真实支出的口径调整、按月图表、支出最多的对象、可在页面上逐组勾选的配对 |
| **Pairs** | Cross-platform duplicates, round-trip transfers, same-day offsets — listed as candidates for you to confirm | 跨平台重复、原路返回、同日一收一支——列为候选，由你确认 |

## Why / 为什么需要它

**[English]**

This came out of reconciling a real, multi-year personal ledger. Three things went wrong before the rules were written down:

- **About a quarter of WeChat's printed "expense" never happened.** WeChat's header total includes transfers the other side never accepted and orders refunded in full. Summing the export — or trusting its header — overstates spending by that much.
- **A parser's own comment was wrong.** It said JD's printed expense total was gross. It is net of refunds (so is Alipay's). For years the check flagged most files as mismatched, and the flag was noise instead of signal. Now each rule is verified against real exports before it goes into the check.
- **Money that went out and came back looked like spending plus income.** A transfer to a person that returns two weeks later inflates both sides. So does a JD order paid by bank card, which shows up in JD *and* in the bank statement.

**[中文]**

这个技能来自一次真实的多年个人账本对账。在把规则写下来之前，踩过三个坑：

- **微信页眉的「支出」合计里，约四分之一从未真实发生。** 它把对方未收款退回的转账、全额退款的订单都算了进去。直接加总导出、或相信页眉合计，支出就被高估这么多。
- **解析脚本自己的注释写错了。** 注释说京东页眉的支出是毛额，实际是扣除退款后的净额（支付宝也是）。结果多年来大部分文件都报「对不上」，警告变成了噪音。现在每条对账规则都先在真实导出上验证，才写进检查。
- **转出去又转回来的钱，看起来像一笔支出加一笔收入。** 转给朋友、两周后原额还回，两边都被放大；用银行卡付的京东订单，京东和银行流水里各记一次。

## Example / 效果

> **You:** Here are my WeChat, Alipay and JD bills for last year. How much did I actually spend?
>
> **AI:** All 3 files reconcile with their own totals ✓. Before the number: WeChat's printed expense includes ¥X of refunded transactions, and I found 4 candidate pairs — 1 JD order also paid through WeChat, 2 transfers to the same person returned within 30 days, 1 same-day offset. Real spend is ¥Y if all 4 pairs are what they look like. Want to go through them one by one?

> **你：** 这是我去年的微信、支付宝、京东账单，我实际花了多少？
>
> **AI：** 3 个文件都和自带合计对上了 ✓。给数字之前先说明：微信页眉的支出里有 ¥X 是已退款交易；另外找到 4 组候选配对——1 笔京东订单在微信里也记了一次，2 笔转给同一个人的钱 30 天内原额转回，1 组同日一收一支。如果这 4 组都属实，真实支出是 ¥Y。要逐组过一遍吗？

## The report / 报表

```bash
python3 scripts/report.py ~/Downloads/bills/ -o ~/Desktop/bill-report.html
# tick pairs in the page → 导出确认结果 → then / 页面勾选并导出后：
python3 scripts/report.py ~/Downloads/bills/ -o ~/Desktop/bill-report.html --confirmed pairs-confirmed.csv
```

**[English]** Private by construction, not by promise:

- A single file with no external resources. A Content-Security-Policy (`default-src 'none'`) blocks every network request, so the page cannot send your data anywhere even if someone edits it.
- It contains only time, amount, direction and counterparty — no order ids, item names, notes, payment methods or balances.
- Your ticks stay in your own browser's local storage.
- `--mask` turns names into `张*` and file names into `wechat-1` for screenshots.
- It warns you if you write the report inside a git repo that doesn't ignore it.

**[中文]** 隐私靠代码保证，不靠承诺：

- 单文件、零外链；CSP（`default-src 'none'`）禁止一切网络请求，就算页面被改动也发不出数据。
- 只含时间、金额、方向、交易对方；不含订单号、商品名、备注、支付方式、余额。
- 勾选状态只存在你自己浏览器的本地存储里。
- `--mask` 把人名变成 `张*`、文件名变成 `wechat-1`，方便截图。
- 报表写进未忽略它的 git 仓库时会发出警告。

Never publish the report. / 报表不要发布或上传。

## Installation / 安装

```bash
npx skills add Yanghe1941/skills --skill cn-bill-parser
```

Python 3.8+, standard library only. CMB PDFs additionally need `pip install pdfplumber`.
需要 Python 3.8+，只用标准库；招行 PDF 需另装 `pdfplumber`。

## Run it yourself / 直接运行

```bash
python3 scripts/bills.py check  ~/Downloads/bills/
python3 scripts/bills.py export ~/Downloads/bills/ -o all.csv
python3 scripts/roundtrip.py all.csv --csv pairs.csv
python3 scripts/report.py  ~/Downloads/bills/ -o ~/Desktop/bill-report.html
python3 tests/test_bills.py        # synthetic fixtures, no real data / 合成数据测试
```

## Limits / 局限

| | EN | 中文 |
|---|---|---|
| Formats | Only the four exports above. Alipay's mobile "个人对账" export and WeChat CSV are **not** supported yet — they're reported as unrecognized, not guessed | 仅支持上述四种。支付宝手机端「个人对账」导出、微信 CSV **暂不支持**，会标为无法识别，不硬猜 |
| CMB | Column positions are tuned to one PDF layout. The ported parser has not yet been re-run on a real statement; a layout change shows up as balance breaks | 列坐标针对一种版式；移植后的版本尚未在真实流水上复测，版式变化会以「余额不连续」暴露 |
| Pairs | Heuristics. Two unrelated ¥50 payments can pair up. That's why nothing is excluded without your confirmation | 启发式规则，两笔无关的 50 元也可能被配上，所以一律由你确认后才剔除 |
| Privacy | Everything runs locally; the skill tells the agent not to upload or paste bill rows | 全程本地运行；技能要求 Agent 不上传、不整行贴出账单 |

Details: [`references/formats.md`](references/formats.md)
