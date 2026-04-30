"""
合同文档解析器 - 支持 docx/pdf/zip 格式
用法: python3 parse_contract.py <file_path> [--output json|text] [--extract-tables]
"""
import sys
import os
import json
import zipfile
import tempfile
import shutil

def parse_docx(file_path):
    """解析 .docx 文件"""
    from docx import Document

    doc = Document(file_path)
    paragraphs = []
    tables = []

    for i, para in enumerate(doc.paragraphs):
        if para.text.strip():
            paragraphs.append({
                "index": i,
                "text": para.text.strip(),
                "style": para.style.name if para.style else None
            })

    for i, table in enumerate(doc.tables):
        table_data = []
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells]
            table_data.append(row_data)
        if table_data:
            tables.append({
                "index": i,
                "data": table_data
            })

    # 检查是否有修订痕迹（tracked changes）
    has_revisions = False
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            with z.open('word/document.xml') as f:
                content = f.read().decode('utf-8')
                if 'w:ins ' in content or 'w:del ' in content or 'w:ins>' in content or 'w:del>' in content:
                    has_revisions = True
    except:
        pass

    return {
        "paragraphs": paragraphs,
        "tables": tables,
        "full_text": "\n".join(p["text"] for p in paragraphs),
        "has_revisions": has_revisions,
        "paragraph_count": len(paragraphs),
        "table_count": len(tables)
    }

def parse_pdf(file_path):
    """解析 PDF 文件"""
    import fitz

    doc = fitz.open(file_path)
    paragraphs = []

    for page_num, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            for i, line in enumerate(text.split('\n')):
                if line.strip():
                    paragraphs.append({
                        "index": len(paragraphs),
                        "text": line.strip(),
                        "page": page_num + 1
                    })

    return {
        "paragraphs": paragraphs,
        "tables": [],
        "full_text": "\n".join(p["text"] for p in paragraphs),
        "has_revisions": False,
        "paragraph_count": len(paragraphs),
        "table_count": 0,
        "page_count": doc.page_count
    }

def parse_zip(file_path):
    """解析 ZIP 压缩包中的合同文件"""
    results = []
    temp_dir = tempfile.mkdtemp(prefix="contract_")

    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            for name in z.namelist():
                if name.startswith('__MACOSX') or name.startswith('.'):
                    continue
                if name.endswith(('.docx', '.pdf', '.doc')):
                    # 跳过隐藏文件
                    basename = os.path.basename(name)
                    if basename.startswith('.'):
                        continue

                    z.extract(name, temp_dir)
                    extracted_path = os.path.join(temp_dir, name)

                    try:
                        if name.endswith('.docx'):
                            result = parse_docx(extracted_path)
                        elif name.endswith('.pdf'):
                            result = parse_pdf(extracted_path)
                        elif name.endswith('.doc'):
                            # .doc 格式尝试作为 docx 解析
                            try:
                                result = parse_docx(extracted_path)
                            except:
                                result = {"error": f"无法解析 .doc 格式: {name}", "full_text": ""}
                        else:
                            continue

                        result["file_name"] = basename
                        result["file_type"] = os.path.splitext(name)[1]
                        results.append(result)
                    except Exception as e:
                        results.append({
                            "file_name": basename,
                            "file_type": os.path.splitext(name)[1],
                            "error": str(e),
                            "full_text": ""
                        })
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "type": "zip",
        "file_count": len(results),
        "files": results
    }

def parse_contract(file_path, output_format="json", extract_tables=False):
    """主解析函数"""
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    ext = os.path.splitext(file_path)[1].lower()
    result = {"source_file": os.path.basename(file_path)}

    if ext == '.docx':
        result["file_type"] = "docx"
        parsed = parse_docx(file_path)
        result.update(parsed)
    elif ext == '.pdf':
        result["file_type"] = "pdf"
        parsed = parse_pdf(file_path)
        result.update(parsed)
    elif ext in ('.zip', '.rar'):
        result["file_type"] = ext[1:]
        parsed = parse_zip(file_path)
        result.update(parsed)
    elif ext == '.doc':
        result["file_type"] = "doc"
        try:
            parsed = parse_docx(file_path)
            result.update(parsed)
        except:
            result["error"] = "无法解析 .doc 格式，建议转换为 .docx"
            result["full_text"] = ""
    else:
        result["error"] = f"不支持的文件格式: {ext}"
        result["full_text"] = ""

    if output_format == "text":
        if "files" in result:
            # ZIP: 输出每个文件的文本
            output = []
            for f in result["files"]:
                output.append(f"\n{'='*60}")
                output.append(f"文件: {f.get('file_name', '未知')}")
                output.append(f"{'='*60}")
                output.append(f.get("full_text", f.get("error", "")))
            return "\n".join(output)
        else:
            return result.get("full_text", result.get("error", ""))
    else:
        return json.dumps(result, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="合同文档解析器")
    parser.add_argument("file_path", help="合同文件路径")
    parser.add_argument("--output", choices=["json", "text"], default="json", help="输出格式")
    parser.add_argument("--extract-tables", action="store_true", help="提取表格")
    args = parser.parse_args()

    result = parse_contract(args.file_path, args.output, args.extract_tables)
    print(result)
