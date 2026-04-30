"""
配置加载器 - 加载和验证公司配置
用法:
  from config_loader import ConfigLoader
  config = ConfigLoader.load()
  config.get_company_entities()
  config.get_standard("party_a", "late_payment_penalty_rate")
"""
import json
import os
import sys
from pathlib import Path

class ConfigLoader:
    """配置加载器，支持默认配置和自定义配置"""

    DEFAULT_CONFIG_NAME = "config.json"
    SCHEMA_NAME = "config.schema.json"

    def __init__(self, config_path=None):
        """
        初始化配置加载器
        Args:
            config_path: 自定义配置文件路径，默认使用skill目录下的config.json
        """
        self.skill_dir = Path(__file__).parent.parent
        self.config_path = config_path or self.skill_dir / self.DEFAULT_CONFIG_NAME
        self.schema_path = self.skill_dir / self.SCHEMA_NAME
        self._config = None

    @classmethod
    def load(cls, config_path=None):
        """快捷方法：加载配置"""
        loader = cls(config_path)
        return loader

    def get_config(self):
        """获取完整配置对象"""
        if self._config is None:
            self._load_config()
        return self._config

    def _load_config(self):
        """加载配置文件"""
        if not self.config_path.exists():
            # 尝试查找schema作为模板提示
            if self.schema_path.exists():
                print(f"⚠️ 配置文件不存在: {self.config_path}")
                print(f"💡 请复制 {self.schema_path} 为 {self.config_path} 并填写公司信息")
            self._config = self._get_default_config()
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ 配置文件解析错误: {e}")
            self._config = self._get_default_config()

    def _get_default_config(self):
        """获取默认配置（CSDN）"""
        return {
            "company": {
                "name": "CSDN",
                "legal_name": "北京创新乐知网络技术有限公司",
                "entities": [
                    "北京创新乐知网络技术有限公司",
                    "涛伯开源（深圳）科技有限公司",
                    "CSDN",
                    "GitCode"
                ],
                "author_name": "CSDN合同审查"
            },
            "standards": {
                "party_a": {
                    "late_payment_penalty_rate": "万分之三",
                    "late_payment_penalty_rate_value": 0.0003,
                    "late_payment_penalty_cap": "10%"
                },
                "party_b": {
                    "late_payment_penalty_rate": "千分之五",
                    "late_payment_penalty_rate_value": 0.005,
                    "breach_penalty_cap": "30%"
                }
            }
        }

    # ========== 公司信息 ==========

    def get_company_name(self):
        """获取公司简称"""
        return self.get_config().get("company", {}).get("name", "公司")

    def get_company_legal_name(self):
        """获取公司全称"""
        return self.get_config().get("company", {}).get("legal_name", "")

    def get_company_entities(self):
        """获取关联公司列表（用于识别'我方'）"""
        return self.get_config().get("company", {}).get("entities", [])

    def get_author_name(self):
        """获取修订痕迹作者名称"""
        return self.get_config().get("company", {}).get("author_name", "合同审查")

    def get_logo_text(self):
        """获取品牌显示文字"""
        return self.get_config().get("company", {}).get("logo_text", "法务")

    # ========== 审核标准 ==========

    def get_standard(self, role, key):
        """
        获取指定角色的审核标准值
        Args:
            role: "party_a" 或 "party_b"
            key: 标准键名，如 "late_payment_penalty_rate"
        """
        return self.get_config().get("standards", {}).get(role, {}).get(key)

    def get_party_a_standards(self):
        """获取甲方视角全部标准"""
        return self.get_config().get("standards", {}).get("party_a", {})

    def get_party_b_standards(self):
        """获取乙方视角全部标准"""
        return self.get_config().get("standards", {}).get("party_b", {})

    # ========== 红线条款 ==========

    def get_redlines(self, role):
        """获取指定角色的红线条款列表"""
        return self.get_config().get("redlines", {}).get(role, [])

    # ========== 输出配置 ==========

    def get_output_dir(self):
        """获取默认输出目录"""
        import os
        default = self.get_config().get("output", {}).get("default_dir", "~/Desktop")
        return Path(default).expanduser()

    def get_output_suffix(self, suffix_type):
        """获取输出文件后缀"""
        suffixes = {
            "redline": "_修改痕迹",
            "report": "_审查报告",
            "dashboard": "_审核工作台"
        }
        return self.get_config().get("output", {}).get(f"{suffix_type}_suffix", suffixes.get(suffix_type, ""))

    # ========== 合同类型 ==========

    def get_contract_type_mapping(self):
        """获取合同类型映射"""
        return self.get_config().get("contract_types", {})

    # ========== 工具方法 ==========

    def print_summary(self):
        """打印配置摘要"""
        c = self.get_config()
        print("=" * 50)
        print("配置摘要")
        print("=" * 50)
        print(f"公司: {c.get('company', {}).get('name', '未知')}")
        print(f"全称: {c.get('company', {}).get('legal_name', '未知')}")
        print(f"关联实体: {len(c.get('company', {}).get('entities', []))} 个")
        print("-" * 50)
        print("甲方标准:")
        for k, v in c.get("standards", {}).get("party_a", {}).items():
            if not k.endswith("_value"):
                print(f"  {k}: {v}")
        print("-" * 50)
        print("乙方标准:")
        for k, v in c.get("standards", {}).get("party_b", {}).items():
            if not k.endswith("_value"):
                print(f"  {k}: {v}")
        print("=" * 50)


if __name__ == "__main__":
    # 测试配置加载
    loader = ConfigLoader.load()
    loader.print_summary()