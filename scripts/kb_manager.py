"""
错题集管理器 - 管理审核经验的学习系统
用法:
  python3 kb_manager.py load --type <合同类型>
  python3 kb_manager.py save --correction <correction.json>
  python3 kb_manager.py list --type <合同类型>
  python3 kb_manager.py search --query <关键词>
  python3 kb_manager.py promote  # 提炼规则
  python3 kb_manager.py stats
"""
import sys
import os
import json
import glob
import hashlib
from datetime import datetime
from collections import defaultdict

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "knowledge-base")
CORRECTIONS_DIR = os.path.join(KB_DIR, "corrections")
RULES_DIR = os.path.join(KB_DIR, "rules")
CONTRACTS_DIR = os.path.join(KB_DIR, "contracts")

def ensure_dirs():
    for d in [CORRECTIONS_DIR, RULES_DIR, CONTRACTS_DIR]:
        os.makedirs(d, exist_ok=True)

def generate_id():
    date_str = datetime.now().strftime("%Y-%m-%d")
    hash_str = hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:6]
    return f"{date_str}_{hash_str}"

def load_rules(contract_type=None):
    """加载规则和最近的修正记录"""
    ensure_dirs()
    result = {"rules": [], "recent_corrections": []}

    # 加载通用规则
    general_rules_path = os.path.join(RULES_DIR, "general-rules.json")
    if os.path.exists(general_rules_path):
        with open(general_rules_path, 'r', encoding='utf-8') as f:
            result["rules"].extend(json.load(f))

    # 加载合同类型特定规则
    if contract_type:
        type_map = {
            "采购合同": "procurement-rules",
            "销售合同": "sales-rules",
            "技术服务合同": "service-rules",
            "合作协议": "cooperation-rules",
            "代销合同": "agency-rules",
            "保密协议": "nda-rules",
            "赞助协议": "sponsorship-rules",
        }
        rule_key = type_map.get(contract_type, "other-rules")
        type_rules_path = os.path.join(RULES_DIR, f"{rule_key}.json")
        if os.path.exists(type_rules_path):
            with open(type_rules_path, 'r', encoding='utf-8') as f:
                result["rules"].extend(json.load(f))

    # 加载最近的修正记录（最多 20 条）
    corrections = []
    for f in sorted(glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")), reverse=True)[:20]:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                corr = json.load(fh)
                if not contract_type or corr.get("contract_type") == contract_type:
                    corrections.append(corr)
        except:
            pass

    result["recent_corrections"] = corrections[:10]
    result["total_rules"] = len(result["rules"])
    result["total_corrections"] = len(corrections)

    return result

def save_correction(correction_data):
    """保存修正记录"""
    ensure_dirs()

    if isinstance(correction_data, str):
        with open(correction_data, 'r', encoding='utf-8') as f:
            correction_data = json.load(f)

    # 添加 ID 和日期
    if "id" not in correction_data:
        correction_data["id"] = generate_id()
    if "date" not in correction_data:
        correction_data["date"] = datetime.now().strftime("%Y-%m-%d")

    # 保存文件
    file_path = os.path.join(CORRECTIONS_DIR, f"{correction_data['id']}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(correction_data, f, ensure_ascii=False, indent=2)

    # 检查是否需要提炼规则
    _check_promote_rules(correction_data.get("contract_type"), correction_data.get("clause_category"))

    return {"status": "saved", "id": correction_data["id"], "path": file_path}

def list_corrections(contract_type=None, limit=20):
    """列出修正记录"""
    ensure_dirs()
    corrections = []

    for f in sorted(glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")), reverse=True):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                corr = json.load(fh)
                if not contract_type or corr.get("contract_type") == contract_type:
                    corrections.append(corr)
        except:
            pass

    return {"count": len(corrections), "corrections": corrections[:limit]}

def search_corrections(query):
    """搜索修正记录"""
    ensure_dirs()
    results = []

    for f in glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
                if query.lower() in content.lower():
                    results.append(json.loads(content))
        except:
            pass

    return {"query": query, "count": len(results), "results": results[:10]}

def _check_promote_rules(contract_type, clause_category):
    """检查是否有同类修正达到提炼阈值（3次）"""
    if not clause_category:
        return

    ensure_dirs()
    count = 0
    pattern_texts = []

    for f in glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                corr = json.load(fh)
                if corr.get("clause_category") == clause_category:
                    count += 1
                    if corr.get("user_correction"):
                        pattern_texts.append(corr["user_correction"])
        except:
            pass

    if count >= 3:
        # 自动提炼规则
        rule_id = f"RULE-{clause_category}-{generate_id()}"
        rule = {
            "id": rule_id,
            "source": "auto_promoted",
            "category": clause_category,
            "condition": f"同类修正已出现 {count} 次",
            "action": pattern_texts[-1] if pattern_texts else "参见历史修正",
            "priority": "high",
            "contract_types": [contract_type] if contract_type else [],
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "occurrence_count": count
        }

        rules_path = os.path.join(RULES_DIR, "general-rules.json")
        existing = []
        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)

        # 检查是否已有同类规则
        if not any(r.get("category") == clause_category for r in existing):
            existing.append(rule)
            with open(rules_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

            return {"promoted": True, "rule_id": rule_id}

    return {"promoted": False}

def promote_rules():
    """手动触发规则提炼"""
    ensure_dirs()
    promoted = []

    # 统计所有类别
    category_counts = defaultdict(lambda: {"count": 0, "types": set(), "examples": []})

    for f in glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                corr = json.load(fh)
                cat = corr.get("clause_category")
                if cat:
                    category_counts[cat]["count"] += 1
                    if corr.get("contract_type"):
                        category_counts[cat]["types"].add(corr["contract_type"])
                    if corr.get("user_correction"):
                        category_counts[cat]["examples"].append(corr["user_correction"])
        except:
            pass

    # 对达到阈值的类别提炼规则
    for cat, data in category_counts.items():
        if data["count"] >= 3:
            _check_promote_rules(list(data["types"])[0] if data["types"] else None, cat)
            promoted.append({"category": cat, "count": data["count"]})

    return {"promoted_count": len(promoted), "categories": promoted}

def get_stats():
    """获取知识库统计"""
    ensure_dirs()

    correction_count = len(glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")))
    rules_count = 0
    for f in glob.glob(os.path.join(RULES_DIR, "*.json")):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                rules_count += len(json.load(fh))
        except:
            pass

    contract_count = len(glob.glob(os.path.join(CONTRACTS_DIR, "*.json")))

    return {
        "corrections": correction_count,
        "rules": rules_count,
        "indexed_contracts": contract_count,
        "status": "ready" if correction_count > 0 else "empty"
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="错题集管理器")
    subparsers = parser.add_subparsers(dest="command")

    # load
    load_parser = subparsers.add_parser("load")
    load_parser.add_argument("--type", help="合同类型")

    # save
    save_parser = subparsers.add_parser("save")
    save_parser.add_argument("--correction", required=True, help="修正记录 JSON 路径或 JSON 字符串")

    # list
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--type", help="合同类型")
    list_parser.add_argument("--limit", type=int, default=20)

    # search
    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--query", required=True)

    # promote
    subparsers.add_parser("promote")

    # stats
    subparsers.add_parser("stats")

    args = parser.parse_args()

    if args.command == "load":
        result = load_rules(args.type)
    elif args.command == "save":
        if os.path.exists(args.correction):
            result = save_correction(args.correction)
        else:
            result = save_correction(json.loads(args.correction))
    elif args.command == "list":
        result = list_corrections(args.type, args.limit)
    elif args.command == "search":
        result = search_corrections(args.query)
    elif args.command == "promote":
        result = promote_rules()
    elif args.command == "stats":
        result = get_stats()
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
