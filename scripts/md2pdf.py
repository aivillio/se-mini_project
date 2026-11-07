"""Render Markdown documents to styled HTML/PDF (headless Chromium via Playwright).

Usage: python scripts/md2pdf.py docs/reports/*.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import markdown

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: "Inter", "Segoe UI", Arial, sans-serif; font-size: 10.5pt; color: #14202e; line-height: 1.45; }
h1 { font-size: 20pt; color: #13233a; border-bottom: 3px solid #0e7c66; padding-bottom: 6px; margin-top: 0; }
h2 { font-size: 14pt; color: #13233a; margin-top: 22px; border-bottom: 1px solid #dde3ea; padding-bottom: 3px; }
h3 { font-size: 11.5pt; color: #13233a; margin-top: 16px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 8.8pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #13233a; color: #fff; text-align: left; padding: 5px 6px; font-weight: 600; }
td { border-bottom: 1px solid #dde3ea; padding: 4px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #f5f7fa; }
code { font-family: Consolas, monospace; font-size: 8.8pt; background: #eef2f6; padding: 1px 4px; border-radius: 3px; }
pre { background: #f3f5f8; padding: 8px 10px; border-radius: 6px; font-size: 8.5pt; overflow-x: hidden; white-space: pre-wrap; }
blockquote { border-left: 4px solid #0e7c66; margin: 8px 0; padding: 4px 12px; background: #eef8f5; }
"""


def to_html(md_text: str, title: str) -> str:
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head>" \
           f"<body>{body}</body></html>"


def render(paths: list[Path]) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for md in paths:
            html = to_html(md.read_text(encoding="utf-8"), md.stem.replace("_", " "))
            page.set_content(html, wait_until="load")
            pdf = md.with_suffix(".pdf")
            page.pdf(path=str(pdf), format="A4", print_background=True,
                     margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
                     display_header_footer=True, header_template="<span></span>",
                     footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#777'>"
                                     f"{md.stem.replace('_', ' ')} &middot; page <span class='pageNumber'></span> / "
                                     "<span class='totalPages'></span></div>")
            out.append(pdf)
        browser.close()
    return out


if __name__ == "__main__":
    for pdf in render([Path(a) for a in sys.argv[1:]]):
        print("wrote", pdf)
