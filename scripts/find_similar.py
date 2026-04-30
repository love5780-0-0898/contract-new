"""
相似合同匹配 - 基于关键词的相似度匹配
用法: python3 find_similar.py --text "<合同摘要>" --top 5
"""
import sys
import os
import json
import math
from collections import Counter

CONTRACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "knowledge-base", "contracts")

def tokenize(text):
    """简单分词（基于字符和标点）"""
    if not text:
        return []
    # 移除标点和空白，按 2-gram 分词
    text = ''.join(c for c in text if c.isalnum() or '\u4e00' <= c <= '\u9fff')
    if len(text) < 2:
        return [text] if text else []
    return [text[i:i+2] for i in range(len(text)-1)]

def compute_tf(text):
    """计算词频"""
    tokens = tokenize(text)
    counter = Counter(tokens)
    total = len(tokens) or 1
    return {k: v / total for k, v in counter.items()}

def cosine_similarity(tf1, tf2):
    """计算余弦相似度"""
    all_keys = set(tf1.keys()) | set(tf2.keys())
    if not all_keys:
        return 0.0

    dot_product = sum(tf1.get(k, 0) * tf2.get(k, 0) for k in all_keys)
    norm1 = math.sqrt(sum(v ** 2 for v in tf1.values()))
    norm2 = math.sqrt(sum(v ** 2 for v in tf2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)

def find_similar(query_text, top=5):
    """查找相似合同"""
    index_path = os.path.join(CONTRACTS_DIR, "index.json")

    if not os.path.exists(index_path):
        return {"status": "no_index", "message": "尚无历史合同索引", "results": []}

    with open(index_path, 'r', encoding='utf-8') as f:
        contracts = json.load(f)

    if not contracts:
        return {"status": "empty", "message": "索引为空", "results": []}

    query_tf = compute_tf(query_text)
    results = []

    for contract in contracts:
        summary = contract.get("summary", "") or contract.get("title", "")
        contract_tf = compute_tf(summary)
        similarity = cosine_similarity(query_tf, contract_tf)

        if similarity > 0.01:
            results.append({
                "contract": contract,
                "similarity": round(similarity, 4)
            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    results = results[:top]

    return {"status": "success", "query_length": len(query_text), "results": results}

def add_to_index(contract_info):
    """添加合同到索引"""
    os.makedirs(CONTRACTS_DIR, exist_ok=True)
    index_path = os.path.join(CONTRACTS_DIR, "index.json")

    contracts = []
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            contracts = json.load(f)

    contracts.append(contract_info)

    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(contracts, f, ensure_ascii=False, indent=2)

    return {"status": "added", "total": len(contracts)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="相似合同匹配")
    parser.add_argument("--text", required=True, help="合同摘要文本")
    parser.add_argument("--top", type=int, default=5, help="返回数量")
    parser.add_argument("--add", help="添加合同到索引（JSON 格式）")
    args = parser.parse_args()

    if args.add:
        result = add_to_index(json.loads(args.add))
    else:
        result = find_similar(args.text, args.top)

    print(json.dumps(result, ensure_ascii=False, indent=2))
