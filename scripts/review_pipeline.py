"""
合同审查流水线 - 一键完成解析、识别、规则匹配、条款扫描
用法: python3 review_pipeline.py <contract_file> [--output json]
输出: 结构化 JSON，包含合同信息、逐条款扫描结果、修改建议
"""
import sys
import os
import json
import re
import glob
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(SKILL_DIR, "knowledge")
KB_DIR = os.path.join(SKILL_DIR, "knowledge-base")
CORRECTIONS_DIR = os.path.join(KB_DIR, "corrections")
RULES_DIR = os.path.join(KB_DIR, "rules")

# ============================================================
# CSDN 关联公司
# ============================================================
CSDN_ENTITIES = [
    "北京创新乐知网络技术有限公司",
    "涛伯开源（深圳）科技有限公司",
    "涛伯开源(深圳)科技有限公司",
    "人工智能6S店",
    "CSDN",
    "GitCode",
]

# ============================================================
# 合同类型识别
# ============================================================
CONTRACT_TYPE_KEYWORDS = {
    "采购合同": ["采购", "购买", "购销", "订购", "供货", "送货"],
    "销售/技术服务合同": ["销售", "技术服务", "开发服务", "平台服务", "推广服务"],
    "合作协议": ["合作协议", "联合", "共同", "协作", "品牌合作"],
    "代销合同": ["代销", "委托销售", "代理销售", "经销"],
    "保密协议": ["保密协议", "NDA", "不披露"],
    "赞助协议": ["赞助", "冠名"],
    "培训协议": ["培训", "教育", "课程"],
    "补充协议": ["补充协议", "变更协议", "修改协议"],
}

