"""
统一审核工作台生成器 - 将审核报告、修订对比、错题集集成为一个 HTML 页面
用法: python3 generate_dashboard.py \
    --review-data <review.json> \
    --contract-text <原始合同文本或json> \
    --output <dashboard.html>
"""
import sys
import os
import json
import glob
import html as html_lib
from datetime import datetime
from collections import Counter

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "knowledge-base")
CORRECTIONS_DIR = os.path.join(KB_DIR, "corrections")
RULES_DIR = os.path.join(KB_DIR, "rules")


# ─── 数据加载 ───────────────────────────────────────────────

def load_corrections(contract_type=None):
    records = []
    for f in sorted(glob.glob(os.path.join(CORRECTIONS_DIR, "*.json")), reverse=True):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                r = json.load(fh)
                if not contract_type or r.get("contract_type") == contract_type:
                    records.append(r)
        except:
            pass
    return records


def load_rules():
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


# ─── HTML 片段 ──────────────────────────────────────────────

CSS = """
:root {
  --bg: #f0f2f5; --card: #fff; --text: #1a1a2e; --text2: #6c757d;
  --accent: #e94560; --accent2: #0f3460; --border: #e4e7eb;
  --green: #28a745; --yellow: #ffc107; --red: #dc3545; --blue: #007bff;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); }

/* === 顶栏 === */
.topbar { background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 100%); color: #fff; padding: 18px 30px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.topbar h1 { font-size: 20px; font-weight: 600; }
.topbar-meta { display: flex; gap: 18px; font-size: 13px; opacity: .85; }
.topbar-meta span { display: flex; align-items: center; gap: 4px; }

/* === 风险概览条 === */
.risk-bar { display: flex; gap: 12px; padding: 16px 30px; background: #fff; border-bottom: 1px solid var(--border); }
.risk-chip { padding: 8px 18px; border-radius: 20px; font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.risk-chip.high { background: #fce4e4; color: var(--red); }
.risk-chip.medium { background: #fff8e1; color: #e67e00; }
.risk-chip.low { background: #e8f5e9; color: var(--green); }

/* === Tab 导航 === */
.tab-nav { display: flex; gap: 0; background: #fff; border-bottom: 2px solid var(--border); padding: 0 30px; position: sticky; top: 0; z-index: 100; }
.tab-btn { padding: 14px 28px; font-size: 15px; font-weight: 500; cursor: pointer; border: none; background: none; color: var(--text2); border-bottom: 3px solid transparent; transition: all .15s; }
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }

.tab-panel { display: none; padding: 24px 30px; max-width: 1400px; margin: 0 auto; }
.tab-panel.active { display: block; }

/* === 操作栏 === */
.action-bar { display: flex; gap: 10px; justify-content: flex-end; padding: 12px 30px; background: #fff; border-bottom: 1px solid var(--border); }
.btn { padding: 8px 20px; border-radius: 6px; font-size: 14px; cursor: pointer; border: 1px solid var(--border); background: #fff; color: var(--text); display: inline-flex; align-items: center; gap: 6px; transition: all .15s; }
.btn:hover { background: var(--bg); }
.btn-primary { background: var(--accent2); color: #fff; border-color: var(--accent2); }
.btn-primary:hover { background: #1a4a8a; }

/* === 卡片 === */
.card { background: var(--card); border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.06); margin-bottom: 16px; overflow: hidden; }
.card-header { padding: 12px 18px; background: #fafbfc; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.card-body { padding: 18px; }

/* === 表格 === */
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { background: var(--accent2); color: #fff; padding: 10px 8px; text-align: left; font-weight: 500; }
td { padding: 10px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
tr:hover td { background: #f8f9fa; }

/* === 修订对比 === */
.diff-section { margin-bottom: 20px; border-left: 4px solid var(--accent); border-radius: 0 8px 8px 0; background: #fff; }
.diff-header { padding: 10px 16px; background: #fafbfc; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; cursor: pointer; }
.diff-header:hover { background: #f0f2f5; }
.diff-body { padding: 16px; }
.diff-body.collapsed { display: none; }
.diff-row { margin-bottom: 10px; }
.diff-row label { display: block; font-size: 12px; color: var(--text2); margin-bottom: 2px; font-weight: 500; }
del { color: var(--red); text-decoration: line-through; background: #ffeaea; padding: 2px 4px; border-radius: 3px; }
ins { color: var(--green); text-decoration: underline; background: #e6f9e6; padding: 2px 4px; border-radius: 3px; }
.diff-reason { margin-top: 10px; padding: 10px; background: #f0f7ff; border-radius: 6px; font-size: 13px; }
.diff-reason strong { color: var(--accent2); }
.diff-source { font-size: 12px; color: var(--text2); margin-top: 4px; }

.severity-badge { padding: 2px 8px; border-radius: 10px; color: #fff; font-size: 12px; font-weight: 600; }
.severity-high { background: var(--red); }
.severity-medium { background: var(--yellow); color: #333; }
.severity-low { background: var(--green); }

/* === 错题集 === */
.kb-stats { display: flex; gap: 12px; margin-bottom: 20px; }
.kb-stat { flex: 1; text-align: center; padding: 14px; border-radius: 8px; }
.kb-stat .num { font-size: 28px; font-weight: 700; }
.kb-stat .label { font-size: 13px; color: var(--text2); margin-top: 2px; }
.filter-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-bar select, .filter-bar input { padding: 7px 12px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; background: #fff; }
.filter-bar input { flex: 1; min-width: 180px; }
.kb-card { border-left-color: var(--accent); }
.kb-card .original { color: var(--red); text-decoration: line-through; }
.kb-card .corrected { color: var(--green); font-weight: 500; }
.tag { display: inline-block; padding: 2px 8px; background: #eef2ff; color: var(--accent2); border-radius: 4px; font-size: 12px; margin: 2px; }
.chart-box { background: #fff; border-radius: 8px; padding: 18px; margin-bottom: 16px; }
.chart-box h4 { margin-bottom: 12px; font-size: 14px; color: var(--accent2); }
.chart-row { display: flex; align-items: center; margin-bottom: 6px; }
.chart-label { width: 110px; font-size: 12px; text-align: right; padding-right: 8px; color: var(--text2); flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chart-bar { height: 22px; border-radius: 4px; display: flex; align-items: center; padding-left: 6px; color: #fff; font-size: 12px; min-width: 24px; }

.empty-state { text-align: center; padding: 50px 20px; color: var(--text2); }
.empty-state .icon { font-size: 40px; margin-bottom: 12px; }
.empty-state h3 { margin-bottom: 6px; color: var(--text); }

.footer { text-align: center; padding: 16px; font-size: 12px; color: var(--text2); border-top: 1px solid var(--border); margin-top: 30px; }

/* === 打印：默认输出修订对比 === */
@media print {{
  .topbar, .risk-bar, .tab-nav, .btn, .print-header {{ display: none !important; }}
  .tab-panel {{ display: none !important; }}
  #tab-diff {{ display: block !important; padding: 0 !important; }}
  .contract-para {{ page-break-inside: avoid; }}
  .contract-body {{ max-width: 100%; }}
  .contract-para.modified {{ background: #fff !important; }}
  .para-comment {{ border: 1px solid #ccc; background: #f9f9f9 !important; }}
  .footer {{ display: block !important; }}
}}
"""

