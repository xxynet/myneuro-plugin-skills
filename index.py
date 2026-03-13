from plugin_sdk import Plugin, run
import yaml
import os
import subprocess

SKILLS_PROMPT = """\
以下是你的技能列表，当你需要使用某个技能时，可以调用 fetch_skill 工具并传入技能名称来获取该技能的详细信息。
When a user request matches a skill:

1 call fetch_skill
2 read SKILL.md
3 follow instructions
技能列表：
"""

class SkillsPlugin(Plugin):
    skills: dict = {}  # key: skill_name, values: {description, folder path}
    cwd: str = os.getcwd()

    async def on_start(self):
        os.makedirs(f"{self.cwd}/skills", exist_ok=True)
        self.prompt = SKILLS_PROMPT
        await self._scan_skills()
    
    async def _scan_skills(self):
        skills_dir = f"{self.cwd}/skills"
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
                        self.prompt += f"- {skill_info['name']}: {skill_info['description']}\n"
                    else:
                        self.context.log('warning', f"Failed to parse SKILL.md for skill: {skill_dir}")
                else:
                    self.context.log('warning', f"No SKILL.md found for skill: {skill_dir}")
        self.context.storage.set("skills", self.skills)
        self.prompt += "---"
        self.context.storage.set('skills_prompt', self.prompt)

    async def _parse_skill_md(self, skill_path):
        # Read SKILL.md file and extract name and description

        """Example SKILL.md head:
        ---
        name: pdf
        description: Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables from PDFs, combining or merging multiple PDFs into one, splitting PDFs apart, rotating pages, adding watermarks, creating new PDFs, filling PDF forms, encrypting/decrypting PDFs, extracting images, and OCR on scanned PDFs to make them searchable. If the user mentions a .pdf file or asks to produce one, use this skill.
        license: Proprietary. LICENSE.txt has complete terms
        ---
        """
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                text = f.read()

            frontmatter = text.split('---')[1]
            data = yaml.safe_load(frontmatter)
            if not data.get('name') or not data.get('description'):
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
            return 'Skill name is required.'
        cwd = os.getcwd()
        skill_path = self.context.storage.get("skills").get(skill_name).get("path")
        md_path = os.path.join(cwd, skill_path, 'SKILL.md') if skill_path else None
        if not os.path.exists(md_path):
            return None
        with open(md_path, 'r', encoding='utf-8') as f:
            return f.read()

    async def on_user_input(self, event):
        self.context.log('info', 'Skills 插件已注入技能 Prompt')
        event.add_context(self.context.storage.get('skills_prompt'))

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
                    'description': 'Execute a shell command specifically for a skill.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'shell_command': {
                                'type': 'string',
                                'description': 'The shell command to execute'
                            },
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
                                'description': 'Resource relative path, e.g. references/pdf_spec.md, workflows/xxx.md'
                            }
                        },
                        'required': ['skill_name', 'resource_path']
                    }
                }
            }
        ]

    # ===== 工具执行 =====

    async def execute_tool(self, name, params):
        self.context.log('info', f'Executing tool: {name} with params: {params}')
        if name == 'list_skills':
            try:
                skills = self.context.storage.get('skills')
                if not skills:
                    self.context.log('info', 'No skills available.')
                    return 'No skills available.'
                skill_list = '\n'.join([f"- {name}: {info['description']} (path: {info['path']})" for name, info in skills.items()])
                self.context.log('info', f'Available skills:\n{skill_list}')
                return skill_list
            except Exception as e:
                self.context.log('error', f'Error listing skills: {e}')
                return f'Error listing skills: {e}'
        

        elif name == 'fetch_skill':
            try:
                skill_name = params.get('skill_name', '').strip()
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
        

        elif name == 'execute_shell_command':
            try:
                shell_command = params.get('shell_command', '').strip()
                if not shell_command:
                    self.context.log('warning', 'execute_shell_command called without shell_command')
                    return 'Shell command cannot be empty.'
                # Execute the shell command directly
                self.context.log('info', f'Executing shell command: {shell_command}')
                result = subprocess.run(shell_command, shell=True, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    self.context.log('info', f'Shell command executed successfully: {shell_command}')
                    self.context.log('info', f'Shell command output:\n{result.stdout}')
                    return f'Shell command output:\n{result.stdout}'
                else:
                    self.context.log('error', f'Error occurred while executing shell command: {shell_command}')
                    return f'Error occurred while executing shell command: {shell_command}'
            except Exception as e:
                self.context.log('error', f'Unexpected error while executing shell command: {e}')
                return f'Unexpected error while executing shell command: {e}'

        
        elif name == 'fetch_skill_resource':
            try:
                skill_name = params.get('skill_name', '').strip()
                resource_path = params.get('resource_path', '').strip()
                if not skill_name or not resource_path:
                    self.context.log('warning', 'fetch_skill_resource called without skill_name or resource_path')
                    return 'Skill name and resource path cannot be empty.'
                skill_path = self.context.storage.get(f'skills').get(skill_name).get('path')
                if not skill_path:
                    self.context.log('warning', f'Skill "{skill_name}" not found for fetching resource.')
                    return f'Skill "{skill_name}" not found.'
                resource_path = os.path.join(os.getcwd(), skill_path, resource_path)
                if not os.path.exists(resource_path):
                    self.context.log('warning', f'Resource "{resource_path}" not found for skill "{skill_name}".')
                    return f'Resource "{resource_path}" not found for skill "{skill_name}".'
                with open(resource_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.context.log('info', f'Fetched resource "{resource_path}" for skill "{skill_name}".')
                return content
            except Exception as e:
                self.context.log('error', f'Error fetching resource "{resource_path}" for skill "{skill_name}": {e}')
                return f'Error fetching resource "{resource_path}" for skill "{skill_name}": {e}'

        return 'Unknown tool.'

if __name__ == '__main__':
    run(SkillsPlugin)