# ============================================================
# 审核维度定义：关键词 + 检查逻辑 + 规则
# ============================================================
AUDIT_DIMENSIONS = {
    "价款及支付": {
        "keywords": ["付款", "支付", "结算", "发票", "货款", "价款", "费用", "报酬", "佣金"],
        "rules_role_a": {
            "description": "CSDN为甲方：验收合格后付款、先票后款、违约金≤万分之三/日、上限10%",
            "checks": [
                {
                    "name": "逾期付款违约金过高",
                    "pattern": r"万分之[五5]|[0-5]\.[0-9]%|千分之一|千分之[二三四五六七八九十]",
                    "severity": "high",
                    "issue": "甲方逾期付款违约金标准过高",
                    "suggestion": "按逾期付款金额的万分之三/日计算，累计不超过逾期金额的10%",
                    "rule_ref": "审核要点一(一)甲方视角：逾期付款违约金每逾期一日按逾期金额的万分之三计算，累计不超过逾期金额的10%",
                    "category": "价款及支付",
                },
                {
                    "name": "逾期付款违约金无上限",
                    "pattern": r"违约金[^。]*(?!累计|上限|不超过|最高)[^。]*$",
                    "severity": "high",
                    "issue": "违约金缺乏累计上限",
                    "suggestion": "违约金累计不超过逾期金额的10%",
                    "rule_ref": "审核要点一(一)甲方视角：累计不超过逾期金额的10%",
                    "category": "价款及支付",
                    "context_required": "违约金",
                },
                {
                    "name": "乙方逾期付款单方解除权",
                    "pattern": r"乙方[^。]{0,20}(有权|可以).{0,10}解除",
                    "severity": "high",
                    "issue": "赋予乙方逾期付款单方解除权",
                    "suggestion": "删除乙方因逾期付款的单方解除权",
                    "rule_ref": "审核要点一(一)甲方视角：注意避免乙方拥有单方解除权",
                    "category": "价款及支付",
                },
            ],
        },
        "rules_role_b": {
            "description": "CSDN为乙方：交付后付款、先款后票、违约金≥千分之五/日、逾期15日可解除",
            "checks": [
                {
                    "name": "逾期付款违约金过低",
                    "pattern": r"万分之[一二三四]",
                    "severity": "high",
                    "issue": "甲方逾期付款违约金过低，不足以弥补损失",
                    "suggestion": "按逾期付款金额的千分之五/日计算，逾期超过15日乙方有权解除",
                    "rule_ref": "审核要点一(二)乙方视角：逾期付款违约金每逾期一日按逾期金额的千分之五计算",
                    "category": "价款及支付",
                },
            ],
        },
    },
    "违约责任": {
        "keywords": ["违约金", "赔偿", "解除", "违约责任", "罚款"],
        "rules_role_a": {
            "description": "CSDN为甲方：加重乙方违约成本、控制甲方违约金上限≤30%",
            "checks": [
                {
                    "name": "甲方违约金无上限",
                    "pattern": r"(甲方|代销方|采购方)[^。]{0,50}赔偿[^。]*(?!上限|不超过|最高|累计)",
                    "severity": "medium",
                    "issue": "甲方赔偿责任缺乏上限",
                    "suggestion": "赔偿金额累计不超过合同总价款的30%",
                    "rule_ref": "审核要点三(二)乙方视角：违约金累计不超过合同总价款30%",
                    "category": "违约责任",
                },
                {
                    "name": "乙方违约金过低",
                    "pattern": r"(乙方|供货方|委托方)[^。]{0,30}(违约金|赔偿).{0,5}[0-9]*\.?[0-9]*%",
                    "severity": "medium",
                    "issue": "乙方违约金比例需检查是否足以弥补损失",
                    "suggestion": "乙方违约金建议为合同总价款的10%以上",
                    "rule_ref": "审核要点三(一)甲方视角：质量违约金为合同总价款10%",
                    "category": "违约责任",
                },
            ],
        },
        "rules_role_b": {
            "description": "CSDN为乙方：控制自身违约金上限≤30%",
            "checks": [
                {
                    "name": "乙方违约金上限过高",
                    "pattern": r"(乙方|服务方|销售方)[^。]{0,50}(违约金|赔偿).{0,20}[2-9][0-9]%|100%",
                    "severity": "high",
                    "issue": "乙方违约金上限过高",
                    "suggestion": "乙方违约金累计不超过合同总价款的30%",
                    "rule_ref": "审核要点三(二)乙方视角：违约金累计不超过合同总价款30%",
                    "category": "违约责任",
                },
            ],
        },
    },
    "争议解决": {
        "keywords": ["争议", "管辖", "仲裁", "诉讼", "法院", "起诉"],
        "rules_role_a": {
            "description": "CSDN为甲方：甲方所在地法院管辖",
            "checks": [
                {
                    "name": "非甲方所在地管辖",
                    "pattern": r"(乙方|对方|被告|原告|非违约方|守约方|履行地|合同签订地)[^。]{0,20}(法院|人民法院|管辖|仲裁)",
                    "severity": "high",
                    "issue": "管辖约定不利于甲方",
                    "suggestion": "应提交甲方所在地有管辖权的人民法院通过诉讼解决",
                    "rule_ref": "审核要点七(一)甲方视角：优先方案为诉讼加甲方所在地管辖",
                    "category": "争议解决",
                },
                {
                    "name": "原告方所在地管辖",
                    "pattern": r"原告方所在地",
                    "severity": "high",
                    "issue": "原告方所在地管辖不确定",
                    "suggestion": "应提交甲方所在地有管辖权的人民法院通过诉讼解决",
                    "rule_ref": "审核要点七(一)甲方视角：优先方案为诉讼加甲方所在地管辖",
                    "category": "争议解决",
                },
            ],
        },
        "rules_role_b": {
            "description": "CSDN为乙方：乙方所在地管辖",
            "checks": [
                {
                    "name": "非乙方所在地管辖",
                    "pattern": r"(甲方|对方|被告|原告|非违约方|守约方|履行地|合同签订地)[^。]{0,20}(法院|人民法院|管辖|仲裁)",
                    "severity": "high",
                    "issue": "管辖约定不利于乙方",
                    "suggestion": "应提交乙方所在地有管辖权的人民法院通过诉讼解决",
                    "rule_ref": "审核要点七(二)乙方视角：优先方案为诉讼加乙方所在地管辖",
                    "category": "争议解决",
                },
            ],
        },
    },
    "知识产权": {
        "keywords": ["知识产权", "著作权", "侵权", "专利", "商标", "版权"],
        "rules_role_a": {
            "description": "CSDN为甲方：对方保证不侵权、成果归甲方",
            "checks": [
                {
                    "name": "缺少不侵权保证",
                    "pattern": r"(知识产权|著作权|侵权)",
                    "anti_pattern": r"(保证|承诺|确保).{0,20}(不侵犯|无侵权)",
                    "severity": "high",
                    "issue": "缺少乙方不侵权保证条款",
                    "suggestion": "增加：乙方保证所提供的产品不侵犯任何第三方的知识产权，若因侵权导致第三方索赔，由乙方承担全部责任",
                    "rule_ref": "审核要点六(一)甲方视角：乙方保证所提供的标的不侵犯第三方知识产权",
                    "category": "知识产权",
                    "check_type": "anti_pattern_missing",
                },
            ],
        },
        "rules_role_b": {
            "description": "CSDN为乙方：保留未约定归属的成果知识产权",
            "checks": [],
        },
    },
    "保密条款": {
        "keywords": ["保密", "机密", "不披露", "秘密"],
        "rules_role_a": {
            "description": "CSDN为甲方：保密期限3年、违约金合同总价款10%",
            "checks": [
                {
                    "name": "保密期限不明确",
                    "pattern": r"(保密|商业秘密)[^。]*(?!年)",
                    "severity": "medium",
                    "issue": "保密期限未明确或过于宽泛",
                    "suggestion": "保密期限为合同终止后3年",
                    "rule_ref": "审核要点七甲方视角：保密期限3年",
                    "category": "保密条款",
                },
                {
                    "name": "保密违约金缺失",
                    "pattern": r"(保密|商业秘密)[^。]*(?!违约金)",
                    "severity": "medium",
                    "issue": "保密条款缺少具体违约金标准",
                    "suggestion": "违反保密条款应支付合同总价款10%的违约金",
                    "rule_ref": "审核要点七甲方视角：保密违约金为合同总价款10%",
                    "category": "保密条款",
                },
            ],
        },
        "rules_role_b": {
            "description": "CSDN为乙方：保密期限2年、排除已公开信息",
            "checks": [],
        },
    },
    "不可抗力": {
        "keywords": ["不可抗力", "免责"],
        "rules_role_a": {
            "description": "CSDN为甲方：不可抗力应完全免责",
            "checks": [
                {
                    "name": "不可抗力仍需赔偿",
                    "pattern": r"不可抗力[^。]*(赔偿|承担损失|承担.*损失)",
                    "severity": "medium",
                    "issue": "不可抗力条款仍要求赔偿，与免责原则矛盾",
                    "suggestion": "不可抗力发生后，遭受方在合理期限内提供证明后，双方互不承担违约责任及赔偿责任",
                    "rule_ref": "审核要点八（不可抗力）：不可抗力发生后，遭受方可不承担违约责任",
                    "category": "不可抗力",
                },
            ],
        },
        "rules_role_b": {
            "description": "CSDN为乙方：扩大不可抗力范围、完全免责",
            "checks": [
                {
                    "name": "不可抗力仍需赔偿",
                    "pattern": r"不可抗力[^。]*(赔偿|承担损失)",
                    "severity": "medium",
                    "issue": "不可抗力仍要求赔偿",
                    "suggestion": "不可抗力应完全免责",
                    "rule_ref": "审核要点八（不可抗力）",
                    "category": "不可抗力",
                },
            ],
        },
    },
}

