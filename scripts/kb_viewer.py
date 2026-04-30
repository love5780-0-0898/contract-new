"""
错题集可视化页面生成器
用法: python3 kb_viewer.py [--output <output.html>]
生成一个独立的 HTML 页面，展示错题集的所有内容。
"""
import sys
import os
import json
import glob
from datetime import datetime

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "knowledge-base")
CORRECTIONS_DIR = os.path.join(KB_DIR, "corrections")
RULES_DIR = os.path.join(KB_DIR, "rules")
CONTRACTS_DIR = os.path.join(KB_DIR, "contracts")


def load_all_corrections():
    """加载所有修正记录"""
    corrections = []
    for f in sorted(glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")), reverse=True):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                corrections.append(json.load(fh))
        except:
            pass
    return corrections


def load_all_rules():
    """加载所有规则"""
    rules = []
    for f in glob.glob(os.path.join(RULES_DIR, "*.json")):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                items = json.load(fh)
                if isinstance(items, list):
                    rules.extend(items)
        except:
            pass
    return rules


def load_indexed_contracts():
    """加载已索引合同"""
    index_path = os.path.join(CONTRACTS_DIR, "index.json")
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def get_stats(corrections, rules, contracts):
    """统计数据"""
    from collections import Counter

    # 按合同类型统计
    type_counts = Counter(c.get("contract_type", "未分类") for c in corrections)
    # 按条款类别统计
    category_counts = Counter(c.get("clause_category", "未分类") for c in corrections)
    # 按风险等级统计
    severity_counts = Counter(c.get("severity", "未标注") for c in corrections)
    # 按月份统计
    month_counts = Counter(c.get("date", "")[:7] for c in corrections if c.get("date"))
    # 高频标签
    tag_counts = Counter()
    for c in corrections:
        for tag in c.get("tags", []):
            tag_counts[tag] += 1

    return {
        "total_corrections": len(corrections),
        "total_rules": len(rules),
        "total_contracts": len(contracts),
        "type_counts": dict(type_counts),
        "category_counts": dict(category_counts),
        "severity_counts": dict(severity_counts),
        "month_counts": dict(sorted(month_counts.items())),
        "top_tags": dict(tag_counts.most_common(10))
    }


def generate_html(output_path):
    corrections = load_all_corrections()
    rules = load_all_rules()
    contracts = load_indexed_contracts()
    stats = get_stats(corrections, rules, contracts)

    severity_style = {
        "high": ("高风险 🔴", "#dc3545"),
        "medium": ("中风险 🟡", "#ffc107"),
        "low": ("低风险 🟢", "#28a745"),
    }

    # === 修正记录卡片 ===
    correction_cards = ""
    for c in corrections:
        sev = c.get("severity", "low")
        sev_label, sev_color = severity_style.get(sev, ("未知", "#6c757d"))
        tags_html = "".join(
            f'<span class="tag">{t}</span>' for t in c.get("tags", [])
        )
        card = f"""
        <div class="card" data-type="{c.get('contract_type', '')}" data-category="{c.get('clause_category', '')}" data-severity="{sev}">
            <div class="card-header">
                <span class="severity-badge" style="background:{sev_color}">{sev_label}</span>
                <span class="card-id">{c.get('id', '')}</span>
                <span class="card-date">{c.get('date', '')}</span>
                <span class="card-type">{c.get('contract_type', '')}</span>
            </div>
            <div class="card-body">
                <div class="field-group">
                    <label>条款类别</label>
                    <span>{c.get('clause_category', '')}</span>
                </div>
                <div class="diff-section">
                    <div class="diff-item">
                        <label>原文条款</label>
                        <div class="original-text">{c.get('original_clause', '')}</div>
                    </div>
                    <div class="diff-arrow">→ 用户修正 ↓</div>
                    <div class="diff-item">
                        <label>AI 建议</label>
                        <div class="ai-text">{c.get('ai_suggestion', '')}</div>
                    </div>
                    <div class="diff-arrow">→</div>
                    <div class="diff-item">
                        <label>用户最终修正</label>
                        <div class="corrected-text">{c.get('user_correction', '')}</div>
                    </div>
                </div>
                <div class="field-group">
                    <label>修正理由</label>
                    <span class="reason">{c.get('correction_reason', '')}</span>
                </div>
                <div class="tags">{tags_html}</div>
            </div>
        </div>"""
        correction_cards += card

    if not correction_cards:
        correction_cards = """
        <div class="empty-state">
            <div class="empty-icon">📝</div>
            <h3>错题集为空</h3>
            <p>当你审查合同时，对 AI 建议进行修正后，经验会自动积累到这里。</p>
            <p>使用方式：在审查合同后说"这条不对，应该是XXX"</p>
        </div>"""

    # === 规则卡片 ===
    rule_cards = ""
    for r in rules:
        priority_style = {"high": "#dc3545", "medium": "#ffc107", "low": "#28a745"}
        p_color = priority_style.get(r.get("priority", "low"), "#6c757d")
        card = f"""
        <div class="rule-card">
            <div class="rule-header">
                <span class="rule-id">{r.get('id', '')}</span>
                <span class="priority-badge" style="background:{p_color}">优先级：{r.get('priority', '')}</span>
                <span class="rule-date">创建于 {r.get('created_date', '')}</span>
            </div>
            <div class="rule-body">
                <div class="field-group">
                    <label>触发条件</label>
                    <span>{r.get('condition', '')}</span>
                </div>
                <div class="field-group">
                    <label>建议动作</label>
                    <span>{r.get('action', '')}</span>
                </div>
                <div class="field-group">
                    <label>适用合同类型</label>
                    <span>{', '.join(r.get('contract_types', [])) or '全部'}</span>
                </div>
                <div class="field-group">
                    <label>来源修正</label>
                    <span>{', '.join(r.get('source_correction_ids', []))}</span>
                </div>
            </div>
        </div>"""
        rule_cards += card

    if not rule_cards:
        rule_cards = """
        <div class="empty-state">
            <div class="empty-icon">📊</div>
            <h3>尚无自动提炼的规则</h3>
            <p>当同类修正出现 3 次以上时，系统会自动提炼为审核规则。</p>
        </div>"""

    # === 统计图表 ===
    type_chart_bars = ""
    max_type_count = max(stats["type_counts"].values()) if stats["type_counts"] else 1
    for t, cnt in sorted(stats["type_counts"].items(), key=lambda x: -x[1]):
        pct = int(cnt / max_type_count * 100)
        type_chart_bars += f"""
        <div class="chart-row">
            <span class="chart-label">{t}</span>
            <div class="chart-bar" style="width:{pct}%"><span>{cnt}</span></div>
        </div>"""

    category_chart_bars = ""
    max_cat_count = max(stats["category_counts"].values()) if stats["category_counts"] else 1
    for cat, cnt in sorted(stats["category_counts"].items(), key=lambda x: -x[1]):
        pct = int(cnt / max_cat_count * 100)
        category_chart_bars += f"""
        <div class="chart-row">
            <span class="chart-label">{cat}</span>
            <div class="chart-bar cat-bar" style="width:{pct}%"><span>{cnt}</span></div>
        </div>"""

    # === 页面 ===
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CSDN 合同审核 · 错题集</title>
<style>
:root {{
  --bg: #f5f7fa; --card-bg: #fff; --text: #1a1a2e; --text2: #6c757d;
  --accent: #e94560; --accent2: #0f3460; --border: #dee2e6;
  --green: #28a745; --yellow: #ffc107; --red: #dc3545;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); }}

.header {{ background: linear-gradient(135deg, #1a1a2e, #0f3460); color: #fff; padding: 30px 40px; }}
.header h1 {{ font-size: 24px; margin-bottom: 5px; }}
.header p {{ opacity: 0.7; font-size: 14px; }}

.stats-bar {{ display: flex; gap: 15px; padding: 20px 40px; background: #fff; border-bottom: 1px solid var(--border); flex-wrap: wrap; }}
.stat-card {{ flex: 1; min-width: 140px; padding: 15px; border-radius: 10px; text-align: center; }}
.stat-card .num {{ font-size: 32px; font-weight: bold; }}
.stat-card .label {{ font-size: 13px; color: var(--text2); margin-top: 4px; }}
.stat-total {{ background: #eef2ff; }}
.stat-rules {{ background: #e8f5e9; }}
.stat-contracts {{ background: #fff3e0; }}

.container {{ max-width: 1200px; margin: 0 auto; padding: 25px 40px; }}

.tabs {{ display: flex; gap: 0; margin-bottom: 25px; border-bottom: 2px solid var(--border); }}
.tab {{ padding: 12px 24px; cursor: pointer; font-size: 15px; font-weight: 500; border-bottom: 3px solid transparent; color: var(--text2); transition: all 0.2s; }}
.tab:hover {{ color: var(--text); }}
.tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}

.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

/* 筛选栏 */
.filter-bar {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }}
.filter-bar select, .filter-bar input {{
  padding: 8px 12px; border: 1px solid var(--border); border-radius: 6px;
  font-size: 14px; background: #fff; outline: none;
}}
.filter-bar input {{ flex: 1; min-width: 200px; }}
.filter-bar input:focus, .filter-bar select:focus {{ border-color: var(--accent); }}

/* 修正记录卡片 */
.card {{
  background: var(--card-bg); border-radius: 10px; margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: hidden; border-left: 4px solid var(--accent);
}}
.card-header {{ padding: 12px 18px; display: flex; align-items: center; gap: 10px; background: #fafbfc; border-bottom: 1px solid var(--border); flex-wrap: wrap; }}
.card-body {{ padding: 18px; }}

.severity-badge {{ padding: 3px 10px; border-radius: 12px; color: #fff; font-size: 12px; font-weight: bold; }}
.card-id {{ font-size: 12px; color: var(--text2); font-family: monospace; }}
.card-date {{ font-size: 13px; color: var(--text2); }}
.card-type {{ font-size: 13px; background: #eef2ff; padding: 2px 8px; border-radius: 4px; }}

.field-group {{ margin-bottom: 10px; }}
.field-group label {{ display: block; font-size: 12px; color: var(--text2); margin-bottom: 3px; font-weight: 500; }}

.diff-section {{ background: #fafbfc; border-radius: 8px; padding: 14px; margin: 10px 0; border: 1px solid var(--border); }}
.diff-item {{ margin-bottom: 8px; }}
.diff-item label {{ font-size: 11px; color: var(--text2); }}
.original-text {{ color: var(--red); text-decoration: line-through; padding: 4px 8px; background: #fff5f5; border-radius: 4px; }}
.ai-text {{ color: #fd7e14; padding: 4px 8px; background: #fff8f0; border-radius: 4px; }}
.corrected-text {{ color: var(--green); padding: 4px 8px; background: #f0fff4; border-radius: 4px; font-weight: 500; }}
.diff-arrow {{ text-align: center; color: var(--text2); font-size: 12px; margin: 4px 0; }}

.tags {{ display: flex; gap: 5px; flex-wrap: wrap; margin-top: 8px; }}
.tag {{ padding: 2px 8px; background: #eef2ff; color: var(--accent2); border-radius: 4px; font-size: 12px; }}

/* 规则卡片 */
.rule-card {{
  background: var(--card-bg); border-radius: 10px; margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08); border-left: 4px solid var(--green);
}}
.rule-header {{ padding: 12px 18px; display: flex; align-items: center; gap: 10px; background: #fafbfc; border-bottom: 1px solid var(--border); flex-wrap: wrap; }}
.rule-body {{ padding: 18px; }}
.rule-id {{ font-weight: bold; color: var(--accent2); font-family: monospace; }}
.priority-badge {{ padding: 3px 10px; border-radius: 12px; color: #fff; font-size: 12px; }}
.rule-date {{ font-size: 13px; color: var(--text2); }}

/* 统计图表 */
.charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
.chart-box {{ background: var(--card-bg); border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
.chart-box h3 {{ margin-bottom: 15px; font-size: 15px; color: var(--accent2); }}
.chart-row {{ display: flex; align-items: center; margin-bottom: 8px; }}
.chart-label {{ width: 120px; font-size: 13px; text-align: right; padding-right: 10px; color: var(--text2); flex-shrink: 0; }}
.chart-bar {{ height: 24px; background: linear-gradient(90deg, var(--accent2), var(--accent)); border-radius: 4px; display: flex; align-items: center; padding-left: 8px; color: #fff; font-size: 12px; min-width: 30px; }}
.cat-bar {{ background: linear-gradient(90deg, #28a745, #20c997); }}

.empty-state {{ text-align: center; padding: 60px 20px; color: var(--text2); }}
.empty-icon {{ font-size: 48px; margin-bottom: 15px; }}
.empty-state h3 {{ margin-bottom: 8px; color: var(--text); }}

.footer {{ text-align: center; padding: 20px; color: var(--text2); font-size: 12px; border-top: 1px solid var(--border); margin-top: 30px; }}

@media (max-width: 768px) {{
  .container {{ padding: 15px; }}
  .charts {{ grid-template-columns: 1fr; }}
  .stats-bar {{ padding: 15px; }}
  .header {{ padding: 20px 15px; }}
}}
</style>
</head>
<body>

<div class="header">
  <h1>CSDN 合同审核 · 错题集</h1>
  <p>审核经验积累与规则提炼 · 最后更新：{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
</div>

<div class="stats-bar">
  <div class="stat-card stat-total">
    <div class="num">{stats["total_corrections"]}</div>
    <div class="label">修正记录</div>
  </div>
  <div class="stat-card stat-rules">
    <div class="num">{stats["total_rules"]}</div>
    <div class="label">提炼规则</div>
  </div>
  <div class="stat-card stat-contracts">
    <div class="num">{stats["total_contracts"]}</div>
    <div class="label">已审合同</div>
  </div>
</div>

<div class="container">
  <div class="tabs">
    <div class="tab active" onclick="switchTab('corrections')">修正记录</div>
    <div class="tab" onclick="switchTab('rules')">提炼规则</div>
    <div class="tab" onclick="switchTab('stats')">统计分析</div>
  </div>

  <!-- 修正记录 -->
  <div id="tab-corrections" class="tab-content active">
    <div class="filter-bar">
      <select id="filter-type" onchange="filterCards()">
        <option value="">全部合同类型</option>
        {''.join(f'<option value="{t}">{t} ({c})</option>' for t, c in stats["type_counts"].items())}
      </select>
      <select id="filter-severity" onchange="filterCards()">
        <option value="">全部风险等级</option>
        <option value="high">高风险</option>
        <option value="medium">中风险</option>
        <option value="low">低风险</option>
      </select>
      <input id="filter-search" type="text" placeholder="搜索关键词..." oninput="filterCards()">
    </div>
    <div id="corrections-list">
      {correction_cards}
    </div>
  </div>

  <!-- 提炼规则 -->
  <div id="tab-rules" class="tab-content">
    <div style="margin-bottom:15px;color:var(--text2);font-size:14px;">
      同类修正出现 3 次以上时自动提炼为规则，审核同类合同时会自动加载。
    </div>
    {rule_cards}
  </div>

  <!-- 统计分析 -->
  <div id="tab-stats" class="tab-content">
    <div class="charts">
      <div class="chart-box">
        <h3>按合同类型分布</h3>
        {type_chart_bars if type_chart_bars else '<div class="empty-state"><p>暂无数据</p></div>'}
      </div>
      <div class="chart-box">
        <h3>按条款类别分布</h3>
        {category_chart_bars if category_chart_bars else '<div class="empty-state"><p>暂无数据</p></div>'}
      </div>
    </div>
  </div>
</div>

<div class="footer">
  CSDN 法务合同审核系统 · 错题集 · 数据存储在 ~/.claude/skills/csdn-contract-review/knowledge-base/
</div>

<script>
function switchTab(name) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}}

function filterCards() {{
  const type = document.getElementById('filter-type').value;
  const severity = document.getElementById('filter-severity').value;
  const search = document.getElementById('filter-search').value.toLowerCase();

  document.querySelectorAll('.card').forEach(card => {{
    const cardType = card.dataset.type || '';
    const cardSeverity = card.dataset.severity || '';
    const cardText = card.textContent.toLowerCase();

    let show = true;
    if (type && cardType !== type) show = false;
    if (severity && cardSeverity !== severity) show = false;
    if (search && !cardText.includes(search)) show = false;

    card.style.display = show ? 'block' : 'none';
  }});
}}
</script>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return {"status": "success", "output": output_path, "corrections": len(corrections), "rules": len(rules)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="错题集可视化页面生成器")
    parser.add_argument("--output", default=os.path.expanduser("~/Desktop/CSDN错题集.html"),
                        help="输出 HTML 文件路径（默认桌面）")
    args = parser.parse_args()

    result = generate_html(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
