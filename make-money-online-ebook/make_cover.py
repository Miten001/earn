#!/usr/bin/env python3
"""Render the ebook cover section to a standalone high-res PNG + JPG."""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "ebook.html")
PNG = os.path.join(HERE, "cover.png")
JPG = os.path.join(HERE, "cover.jpg")

# Gumroad recommends a 2:3-ish portrait cover. We render the cover section at
# high resolution (deviceScaleFactor=2) for a crisp thumbnail.
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(
        viewport={"width": 760, "height": 1140},
        device_scale_factor=2,
    )
    page.goto("file://" + HTML, wait_until="networkidle")
    cover = page.query_selector("section.cover")
    cover.screenshot(path=PNG)
    cover.screenshot(path=JPG, type="jpeg", quality=90)
    browser.close()

print("Cover written:", PNG, JPG)