# ============================================================
# CUAD 41 风险类别全面扫描
# ============================================================
CUAD_CATEGORIES = {
    "A01 签约主体资格": {
        "keywords": ["甲方", "乙方", "统一社会信用代码", "营业执照"],
        "check_missing": False,
        "description": "签约主体是否具备合法资格",
    },
    "A02 代理权限": {
        "keywords": ["授权代表", "法定代表人", "委托代理人", "授权委托"],
        "check_missing": False,
        "description": "签约人是否有合法授权",
    },
    "A03 合同生效条件": {
        "keywords": ["生效", "签字", "盖章", "生效条件"],
        "check_missing": False,
        "description": "合同生效的前提条件",
    },
    "A04 合同期限": {
        "keywords": ["有效期", "合同期限", "合作期限", "服务期限"],
        "check_missing": False,
        "description": "合同起止日期和续约条件",
    },
    "B01 价款明确性": {
        "keywords": ["总价", "单价", "价款", "含税", "费用"],
        "check_missing": True,
        "description": "总价、单价是否明确，是否含税",
    },
    "B02 支付方式": {
        "keywords": ["付款", "支付", "结算", "账期"],
        "check_missing": True,
        "description": "支付条件、付款节点、先票后款/先款后票",
    },
    "B03 发票条款": {
        "keywords": ["发票", "增值税", "开票"],
        "check_missing": False,
        "description": "发票类型、开票时间、不合格发票处理",
    },
    "B04 逾期付款违约金": {
        "keywords": ["逾期付款", "逾期支付", "违约金"],
        "check_missing": False,
        "description": "逾期付款违约金计算标准和上限",
    },
    "B05 价格调整": {
        "keywords": ["调价", "价格调整", "价格变更"],
        "check_missing": False,
        "description": "调价条件和流程",
    },
    "C01 交付标准": {
        "keywords": ["交付", "发货", "送货"],
        "check_missing": False,
        "description": "交付物、交付时间、交付地点",
    },
    "C02 验收标准": {
        "keywords": ["验收", "检验", "检测", "合格"],
        "check_missing": True,
        "description": "验收条件和验收时限",
    },
    "C03 验收异议": {
        "keywords": ["异议", "整改", "退换"],
        "check_missing": False,
        "description": "异议提出方式和处理流程",
    },
    "C04 风险转移": {
        "keywords": ["风险转移", "毁损", "灭失", "所有权转移"],
        "check_missing": False,
        "description": "风险转移时点",
    },
    "D01 违约金过高": {
        "keywords": ["违约金", "万分之", "千分之", "%"],
        "check_missing": False,
        "description": "违约金是否超出合理范围",
    },
    "D02 违约金过低": {
        "keywords": ["违约金", "赔偿"],
        "check_missing": False,
        "description": "违约金是否足以弥补损失",
    },
    "D03 违约金无上限": {
        "keywords": ["违约金", "赔偿"],
        "check_missing": False,
        "description": "违约金是否有累计上限",
    },
    "D04 单方解除权": {
        "keywords": ["解除", "终止", "单方"],
        "check_missing": False,
        "description": "解除条件是否对等",
    },
    "D05 赔偿范围": {
        "keywords": ["赔偿", "损失", "律师费", "诉讼费"],
        "check_missing": False,
        "description": "赔偿是否包含间接损失和维权费用",
    },
    "E01 管辖法院": {
        "keywords": ["管辖", "法院", "诉讼", "仲裁"],
        "check_missing": True,
        "description": "管辖法院是否有利于CSDN",
    },
    "E02 仲裁条款": {
        "keywords": ["仲裁", "仲裁委员会", "仲裁机构"],
        "check_missing": False,
        "description": "仲裁机构和仲裁地点",
    },
    "E03 争议期间履约": {
        "keywords": ["争议期间", "继续履行", "暂停"],
        "check_missing": False,
        "description": "争议期间是否继续履约",
    },
    "E04 送达地址": {
        "keywords": ["送达", "通知", "地址"],
        "check_missing": False,
        "description": "司法文书和通知的送达地址",
    },
    "F01 知识产权归属": {
        "keywords": ["知识产权", "著作权", "所有权", "归属"],
        "check_missing": True,
        "description": "成果知识产权归谁所有",
    },
    "F02 侵权保证": {
        "keywords": ["不侵犯", "不侵权", "保证.*知识产权", "侵权责任"],
        "check_missing": True,
        "description": "是否有不侵权保证条款",
    },
    "F03 侵权责任": {
        "keywords": ["侵权", "知识产权.*责任", "赔偿.*侵权"],
        "check_missing": False,
        "description": "侵权时的责任承担",
    },
    "F04 使用许可": {
        "keywords": ["许可", "授权", "使用范围", "使用期限"],
        "check_missing": False,
        "description": "使用范围和期限",
    },
    "G01 保密范围": {
        "keywords": ["保密", "机密", "保密信息", "保密范围"],
        "check_missing": True,
        "description": "保密信息范围是否明确",
    },
    "G02 保密期限": {
        "keywords": ["保密.*年", "保密期限", "保密.*月"],
        "check_missing": True,
        "description": "保密义务期限（2年/3年）",
    },
    "G03 保密违约金": {
        "keywords": ["保密.*违约金", "保密.*赔偿"],
        "check_missing": True,
        "description": "违反保密义务的违约金",
    },
    "G04 保密除外": {
        "keywords": ["除外", "已公开", "合法获取", "不属于保密"],
        "check_missing": False,
        "description": "保密义务的除外情形",
    },
    "H01 不可抗力范围": {
        "keywords": ["不可抗力", "自然灾害", "政府"],
        "check_missing": False,
        "description": "不可抗力的定义范围",
    },
    "H02 通知义务": {
        "keywords": ["不可抗力", "通知", "证明"],
        "check_missing": False,
        "description": "不可抗力发生后的通知时限",
    },
    "H03 免责范围": {
        "keywords": ["不可抗力", "免责", "不承担.*责任"],
        "check_missing": False,
        "description": "哪些责任可以免除",
    },
    "H04 不可抗力解除权": {
        "keywords": ["不可抗力", "解除"],
        "check_missing": False,
        "description": "因不可抗力解除合同的条件",
    },
    "I01 变更流程": {
        "keywords": ["变更", "修改", "补充协议", "书面"],
        "check_missing": False,
        "description": "合同变更是否需要书面协议",
    },
    "I02 解除条件": {
        "keywords": ["解除", "终止"],
        "check_missing": False,
        "description": "双方解除条件是否对等",
    },
    "I03 解除后清算": {
        "keywords": ["解除后", "终止后", "清算", "结算"],
        "check_missing": False,
        "description": "解除后的款项结算",
    },
    "I04 通知义务": {
        "keywords": ["提前通知", "书面通知", "通知.*解除"],
        "check_missing": False,
        "description": "解除通知的方式和效力",
    },
    "J01 附件效力": {
        "keywords": ["附件", "补充", "组成部分"],
        "check_missing": False,
        "description": "附件与主合同关系",
    },
    "J02 冲突解决": {
        "keywords": ["冲突", "不一致", "以.*为准", "优先"],
        "check_missing": False,
        "description": "条款冲突时的优先顺序",
    },
    "J03 通知送达": {
        "keywords": ["通知", "送达", "联系方式", "书面方式"],
        "check_missing": False,
        "description": "通知方式、送达地址",
    },
    "J04 完整协议": {
        "keywords": ["完整协议", "全部约定", "取代", "以本合同为准"],
        "check_missing": False,
        "description": "是否有完整协议条款",
    },
    "J05 可分割性": {
        "keywords": ["可分割", "部分无效", "不影响"],
        "check_missing": False,
        "description": "部分无效时的处理",
    },
    "J06 转让限制": {
        "keywords": ["转让", "转移", "让与", "未经同意"],
        "check_missing": False,
        "description": "合同权利义务转让限制",
    },
    # 额外类别（超越CUAD，适配中国市场）
    "K01 数据安全保护": {
        "keywords": ["数据", "个人信息", "隐私", "存储", "删除"],
        "check_missing": True,
        "description": "客户数据的保护和限制",
    },
    "K02 客户信息保护": {
        "keywords": ["客户", "用户", "客户信息", "用户信息"],
        "check_missing": True,
        "description": "客户信息的获取和使用限制",
    },
    "K03 质保期": {
        "keywords": ["质保", "保修", "质量保证", "三包"],
        "check_missing": True,
        "description": "商品/服务的质量保证期限",
    },
    "K04 金额大写校验": {
        "keywords": ["大写", "壹", "贰", "叁"],
        "check_missing": False,
        "description": "阿拉伯数字与中文大写是否一致",
    },
}


