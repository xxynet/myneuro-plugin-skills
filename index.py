from plugin_sdk import Plugin, run
import os

SKILLS_PROMPT = """\
以下是你的技能列表，技能以文件夹形式存放在 skills 目录下，每个技能文件夹内有一个 SKILL.md 文件，里面包含了技能的名称和描述。当你需要使用某个技能时，可以调用 fetch_skill 工具并传入技能名称来获取该技能的详细信息。
技能列表：
"""

class SkillsPlugin(Plugin):

    async def on_start(self):
        cwd = os.getcwd()
        os.makedirs(f"{cwd}/skills", exist_ok=True)
        self.prompt = SKILLS_PROMPT
        await self._scan_skills()
    
    async def _scan_skills(self):
        cwd = os.getcwd()
        skills_dir = f"{cwd}/skills"
        self.context.storage.set('skills_mapping', {})
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
                        self.prompt += f"- {skill_info['name']}: {skill_info['description']}\n"
                        self.context.storage.set(f'skill_{skill_info["name"]}', skill_path)
                    else:
                        self.context.log('warning', f"Failed to parse SKILL.md for skill: {skill_dir}")
                else:
                    self.context.log('warning', f"No SKILL.md found for skill: {skill_dir}")
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
                lines = f.readlines()
                if lines[0].strip() != '---':
                    return None
                name = ''
                description = ''
                for line in lines[1:]:
                    if line.strip() == '---':
                        break
                    if line.startswith('name:'):
                        name = line[len('name:'):].strip()
                    elif line.startswith('description:'):
                        description = line[len('description:'):].strip()
                return {
                    'name': name,
                    'description': description
                }        
        except Exception as e:
            self.context.log('error', f'Failed to parse {skill_path}: {e}')
        return {
            'name': name,
            'description': description
        }
    
    async def get_skill_md(self, skill_name):
        if not skill_name:
            return 'Skill name is required.'
        cwd = os.getcwd()
        skill_path = self.context.storage.get(f'skill_{skill_name}')
        skill_path = os.path.join(cwd, skill_path, 'SKILL.md') if skill_path else None
        if not os.path.exists(skill_path):
            return f'Skill "{skill_name}" not found.'
        with open(skill_path, 'r', encoding='utf-8') as f:
            return f.read()

    async def on_user_input(self, event):
        event.add_context(self.context.storage.get('skills_prompt'))

    def get_tools(self):
        return [
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
            }
        ]

    # ===== 工具执行 =====

    async def execute_tool(self, name, params):
        if name == 'fetch_skill':
            skill_name = params.get('skill_name', '').strip()
            if not skill_name:
                self.context.log('warning', 'fetch_skill called without skill_name')
                return 'Skill name cannot be empty.'
            skill_md = await self.get_skill_md(skill_name)
            if not skill_md:
                self.context.log('warning', f'Skill "{skill_name}" not found.')
                return f'Skill "{skill_name}" not found.'
            self.context.log('info', f'Fetched skill "{skill_name}" successfully.')
            self.context.log('info', skill_md)
            return skill_md

        return 'Unknown tool.'

if __name__ == '__main__':
    run(SkillsPlugin)