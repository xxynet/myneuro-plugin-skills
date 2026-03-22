# My-neuro-plugin-skills

Make my-neuro capable of using Skills functionality.

## Usage

- Install this plugin
- Run `肥牛.exe` and a folder named `skills` would be created in `live2d`.
- Copy your skills folders into `live2d/skills`
Each skill must have a `SKILL.md` placed in the skill folder

SKILL.md must start with the following format:
```
---
name: skill_name
description: skill_description
---
```

## Changelog (1.1.0)

- **System prompt**: 使用 `add_system_prompt_patch` 注入技能说明，避免通过用户消息上下文重复注入长文本。
- **Shell 执行**: Windows 下 `chcp 65001`、UTF-8 环境变量、`stdin=subprocess.DEVNULL` 避免子进程挂起；超时延长至 120s；可选 `cwd`。
- **Python 路径**: 将裸 `python`/`python3` 解析为当前解释器，减少 Windows Store 别名导致的 9009。
- **参数纠错**: 若模型将 `shell_command` 与 `cwd` 颠倒，自动交换。
- **新工具**: `write_file`（UTF-8 写文件，便于技能写入标题/正文等）。
- **fetch_skill_resource**: 路径遍历防护；支持子技能路径说明（如 `skills/.../SKILL.md`）。
- **错误处理**: `execute_tool` 外层统一捕获异常并记录日志。