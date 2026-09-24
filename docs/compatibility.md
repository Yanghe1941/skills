# Compatibility · 多端兼容

Every skill here is a folder containing one `SKILL.md` — YAML frontmatter (`name` + `description`) plus a Markdown body — following the open Agent Skills format. The same folder works in every tool below; only the install location differs.

这里的每个技能都是一个包含 `SKILL.md` 的文件夹——YAML frontmatter（`name` + `description`）加 Markdown 正文，遵循开放的 Agent Skills 格式。同一个文件夹可在下列所有工具中使用，区别只在安装目录。

## Where each tool looks · 各工具的技能目录

| Tool / 工具 | Personal (all projects) / 全局 | Project / 项目级 | `install.sh --tool` |
|---|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` | `claude` |
| OpenAI Codex CLI | `~/.agents/skills/` (older: `~/.codex/skills/`) | `.agents/skills/` | `codex` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` (also reads `.claude/` `.codex/` `.agents/`) | `cursor` |
| Gemini CLI | `~/.gemini/skills/` or `~/.agents/skills/` | `.gemini/skills/` or `.agents/skills/` | `gemini` |
| OpenClaw | via ClawHub: `openclaw skills install @yanghe1941/<skill>` | — | — |
| Any agent reading `~/.agents/skills/` | `~/.agents/skills/` | `.agents/skills/` | `agents` |

> Paths checked on 2026-09-24 against the official docs below. These tools move fast — if a path stops working, check the tool's current docs first.
> 路径于 2026-09-24 按下列官方文档核对。这些工具更新很快，路径失效时请以官方最新文档为准。

**Don't want to track paths yourself?** [`npx skills`](https://github.com/vercel-labs/skills) knows them: `npx skills add Yanghe1941/skills --skill <name> -a <agent>`.
**不想自己记路径？** [`npx skills`](https://github.com/vercel-labs/skills) 会自动放到对的位置：`npx skills add Yanghe1941/skills --skill <name> -a <agent>`。

## Writing portable skills · 写出可移植的技能

| Rule / 规则 | Why / 原因 |
|---|---|
| Rely only on `name` + `description` in frontmatter<br>frontmatter 只依赖 `name` 和 `description` | Other fields are tool-specific and silently ignored elsewhere<br>其他字段各家不通用，换个工具就被静默忽略 |
| Keep frontmatter valid YAML — no unquoted `: ` in a value<br>frontmatter 必须是合法 YAML——值里不能有未加引号的 `: ` | A parse error makes installers skip the skill without saying so<br>解析失败时安装器会一声不吭地跳过该技能 |
| Refer to bundled files by paths relative to the skill folder<br>引用附带文件时用相对技能目录的路径 | The install location differs per tool<br>每个工具的安装位置都不同 |
| Scripts: standard library only, no hardcoded home paths<br>脚本只用标准库，不写死家目录路径 | They must run wherever the folder is copied<br>复制到哪里都要能跑 |
| Put trigger phrases (EN + 中文) in `description`<br>把中英文触发词写进 `description` | It's the only thing the agent sees before loading the skill<br>加载技能之前，Agent 只看得到它 |

## Sources · 来源

- Claude Code — <https://docs.claude.com/en/docs/claude-code/skills>
- Codex CLI — <https://developers.openai.com/codex/skills>
- Cursor — <https://cursor.com/docs/skills>
- Gemini CLI — <https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md>
- `npx skills` — <https://github.com/vercel-labs/skills>