def cuad_full_scan(text, csdn_role, contract_type):
    """CUAD 41+风险类别全面扫描，输出每个类别的检查结果"""
    results = []

    for cat_id, cat_config in CUAD_CATEGORIES.items():
        keywords = cat_config["keywords"]
        check_missing = cat_config["check_missing"]

        # 检查关键词是否存在
        found_keywords = [kw for kw in keywords if kw in text]

        if found_keywords:
            # 找到关键词 → 提取相关段落
            paragraphs = extract_relevant_paragraphs(text, found_keywords)
            # 标记为"已检查"
            results.append({
                "category_id": cat_id,
                "category_name": cat_config["description"],
                "status": "checked",
                "keywords_found": found_keywords,
                "relevant_paragraphs": paragraphs[:3],  # 最多3段
                "paragraph_count": len(paragraphs),
            })
        else:
            # 未找到关键词
            if check_missing:
                results.append({
                    "category_id": cat_id,
                    "category_name": cat_config["description"],
                    "status": "missing",
                    "keywords_found": [],
                    "relevant_paragraphs": [],
                    "paragraph_count": 0,
                    "insertion_hint": f"该位置需要增加{cat_config['description']}相关条款",
                })
            else:
                results.append({
                    "category_id": cat_id,
                    "category_name": cat_config["description"],
                    "status": "not_found",
                    "keywords_found": [],
                    "relevant_paragraphs": [],
                    "paragraph_count": 0,
                })

    return results


# 缺失条款检查
REQUIRED_CLAUSES = [
    ("价款及支付方式", ["付款", "支付", "结算", "发票", "货款", "价款"]),
    ("验收标准和流程", ["验收", "检验", "检测", "合格"]),
    ("违约责任", ["违约", "赔偿", "违约金"]),
    ("争议解决", ["争议", "管辖", "仲裁", "诉讼", "法院"]),
    ("知识产权", ["知识产权", "著作权", "侵权", "专利"]),
    ("保密条款", ["保密", "机密", "不披露"]),
    ("不可抗力", ["不可抗力"]),
    ("合同变更解除", ["变更", "解除", "终止"]),
    ("通知送达", ["通知", "送达", "联系方式"]),
    ("合同生效条件", ["生效", "签字", "盖章"]),
    ("签字盖章页", ["签字", "盖章", "授权代表"]),
]


