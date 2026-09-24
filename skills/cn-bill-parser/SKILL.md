---
name: cn-bill-parser
description: "Parse Chinese bill exports (WeChat Pay, Alipay, JD, China Merchants Bank), prove every file against the platform's own printed totals before any analysis, then flag money that only looks like it moved — refunds counted as spending, round-trip transfers, cross-platform duplicates. Use when the user shares 微信/支付宝/京东/招行 bill exports or asks about spending, cash flow or reconciliation from them. 国内账单解析与对账：先用平台自带合计证明解析完整，再找出「看起来花了、其实没花」的钱（退款、原路返回、跨平台重复）。用户提到「微信账单」「支付宝账单」「京东流水」「招行流水」「对账」「消费分析」「现金流」时使用。"
---

# CN Bill Parser / 国内账单解析与对账

Reconcile first, analyze second. A bill total you haven't proven against the platform's own number is a guess — and in Chinese bill exports the gap is often large, because refunds, round trips and cross-platform duplicates all look like spending.

先对账，再分析。没跟平台自带合计对上的数字只是猜测——国内账单里退款、原路返回、跨平台重复都长得像消费，差额往往很大。

## When to activate / 何时启用

| Situation / 场景 | What to do / 做法 |
|---|---|
| User shares or points to bill exports | Full flow below / 走下方完整流程 |
| User asks "how much did I spend" from bills | Full flow — never sum raw rows / 走完整流程，不直接加总原始行 |
| Only one small file, one quick question | Still run `check` first; skip `roundtrip` if single-source / 仍先 `check`，单一来源可跳过配对 |

## Scripts / 脚本

All in `scripts/` next to this file — call them by absolute path. Standard library only, except CMB PDF which needs `pdfplumber`.
脚本都在本文件旁的 `scripts/`，用绝对路径调用。只用标准库；仅招行 PDF 需要 `pdfplumber`。

| Command | Purpose |
|---|---|
| `python3 scripts/bills.py check <files-or-dirs>` | Parse + reconcile each file against its printed totals. Exit 1 on any mismatch. / 解析并逐文件对账 |
| `python3 scripts/bills.py export <files-or-dirs> -o all.csv` | One normalized CSV across all sources. / 导出统一 CSV |
| `python3 scripts/roundtrip.py all.csv --csv pairs.csv` | Candidate pairs: cross-source duplicates, round trips, offset pairs. / 输出候选配对 |
| `python3 scripts/report.py <files-or-dirs> -o bill-report.html [--confirmed pairs-confirmed.csv] [--mask]` | One self-contained local HTML report: reconciliation, refund/pair adjustments, monthly chart, top counterparties, pairs to tick off. / 生成单文件本地 HTML 报表 |

Formats, quirks and how to get each export: [`references/formats.md`](references/formats.md).

## Steps / 步骤

1. **Locate files.** Ask where the exports are. Never ask the user to paste bill rows into chat.
   **定位文件。** 问清文件位置，不要让用户把账单内容贴进对话。
2. **`check`.** Report the ✓/⚠ table. If any file shows ⚠ or `?` (unrecognized), **stop**: say which file, which total disagrees, and that analysis would be built on an incomplete parse. Do not "adjust" numbers to make it match.
   **对账。** 汇报 ✓/⚠。任何文件 ⚠ 或无法识别就**停下**，说明哪个文件、哪项合计不符；不要为了对上而调数字。
3. **`export`** to a working folder the user picks — never into the folder holding the original exports.
   **导出**到用户指定的工作目录，不写进原始账单所在目录。
4. **`roundtrip`** when there are 2+ sources or transfers. Present each type's count and total, largest pairs first. They are **candidates**: ask the user to confirm before excluding any.
   **配对。** 多来源或含转账时运行。按类型汇报组数与金额，大额优先；配对是**候选**，剔除前逐组确认。
5. **Report (optional).** When the user wants something visual, run `report.py`. The user ticks pairs in the page, clicks 导出确认结果, and you re-run with `--confirmed <that csv>` so totals and charts drop them.
   **报表（可选）。** 用户要看图时运行 `report.py`；用户在页面勾选配对并导出确认结果后，带 `--confirmed` 重新生成。
6. **Analyze** only after 2–4, using these rules:
   **分析**，遵守以下口径：
   - Real spending = `amount − refund` for `direction == 支出`. WeChat's printed "支出" total includes refunded transactions.
     真实支出用 `amount − refund`。微信页眉的「支出」合计含已退款交易。
   - `不计收支` (transfers between own accounts, fund moves) is neither spending nor income.
     「不计收支」既不是支出也不是收入。
   - Exclude confirmed round trips and duplicates; state how much was excluded.
     剔除已确认的原路返回与重复，并写明剔除了多少。

## Output / 输出

| Section / 部分 | Content / 内容 |
|---|---|
| Reconciliation / 对账 | Per file: ✓/⚠, record count, range / 每个文件的对账结果 |
| Adjustments / 口径调整 | Refunds removed, pairs excluded, with amounts / 剔除的退款与配对金额 |
| Findings / 结论 | Each figure traceable to a file and a rule above / 每个数字可追溯到文件与口径 |
| Unknowns / 未知项 | Unconfirmed pairs, unsupported files / 未确认配对、不支持的文件 |

## Guardrails / 边界

- Read-only on the original exports. Never modify, move or delete them.
  原始账单只读，不修改、移动、删除。
- Bills are sensitive: no uploading, no pasting full rows into chat, quote only what a finding needs.
  账单是敏感数据：不上传，不整行贴出，只引用结论所需的最少信息。
- A ⚠ from `check` blocks analysis until the user decides how to proceed.
  `check` 出现 ⚠ 时，在用户决定前不做分析。
- Pairs are never auto-excluded. The user confirms each one.
  配对不自动剔除，由用户逐组确认。
- The HTML report is for the user's own machine. Never publish it, upload it, host it, or turn it into a shareable web page/artifact. Write it outside any git repo (or make sure it's ignored). For screenshots, regenerate with `--mask`.
  HTML 报表只在用户本机打开：不发布、不上传、不托管、不做成可分享网页；不要写进 git 仓库（或确认已忽略）；要截图就用 `--mask` 重新生成。
- Describe what the money did; do not give investment, tax or credit advice.
  只描述资金发生了什么，不提供投资、税务或信贷建议。
