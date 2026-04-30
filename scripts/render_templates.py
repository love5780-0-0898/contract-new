"""
模板渲染器 - 从config.json和模板文件生成知识库文件
用法:
  python3 render_templates.py                     # 渲染所有模板
  python3 render_templates.py --template rules    # 只渲染规则模板
"""
import json
import os
import re
import sys
from pathlib import Path


class TemplateRenderer:
    """简单的模板渲染器，支持 {{var}} 和 {{#each}} 语法"""

    def __init__(self, config_path=None):
        self.skill_dir = Path(__file__).parent.parent
        self.config_path = config_path or self.skill_dir / "config.json"
        self.templates_dir = self.skill_dir / "templates"
        self.knowledge_dir = self.skill_dir / "knowledge"
        self._config = None

    def load_config(self):
        """加载配置"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = json.load(f)
        return self._config

    def render_string(self, template_str, data):
        """
        渲染模板字符串
        支持:
          {{company.name}}  → 变量替换
          {{#each company.entities}}\n- {{this}}\n{{/each}}  → 列表循环
        """
        result = template_str

        # 处理 {{#each}} 循环
        each_pattern = r'\{\{#each\s+([\w.]+)\}\}\n(.*?)\n\{\{/each\}\}'
        for match in re.finditer(each_pattern, result, re.DOTALL):
            list_path = match.group(1)
            body = match.group(2)
            items = self._get_nested(data, list_path, [])
            rendered_items = []
            for item in items:
                item_text = body.replace("{{this}}", str(item))
                rendered_items.append(item_text)
            result = result.replace(match.group(0), "\n".join(rendered_items))

        # 处理 {{var}} 变量
        var_pattern = r'\{\{([\w.]+)\}\}'
        for match in re.finditer(var_pattern, result):
            var_path = match.group(1)
            value = self._get_nested(data, var_path, "")
            result = result.replace(match.group(0), str(value))

        return result

    def render_file(self, template_path, output_path):
        """渲染模板文件"""
        with open(template_path, 'r', encoding='utf-8') as f:
            template_str = f.read()

        if not self._config:
            self.load_config()

        rendered = self.render_string(template_str, self._config)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered)

        return output_path

    def render_all(self):
        """渲染所有模板"""
        if not self.templates_dir.exists():
            print("⚠️ 模板目录不存在")
            return

        rendered = []
        for template_file in self.templates_dir.glob("*.template"):
            # 从模板名推导输出文件名
            # company-rules.md.template → knowledge/company-rules.md
            output_name = template_file.name.replace(".template", "")
            output_path = self.knowledge_dir / output_name

            self.render_file(template_file, output_path)
            rendered.append(output_path)
            print(f"✅ {template_file.name} → {output_path}")

        return rendered

    def _get_nested(self, data, path, default=None):
        """获取嵌套字典值，支持点号路径如 'standards.party_a.late_payment_penalty_rate'"""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current


def main():
    import argparse
    parser = argparse.ArgumentParser(description="模板渲染器")
    parser.add_argument("--template", help="指定模板名称（不含.template后缀）")
    parser.add_argument("--config", help="指定配置文件路径")

    args = parser.parse_args()

    renderer = TemplateRenderer(args.config)
    renderer.load_config()

    if args.template:
        template_path = renderer.templates_dir / f"{args.template}.template"
        if not template_path.exists():
            print(f"❌ 模板不存在: {template_path}")
            sys.exit(1)
        # 推导输出路径
        output_name = template_path.name.replace(".template", "")
        output_path = renderer.knowledge_dir / output_name
        renderer.render_file(template_path, output_path)
        print(f"✅ {template_path.name} → {output_path}")
    else:
        renderer.render_all()


if __name__ == "__main__":
    main()