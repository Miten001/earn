#!/usr/bin/env python3
"""Generate the ebook PDF from ebook.html using Playwright/Chromium."""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "ebook.html")
PDF = os.path.join(HERE, "AI-Prompts-That-Print-Money.pdf")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("file://" + HTML, wait_until="networkidle")
    page.pdf(
        path=PDF,
        format="A4",
        print_background=True,
        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
    )
    browser.close()

print("PDF written to", PDF)
