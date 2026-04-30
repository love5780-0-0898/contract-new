"""
公司配置初始化向导 - 帮助用户创建公司配置文件
用法:
  python3 init_company.py                    # 交互式向导
  python3 init_company.py --name XX公司       # 快速创建
  python3 init_company.py --template          # 生成空白模板
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime

class CompanyInitWizard:
    """公司配置初始化向导"""

    def __init__(self):
        self.skill_dir = Path(__file__).parent.parent
        self.config_path = self.skill_dir / "config.json"
        self.schema_path = self.skill_dir / "config.schema.json"

    def run_interactive(self):
        """运行交互式向导"""
        print("=" * 60)
        print("       合同审查Skill - 公司配置向导")
        print("=" * 60)
        print()
        print("此向导将帮助您创建公司专属的配置文件。")
        print("配置完成后，Skill 将从您公司的立场审查合同。")
        print()

        # 公司基本信息
        print("【第一步】公司基本信息")
        print("-" * 40)
        company_name = self._input("公司简称", "如：华为、阿里")
        legal_name = self._input("公司全称", "如：华为技术有限公司")
        entities_input = self._input("关联公司/品牌", "多个用逗号分隔，如：华为,荣耀", default=company_name)
        entities = [e.strip() for e in entities_input.split(",")]
        author_name = self._input("修订痕迹作者名", default=f"{company_name}合同审查")

        print()
        print("【第二步】甲方视角审核标准（我方为采购方）")
        print("-" * 40)
        print("当您公司作为甲方（付款方）时的标准：")
        party_a_late_penalty = self._input("逾期付款违约金比例", default="万分之三")
        party_a_late_cap = self._input("违约金上限", default="10%")
        party_a_acceptance_days = self._input("验收整改期限（工作日）", default="3")
        party_a_conf_years = self._input("保密期限（年）", default="3")
        party_a_jurisdiction = self._input("管辖法院偏好", default="甲方所在地法院")

        print()
        print("【第三步】乙方视角审核标准（我方为销售方）")
        print("-" * 40)
        print("当您公司作为乙方（收款方）时的标准：")
        party_b_late_penalty = self._input("要求对方的逾期付款违约金比例", default="千分之五")
        party_b_termination_days = self._input("逾期多少天可解除合同", default="15")
        party_b_breach_cap = self._input("我方违约金上限", default="30%")
        party_b_acceptance_days = self._input("要求对方验收期限（工作日）", default="3")
        party_b_jurisdiction = self._input("管辖法院偏好", default="乙方所在地法院")

        # 构建配置
        config = {
            "company": {
                "name": company_name,
                "legal_name": legal_name,
                "short_name": company_name,
                "entities": entities,
                "author_name": author_name,
                "logo_text": f"{company_name}法务",
                "brands": entities
            },
            "standards": {
                "party_a": {
                    "role_name": "甲方（采购方）",
                    "late_payment_penalty_rate": party_a_late_penalty,
                    "late_payment_penalty_cap": party_a_late_cap,
                    "acceptance_rectification_days": int(party_a_acceptance_days),
                    "confidentiality_years": int(party_a_conf_years),
                    "jurisdiction": party_a_jurisdiction
                },
                "party_b": {
                    "role_name": "乙方（销售方）",
                    "late_payment_penalty_rate": party_b_late_penalty,
                    "late_payment_termination_days": int(party_b_termination_days),
                    "breach_penalty_cap": party_b_breach_cap,
                    "acceptance_days": int(party_b_acceptance_days),
                    "jurisdiction": party_b_jurisdiction
                }
            },
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 确认保存
        print()
        print("【配置预览】")
        print("-" * 40)
        print(json.dumps(config, ensure_ascii=False, indent=2)[:500])
        print()
        confirm = self._input("确认保存？(y/n)", default="y")
        if confirm.lower() == "y":
            self._save_config(config)
            print()
            print("✅ 配置已保存！")
            print(f"   文件位置: {self.config_path}")
            print()
            print("现在可以使用 /csdn-contract-review 命令审查合同了。")
        else:
            print("❌ 配置未保存")

    def run_quick(self, name, legal_name=None):
        """快速创建配置"""
        legal_name = legal_name or name
        config = {
            "company": {
                "name": name,
                "legal_name": legal_name,
                "entities": [legal_name, name],
                "author_name": f"{name}合同审查"
            },
            "standards": {
                "party_a": {
                    "late_payment_penalty_rate": "万分之三",
                    "late_payment_penalty_cap": "10%"
                },
                "party_b": {
                    "late_payment_penalty_rate": "千分之五",
                    "breach_penalty_cap": "30%"
                }
            }
        }
        self._save_config(config)
        print(f"✅ 已为 {name} 创建配置文件")

    def generate_template(self):
        """生成空白模板"""
        template = {
            "company": {
                "name": "【填写公司简称】",
                "legal_name": "【填写公司全称】",
                "entities": ["【填写关联公司列表】"]
            },
            "standards": {
                "party_a": {
                    "late_payment_penalty_rate": "万分之三",
                    "late_payment_penalty_cap": "10%"
                },
                "party_b": {
                    "late_payment_penalty_rate": "千分之五",
                    "breach_penalty_cap": "30%"
                }
            }
        }
        template_path = self.skill_dir / "config.template.json"
        with open(template_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        print(f"✅ 模板已生成: {template_path}")
        print("   请填写后重命名为 config.json")

    def _input(self, prompt, hint=None, default=None):
        """交互式输入"""
        full_prompt = prompt
        if hint:
            full_prompt += f" ({hint})"
        if default:
            full_prompt += f" [默认: {default}]"
        full_prompt += ": "

        try:
            value = input(full_prompt).strip()
            if not value and default:
                return default
            return value
        except EOFError:
            return default or ""

    def _save_config(self, config):
        """保存配置文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="公司配置初始化向导")
    parser.add_argument("--name", help="公司简称（快速创建）")
    parser.add_argument("--legal-name", help="公司全称（快速创建）")
    parser.add_argument("--template", action="store_true", help="生成空白模板")

    args = parser.parse_args()

    wizard = CompanyInitWizard()

    if args.template:
        wizard.generate_template()
    elif args.name:
        wizard.run_quick(args.name, args.legal_name)
    else:
        wizard.run_interactive()


if __name__ == "__main__":
    main()