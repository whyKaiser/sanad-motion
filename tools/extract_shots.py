# -*- coding: utf-8 -*-
"""Pulls the SANAD v2 interface guide and extracts its UI screenshots.

The guide lives in the sanad-v2 repository and holds one full-resolution
screenshot per documented screen. This script saves each one as PNG (for the
video build) and as WebP (for the web tour), so neither output has to be
committed here.

    python tools/extract_shots.py
"""
import io
import json
import os
import subprocess
import sys
import urllib.request

import fitz  # PyMuPDF

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GUIDE_URL = (
    "https://raw.githubusercontent.com/whyKaiser/sanad-v2/main/"
    "docs/SANAD-v2-complete-interface-guide.pdf"
)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
SHOTS = os.path.join(BUILD, "shots")
WEB = os.path.join(BUILD, "web")
WEB_WIDTH = 1180  # matches the <img> size used by web/sanad-tour.html


def fetch_guide(path):
    if os.path.exists(path) and os.path.getsize(path) > 100000:
        print("guide already present")
        return
    print("downloading interface guide…")
    with urllib.request.urlopen(GUIDE_URL) as r, open(path, "wb") as f:
        f.write(r.read())
    print("saved %.1f MB" % (os.path.getsize(path) / 1048576))


def extract(pdf_path):
    doc = fitz.open(pdf_path)
    meta = []
    for i, page in enumerate(doc):
        images = page.get_images(full=True)
        if not images:
            continue
        pix = fitz.Pixmap(doc, images[0][0])
        if pix.n > 4:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        name = "p%02d" % (i + 1)
        pix.save(os.path.join(SHOTS, name + ".png"))
        meta.append({
            "page": i + 1,
            "name": name,
            "caption": " ".join(page.get_text().split())[:220],
        })
    with io.open(os.path.join(BUILD, "shots.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


def to_webp(meta):
    if not shutil_which("ffmpeg"):
        print("ffmpeg not found — skipping WebP conversion (video build needs it too)")
        return
    for m in meta:
        src = os.path.join(SHOTS, m["name"] + ".png")
        dst = os.path.join(WEB, m["name"] + ".webp")
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", src,
             "-vf", "scale=%d:-2" % WEB_WIDTH, "-q:v", "78", dst],
            check=True,
        )


def shutil_which(name):
    import shutil
    return shutil.which(name)


if __name__ == "__main__":
    for d in (BUILD, SHOTS, WEB):
        os.makedirs(d, exist_ok=True)
    pdf = os.path.join(BUILD, "interface-guide.pdf")
    fetch_guide(pdf)
    meta = extract(pdf)
    to_webp(meta)
    print("extracted %d screenshots into %s" % (len(meta), BUILD))
    if not meta:
        sys.exit("no images found in the guide — check the source PDF")
