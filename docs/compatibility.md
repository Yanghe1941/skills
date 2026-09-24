# Compatibility / 多端兼容

Every skill here is a folder with one `SKILL.md` (YAML frontmatter `name` + `description`, Markdown body), following the open Agent Skills format. The same folder works across tools — only the install location differs.

本仓库每个技能都是一个含 `SKILL.md` 的文件夹（Agent Skills 开放格式）。同一份文件可在多个工具中使用，区别只在安装目录。

| Tool / 工具 | Personal (all projects) / 全局 | Project / 项目级 | `install.sh --tool` |
|---|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` | `claude` |
| OpenAI Codex CLI | `~/.agents/skills/` (older: `~/.codex/skills/`) | `.agents/skills/` | `codex` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` (also reads `.claude/` `.codex/` `.agents/`) | `cursor` |
| Gemini CLI | `~/.gemini/skills/` or `~/.agents/skills/` | `.gemini/skills/` or `.agents/skills/` | `gemini` |
| OpenClaw | via ClawHub: `clawhub install <skill>` | — | — |
| Any agent reading `~/.agents/skills/` | `~/.agents/skills/` | `.agents/skills/` | `agents` |

> Paths checked 2026-09-24 against the official docs below. Tools move fast — if a path stops working, check the tool's current docs first.
> 路径于 2026-09-24 按下列官方文档核对；工具更新快，失效时以官方最新文档为准。

## Sources / 来源

- Cursor — <https://cursor.com/docs/skills>
- Gemini CLI — <https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md>
- Codex CLI — <https://developers.openai.com/codex/skills>
- Claude Code — <https://docs.claude.com/en/docs/claude-code/skills>

## Writing portable skills / 写出可移植的技能

| Rule / 规则 | Why / 原因 |
|---|---|
| Only rely on `name` + `description` in frontmatter | Other fields are tool-specific and silently ignored elsewhere / 其他字段各家不通用 |
| Refer to bundled files by path relative to the skill folder | Install location differs per tool / 各工具安装路径不同 |
| Scripts: stdlib only, no hardcoded home paths | Must run wherever the folder is copied / 复制到哪都能跑 |
| Put trigger phrases (EN + 中文) in `description` | It is the only thing the agent sees before loading / 加载前 Agent 只看得到它 |
