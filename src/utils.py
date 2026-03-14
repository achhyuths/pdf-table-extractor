"""
Shared helpers for heading detection, image cropping, text cleaning, and filename parsing.
"""

import re
from pathlib import Path


# Subtitle indicators — if the closest line above a table contains any of these,
# grab the line above it as the main heading.
SUBTITLE_PATTERNS = [
    r"in\s+(millions|thousands|billions)",
    r"unaudited",
    r"\(continued\)",
    r"three\s+months",
    r"six\s+months",
    r"nine\s+months",
    r"twelve\s+months",
    r"year\s+ended",
    r"quarter\s+ended",
]

# Patterns that indicate a line is a column header, NOT a real table title.
# These get skipped when searching for the heading.
COLUMN_HEADER_PATTERNS = [
    # Just years like "2024 2023 2022"
    r"^[\s\d,\$%\.\-]+$",
    # Date columns like "December 31, 2024 December 31, 2023"
    r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d",
    # Just quarter labels like "Q3-2024 Q4-2024"
    r"^[Q\d\-\s]+$",
    # Starts with $ or purely numeric content
    r"^\$?\s*[\d,\.\-\s\$%]+$",
    # Column layout hints like "Level I Level II Level III"
    r"^Level\s",
    # Multi-word column sub-headers that are just a list of column names
    # e.g. "Shares Amount Capital Income (Loss) Earnings Equity Interests"
    r"^(Shares|Amount|Capital|Interests|Balance|Current|Long-Term)\s",
    # e.g. "Noncontrolling Paid-In Comprehensive Retained Stockholders'"
    r"^Noncontrolling\s",
    # Dates like "30-Sep-23 31-Dec-23"
    r"^\d{1,2}-\w{3}-\d{2}",
    # Parenthetical unit descriptions mixed with column years
    # e.g. "(Dollars in millions) 2024 2023 2022 $ % $ %"
    r"^\(Dollars\s+in\s",
    r"^\(in\s+(millions|thousands|billions)",
    # Adjusted Cost Gains Losses Fair Value etc.
    r"^Adjusted\s+Cost\s",
    # "Fair Value Level I" etc.
    r"^Fair\s+Value\s+Level\s",
    # "Recourse debt Non-recourse debt"
    r"^Recourse\s",
    # "Units Cost Basis Fair Value"
    r"^Units\s+Cost\s",
]

# Minimum word count for a heading to be considered real (filters out stray numbers/page numbers)
MIN_HEADING_WORDS = 2
# Minimum character length
MIN_HEADING_LENGTH = 5


def is_subtitle(text: str) -> bool:
    """Check if a line looks like a subtitle rather than a main heading."""
    lower = text.lower().strip()
    return any(re.search(p, lower) for p in SUBTITLE_PATTERNS)


def is_column_header(text: str) -> bool:
    """Check if a line looks like a column header rather than a table title."""
    stripped = text.strip()
    # Too short — likely a page number or stray text
    if len(stripped) < MIN_HEADING_LENGTH:
        return True
    # Check against column header patterns
    for pattern in COLUMN_HEADER_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return True
    return False


def is_data_row(text: str) -> bool:
    """Check if a line contains financial data values (not a heading).

    Lines with dollar amounts, comma-formatted numbers, or percentages mixed
    with labels are data rows from the table itself, not headings above it.
    """
    stripped = text.strip()
    # Contains dollar amounts like $178,353 or $ 178,353
    if re.search(r'\$\s*[\d,]+', stripped):
        return True
    # Contains comma-formatted numbers like 178,353
    if re.search(r'\b\d{1,3}(?:,\d{3})+\b', stripped):
        return True
    return False


def cluster_words_into_lines(words: list[dict], y_tolerance: float = 3.0) -> list[dict]:
    """
    Group words by vertical position into lines.

    Returns a list of dicts: {"y": float, "text": str, "x0": float, "x1": float}
    sorted by y position (top to bottom on page).
    """
    if not words:
        return []

    # Sort words by vertical position, then horizontal
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))

    lines = []
    current_line_words = [sorted_words[0]]
    current_y = sorted_words[0]["top"]

    for word in sorted_words[1:]:
        if abs(word["top"] - current_y) <= y_tolerance:
            current_line_words.append(word)
        else:
            # Finalize current line
            line_text = " ".join(w["text"] for w in sorted(current_line_words, key=lambda w: w["x0"]))
            lines.append({
                "y": current_y,
                "text": line_text.strip(),
                "x0": min(w["x0"] for w in current_line_words),
                "x1": max(w["x1"] for w in current_line_words),
            })
            current_line_words = [word]
            current_y = word["top"]

    # Don't forget the last line
    if current_line_words:
        line_text = " ".join(w["text"] for w in sorted(current_line_words, key=lambda w: w["x0"]))
        lines.append({
            "y": current_y,
            "text": line_text.strip(),
            "x0": min(w["x0"] for w in current_line_words),
            "x1": max(w["x1"] for w in current_line_words),
        })

    return sorted(lines, key=lambda l: l["y"])


