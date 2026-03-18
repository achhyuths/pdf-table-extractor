"""
Compare PDF-extracted tables vs OCR-extracted tables.

Reads export_json (direct from PDF) and ocr_json (Tesseract on images),
flattens both to text, and shows the differences.

Usage:
    python compare_methods.py                      # all companies
    python compare_methods.py --company AAPL       # just Apple
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def flatten_pdf_table(table):
    """Flatten a PDF-extracted table (2D grid) into lines of text."""
    lines = []
    for row in table.get("data", []):
        line = " | ".join(cell for cell in row if cell)
        if line.strip():
            lines.append(line.strip())
    return lines


def flatten_ocr_table(table):
    """Flatten an OCR-extracted table (list of strings) into lines."""
    return [line.strip() for line in table.get("data", []) if line.strip()]


def compare_table(pdf_table, ocr_table):
    """Compare one table from both methods. Returns a dict with results."""
    pdf_lines = flatten_pdf_table(pdf_table)
    ocr_lines = flatten_ocr_table(ocr_table)

    pdf_text = "\n".join(pdf_lines)
    ocr_text = "\n".join(ocr_lines)

    # Simple similarity: count matching lines
    matches = 0
    total = max(len(pdf_lines), len(ocr_lines), 1)

    for pdf_line in pdf_lines:
        for ocr_line in ocr_lines:
            # Check if OCR line contains most of the PDF line's words
            pdf_words = set(pdf_line.lower().split())
            ocr_words = set(ocr_line.lower().split())
            if pdf_words and len(pdf_words & ocr_words) / len(pdf_words) > 0.5:
                matches += 1
                break

    similarity = round(matches / total * 100, 1)

    return {
        "page": pdf_table.get("page", "?"),
        "table_index": pdf_table.get("table_index", "?"),
        "heading": pdf_table.get("heading", ""),
        "pdf_lines": len(pdf_lines),
        "ocr_lines": len(ocr_lines),
        "similarity": similarity,
        "pdf_sample": pdf_lines[:3],
        "ocr_sample": ocr_lines[:3],
    }


def compare_company(company):
    """Compare all tables for one company."""
    pdf_dir = PROJECT_ROOT / "data" / "export_json" / company
    ocr_dir = PROJECT_ROOT / "data" / "ocr_json" / company

    if not pdf_dir.exists():
        print(f"  No export_json found for {company}")
        return []
    if not ocr_dir.exists():
        print(f"  No ocr_json found for {company}")
        return []

    # Load all PDF-extracted tables
    pdf_tables = []
    for f in sorted(pdf_dir.glob("*.json")):
        with open(f) as fp:
            pdf_tables.extend(json.load(fp))

    # Load all OCR-extracted tables
    ocr_tables = []
    for f in sorted(ocr_dir.glob("*.json")):
        with open(f) as fp:
            ocr_tables.extend(json.load(fp))

    print(f"  PDF method: {len(pdf_tables)} tables")
    print(f"  OCR method: {len(ocr_tables)} tables")

    # Match tables by page + table_index
    ocr_lookup = {}
    for t in ocr_tables:
        key = f"p{t.get('page', 0)}_t{t.get('table_index', 0)}"
        ocr_lookup[key] = t

    results = []
    matched = 0
    for pdf_t in pdf_tables:
        key = f"p{pdf_t.get('page', 0)}_t{pdf_t.get('table_index', 0)}"
        ocr_t = ocr_lookup.get(key)
        if ocr_t:
            matched += 1
            results.append(compare_table(pdf_t, ocr_t))

    print(f"  Matched: {matched} tables")
    return results


def main():
    # Parse args
    company_filter = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--company" and i + 1 < len(args):
            company_filter = args[i + 1]
            i += 2
        else:
            i += 1

    # Find companies
    pdf_dir = PROJECT_ROOT / "data" / "export_json"
    if not pdf_dir.exists():
        print("ERROR: Run export_json.py first")
        sys.exit(1)

    folders = sorted(d.name for d in pdf_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

    if company_filter:
        if company_filter not in folders:
            print(f"ERROR: company '{company_filter}' not found")
            sys.exit(1)
        folders = [company_filter]

    all_results = []
    for company in folders:
        print(f"\n[{company}]")
        results = compare_company(company)
        all_results.extend(results)

    if not all_results:
        print("\nNo tables to compare.")
        return

    # Print summary
    similarities = [r["similarity"] for r in all_results]
    avg = round(sum(similarities) / len(similarities), 1)

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {len(all_results)} tables compared")
    print(f"  Average similarity: {avg}%")
    print(f"  Perfect (100%):     {sum(1 for s in similarities if s == 100)}")
    print(f"  Good (>75%):        {sum(1 for s in similarities if s > 75)}")
    print(f"  Low (<50%):         {sum(1 for s in similarities if s < 50)}")

    # Show worst 5
    worst = sorted(all_results, key=lambda r: r["similarity"])[:5]
    if worst:
        print(f"\nLowest similarity tables:")
        for r in worst:
            print(f"  Page {r['page']}, Table {r['table_index']}: {r['similarity']}% — {r['heading'][:50]}")
            print(f"    PDF ({r['pdf_lines']} lines): {r['pdf_sample'][0][:60] if r['pdf_sample'] else '(empty)'}...")
            print(f"    OCR ({r['ocr_lines']} lines): {r['ocr_sample'][0][:60] if r['ocr_sample'] else '(empty)'}...")

    # Save full report
    report_path = PROJECT_ROOT / "data" / "index" / "comparison_report.json"
    with open(report_path, "w") as f:
        json.dump({
            "total_tables": len(all_results),
            "average_similarity": avg,
            "tables": all_results,
        }, f, indent=2)
    print(f"\nFull report saved: {report_path}")


if __name__ == "__main__":
    main()
