"""
审查报告生成器 - 生成 HTML 格式的合同审查报告
用法: python3 generate_report.py --review-data <review.json> --output <report.html>
"""
import sys
import os
import json
from datetime import datetime

def generate_html_report(review_data, output_path):
    """生成 HTML 审查报告"""

    contract_type = review_data.get("contract_type", "未识别")
    csdn_role = review_data.get("csdn_role", "未确定")
    counterparty = review_data.get("counterparty", "未知")
    contract_amount = review_data.get("contract_amount", "未明确")
    contract_date = review_data.get("contract_date", "未明确")
    findings = review_data.get("findings", [])

    # 统计风险
    high_count = sum(1 for f in findings if f.get("severity") == "high")
    medium_count = sum(1 for f in findings if f.get("severity") == "medium")
    low_count = sum(1 for f in findings if f.get("severity") == "low")

    severity_map = {
        "high": ("高风险 🔴", "#dc3545"),
        "medium": ("中风险 🟡", "#ffc107"),
        "low": ("低风险 🟢", "#28a745")
    }

    findings_rows = ""
    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "low")
        sev_label, sev_color = severity_map.get(sev, ("未知", "#6c757d"))
        findings_rows += f"""
        <tr>
            <td>{i}</td>
            <td>{f.get('clause', '')}</td>
            <td style="color:{sev_color};font-weight:bold">{sev_label}</td>
            <td>{f.get('category', '')}</td>
            <td><pre style="white-space:pre-wrap;margin:0">{f.get('original_text', '')}</pre></td>
            <td><pre style="white-space:pre-wrap;margin:0">{f.get('suggested_text', '')}</pre></td>
            <td>{f.get('reason', '')}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CSDN 合同审查报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; margin: 40px; color: #333; }}
        h1 {{ color: #1a1a2e; border-bottom: 3px solid #e94560; padding-bottom: 10px; }}
        h2 {{ color: #16213e; margin-top: 30px; }}
        .header-info {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .header-info p {{ margin: 5px 0; }}
        .risk-summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .risk-card {{ padding: 15px 25px; border-radius: 8px; color: white; font-weight: bold; text-align: center; min-width: 120px; }}
        .risk-high {{ background: #dc3545; }}
        .risk-medium {{ background: #ffc107; color: #333; }}
        .risk-low {{ background: #28a745; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 14px; }}
        th {{ background: #1a1a2e; color: white; padding: 12px 8px; text-align: left; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #dee2e6; vertical-align: top; }}
        tr:hover {{ background: #f8f9fa; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 12px; }}
        pre {{ font-family: inherit; }}
    </style>
</head>
<body>
    <h1>CSDN 合同审查报告</h1>

    <div class="header-info">
        <p><strong>合同类型：</strong>{contract_type}</p>
        <p><strong>CSDN 角色：</strong>{csdn_role}</p>
        <p><strong>对方当事人：</strong>{counterparty}</p>
        <p><strong>合同金额：</strong>{contract_amount}</p>
        <p><strong>合同日期：</strong>{contract_date}</p>
        <p><strong>审查时间：</strong>{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
        <p><strong>审查工具：</strong>CSDN 法务合同审核系统</p>
    </div>

    <h2>风险概览</h2>
    <div class="risk-summary">
        <div class="risk-card risk-high">
            <div style="font-size:28px">{high_count}</div>
            <div>高风险</div>
        </div>
        <div class="risk-card risk-medium">
            <div style="font-size:28px">{medium_count}</div>
            <div>中风险</div>
        </div>
        <div class="risk-card risk-low">
            <div style="font-size:28px">{low_count}</div>
            <div>低风险</div>
        </div>
    </div>

    <h2>审查明细</h2>
    <table>
        <thead>
            <tr>
                <th style="width:30px">#</th>
                <th style="width:80px">条款</th>
                <th style="width:70px">风险等级</th>
                <th style="width:90px">类别</th>
                <th>原文内容</th>
                <th>建议修改</th>
                <th>修改理由</th>
            </tr>
        </thead>
        <tbody>
            {findings_rows if findings_rows else '<tr><td colspan="7" style="text-align:center">未发现风险</td></tr>'}
        </tbody>
    </table>

    <div class="footer">
        <p>本报告由 CSDN 法务合同审核系统自动生成，仅供参考。最终审查意见请以法务团队确认为准。</p>
        <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return {"status": "success", "output": output_path, "findings_count": len(findings)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="审查报告生成器")
    parser.add_argument("--review-data", required=True, help="审查结果 JSON 文件路径")
    parser.add_argument("--output", required=True, help="输出 HTML 文件路径")
    args = parser.parse_args()

    with open(args.review_data, 'r', encoding='utf-8') as f:
        review_data = json.load(f)

    result = generate_html_report(review_data, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