def parse_contract(file_path):
    """解析合同文件"""
    sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
    from parse_contract import parse_docx, parse_pdf

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".docx":
        return parse_docx(file_path)
    elif ext == ".pdf":
        return parse_pdf(file_path)
    elif ext == ".zip":
        from parse_contract import parse_zip
        return parse_zip(file_path)
    else:
        return {"error": f"不支持的文件格式: {ext}"}


def identify_contract_type(text):
    """识别合同类型"""
    best_type = "其他"
    best_score = 0
    for ctype, keywords in CONTRACT_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_type = ctype
    return best_type


def identify_csdn_role(text):
    """识别 CSDN 在合同中的角色"""
    for entity in CSDN_ENTITIES:
        # 找 "甲方：xxx" 或 "甲方（xxx）：xxx" 模式
        pattern_a = rf"甲方[^。\n]*?{re.escape(entity)}"
        pattern_b = rf"乙方[^。\n]*?{re.escape(entity)}"
        if re.search(pattern_a, text):
            return "甲方"
        if re.search(pattern_b, text):
            return "乙方"

    # 第二轮：在整段中查找
    for entity in CSDN_ENTITIES:
        if entity not in text:
            continue
        # 找甲方/乙方段落
        lines = text.split("\n")
        for line in lines:
            if entity in line:
                if "甲方" in line:
                    return "甲方"
                if "乙方" in line:
                    return "乙方"
    return "未知"


def identify_counterparty(text, csdn_role):
    """识别对方当事人"""
    target_role = "乙方" if csdn_role == "甲方" else "甲方"
    for line in text.split("\n"):
        if line.strip().startswith(target_role):
            # 提取公司名
            match = re.search(r"[\：:]?\s*(.+?公司|.+?有限公司|.+?研究院|.+?大学)", line)
            if match:
                name = match.group(1).strip()
                if not any(e in name for e in CSDN_ENTITIES):
                    return name
    return "未识别"