def extract_heading_above_table(page, table_bbox: tuple, max_distance: float = 200.0) -> str:
    """
    Extract the heading text above a table by looking at words above the table's top edge.

    Skips column headers (years, dates, dollar amounts) and looks for real titles
    like "Consolidated Statements of Operations".

    Args:
        page: pdfplumber page object
        table_bbox: (x0, y0, x1, y1) of the table
        max_distance: max points above the table top to search

    Returns:
        Heading string, or empty string if nothing found.
    """
    x0, y0, x1, y1 = table_bbox

    # Get all words on the page
    words = page.extract_words(keep_blank_chars=True, x_tolerance=3, y_tolerance=3)
    if not words:
        return ""

    # Filter words that are above the table and horizontally overlapping with it
    table_width = x1 - x0
    horizontal_margin = table_width * 0.1  # allow 10% margin on sides

    above_words = []
    for w in words:
        word_bottom = w["bottom"]
        # Word must be above the table's top edge
        if word_bottom > y0:
            continue
        # Word must be within max_distance of the table
        if (y0 - word_bottom) > max_distance:
            continue
        # Word must horizontally overlap with the table region (with margin)
        if w["x1"] < (x0 - horizontal_margin) or w["x0"] > (x1 + horizontal_margin):
            continue
        above_words.append(w)

    if not above_words:
        return ""

    # Cluster into lines
    lines = cluster_words_into_lines(above_words)
    if not lines:
        return ""

    # Sort lines by distance from table (closest first)
    lines_by_distance = sorted(lines, key=lambda l: y0 - l["y"])

    # Walk up from the closest line, skipping column headers, to find the real title
    heading = ""
    subtitle = ""

    for line in lines_by_distance:
        text = line["text"].strip()

        # Skip column headers (years, dates, numbers)
        if is_column_header(text):
            continue

        # Skip data rows (lines containing $amounts or comma-formatted numbers)
        if is_data_row(text):
            continue

        # If this looks like a subtitle, save it and keep looking for the main title
        if is_subtitle(text):
            if not subtitle:
                subtitle = text
            continue

        # Found a real heading
        heading = text
        break

    # Combine heading + subtitle if both found
    if heading and subtitle:
        heading = f"{heading} — {subtitle}"
    elif subtitle and not heading:
        heading = subtitle

    return heading


def parse_period_from_filename(filename: str) -> str:
    """
    Try to extract a period like 'Q1-2025' from a PDF filename.

    Examples:
        'TSLA-Q3-2025-Update.pdf' -> 'Q3-2025'
        'TSLA-Annual-2024.pdf' -> 'Annual-2024'
        'some-random.pdf' -> ''
    """
    # Match Q1-2025, Q2-2024 etc.
    match = re.search(r"(Q[1-4][-_]\d{4})", filename, re.IGNORECASE)
    if match:
        return match.group(1).upper().replace("_", "-")

    # Match Annual/FY patterns
    match = re.search(r"((?:Annual|FY)[-_]\d{4})", filename, re.IGNORECASE)
    if match:
        return match.group(1).replace("_", "-")

    # Match just a year
    match = re.search(r"(20\d{2})", filename)
    if match:
        return match.group(1)

    return ""


def sanitize_filename(text: str, max_length: int = 50) -> str:
    """Remove characters that are unsafe for filenames."""
    clean = re.sub(r'[<>:"/\\|?*\n\r\t]', '', text)
    clean = clean.strip(". ")
    return clean[:max_length]


def build_image_filename(company: str, report_name: str, page_num: int, table_idx: int) -> str:
    """
    Build a standardized image filename.

    Example: TSLA_Q3-2025-Update_p04_t01.png
    """
    return f"{company}_{report_name}_p{page_num:02d}_t{table_idx:02d}.png"


def ensure_dirs(base_path: Path, company: str) -> dict:
    """Ensure output directories exist and return their paths."""
    extracted_dir = base_path / "data" / "extracted_tables" / company
    index_dir = base_path / "data" / "index"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    return {"extracted": extracted_dir, "index": index_dir}
