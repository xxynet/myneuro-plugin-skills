from plugin_sdk import Plugin, run
import yaml
import os
import subprocess
import sys

SKILLS_PROMPT = """\
你有以下技能可用。当用户请求匹配某个技能时，你必须亲自按以下步骤执行，不得委派给其他智能体或通过其他工具间接执行：

1. 直接调用 fetch_skill 工具获取技能的 SKILL.md
2. 阅读 SKILL.md 中的指令
3. 如需读取子技能，直接调用 fetch_skill_resource 获取子技能的 SKILL.md
4. 需要执行命令时，直接调用 execute_shell_command 工具（不要使用 world_eye_execute 或其他间接方式），并将 cwd 设置为技能的目录路径
5. 所有涉及浏览器的命令默认添加 --headless 参数（Chrome 后台运行不弹窗口）。仅当用户明确要求看到浏览器时才去掉
6. 严格按照 SKILL.md 中的指令操作

重要：技能相关的工具（fetch_skill、execute_shell_command、fetch_skill_resource、list_skills）由你直接调用，禁止通过 world_eye_execute 委派。

技能列表：
"""

class SkillsPlugin(Plugin):

    async def on_start(self):
        self.skills = {}
        self.cwd = os.getcwd()
        os.makedirs(os.path.join(self.cwd, 'skills'), exist_ok=True)
        self.prompt = SKILLS_PROMPT
        await self._scan_skills()
    
    async def _scan_skills(self):
        skills_dir = os.path.join(self.cwd, 'skills')
        self.context.storage.set('skills', {})
        if not os.path.exists(skills_dir):
            self.context.log('info', 'No skills directory found.')
            return
        for skill_dir in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, skill_dir)
            if os.path.isdir(skill_path):
                md_path = os.path.join(skill_path, 'SKILL.md')
                if os.path.exists(md_path):
                    skill_info = await self._parse_skill_md(md_path)
                    if skill_info:
                        self.context.log('info', f"Loaded skill: {skill_info['name']} - {skill_info['description']}")
                        self.skills[skill_info['name']] = {
                            'description': skill_info['description'],
                            'path': skill_path
                        }
                        self.prompt += f"- {skill_info['name']} (path: {skill_path}): {skill_info['description']}\n"
                    else:
                        self.context.log('warning', f"Failed to parse SKILL.md for skill: {skill_dir}")
                else:
                    self.context.log('warning', f"No SKILL.md found for skill: {skill_dir}")
        self.context.storage.set("skills", self.skills)
        self.prompt += "---"
        self.context.storage.set('skills_prompt', self.prompt)
        self.context.add_system_prompt_patch('skills_prompt', self.prompt)

    async def _parse_skill_md(self, skill_path):
        """Example SKILL.md head:
        ---
        name: pdf
        description: Use this skill whenever the user wants to do anything with PDF files.
        license: Proprietary. LICENSE.txt has complete terms
        ---
        """
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                text = f.read()

            parts = text.split('---')
            if len(parts) < 3:
                self.context.log('warning', f'Invalid frontmatter format in {skill_path}')
                return None

            frontmatter = parts[1]
            data = yaml.safe_load(frontmatter)
            if not data or not data.get('name') or not data.get('description'):
                self.context.log('warning', f'Missing name or description in {skill_path}')
                return None

            return {
                'name': data.get('name'),
                'description': data.get('description')
            }        
        except Exception as e:
            self.context.log('error', f'Failed to parse {skill_path}: {e}')
            return None
    
    async def get_skill_md(self, skill_name):
        if not skill_name:
            return None
        skills = self.context.storage.get("skills")
        if not skills or skill_name not in skills:
            return None
        skill_info = skills[skill_name]
        skill_path = skill_info.get("path")
        if not skill_path:
            return None
        md_path = os.path.join(skill_path, 'SKILL.md')
        if not os.path.exists(md_path):
            return None
        with open(md_path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def _resolve_python_path(command):
        """Replace bare 'python' in command with the actual interpreter path to avoid
        Windows Store alias redirect (exit code 9009)."""
        py = sys.executable
        if not py:
            return command
        quoted_py = f'"{py}"' if ' ' in py else py
        if command.startswith('python3 ') or command == 'python3':
            return quoted_py + command[7:]
        if command.startswith('python ') or command == 'python':
            return quoted_py + command[6:]
        return command

    async def on_user_input(self, event):
        pass

    def get_tools(self):
        return [
            {
                'type': 'function',
                'function': {
                    'name': 'list_skills',
                    'description': 'List all available skills',
                    'parameters': {
                        'type': 'object',
                        'properties': {},
                        'required': []
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'fetch_skill',
                    'description': 'Get SKILL by skill name',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'skill_name': {
                                'type': 'string',
                                'description': 'Skill name'
                            }
                        },
                        'required': ['skill_name']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'execute_shell_command',
                    'description': 'Execute a shell command specifically for a skill. Supports optional cwd (working directory) parameter.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'shell_command': {
                                'type': 'string',
                                'description': 'The shell command to execute'
                            },
                            'cwd': {
                                'type': 'string',
                                'description': 'Working directory to run the command in. If not provided, uses the skill directory or current directory.'
                            }
                        },
                        'required': ['shell_command']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'fetch_skill_resource',
                    'description': 'Fetch a resource related to a skill by its name',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'skill_name': {
                                'type': 'string',
                                'description': 'Skill name'
                            },
                            'resource_path': {
                                'type': 'string',
                                'description': 'Resource path relative to the skill root directory. For sub-skills use skills/ prefix, e.g. skills/xhs-auth/SKILL.md, skills/xhs-publish/SKILL.md'
                            }
                        },
                        'required': ['skill_name', 'resource_path']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'write_file',
                    'description': 'Write text content to a file (UTF-8). Use this to write title/content files for skills instead of passing Chinese text via shell commands.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'file_path': {
                                'type': 'string',
                                'description': 'Absolute path to the file to write'
                            },
                            'content': {
                                'type': 'string',
                                'description': 'Text content to write to the file'
                            }
                        },
                        'required': ['file_path', 'content']
                    }
                }
            }
        ]

    # ===== 工具执行 =====

    async def execute_tool(self, tool_name, params):
        try:
            return await self._execute_tool_impl(tool_name, params)
        except Exception as e:
            self.context.log('error', f'Unhandled error in execute_tool({tool_name}): {e}')
            return f'Tool execution error ({tool_name}): {e}'

    async def _execute_tool_impl(self, tool_name, params):
        self.context.log('info', f'Executing tool: {tool_name} with params: {params}')
        if tool_name == 'list_skills':
            try:
                skills = self.context.storage.get('skills')
                if not skills:
                    self.context.log('info', 'No skills available.')
                    return 'No skills available.'
                skill_list = '\n'.join([
                    f"- {sname}: {info['description']} (path: {info['path']})"
                    for sname, info in skills.items()
                ])
                self.context.log('info', f'Available skills:\n{skill_list}')
                return skill_list
            except Exception as e:
                self.context.log('error', f'Error listing skills: {e}')
                return f'Error listing skills: {e}'

        elif tool_name == 'fetch_skill':
            skill_name = params.get('skill_name', '').strip()
            try:
                if not skill_name:
                    self.context.log('warning', 'fetch_skill called without skill_name')
                    return 'Skill name cannot be empty.'
                skill_md = await self.get_skill_md(skill_name)
                if not skill_md:
                    self.context.log('warning', f'Skill "{skill_name}" not found.')
                    return f'Skill "{skill_name}" not found.'
                self.context.log('info', f'Fetched skill "{skill_name}" successfully.')
                return skill_md
            except Exception as e:
                self.context.log('error', f'Error fetching skill "{skill_name}": {e}')
                return f'Error fetching skill "{skill_name}": {e}'

        elif tool_name == 'execute_shell_command':
            cfg = self.context.get_plugin_config()
            shell_enabled = cfg.get("shell_tool", False)
            if not shell_enabled:
                self.context.log('warning', 'execute_shell_command called but shell_tool is disabled in config')
                return 'Shell command execution is disabled in the plugin configuration.'
            shell_command = ''
            try:
                shell_command = params.get('shell_command', '').strip()
                work_dir = params.get('cwd', '').strip() if params.get('cwd') else ''

                if shell_command and work_dir and os.path.isdir(shell_command) and not os.path.isdir(work_dir):
                    shell_command, work_dir = work_dir, shell_command
                    self.context.log('info', 'Auto-swapped shell_command and cwd (params were reversed)')

                if not shell_command:
                    self.context.log('warning', 'execute_shell_command called without shell_command')
                    return 'Shell command cannot be empty.'

                shell_command = self._resolve_python_path(shell_command)

                if not work_dir or not os.path.isdir(work_dir):
                    work_dir = os.getcwd()

                env = os.environ.copy()
                env['PYTHONIOENCODING'] = 'utf-8'
                if os.name == 'nt':
                    shell_command = f'chcp 65001 >nul && {shell_command}'

                self.context.log('info', f'Executing shell command: {shell_command} (cwd: {work_dir})')
                result = subprocess.run(
                    shell_command, shell=True, capture_output=True,
                    stdin=subprocess.DEVNULL,
                    timeout=120, cwd=work_dir, env=env, encoding='utf-8', errors='replace'
                )
                output = (result.stdout or '') + (result.stderr or '')
                if result.returncode == 0:
                    self.context.log('info', f'Shell command executed successfully: {shell_command}')
                    return f'Shell command output:\n{output}'
                else:
                    self.context.log('error', f'Shell command failed (exit {result.returncode}): {shell_command}')
                    return f'Shell command failed (exit {result.returncode}):\n{output}'
            except subprocess.TimeoutExpired:
                self.context.log('error', f'Shell command timed out (120s): {shell_command}')
                return f'Shell command timed out after 120 seconds: {shell_command}'
            except Exception as e:
                self.context.log('error', f'Unexpected error while executing shell command: {e}')
                return f'Unexpected error while executing shell command: {e}'

        elif tool_name == 'fetch_skill_resource':
            skill_name = ''
            resource_rel = ''
            try:
                skill_name = params.get('skill_name', '').strip()
                resource_rel = params.get('resource_path', '').strip()
                if not skill_name or not resource_rel:
                    self.context.log('warning', 'fetch_skill_resource called without skill_name or resource_path')
                    return 'Skill name and resource path cannot be empty.'

                skills = self.context.storage.get('skills')
                if not skills or skill_name not in skills:
                    self.context.log('warning', f'Skill "{skill_name}" not found for fetching resource.')
                    return f'Skill "{skill_name}" not found.'

                skill_path = skills[skill_name].get('path')
                if not skill_path:
                    return f'Skill "{skill_name}" has no path configured.'

                full_path = os.path.normpath(os.path.join(skill_path, resource_rel))
                if not full_path.startswith(os.path.normpath(skill_path)):
                    self.context.log('warning', f'Path traversal blocked: {resource_rel}')
                    return 'Invalid resource path: path traversal not allowed.'

                if not os.path.exists(full_path):
                    self.context.log('warning', f'Resource "{resource_rel}" not found for skill "{skill_name}".')
                    return f'Resource "{resource_rel}" not found for skill "{skill_name}".'
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.context.log('info', f'Fetched resource "{resource_rel}" for skill "{skill_name}".')
                return content
            except Exception as e:
                self.context.log('error', f'Error fetching resource "{resource_rel}" for skill "{skill_name}": {e}')
                return f'Error fetching resource "{resource_rel}" for skill "{skill_name}": {e}'

        elif tool_name == 'write_file':
            file_path = ''
            try:
                file_path = params.get('file_path', '').strip()
                content = params.get('content', '')
                if not file_path:
                    return 'File path cannot be empty.'
                os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.context.log('info', f'Written {len(content)} chars to {file_path}')
                return f'File written successfully: {file_path} ({len(content)} chars)'
            except Exception as e:
                self.context.log('error', f'Error writing file "{file_path}": {e}')
                return f'Error writing file "{file_path}": {e}'

        return 'Unknown tool.'

if __name__ == '__main__':
    run(SkillsPlugin)