def load_knowledge_base(contract_type):
    """加载错题集"""
    corrections = []
    if os.path.exists(CORRECTIONS_DIR):
        for f in sorted(glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    c = json.load(fh)
                    if c.get("contract_type") == contract_type or not c.get("contract_type"):
                        corrections.append(c)
            except:
                pass

    rules = []
    if os.path.exists(RULES_DIR):
        for f in glob.glob(os.path.join(RULES_DIR, "*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    items = json.load(fh)
                    if isinstance(items, list):
                        rules.extend(items)
            except:
                pass

    return {"corrections": corrections[:20], "rules": rules}


def extract_relevant_paragraphs(text, keywords, window=150):
    """提取包含关键词的相关段落"""
    results = []
    seen = set()
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text):
            start = max(0, m.start() - window)
            end = min(len(text), m.end() + window)
            snippet = text[start:end].strip()
            if snippet not in seen:
                seen.add(snippet)
                results.append(snippet)
    return results[:10]  # 最多10条


def scan_dimension(text, dimension_config, role):
    """扫描单个审核维度"""
    results = []
    keywords = dimension_config["keywords"]

    # 获取对应角色的规则
    role_key = "rules_role_a" if role == "甲方" else "rules_role_b"
    role_rules = dimension_config.get(role_key, {})
    checks = role_rules.get("checks", [])

    # 提取相关段落
    paragraphs = extract_relevant_paragraphs(text, keywords)

    for check in checks:
        pattern = check["pattern"]
        anti_pattern = check.get("anti_pattern")

        # 在相关段落中搜索
        for para in paragraphs:
            match = re.search(pattern, para)
            if not match:
                continue

            # 如果有反模式（检查缺失的情况），跳过已有反模式的段落
            if anti_pattern and check.get("check_type") == "anti_pattern_missing":
                if re.search(anti_pattern, para):
                    continue
                # 对于缺失检查，用整个文本判断
                if re.search(anti_pattern, text):
                    continue

            # 提取原始句子（包含匹配的句子）
            sentences = re.split(r"[。；！？\n]", para)
            matched_sentence = ""
            for s in sentences:
                if re.search(pattern, s):
                    matched_sentence = s.strip()
                    break

            if not matched_sentence:
                matched_sentence = para[:100]

            # 避免重复
            issue_key = f"{check['name']}:{matched_sentence[:50]}"
            if any(r.get("_key") == issue_key for r in results):
                continue

            results.append({
                "dimension": dimension_config.get("dimension_name", ""),
                "check_name": check["name"],
                "severity": check["severity"],
                "original_text": matched_sentence,
                "suggested_modification": check["suggestion"],
                "reason": check["issue"],
                "rule_reference": check["rule_ref"],
                "source": "审核要点",
                "category": check.get("category", ""),
            })
            results[-1]["_key"] = issue_key
            break  # 每个检查只匹配第一个

    return results


# ============================================================
# 文字校对：错别字/多余字/标点问题
# ============================================================

# 错误词 → (正确词, 说明)
TYPO_DICTIONARY = {
    # 财务/金额类
    "帐号": ("账号", "财务用语应为'账号'"),
    "帐户": ("账户", "财务用语应为'账户'"),
    "进帐": ("进账", "财务用语应为'进账'"),
    "收帐": ("收账", "财务用语应为'收账'"),
    "转帐": ("转账", "财务用语应为'转账'"),
    "付帐": ("付账", "财务用语应为'付账'"),
    "欠帐": ("欠账", "财务用语应为'欠账'"),
    "坏帐": ("坏账", "财务用语应为'坏账'"),
    "报帐": ("报账", "财务用语应为'报账'"),
    "结帐": ("结账", "财务用语应为'结账'"),
    "呆帐": ("呆账", "财务用语应为'呆账'"),
    # 合同/法律术语
    "签定": ("签订", "法律用语应为'签订'"),
    "定立": ("订立", "法律用语应为'订立'"),
    "撤消": ("撤销", "法律用语应为'撤销'"),
    "申斥": ("申诉", "法律用语应为'申诉'"),
    "辩驳": ("答辩", "法律用语应为'答辩'"),
    "做为": ("作为", "应使用'作为'"),
    "作法": ("做法", "应使用'做法'"),
    "申明": ("声明", "法律文件中一般使用'声明'"),
    "反应": ("反映", "表示'反馈'义时应为'反映'"),
    "权力": None,  # 上下文判断：权力(rights) vs 权利(rights)
    "权利": None,
    # 常见错别字
    "既使": ("即使", "应为'即使'"),
    "凑和": ("凑合", "应为'凑合'"),
    "迫不急待": ("迫不及待", "应为'迫不及待'"),
    "一如继往": ("一如既往", "应为'一如既往'"),
    "默守成规": ("墨守成规", "应为'墨守成规'"),
    "按装": ("安装", "应为'安装'"),
    "不记其数": ("不计其数", "应为'不计其数'"),
    "自暴自起": ("自暴自弃", "应为'自暴自弃'"),
    "一幅对联": ("一副对联", "量词应为'副'"),
    "再接再历": ("再接再厉", "应为'再接再厉'"),
    "谈笑风声": ("谈笑风生", "应为'谈笑风生'"),
    "床第之私": ("床笫之私", "应为'床笫之私'"),
    "世外桃园": ("世外桃源", "应为'世外桃源'"),
    "金壁辉煌": ("金碧辉煌", "应为'金碧辉煌'"),
    "一愁莫展": ("一筹莫展", "应为'一筹莫展'"),
    "穿流不息": ("川流不息", "应为'川流不息'"),
    "竭泽而鱼": ("竭泽而渔", "应为'竭泽而渔'"),
    "旁证博引": ("旁征博引", "应为'旁征博引'"),
    "山洪爆法": ("山洪暴发", "应为'暴发'"),
    "必需品": ("必需品", None),  # "必需"和"必须"需上下文判断
    "承诺书": None,  # 正确用法，跳过
}

# 不应被误报为重复字符的合法叠词
REPEAT_WHITELIST = {
    "常常", "时时", "处处", "事事", "人人", "种种", "层层", "步步",
    "件件", "条条", "款款", "项项", "条条框框", "明明白白", "清清楚楚",
    "认认真真", "严严实实", "实实在在", "妥妥当当", "顺顺利利",
    "平平安安", "方方正正", "整整齐齐", "完完全全", "确确实实",
    "好好", "慢慢", "轻轻", "细细", "紧紧", "牢牢", "多多",
    "谢谢", "得得", "行行", "对对", "是是", "好好",
    "某某", "某某某",  # 代称
    "方方", "圆圆",  # 常见人名
}


def check_text_typos(text):
    """检测合同文本中的错别字、多余字、别字"""
    issues = []

    # ---- 1. 错别字词典扫描 ----
    for wrong, info in TYPO_DICTIONARY.items():
        if info is None:
            continue  # 需要上下文判断的跳过
        correct, reason = info
        # 找所有出现位置
        for m in re.finditer(re.escape(wrong), text):
            pos = m.start()
            # 提取上下文（前后各30字）
            ctx_start = max(0, pos - 30)
            ctx_end = min(len(text), pos + len(wrong) + 30)
            context = text[ctx_start:ctx_end].strip()

            # 跳过标题/文件名中的（通常是引用）
            line_start = text.rfind("\n", 0, pos)
            line = text[line_start:pos + len(wrong) + 10].strip()

            issue_key = f"typo:{wrong}:{pos}"
            if any(i.get("_key") == issue_key for i in issues):
                continue

            issues.append({
                "dimension": "文字校对",
                "check_name": "错别字",
                "severity": "low",
                "original_text": context,
                "suggested_modification": f"将'{wrong}'改为'{correct}'",
                "reason": f"'{wrong}'为错别字，{reason}",
                "rule_reference": "文字校对规范",
                "source": "文字校对",
                "category": "文字校对",
            })
            issues[-1]["_key"] = issue_key

    # ---- 2. 重复字符检测（连续重复2字以上的中文） ----
    for m in re.finditer(r'([\u4e00-\u9fff]{1,2})\1{1,}', text):
        matched = m.group(0)
        # 检查是否为合法叠词
        base = m.group(1)
        if matched in REPEAT_WHITELIST or base in REPEAT_WHITELIST:
            continue
        # 2字叠词如"条条款款"也可能是合法的
        if len(base) == 2 and matched == base + base:
            # 如"认认真真"这种AABB格式，检查是否全在白名单
            continue
        if len(base) == 1 and matched == base * 2 and base * 2 in REPEAT_WHITELIST:
            continue

        pos = m.start()
        ctx_start = max(0, pos - 20)
        ctx_end = min(len(text), pos + len(matched) + 20)
        context = text[ctx_start:ctx_end].strip()

        issue_key = f"repeat:{matched}:{pos}"
        issues.append({
            "dimension": "文字校对",
            "check_name": "重复多余字符",
            "severity": "low",
            "original_text": context,
            "suggested_modification": f"删除重复的'{base}'",
            "reason": f"疑似重复多余字符：'{matched}'",
            "rule_reference": "文字校对规范",
            "source": "文字校对",
            "category": "文字校对",
        })
        issues[-1]["_key"] = issue_key

    # ---- 3. 标点问题（连续3个以上相同中文标点） ----
    for m in re.finditer(r'([。，、；：！？…])\1{2,}', text):
        matched = m.group(0)
        pos = m.start()
        ctx_start = max(0, pos - 20)
        ctx_end = min(len(text), pos + len(matched) + 20)
        context = text[ctx_start:ctx_end].strip()

        issue_key = f"punct:{matched}:{pos}"
        issues.append({
            "dimension": "文字校对",
            "check_name": "标点重复",
            "severity": "low",
            "original_text": context,
            "suggested_modification": f"将连续{len(matched)}个'{matched[0]}'改为1个",
            "reason": f"标点符号重复：'{matched}'",
            "rule_reference": "文字校对规范",
            "source": "文字校对",
            "category": "文字校对",
        })
        issues[-1]["_key"] = issue_key

    # ---- 4. 中英文标点混用 ----
    # 中文句子中出现英文标点（排除数字、英文、括号内）
    lines = text.split("\n")
    for line_idx, line in enumerate(lines):
        # 跳过纯英文/数字/空行
        if not line.strip() or not re.search(r'[\u4e00-\u9fff]', line):
            continue

        # 检查中文语境中使用英文逗号、句号、冒号、分号
        for m in re.finditer(r'[\u4e00-\u9fff]\s*([,;])\s*[\u4e00-\u9fff]', line):
            punct = m.group(1)
            cn_punct = {"，", "；"}
            en_to_cn = {",": "，", ";": "；"}
            ctx_start = max(0, m.start() - 10)
            ctx_end = min(len(line), m.end() + 10)
            context = line[ctx_start:ctx_end].strip()

            issue_key = f"punct_mix:{en_to_cn[punct]}:{line_idx}:{m.start()}"
            issues.append({
                "dimension": "文字校对",
                "check_name": "中英文标点混用",
                "severity": "low",
                "original_text": context,
                "suggested_modification": f"将英文'{punct}'改为中文'{en_to_cn[punct]}'",
                "reason": f"中文语境中使用了英文标点'{punct}'，应使用中文标点",
                "rule_reference": "文字校对规范",
                "source": "文字校对",
                "category": "文字校对",
            })
            issues[-1]["_key"] = issue_key

    return issues


def check_missing_clauses(text):
    """检查缺失的必要条款"""
    missing = []
    for clause_name, keywords in REQUIRED_CLAUSES:
        found = any(kw in text for kw in keywords)
        if not found:
            missing.append({
                "clause": clause_name,
                "severity": "medium",
                "suggestion": f"建议增加{clause_name}相关条款",
            })
    return missing


# ============================================================
# 金额大写校验
# ============================================================
# 中文大写数字映射
CN_DIGIT_MAP = {
    "零": 0, "壹": 1, "贰": 2, "叁": 3, "肆": 4,
    "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9,
}
CN_UNIT_MAP = {
    "拾": 10, "佰": 100, "仟": 1000,
    "万": 10000, "亿": 100000000,
}


def cn_amount_to_number(cn_text):
    """将中文大写金额转换为数字（支持：壹拾贰万叁仟肆佰伍拾陆元整）"""
    cn_text = cn_text.strip()
    # 移除常见前缀和后缀
    for prefix in ["人民币", "大写", "：", ":"]:
        if cn_text.startswith(prefix):
            cn_text = cn_text[len(prefix):]
    for suffix in ["元整", "圆整", "元", "圆", "整"]:
        if cn_text.endswith(suffix):
            cn_text = cn_text[:-len(suffix)]

    cn_text = cn_text.strip()
    if not cn_text:
        return None

    try:
        result = 0
        section = 0  # 亿/万分段内的值
        current = 0  # 当前累积的数字

        for char in cn_text:
            if char in CN_DIGIT_MAP:
                current = CN_DIGIT_MAP[char]
            elif char == "拾":
                if current == 0:
                    current = 1  # "拾万" = 10万
                section += current * 10
                current = 0
            elif char == "佰":
                if current == 0:
                    current = 1
                section += current * 100
                current = 0
            elif char == "仟":
                if current == 0:
                    current = 1
                section += current * 1000
                current = 0
            elif char == "万":
                section += current
                current = 0
                result = (result + section) * 10000
                section = 0
            elif char == "亿":
                section += current
                current = 0
                result = (result + section) * 100000000
                section = 0
            else:
                return None

        section += current
        result += section
        return result
    except Exception:
        return None


def check_amount_consistency(text):
    """校验合同中阿拉伯数字金额与中文大写金额是否一致"""
    issues = []

    # 匹配模式1: 数字+（大写：XXX元整）
    pattern1 = re.findall(
        r'[￥￥]?\s*([\d,]+\.?\d*)\s*元?\s*[（(]\s*(?:大写[：:]?\s*)?(?:人民币)?\s*([壹贰叁肆伍陆柒捌玖零拾佰仟万亿]+[元圆][整]?)\s*[）)]',
        text
    )
    # 匹配模式2: 大写在前，数字在后
    pattern2 = re.findall(
        r'([壹贰叁肆伍陆柒捌玖零拾佰仟万亿]+[元圆][整]?)\s*[（(]\s*[￥￥]?\s*([\d,]+\.?\d*)\s*元?\s*[）)]',
        text
    )

    checked = set()

    for arabic_str, cn_str in pattern1:
        key = f"{arabic_str}|{cn_str}"
        if key in checked:
            continue
        checked.add(key)

        try:
            arabic_num = float(arabic_str.replace(",", ""))
        except ValueError:
            continue

        cn_num = cn_amount_to_number(cn_str)
        if cn_num is not None and abs(arabic_num - cn_num) > 0.01:
            issues.append({
                "dimension": "金额校验",
                "check_name": "金额大写不一致",
                "severity": "high",
                "original_text": f"{arabic_str}元 vs {cn_str}",
                "suggested_modification": f"两处金额不一致：阿拉伯数字为{arabic_num}元，中文大写为{cn_num}元，请核实正确金额",
                "reason": f"合同金额阿拉伯数字（{arabic_num}元）与中文大写（{cn_num}元）不一致，存在重大风险",
                "rule_reference": "合同金额大写校验：阿拉伯数字与中文大写必须一致（基于99份已审核合同的格式规范）",
                "source": "审核要点",
                "category": "金额校验",
            })

    for cn_str, arabic_str in pattern2:
        key = f"{arabic_str}|{cn_str}"
        if key in checked:
            continue
        checked.add(key)

        try:
            arabic_num = float(arabic_str.replace(",", ""))
        except ValueError:
            continue

        cn_num = cn_amount_to_number(cn_str)
        if cn_num is not None and abs(arabic_num - cn_num) > 0.01:
            issues.append({
                "dimension": "金额校验",
                "check_name": "金额大写不一致",
                "severity": "high",
                "original_text": f"{cn_str} vs {arabic_str}元",
                "suggested_modification": f"两处金额不一致：中文大写为{cn_num}元，阿拉伯数字为{arabic_num}元，请核实正确金额",
                "reason": f"合同金额中文大写（{cn_num}元）与阿拉伯数字（{arabic_num}元）不一致，存在重大风险",
                "rule_reference": "合同金额大写校验：阿拉伯数字与中文大写必须一致（基于99份已审核合同的格式规范）",
                "source": "审核要点",
                "category": "金额校验",
            })

    # 检查是否有金额但缺少大写
    amount_lines = re.findall(r'[￥￥]\s*[\d,]+\.?\d*\s*元', text)
    has_cn_upper = bool(re.search(r'[壹贰叁肆伍陆柒捌玖].*[元圆]', text))
    if amount_lines and not has_cn_upper:
        issues.append({
            "dimension": "金额校验",
            "check_name": "金额缺少中文大写",
            "severity": "medium",
            "original_text": amount_lines[0],
            "suggested_modification": "建议在金额后增加中文大写（如：488,000元（大写：肆拾捌万捌仟元整））",
            "reason": "金额仅有阿拉伯数字，缺少中文大写校验",
            "rule_reference": "CSDN合同规范：55%的已审核合同使用阿拉伯数字+中文大写双格式",
            "source": "审核要点",
            "category": "金额校验",
        })

    return issues


def run_pipeline(file_path):
    """执行完整审查流水线"""
    # 1. 解析合同
    contract = parse_contract(file_path)
    if "error" in contract:
        return {"error": contract["error"]}

    full_text = contract.get("full_text", "")

    # 2. 识别合同类型和角色
    contract_type = identify_contract_type(full_text)
    csdn_role = identify_csdn_role(full_text)
    counterparty = identify_counterparty(full_text, csdn_role)

    # 3. 加载错题集
    kb = load_knowledge_base(contract_type)

    # 4. 逐维度扫描
    all_issues = []
    for dim_name, dim_config in AUDIT_DIMENSIONS.items():
        dim_config["dimension_name"] = dim_name
        issues = scan_dimension(full_text, dim_config, csdn_role)
        all_issues.extend(issues)

    # 5. 缺失条款检查
    missing = check_missing_clauses(full_text)

    # 5.5 金额大写校验
    amount_issues = check_amount_consistency(full_text)
    all_issues.extend(amount_issues)

    # 5.6 文字校对（错别字/多余字/标点）
    typo_issues = check_text_typos(full_text)
    all_issues.extend(typo_issues)

    # 6. CUAD 41+全面扫描
    cuad_results = cuad_full_scan(full_text, csdn_role, contract_type)

    # 7. 组装输出
    output = {
        "contract_info": {
            "file_name": os.path.basename(file_path),
            "contract_type": contract_type,
            "csdn_role": csdn_role,
            "counterparty": counterparty,
            "paragraph_count": contract.get("paragraph_count", 0),
            "text_length": len(full_text),
        },
        "scan_results": all_issues,
        "cuad_scan": cuad_results,
        "market_benchmarks": {
            "source": "knowledge/market-benchmarks.md",
            "csdn_role": csdn_role,
            "note": "CSDN特定标准详见 market-benchmarks.md，每个修改建议应引用市场基准",
        },
        "missing_clauses": missing,
        "confirmed_ok": [],
        "kb_corrections": kb["corrections"][:5],
        "kb_rules": kb["rules"],
        "summary": {
            "high": sum(1 for i in all_issues if i["severity"] == "high"),
            "medium": sum(1 for i in all_issues if i["severity"] == "medium"),
            "low": sum(1 for i in all_issues if i["severity"] == "low"),
            "missing": len(missing),
            "cuad_checked": sum(1 for c in cuad_results if c["status"] == "checked"),
            "cuad_missing": sum(1 for c in cuad_results if c["status"] == "missing"),
            "cuad_total": len(cuad_results),
        },
    }

    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="合同审查流水线")
    parser.add_argument("file", help="合同文件路径")
    parser.add_argument("--output", default="json", choices=["json"], help="输出格式")
    args = parser.parse_args()

    result = run_pipeline(args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
