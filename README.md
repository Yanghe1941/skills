# Skills

Agent skills by [Yanghe1941](https://github.com/Yanghe1941) — one `SKILL.md` per skill, usable in **Claude Code, Codex CLI, Cursor, Gemini CLI and OpenClaw**.
杨鹤的 AI Agent 技能合集。每个技能一份 `SKILL.md`，可在 Claude Code、Codex CLI、Cursor、Gemini CLI、OpenClaw 中通用。

These skills come out of daily use: each one fixes a specific way agents fail at real work, turned into a reusable procedure.
这些技能来自日常实战：每个都针对 Agent 在真实工作里的一种具体失误，沉淀成可复用的流程。

## Skills / 技能

| Skill | What it does / 功能 | Version | ClawHub |
|---|---|---|---|
| [adaptive-eta](skills/adaptive-eta) | Honest time estimates for long tasks, with overrun alerts and self-calibration / 长任务时间预估、超时提醒与自我校准 | 0.3.0 | [adaptive-eta](https://clawhub.ai/yanghe1941/skills/adaptive-eta) |

## Install / 安装

```bash
git clone https://github.com/Yanghe1941/skills.git && cd skills
./scripts/install.sh adaptive-eta                  # Claude Code (default)
./scripts/install.sh adaptive-eta --tool codex     # or cursor / gemini / agents
./scripts/install.sh --all --tool cursor --project # all skills, into the current project
```

Via ClawHub (OpenClaw): `clawhub install adaptive-eta`

Where each tool looks for skills: [docs/compatibility.md](docs/compatibility.md) / 各工具的技能目录见兼容性说明。

## Repository layout / 目录结构

```
skills/<name>/        one folder per skill: SKILL.md + README.md (+ scripts/, references/)
templates/skill/      starting point for a new skill / 新技能模板
scripts/install.sh    install into any supported tool / 多端安装
scripts/validate.py   format + privacy check, also runs in CI / 格式与隐私检查
docs/                 compatibility notes / 兼容性说明
```

## Adding a skill / 新增技能

1. `cp -R templates/skill skills/<name>` and edit both files. / 复制模板并修改。
2. `python3 scripts/validate.py` — must pass. / 必须通过校验。
3. Add a row to the table above. / 在上方表格加一行。

Privacy: skills here are generalized from a private setup. Keep a local, git-ignored `.privacy-denylist` (one term per line); `validate.py` fails if any skill contains one of those terms.
隐私：技能从私人环境提炼而来。本地放一份不入库的 `.privacy-denylist`（每行一个词），校验脚本发现命中即失败。

## License

MIT-0 — free to use, modify and redistribute, no attribution required.