JS = """
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  event.currentTarget.classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
}
function toggleDiff(el) {
  const body = el.nextElementSibling;
  body.classList.toggle('collapsed');
  const arrow = el.querySelector('.arrow');
  arrow.textContent = body.classList.contains('collapsed') ? '▶' : '▼';
}
function filterKB() {
  const type = document.getElementById('kb-filter-type').value;
  const sev = document.getElementById('kb-filter-sev').value;
  const q = document.getElementById('kb-search').value.toLowerCase();
  document.querySelectorAll('.kb-card').forEach(c => {
    let show = true;
    if (type && c.dataset.type !== type) show = false;
    if (sev && c.dataset.severity !== sev) show = false;
    if (q && !c.textContent.toLowerCase().includes(q)) show = false;
    c.style.display = show ? '' : 'none';
  });
}
function printPage() { window.print(); }
"""


def esc(text):
    return html_lib.escape(str(text))


def generate_dashboard(review_path, output_path, contract_text_path=None):
    """生成统一审核工作台 HTML"""

    # ─── 加载审查数据 ────────────────────────────────
    with open(review_path, 'r', encoding='utf-8') as f:
        review = json.load(f)

    findings = review.get("findings", [])
    contract_type = review.get("contract_type", "未识别")
    csdn_role = review.get("csdn_role", "未确定")
    counterparty = review.get("counterparty", "未知")
    contract_amount = review.get("contract_amount", "未明确")
    contract_date = review.get("contract_date", "未明确")

    # ─── 加载合同全文 ────────────────────────────────
    contract_paragraphs = []
    if contract_text_path and os.path.exists(contract_text_path):
        with open(contract_text_path, 'r', encoding='utf-8') as f:
            cdata = json.load(f)
        contract_paragraphs = cdata.get("paragraphs", [])
    elif contract_text_path:
        # 如果传入的是纯文本
        with open(contract_text_path, 'r', encoding='utf-8') as f:
            text = f.read()
        contract_paragraphs = [{"index": i, "text": line.strip()} for i, line in enumerate(text.split('\n')) if line.strip()]

    high_count = sum(1 for f in findings if f.get("severity") == "high")
    medium_count = sum(1 for f in findings if f.get("severity") == "medium")
    low_count = sum(1 for f in findings if f.get("severity") == "low")

    # ─── 加载错题集 ──────────────────────────────────
    corrections = load_corrections()
    rules = load_rules()
    type_counts = Counter(c.get("contract_type", "未分类") for c in corrections)
    cat_counts = Counter(c.get("clause_category", "未分类") for c in corrections)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ═══════════════════════════════════════════════════
    # Tab 1: 审核报告
    # ═══════════════════════════════════════════════════
    findings_rows = ""
    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "low")
        sev_cls = f"severity-{sev}"
        sev_text = {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(sev, "未知")
        source = f.get("source", "⚠️待确认")
        findings_rows += f"""
        <tr>
          <td>{i}</td>
          <td><span class="severity-badge {sev_cls}">{sev_text}</span></td>
          <td>{esc(f.get('category', ''))}</td>
          <td>{esc(f.get('clause', ''))}</td>
          <td><pre style="white-space:pre-wrap;margin:0;font-size:13px">{esc(f.get('original_text', ''))}</pre></td>
          <td><pre style="white-space:pre-wrap;margin:0;font-size:13px">{esc(f.get('suggested_text', ''))}</pre></td>
          <td style="font-size:13px">{esc(f.get('reason', ''))}</td>
          <td style="font-size:12px;color:var(--text2)">{esc(f.get('rule_reference', ''))}</td>
          <td style="font-size:12px">{esc(source)}</td>
        </tr>"""

    tab_report = f"""
    <div class="card" style="margin-bottom:20px">
      <div class="card-header" style="background:#fff;font-size:14px">
        <span><strong>合同类型：</strong>{esc(contract_type)}</span>
        <span><strong>CSDN 角色：</strong>{esc(csdn_role)}</span>
        <span><strong>对方：</strong>{esc(counterparty)}</span>
        <span><strong>金额：</strong>{esc(contract_amount)}</span>
        <span><strong>日期：</strong>{esc(contract_date)}</span>
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th style="width:30px">#</th>
          <th style="width:60px">风险</th>
          <th style="width:80px">类别</th>
          <th style="width:80px">条款</th>
          <th>原文内容</th>
          <th>建议修改</th>
          <th>理由</th>
          <th>规则依据</th>
          <th style="width:70px">来源</th>
        </tr>
      </thead>
      <tbody>
        {findings_rows if findings_rows else '<tr><td colspan="9" style="text-align:center;padding:30px">未发现风险</td></tr>'}
      </tbody>
    </table>"""

    # ═══════════════════════════════════════════════════
    # Tab 2: 修订对比（合同全文 + 内嵌修订标记）
    # ═══════════════════════════════════════════════════

    # 建立 original_text → finding 的映射
    orig_to_finding = {}
    for f in findings:
        orig = f.get("original_text", "").strip()
        if orig:
            orig_to_finding[orig] = f

    # 生成合同全文 HTML，将修改处内嵌
    contract_html = ""
    if contract_paragraphs:
        for p in contract_paragraphs:
            text = p.get("text", "")
            if not text:
                continue

            # 检查该段落是否包含需要修改的内容
            matched_finding = None
            for orig, f in orig_to_finding.items():
                if orig in text:
                    matched_finding = f
                    break

            if matched_finding:
                orig_text = matched_finding.get("original_text", "")
                sug_text = matched_finding.get("suggested_text", "")
                reason = matched_finding.get("reason", "")
                rule_ref = matched_finding.get("rule_reference", "")
                source = matched_finding.get("source", "⚠️待确认")
                sev = matched_finding.get("severity", "low")
                sev_cls = f"severity-{sev}"
                sev_text = {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(sev, "")

                # 在段落中替换为修订标记
                before = esc(text.replace(orig_text, ""))
                contract_html += f"""
          <div class="contract-para modified" data-severity="{sev}">
            <span class="para-index">¶{p.get('index', '')}</span>
            {esc(text[:text.find(orig_text)])}<del>{esc(orig_text)}</del><ins>{esc(sug_text)}</ins>{esc(text[text.find(orig_text)+len(orig_text):])}
            <div class="para-comment">
              <span class="severity-badge {sev_cls}">{sev_text}</span>
              <strong>理由：</strong>{esc(reason)}
              {"<br><strong>依据：</strong>" + esc(rule_ref) if rule_ref else "<br><strong>依据：</strong>⚠️ 需法务确认"}
              <span class="diff-source"> | 来源：{esc(source)}</span>
            </div>
          </div>"""
            else:
                contract_html += f"""
          <div class="contract-para">
            <span class="para-index">¶{p.get('index', '')}</span>{esc(text)}
          </div>"""
    else:
        # 没有合同全文时，回退到独立 diff 展示
        for i, f in enumerate(findings, 1):
            orig = f.get("original_text", "")
            sug = f.get("suggested_text", "")
            if not orig or not sug:
                continue
            sev = f.get("severity", "low")
            sev_cls = f"severity-{sev}"
            sev_text = {"high": "高风险", "medium": "中风险", "low": "低风险"}.get(sev, "")
            source = f.get("source", "⚠️待确认")
            reason = f.get("reason", "")
            rule_ref = f.get("rule_reference", "")
            category = f.get("category", "")

            contract_html += f"""
          <div class="diff-section">
            <div class="diff-header" onclick="toggleDiff(this)">
              <span class="severity-badge {sev_cls}">{sev_text}</span>
              <strong>第 {i} 处修改</strong>
              <span style="color:var(--text2);font-size:13px">{esc(category)}</span>
              <span class="arrow" style="margin-left:auto">▼</span>
            </div>
            <div class="diff-body">
              <div class="diff-row"><label>原文</label><del>{esc(orig)}</del></div>
              <div class="diff-row"><label>改为</label><ins>{esc(sug)}</ins></div>
              <div class="diff-reason">
                <strong>修改理由：</strong>{esc(reason)}<br>
                {"<strong>规则依据：</strong>" + esc(rule_ref) if rule_ref else "<strong>规则依据：</strong>⚠️ 需法务确认"}
                <span class="diff-source"> | 来源：{esc(source)}</span>
              </div>
            </div>
          </div>"""

    tab_diff = f"""
    <div class="print-header" style="margin-bottom:16px">
      <h3 style="font-size:16px;margin-bottom:4px">合同修订版（全文 · 修订标记模式）</h3>
      <p style="font-size:13px;color:var(--text2)">红色删除线 = 原文删除，绿色下划线 = 建议修改，蓝色批注 = 修改理由</p>
    </div>
    <div class="contract-body">
      {contract_html if contract_html else '<div class="empty-state"><div class="icon">📄</div><h3>未提供合同全文</h3><p>请传入 --contract-text 参数以显示全文修订标记</p></div>'}
    </div>"""

    # ═══════════════════════════════════════════════════
    # Tab 3: 错题集
    # ═══════════════════════════════════════════════════

    # 统计卡片
    kb_stat_html = f"""
    <div class="kb-stats">
      <div class="kb-stat" style="background:#eef2ff"><div class="num">{len(corrections)}</div><div class="label">修正记录</div></div>
      <div class="kb-stat" style="background:#e8f5e9"><div class="num">{len(rules)}</div><div class="label">提炼规则</div></div>
    </div>"""

    # 筛选栏
    filter_type_opts = "".join(
        f'<option value="{t}">{t} ({c})</option>' for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    )
    filter_bar = f"""
    <div class="filter-bar">
      <select id="kb-filter-type" onchange="filterKB()"><option value="">全部类型</option>{filter_type_opts}</select>
      <select id="kb-filter-sev" onchange="filterKB()"><option value="">全部等级</option><option value="high">高风险</option><option value="medium">中风险</option><option value="low">低风险</option></select>
      <input id="kb-search" placeholder="搜索关键词..." oninput="filterKB()">
    </div>"""

    # 修正记录卡片
    kb_cards = ""
    for c in corrections:
        sev = c.get("severity", "low")
        tags_html = "".join(f'<span class="tag">{esc(t)}</span>' for t in c.get("tags", []))
        kb_cards += f"""
      <div class="card kb-card" data-type="{esc(c.get('contract_type', ''))}" data-severity="{sev}">
        <div class="card-header">
          <span class="severity-badge severity-{sev}">{{"high":"高风险","medium":"中风险","low":"低风险"}}.get(sev,"")</span>
          <span style="font-size:12px;color:var(--text2)">{esc(c.get('id', ''))}</span>
          <span style="font-size:13px">{esc(c.get('date', ''))}</span>
          <span class="tag">{esc(c.get('contract_type', ''))}</span>
          <span class="tag">{esc(c.get('clause_category', ''))}</span>
        </div>
        <div class="card-body">
          <div style="margin-bottom:8px"><label style="font-size:12px;color:var(--text2)">原文条款</label><br><span class="original">{esc(c.get('original_clause', ''))}</span></div>
          <div style="margin-bottom:8px"><label style="font-size:12px;color:var(--text2)">AI 建议</label><br><span style="color:#fd7e14">{esc(c.get('ai_suggestion', ''))}</span></div>
          <div style="margin-bottom:8px"><label style="font-size:12px;color:var(--text2)">用户修正</label><br><span class="corrected">{esc(c.get('user_correction', ''))}</span></div>
          <div style="font-size:13px;color:var(--text2);margin-bottom:6px"><strong>理由：</strong>{esc(c.get('correction_reason', ''))}</div>
          <div>{tags_html}</div>
        </div>
      </div>"""

    if not kb_cards:
        kb_cards = """<div class="empty-state"><div class="icon">📝</div><h3>错题集为空</h3><p>审查合同时对 AI 建议进行修正后，经验会自动积累到这里</p></div>"""

    # 规则展示
    rule_cards = ""
    for r in rules:
        p = r.get("priority", "low")
        rule_cards += f"""
      <div class="card" style="border-left:4px solid var(--green)">
        <div class="card-header"><strong>{esc(r.get('id', ''))}</strong><span class="severity-badge severity-{p}">优先级：{esc(p)}</span></div>
        <div class="card-body">
          <p><strong>触发条件：</strong>{esc(r.get('condition', ''))}</p>
          <p><strong>建议动作：</strong>{esc(r.get('action', ''))}</p>
        </div>
      </div>"""

    if not rule_cards:
        rule_cards = """<div class="empty-state"><div class="icon">📊</div><h3>尚无提炼规则</h3><p>同类修正出现 3 次以上时自动提炼</p></div>"""

    # 统计图
    max_tc = max(type_counts.values()) if type_counts else 1
    type_chart = "".join(
        f'<div class="chart-row"><span class="chart-label">{esc(t)}</span><div class="chart-bar" style="width:{int(c/max_tc*100)}%;background:linear-gradient(90deg,#0f3460,#e94560)">{c}</div></div>'
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    )
    max_cc = max(cat_counts.values()) if cat_counts else 1
    cat_chart = "".join(
        f'<div class="chart-row"><span class="chart-label">{esc(cat)}</span><div class="chart-bar" style="width:{int(c/max_cc*100)}%;background:linear-gradient(90deg,#28a745,#20c997)">{c}</div></div>'
        for cat, c in sorted(cat_counts.items(), key=lambda x: -x[1])
    )

    tab_kb = f"""
    {kb_stat_html}
    {filter_bar}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
      <div class="chart-box"><h4>按合同类型</h4>{type_chart or '<p style="color:var(--text2)">暂无数据</p>'}</div>
      <div class="chart-box"><h4>按条款类别</h4>{cat_chart or '<p style="color:var(--text2)">暂无数据</p>'}</div>
    </div>
    <h3 style="margin:20px 0 12px;font-size:16px">修正记录</h3>
    {kb_cards}
    <h3 style="margin:20px 0 12px;font-size:16px">提炼规则</h3>
    {rule_cards}"""

    # ═══════════════════════════════════════════════════
    # 组装完整 HTML
    # ═══════════════════════════════════════════════════
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>CSDN 合同审核工作台 · {esc(contract_type)} · {now}</title>
<style>{CSS}</style>
</head>
<body>

<!-- 顶栏 -->
<div class="topbar">
  <h1>CSDN 合同审核工作台</h1>
  <div class="topbar-meta">
    <span>{esc(contract_type)}</span>
    <span>CSDN 角色：{esc(csdn_role)}</span>
    <span>对方：{esc(counterparty)}</span>
    <span>金额：{esc(contract_amount)}</span>
  </div>
</div>

<!-- 风险概览 -->
<div class="risk-bar">
  <div class="risk-chip high">高风险 {high_count}</div>
  <div class="risk-chip medium">中风险 {medium_count}</div>
  <div class="risk-chip low">低风险 {low_count}</div>
  <div style="flex:1"></div>
  <button class="btn" onclick="switchTab('diff');setTimeout(printPage,300)">打印修订版</button>
  <button class="btn" onclick="printPage()">打印当前页</button>
</div>

<!-- Tab 导航 -->
<div class="tab-nav">
  <button class="tab-btn active" onclick="switchTab('report')">审核报告</button>
  <button class="tab-btn" onclick="switchTab('diff')">修订对比</button>
  <button class="tab-btn" onclick="switchTab('kb')">错题集</button>
</div>

<!-- Tab 1: 审核报告 -->
<div id="tab-report" class="tab-panel active">
  {tab_report}
</div>

<!-- Tab 2: 修订对比（合同全文修订版） -->
<div id="tab-diff" class="tab-panel">
  <div class="print-header" style="background:#fff3cd;padding:12px 18px;border-radius:8px;margin-bottom:16px;font-size:14px;display:flex;align-items:center;gap:8px">
    <span>🖨️</span> <strong>提示：点击「打印修订版」按钮可直接打印此修订版，红色删除线为原文删除，绿色下划线为建议修改</strong>
  </div>
  {tab_diff}
</div>

<!-- Tab 3: 错题集 -->
<div id="tab-kb" class="tab-panel">
  {tab_kb}
</div>

<div class="footer">
  CSDN 法务合同审核系统 · 生成时间 {now} · 本报告仅供参考，最终审查意见请以法务团队确认为准
</div>

<script>{JS}</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    return {"status": "success", "output": output_path,
            "findings": len(findings), "corrections": len(corrections), "rules": len(rules)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="统一审核工作台生成器")
    parser.add_argument("--review-data", required=True, help="审查结果 JSON 文件")
    parser.add_argument("--contract-text", help="合同全文 JSON（parse_contract.py 输出）")
    parser.add_argument("--output", required=True, help="输出 HTML 文件路径")
    args = parser.parse_args()

    result = generate_dashboard(args.review_data, args.output, args.contract_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
