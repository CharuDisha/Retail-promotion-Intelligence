"""
Stage 0: Extract the Week's Decode Table (week number -> calendar date + holiday flag)
from the Kilts Center PDF manual.

Input:  config.CODEBOOK_PDF
Output: config.WEEK_DECODE_CSV  (columns: week, start_date, end_date, special_event)

Uses pdfplumber (pure Python, no external `pdftotext`/poppler dependency).
Pages are read one at a time and each page's cache is flushed immediately —
the manual is 500+ pages, and holding all of them open at once is enough to
OOM a small sandbox. We only need the handful of pages containing the week
table, so extraction stops as soon as the end-of-table marker is found.
"""
import re
import csv
import sys

import pdfplumber

from config import CODEBOOK_PDF, WEEK_DECODE_CSV

MAX_PAGES_TO_SCAN = 60  # the week table appears early in the manual; this is a generous safety cap


def extract_table_lines(pdf_path: str) -> list[str]:
    """Read pages incrementally until the week table's start and end markers are both found."""
    lines: list[str] = []
    header_idx = None
    end_idx = None

    with pdfplumber.open(pdf_path) as pdf:
        n_pages = min(len(pdf.pages), MAX_PAGES_TO_SCAN)
        for i in range(n_pages):
            page = pdf.pages[i]
            text = page.extract_text(layout=True) or ""
            lines.extend(text.split("\n"))
            page.flush_cache()

            if header_idx is None:
                for j, line in enumerate(lines):
                    if "Week #" in line and "Start" in line and "End" in line:
                        header_idx = j
                        break

            if header_idx is not None and end_idx is None:
                for j in range(header_idx, len(lines)):
                    if "Last week in file:" in lines[j]:
                        end_idx = j
                        break

            if header_idx is not None and end_idx is not None:
                break

    if header_idx is None:
        raise ValueError("Could not find 'Week #  Start  End' header in codebook text.")
    if end_idx is None:
        # fall back to everything scanned rather than fail outright
        end_idx = len(lines)

    return lines[header_idx:end_idx]


def parse_week_table(lines: list[str]) -> list[tuple]:
    block = "\n".join(lines)
    # matches "N  MM/DD/YY  MM/DD/YY  [optional event text]". pdfplumber's layout=True
    # extraction puts one table row per text line (unlike pdftotext -layout, which packs
    # two columns per line) and separates the optional trailing event name with a single
    # space rather than a wide column gap — the whitespace quantifiers below (\s+ / \s*)
    # are deliberately loose to match that single-space spacing; requiring \s{2,} here
    # (as a naive port from a pdftotext-based version would) silently drops every row
    # that has a holiday/event name attached, which is a real bug worth guarding against
    # if this regex is ever edited.
    pattern = re.compile(
        r"(\d{1,3})\s+(\d{2}/\d{2}/\d{2})\s+(\d{2}/\d{2}/\d{2})"
        r"(?:\s+([A-Za-z][A-Za-z0-9 \-'/]{0,30}?))?"
        r"(?=\s*\d{1,3}\s+\d{2}/\d{2}/\d{2}|\s*\n|$)"
    )
    rows = []
    for m in pattern.finditer(block):
        wk, sdate, edate, event = m.groups()
        rows.append((int(wk), sdate.strip(), edate.strip(), (event or "").strip()))
    # de-dupe and sort; PDF page-break artifacts can occasionally drop a week —
    # cross-check the output against the source PDF for any gaps before relying on it downstream
    rows = sorted(set(rows), key=lambda r: r[0])
    return rows


def main():
    lines = extract_table_lines(CODEBOOK_PDF)
    rows = parse_week_table(lines)

    missing = sorted(set(range(1, max(r[0] for r in rows) + 1)) - {r[0] for r in rows})
    if missing:
        print(f"WARNING: {len(missing)} week numbers not parsed: {missing}. "
              f"Verify these against the PDF directly before trusting downstream joins.",
              file=sys.stderr)

    with open(WEEK_DECODE_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["week", "start_date", "end_date", "special_event"])
        w.writerows(rows)

    print(f"Wrote {len(rows)} weeks to {WEEK_DECODE_CSV}")


if __name__ == "__main__":
    main()