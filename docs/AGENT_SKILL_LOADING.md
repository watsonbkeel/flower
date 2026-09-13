# AGENT_SKILL_LOADING.md

项目 Skills 存于 repo-local `.agents/skills/`。`AGENTS.md` 要求代理按路径**显式读取**对应 `SKILL.md`，因此不依赖某个运行时是否自动扫描该目录。

如果使用支持个人 Skill 目录的 Codex/CLI，可选执行 `scripts/install_project_skills.sh`，把项目 Skill 软链接到 `~/.agents/skills/flower-*`。Claude Code 如需自动发现，可手工链接到其个人 Skill 目录；不要复制出第二份可编辑源文件，以免漂移。

权威源始终是仓库内 `.agents/skills/`。
