#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 Surf-Bash CAPTCHA Clicker — v2 (graph-paper + shape matching)
================================================================
Naya CAPTCHA = 4 cells:
   cell 1..3  -> graph-paper boxes (yahin click karna hai)
   cell 4     -> CLUE cell: laal "Click" + target shape  (KABHI click nahi)

Kaam:
   1. clue cell se shape nikalo
   2. cell 1..3 me wahi shape (rotate hua ho sakta hai) dhoondho
   3. clear match -> wahi box  |  match nahi mila -> 3 me se RANDOM box
   4. timer ke dauraan sirf search; "GO" dikhte hi USI FRAME me click

Ye version asli Surf Bash CAPTCHA ke liye bana hai jisme:
  - boxes graph-paper (squared) hote hain
  - shapes patli colored lines (blue/green/red) se bane hote hain
  - grid lines aur dots/dashes noise hain — inhe ignore kiya jata hai
  - target shape boxes me ghumaya (rotate) hua ho sakta hai

Setup: sab auto (packages + Tesseract) — kuch download nahi karna.

CHALAO:
   clicker.bat par double-click      (ya)      python clicker.py

OPTIONS:
   --once            ek baar solve karke exit
   --dry-run         sirf batao kaunsa box, click NA karo
   --debug           debug/ folder me annotated image save karo
   --manual          region khud select karo (auto-detect fail ho to)
   --region x,y,w,h  region CMD se do
   --interval 0.4    scan gap (seconds)
   --min-match 0.4   isse kam score = "match nahi mila" -> random box
   --go-timeout 3    'Go' na mile to bhi 3s baad click (default 0 = sirf Go par)
   --clicks 2        double-click
   --no-pause        band hone par Enter na puche

STOP: Ctrl+C  ya  mouse screen corner par (emergency stop)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import platform
import random
import tempfile
import threading
import time
import traceback
import urllib.request

if os.name == 'nt':
    os.system('')  # Windows CMD me ANSI colors

CONFIG = {
    "scan_interval": 0.3,
    "click_delay": 0.25,
    "min_confidence": 0.22,     # isse kam = "pata nahi" (log me warning)
    "min_match": 0.32,          # best score isse kam -> koi box match nahi hua
    "min_margin": 0.04,         # best - 2nd best isse kam -> ambiguous -> random
    "clicks": 1,                # ek cell par kitne clicks
    "go_timeout": 0.0,          # 0 = sirf 'Go' dikhne par click (timer ke baad)
    "debug": False,
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGION_FILE = os.path.join(SCRIPT_DIR, 'region.txt')
DEBUG_DIR = os.path.join(SCRIPT_DIR, 'debug')
LOG_FILE = os.path.join(SCRIPT_DIR, 'clicker_log.txt')
LAYOUT_CACHE = os.path.join(SCRIPT_DIR, 'layout_cache.json')

pyautogui = Image = pytesseract = cv2 = np = None


class C:
    GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
    BLUE = "\033[94m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def ts():
    return time.strftime('%H:%M:%S')


def _log_write(line):
    """Har line file me bhi save karo — window band ho jaye to bhi trace mile."""
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass


def log(msg):
    line = f"[{ts()}] {msg}"
    print(line, flush=True)
    _log_write(line)


def crash_report(exc_type=Exception, exc=None, tb=None):
    """Crash ko log karo aur window turant band na ho."""
    if tb is None:
        tb = sys.exc_info()[2]
    if exc is None:
        exc = sys.exc_info()[1]
    text = ''.join(traceback.format_exception(exc_type, exc, tb))
    print(text, flush=True)
    _log_write('\n===== CRASH ' + ts() + ' =====\n' + text)
    try:
        print(f"\n{C.RED}Kuch galti hui — poori detail {os.path.basename(LOG_FILE)} me save ho gayi.{C.RESET}")
        input('ENTER dabao band karne ke liye...')
    except Exception:
        pass


# ==================== AUTO SETUP ====================
def ensure_deps():
    global pyautogui, Image, pytesseract, cv2, np
    pkgs = [('pyautogui', 'pyautogui'), ('PIL', 'pillow'), ('pytesseract', 'pytesseract'),
            ('cv2', 'opencv-python'), ('numpy', 'numpy')]
    missing = []
    for mod, pkg in pkgs:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"{C.YELLOW}📦 Setup: {', '.join(missing)} install kar raha hoon...{C.RESET}")
        cmds = [[sys.executable, '-m', 'pip', 'install'] + missing]
        if os.name != 'nt':
            cmds.insert(0, [sys.executable, '-m', 'pip', 'install',
                            '--break-system-packages'] + missing)
        ok = False
        for cmd in cmds:
            try:
                subprocess.check_call(cmd)
                ok = True
                break
            except subprocess.CalledProcessError:
                continue
        if not ok:
            print(f"{C.RED}❌ Install fail. Internet check karo phir dobara chalao.{C.RESET}")
            sys.exit(1)
        print(f"{C.GREEN}✅ Packages ready!{C.RESET}")

    import pyautogui as _pg
    from PIL import Image as _Img
    import pytesseract as _pt
    import cv2 as _cv
    import numpy as _np
    pyautogui, Image, pytesseract, cv2, np = _pg, _Img, _pt, _cv, _np
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.02


def find_tesseract():
    p = shutil.which('tesseract')
    if p:
        return p
    for c in [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
              r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
              os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe'),
              '/usr/bin/tesseract', '/usr/local/bin/tesseract', '/opt/homebrew/bin/tesseract']:
        if os.path.exists(c):
            return c
    return None


def download_tesseract_windows():
    if shutil.which('winget'):
        print("   winget se Tesseract install...")
        subprocess.run(['winget', 'install', '--id', 'UB-Mannheim.TesseractOCR', '-e',
                        '--accept-source-agreements', '--accept-package-agreements'],
                       capture_output=True)
        p = find_tesseract()
        if p:
            return p
    try:
        with urllib.request.urlopen(
                'https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest', timeout=30) as r:
            data = json.load(r)
        url = next((a['browser_download_url'] for a in data.get('assets', [])
                    if 'w64-setup' in a.get('name', '') and a['name'].endswith('.exe')), None)
        if not url:
            return None
        inst = os.path.join(tempfile.gettempdir(), 'tesseract-setup.exe')
        print(f"   Downloading {os.path.basename(url)} ...")
        urllib.request.urlretrieve(url, inst)
        print("   Silent install (thoda time lagega)...")
        subprocess.run([inst, '/S'], timeout=300)
        return find_tesseract()
    except Exception as e:
        print(f"   fail: {e}")
        return None


def ensure_tesseract():
    path = find_tesseract()
    if not path and os.name == 'nt':
        print(f"{C.YELLOW}🔤 Tesseract nahi mila — auto install...{C.RESET}")
        path = download_tesseract_windows()
    if not path:
        print(f"{C.RED}❌ Tesseract OCR nahi mila{C.RESET}")
        print("   Install: https://github.com/UB-Mannheim/tesseract/wiki")
        sys.exit(1)
    pytesseract.pytesseract.tesseract_cmd = path


# ==================== SCREEN + DPI ====================
def set_dpi_aware():
    """
    Windows par process ko DPI-aware banao.

    KYUN: 125%/150% display scaling par DPI-unaware process ka screenshot
    (physical px) aur click (logical px) alag hota hai — click GALAT jagah
    lagta hai. DPI-aware hone ke baad teeno (screenshot, size, click)
    physical px me hote hain -> koi conversion nahi -> click sahi jagah.
    """
    if os.name != 'nt':
        return 'n/a'
    try:
        import ctypes
    except Exception:
        return 'no-ctypes'
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor v2
        return 'per-monitor'
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()           # system aware
        return 'system'
    except Exception:
        return 'failed'


class Screen:
    """
    Screenshot aur click — dono ka mapping ek jagah.
    DPI-aware hone ke baad scale 1.0 hona chahiye (physical px).
    Agar OS phir bhi scale de, to usi hisaab se convert karte hain.
    """

    def __init__(self):
        self.scale = 1.0
        self.dpi_mode = set_dpi_aware()
        try:
            sw, sh = pyautogui.size()
            shot = pyautogui.screenshot()
            self.phys_w, self.phys_h = shot.size
            self.logi_w, self.logi_h = sw, sh
            if sw:
                self.scale = shot.size[0] / float(sw)
        except Exception:
            self.phys_w = self.phys_h = self.logi_w = self.logi_h = 0
        self.shot_w, self.shot_h = self.phys_w, self.phys_h

        # shakki scale ko 1.0 maan lo (1.0/1.25/1.5/1.75/2.0 hi asli hote hain)
        if abs(self.scale - 1.0) <= 0.04:
            self.scale = 1.0
        else:
            for real in (1.25, 1.5, 1.75, 2.0, 1.1, 1.33):
                if abs(self.scale - real) < 0.06:
                    self.scale = real
                    break

        if self.scale != 1.0:
            log(f"{C.YELLOW}🖥️  Screen {self.phys_w}x{self.phys_h} px, DPI mode={self.dpi_mode}, "
                f"scaling {self.scale:.2f}x — clicks convert honge{C.RESET}")
        else:
            log(f"🖥️  Screen {self.phys_w}x{self.phys_h} px, DPI mode={self.dpi_mode}, scaling 1.0x")

    def grab(self):
        return pyautogui.screenshot().convert('RGB')

    def to_logical(self, px, py):
        """Screenshot px -> click coords."""
        if self.scale == 1.0:
            return float(px), float(py)
        return px / self.scale, py / self.scale


# ==================== OCR ====================
def ocr_words(img, upscale=2, psm=11):
    """OCR words -> [{text,x,y,w,h}] (img ke original coords me)."""
    w, h = img.size
    big = img.resize((w * upscale, h * upscale), Image.LANCZOS)
    cfg = f'--psm {psm}'
    try:
        data = pytesseract.image_to_data(big, config=cfg, output_type=pytesseract.Output.DICT)
    except Exception:
        return []
    out = []
    for i in range(len(data['text'])):
        t = (data['text'][i] or '').strip()
        if not t:
            continue
        out.append({'text': t.lower(),
                    'x': data['left'][i] / upscale, 'y': data['top'][i] / upscale,
                    'w': data['width'][i] / upscale, 'h': data['height'][i] / upscale})
    return out


def locate_words(img):
    """
    'Click'/'Go' dhoondhne ke liye multi-pass OCR.
    Pass 1: RGB 2x  |  Pass 2: grayscale 3x  |  Pass 3: sirf red text 3x
    (asli screen par ek hi pass kabhi fail ho jata hai)
    """
    arr = np.array(img)

    w1 = ocr_words(img, upscale=2, psm=11)
    if find_word(w1, 'click'):
        return w1

    found = list(w1)

    try:
        g = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        w2 = ocr_words(Image.fromarray(g).convert('RGB'), upscale=3, psm=11)
        found += w2
        if find_word(found, 'click'):
            return found
    except Exception:
        pass

    try:
        a = arr.astype(np.int16)
        red = ((a[:, :, 0] - a[:, :, 1] > 50) & (a[:, :, 0] - a[:, :, 2] > 50)).astype(np.uint8)
        red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        redimg = 255 - cv2.dilate(red * 255, np.ones((2, 2), np.uint8))  # black text on white
        w3 = ocr_words(Image.fromarray(redimg).convert('RGB'), upscale=3, psm=11)
        found += w3
    except Exception:
        pass

    return found


def _clean(text):
    return text.strip().strip('.,:;!|()[]{}\'"`~-').lower()


def find_word(words, kw, min_conf_h=6):
    """Substring match (jaise 'click' -> 'Click')."""
    for w in words:
        txt = _clean(w['text'])
        if kw in txt and w['h'] >= min_conf_h:
            return w
    return None


def find_word_exact(words, kw, min_conf_h=8, max_len=3):
    """Exact match — 'go' ko 'Google'/'Logo' se match hone se bachata hai."""
    for w in words:
        txt = _clean(w['text'])
        if txt == kw and w['h'] >= min_conf_h:
            return w
        if txt.startswith(kw) and len(txt) <= max_len and w['h'] >= min_conf_h:
            return w
    return None


# ==================== LAYOUT DETECTION ====================
def _group_line_positions(flags, min_gap=4):
    idx = np.where(flags)[0]
    if len(idx) == 0:
        return []
    groups, cur = [], [idx[0]]
    for v in idx[1:]:
        if v - cur[-1] <= min_gap:
            cur.append(v)
        else:
            groups.append(int(np.mean(cur)))
            cur = [v]
    groups.append(int(np.mean(cur)))
    return groups


STRIP_FAIL = ''   # aakhri fail ka reason (log me dikhta hai)


def _thin_hlines(mask_rows, wy0, min_frac=0.5, max_thick=4):
    """Row-profile se patli lines nikalo (moti dark bars ignore)."""
    out, i = [], 0
    while i < len(mask_rows):
        if mask_rows[i] > min_frac:
            j = i
            while j < len(mask_rows) and mask_rows[j] > min_frac:
                j += 1
            if 1 <= (j - i) <= max_thick:
                out.append(int(round(wy0 + (i + j - 1) / 2.0)))
            i = j
        else:
            i += 1
    return out


def _strip_with_threshold(gray, click_w, thr):
    """Ek threshold se strip dhoondhne ki koshish. Return (cells, strip)."""
    H, W = gray.shape
    th = max(9, int(click_w['h']))
    cx = int(click_w['x'] + click_w['w'] / 2)
    cy = int(click_w['y'] + click_w['h'] / 2)

    # 1) Horizontal borders (patli lines hi)
    wx0 = max(0, cx - int(10 * th)); wx1 = min(W, cx + int(6 * th))
    wy0 = max(0, cy - int(8 * th)); wy1 = min(H, cy + int(8 * th))
    sub = gray[wy0:wy1, wx0:wx1]
    if sub.size == 0:
        return [], None
    rows = (sub < thr).mean(axis=1)

    top = bottom = None
    for need in (0.5, 0.4, 0.3):
        thin = _thin_hlines(rows, wy0, need)
        above = [y for y in thin if y < cy]
        below = [y for y in thin if y > cy]
        if above and below:
            top = max(above)
            cands = [y for y in below if y > top + 2.0 * th]
            bottom = min(cands) if cands else max(below)
            break
    if top is None or bottom is None:
        return [], None
    if bottom - top < 2.2 * th:
        # text ke andar ki lines mili — band bahut chhota hai, skip
        return [], None

    # 2) Vertical dividers (band ke andar, poori chaudai par)
    band = gray[top + 2:bottom - 1, :]
    if band.size == 0:
        return [], None
    cols = (band < thr).mean(axis=0)
    dividers = []
    for need in (0.75, 0.6, 0.5):
        dividers = _group_line_positions(cols > need)
        if len(dividers) >= 2:
            break
    if len(dividers) < 2:
        return [], None

    # 3) Click wale cell se chain
    pair = None
    for i in range(len(dividers) - 1):
        if dividers[i] <= cx <= dividers[i + 1]:
            pair = i
            break
    if pair is None:
        return [], None
    cell_w = dividers[pair + 1] - dividers[pair]
    if cell_w < 0.6 * th:
        return [], None

    lo, hi = pair, pair + 1
    # CAPTCHA ki cells lagbhag barabar hoti hain — bahar ki cheezein (ads)
    # is ratio ke bahar nikal jati hain, isliye chain wahin ruk jati hai
    while lo - 1 >= 0 and 0.72 * cell_w <= dividers[lo] - dividers[lo - 1] <= 1.35 * cell_w:
        lo -= 1
    while hi + 1 < len(dividers) and 0.72 * cell_w <= dividers[hi + 1] - dividers[hi] <= 1.35 * cell_w:
        hi += 1

    cells = [(dividers[k] + 2, top + 3, dividers[k + 1] - 2, bottom - 2)
             for k in range(lo, hi)]
    strip = (dividers[lo], top, dividers[hi], bottom)
    return cells, strip


def _fallback_cells(gray, click_w, thr):
    """
    Last resort: dividers na mile to graph-paper cell width (1.4 x height)
    maan kar cells banao — Click cell se left ki taraf.
    """
    H, W = gray.shape
    th = max(9, int(click_w['h']))
    cx = int(click_w['x'] + click_w['w'] / 2)
    cy = int(click_w['y'] + click_w['h'] / 2)

    # horizontal band (dono thresholds try)
    for t in (thr, 150, 170):
        wx0 = max(0, cx - int(10 * th)); wx1 = min(W, cx + int(6 * th))
        wy0 = max(0, cy - int(8 * th)); wy1 = min(H, cy + int(8 * th))
        sub = gray[wy0:wy1, wx0:wx1]
        if sub.size == 0:
            continue
        rows = (sub < t).mean(axis=1)
        thin = _thin_hlines(rows, wy0, 0.4)
        above = [y for y in thin if y < cy]
        below = [y for y in thin if y > cy]
        if not above or not below:
            continue
        top = max(above)
        cands = [y for y in below if y > top + 2.0 * th]
        bottom = min(cands) if cands else max(below)
        if bottom - top < 2.2 * th:
            continue

        cell_h = bottom - top
        cell_w = int(round(1.42 * cell_h))
        if cell_w < 20:
            continue
        # Click cell ka approx right edge
        click_right = cx + int(cell_w * 0.4)
        left_limit = max(0, click_right - 6 * cell_w)
        band = gray[top + 2:bottom - 1, :]
        cols = (band < 180).mean(axis=0)
        # strip ka left border: koi bhi column jo kaafi bharose se dark ho
        strong = [x for x in range(left_limit, max(left_limit + 1, cx - int(0.5 * cell_w)))
                  if cols[x] > 0.55]
        left = min(strong) if strong else max(0, cx - 3 * cell_w - int(0.5 * cell_w))
        n = max(1, int(round((click_right - left) / float(cell_w))))
        n = min(n, 8)
        cells = []
        for k in range(n):
            x1 = left + k * cell_w
            x2 = x1 + cell_w
            cells.append((int(x1) + 2, top + 3, int(x2) - 2, bottom - 2))
        if len(cells) >= 2:
            return cells, (left, top, left + n * cell_w, bottom)
    return [], None


def detect_strip(gray, click_w):
    """
    'Click' word ke aas-paas CAPTCHA strip dhoondho.
    Adaptive: kai thresholds + Otsu try hote hain (light/antialiased borders
    par bhi kaam kare), sab fail ho to graph-paper fallback.
    """
    global STRIP_FAIL
    th = max(9, int(click_w['h']))
    cx = int(click_w['x'] + click_w['w'] / 2)
    cy = int(click_w['y'] + click_w['h'] / 2)

    # thresholds: Otsu (local) + kuch absolute
    levels = []
    try:
        wx0 = max(0, cx - int(10 * th)); wx1 = min(gray.shape[1], cx + int(6 * th))
        wy0 = max(0, cy - int(8 * th)); wy1 = min(gray.shape[0], cy + int(8 * th))
        patch = gray[wy0:wy1, wx0:wx1]
        if patch.size:
            otsu, _ = cv2.threshold(patch, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            levels.append(int(otsu))
    except Exception:
        pass
    for t in (125, 150, 110, 165, 95, 180):
        if t not in levels:
            levels.append(t)

    best = None
    for thr in levels:
        cells, strip = _strip_with_threshold(gray, click_w, thr)
        if not cells:
            continue
        n = len(cells)
        if n < 2 or n > 9:
            continue
        score = (min(n, 6), strip[3] - strip[1])   # zyada cells + lambi strip
        if best is None or score > best[0]:
            best = (score, cells, strip, thr)

    if best is not None:
        STRIP_FAIL = f'thr={best[3]}'
        return best[1], best[2]

    # last resort
    for thr in levels[:3]:
        cells, strip = _fallback_cells(gray, click_w, thr)
        if cells:
            STRIP_FAIL = f'fallback (thr={thr})'
            return cells, strip

    STRIP_FAIL = 'lines/dividers nahi mile (thr try kiye: ' + ','.join(map(str, levels[:4])) + ')'
    return [], None


def find_captcha_layout(gray, words):
    """
    Page par kai 'Click' ho sakte hain (ads me bhi). Har candidate ke liye
    strip dhoondhne ki koshish karo — jo asli CAPTCHA hai wahi lines dega.
    Return: (click_word, cells, strip, n_candidates)
    """
    cands = []
    for w in words:
        t = _clean(w['text'])
        if 'click' in t and w['h'] >= 6:
            cands.append(w)
    if not cands:
        return None, [], None, 0

    gos = [w for w in words
           if _clean(w['text']) in ('go', 'g0')
           or (_clean(w['text']).startswith('go') and len(_clean(w['text'])) <= 3)]

    # pehle wahi candidates jinke paas 'Go' hai (CAPTCHA me Click+Go paas hote hain),
    # phir chhote text wale (ad text bada hota hai)
    scored = []
    for c in cands:
        ccx, ccy = c['x'] + c['w'] / 2, c['y'] + c['h'] / 2
        d = 1e9
        for g in gos:
            d = min(d, abs(g['x'] + g['w'] / 2 - ccx) + abs(g['y'] + g['h'] / 2 - ccy))
        near_go = 1 if d < 16 * max(8, c['h']) else 0
        scored.append((near_go, -c['h'], -d, c))
    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)

    best = None
    for _, _, _, c in scored:
        cells, strip = detect_strip(gray, c)
        if not cells:
            continue
        has_go = any(cell_has_word(cc, g) for cc in cells for g in gos)
        n = len(cells)
        score = (1 if has_go else 0, 1 if 3 <= n <= 7 else 0, n * 100 - int(c['h']))
        if best is None or score > best[0]:
            best = (score, c, cells, strip)
        if has_go and 3 <= n <= 7:
            break          # pehla hi pakka candidate -> ruk jao (fast)
    if best is None:
        return None, [], None, len(cands)
    return best[1], best[2], best[3], len(cands)


def cell_has_word(cell, word, pad=4):
    if word is None:
        return False
    wx, wy = word['x'] + word['w'] / 2, word['y'] + word['h'] / 2
    return (cell[0] - pad <= wx <= cell[2] + pad) and (cell[1] - pad <= wy <= cell[3] + pad)


# ==================== SHAPE EXTRACTION ====================
def bold_shape(cell_rgb, blank_boxes=(), min_frac=0.008, max_frac=0.55):
    """
    Cell me se 'bold colored shape' nikalo.
    Grid lines aur background grayscale hote hain -> colorfulness se ignore.
    Shapes chhote blocks se bane hote hain -> CLOSE se jodte hain.
    """
    c = cell_rgb.copy()
    for (bx1, by1, bx2, by2) in blank_boxes:
        x1 = max(0, int(bx1)); y1 = max(0, int(by1))
        x2 = min(c.shape[1], int(bx2)); y2 = min(c.shape[0], int(by2))
        if x2 > x1 and y2 > y1:
            c[y1:y2, x1:x2] = 240
    if c.size == 0:
        return None
    cf = c.max(axis=2).astype(np.int16) - c.min(axis=2).astype(np.int16)
    m = (cf > 45).astype(np.uint8) * 255
    if not m.any():
        return None
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN,
                         cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n <= 1:
        return None
    cell_area = m.shape[0] * m.shape[1]
    best, best_area = None, 0
    for i in range(1, n):
        a = st[i, cv2.CC_STAT_AREA]
        if min_frac * cell_area <= a <= max_frac * cell_area and a > best_area:
            best, best_area = i, a
    if best is None:
        return None
    return np.where(lab == best, 255, 0).astype(np.uint8)


def shape_sig(mask, size=80):
    if mask is None:
        return None
    pts = cv2.findNonZero(mask)
    if pts is None:
        return None
    x, y, w, h = cv2.boundingRect(pts)
    if w < 3 or h < 3:
        return None
    part = mask[y:y + h, x:x + w]
    s = max(w, h)
    canvas = np.zeros((s, s), np.uint8)
    canvas[(s - h) // 2:(s - h) // 2 + h, (s - w) // 2:(s - w) // 2 + w] = part
    return cv2.resize(canvas, (size, size), interpolation=cv2.INTER_AREA)


def _rotate(mask, angle):
    h, w = mask.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(mask, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)


def iou(a, b):
    A, B = a > 128, b > 128
    u = (A | B).sum()
    return float((A & B).sum()) / u if u else 0.0


def rotated_variants(sig, step=10):
    return [_rotate(sig, ang) for ang in range(0, 360, step)]


def best_match(target_variants, cand_sig):
    """Target ko ghumaya hua maanke best IoU. Shapes rotate ho sakte hain."""
    if cand_sig is None:
        return 0.0, 0
    best, best_ang = 0.0, 0
    for k, tv in enumerate(target_variants):
        v = iou(tv, cand_sig)
        if v > best:
            best, best_ang = v, k * 10
    return best, best_ang


# ==================== SOLVE ====================
def analyse(frame_rgb, region=None, words=None, go_required=True,
            click_word=None, check_go=False, box_rel=None):
    """
    Ek frame analyse karo.
    click_word diya ho to OCR skip hota hai (fast tracking).
    check_go=True par 'Go' ka chhota crop se pata chalta hai.
    Return dict: status ('ok','no_click','no_strip','no_boxes','no_target','wait_go')
    """
    arr = np.array(frame_rgb)
    if region:
        x, y, w, h = region
        arr = arr[max(0, y):y + h, max(0, x):x + w]
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    pre_cells = pre_strip = None
    n_cand = 0
    if click_word is not None:
        click_w, go_w = click_word, None
        words = words or []
    else:
        if words is None:
            words = locate_words(Image.fromarray(arr))
        go_w = find_word_exact(words, 'go', min_conf_h=10)
        # saare 'click' candidates me se wahi lo jo asli strip deta hai
        click_w, pre_cells, pre_strip, n_cand = find_captcha_layout(gray, words)
        if click_w is None:
            return {'status': 'no_click' if n_cand == 0 else 'no_strip',
                    'words': words, 'n_candidates': n_cand}
    if click_w is None:
        return {'status': 'no_click', 'words': words}

    if pre_cells:
        cells, strip = pre_cells, pre_strip
    else:
        cells, strip = detect_strip(gray, click_w)
    if not cells:
        return {'status': 'no_strip', 'click': click_w, 'go': go_w, 'words': words}

    target_idx = next((i for i, c in enumerate(cells) if cell_has_word(c, click_w)), None)
    if target_idx is None:
        return {'status': 'no_strip', 'click': click_w, 'go': go_w, 'words': words,
                'cells': cells}

    if box_rel is not None:
        # cached layout: kaun se cells answer-boxes hain (Go cell exclude rahega)
        box_idx = [target_idx + r for r in box_rel if 0 <= target_idx + r < len(cells)]
    else:
        go_idx = next((i for i, c in enumerate(cells) if cell_has_word(c, go_w)), None)
        if go_idx is None:
            go_idx = _go_blob_cell(arr, cells, target_idx)   # OCR fail -> blob se
        box_idx = [i for i in range(len(cells)) if i != target_idx and i != go_idx]
    if not box_idx:
        return {'status': 'no_boxes', 'cells': cells, 'click': click_w, 'go': go_w,
                'words': words}

    # Target shape (Click text ko blank karke)
    tc = cells[target_idx]
    tcrop = arr[tc[1]:tc[3], tc[0]:tc[2]]
    blanks = [(click_w['x'] - tc[0] - 4, click_w['y'] - tc[1] - 4,
               click_w['x'] - tc[0] + click_w['w'] + 4, click_w['y'] - tc[1] + click_w['h'] + 4)]
    tsig = shape_sig(bold_shape(tcrop, blank_boxes=blanks))
    if tsig is None:
        return {'status': 'no_target', 'cells': cells, 'click': click_w, 'go': go_w,
                'words': words}
    variants = rotated_variants(tsig, 10)

    scores, angs, sigs = [], [], []
    for i in box_idx:
        c = cells[i]
        csig = shape_sig(bold_shape(arr[c[1]:c[3], c[0]:c[2]]))
        s, ang = best_match(variants, csig)
        scores.append(s); angs.append(ang); sigs.append(csig)

    # 'Go' check (chhota crop = fast)
    go_here = go_w is not None
    if not go_here and check_go:
        # Go target cell ke right me hota hai (strip ke right edge se naapo)
        anchor = cells[target_idx]
        st_global = (anchor[2], strip[1], anchor[2], strip[3])
        if region:
            st_global = (st_global[0] + region[0], st_global[1] + region[1],
                         st_global[2] + region[0], st_global[3] + region[1])
        try:
            go_here = go_visible(frame_rgb, st_global)
        except Exception:
            go_here = False

    best_local = int(np.argmax(scores))
    ordered = sorted(range(len(scores)), key=lambda i: -scores[i])
    second_score = scores[ordered[1]] if len(ordered) > 1 else 0.0
    margin = scores[ordered[0]] - second_score
    strong = (scores[ordered[0]] >= CONFIG['min_match'] and margin >= CONFIG['min_margin'])
    return {
        'margin': margin, 'strong_match': strong,
        'status': 'ok' if (go_here or not go_required) else 'wait_go',
        'cells': cells, 'strip': strip, 'target_idx': target_idx,
        'box_idx': box_idx, 'box_rel': [i - target_idx for i in box_idx],
        'scores': scores, 'angles': angs,
        'best_local': best_local, 'best_cell': cells[box_idx[best_local]],
        'best_score': scores[best_local],
        'target_sig': tsig, 'cell_sigs': sigs,
        'click': click_w, 'go': go_w, 'words': words, 'region': region,
    }


def save_debug(frame_rgb, res, tag=''):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    arr = np.array(frame_rgb).copy()
    if res.get('region'):
        rx, ry, rw, rh = res['region']
        arr = arr[ry:ry + rh, rx:rx + rw].copy()
        ox, oy = -rx, -ry
    else:
        ox, oy = 0, 0
    vis = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    for i, c in enumerate(res.get('cells', [])):
        x1, y1, x2, y2 = c[0] + ox, c[1] + oy, c[2] + ox, c[3] + oy
        color = (0, 255, 255) if i == res.get('target_idx') else (255, 0, 0)
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        cv2.putText(vis, f'c{i+1}', (x1 + 4, y1 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    bc = res.get('best_cell')
    if bc:
        cv2.rectangle(vis, (bc[0] + ox, bc[1] + oy), (bc[2] + ox, bc[3] + oy), (0, 200, 0), 3)
        cv2.putText(vis, f'PICK {res["best_score"]:.2f}',
                    (bc[0] + ox + 4, bc[3] + oy - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 0), 2)

    # shapes panel (target + candidates)
    panels = [('T', res.get('target_sig'))]
    for k, s in zip(res.get('box_idx', []), res.get('cell_sigs', [])):
        panels.append((f'c{k+1}', s))
    ph = 90
    n_panels = max(1, len(panels))
    panel = np.full((ph, ph * n_panels, 3), 30, np.uint8)
    for i, (name, s) in enumerate(panels):
        if s is None:
            continue
        small = cv2.resize(s, (ph - 10, ph - 10), interpolation=cv2.INTER_AREA)
        panel[5:ph - 5, i * ph + 5:i * ph + ph - 5] = cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
        cv2.putText(panel, name, (i * ph + 6, ph - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
    # panel ko image jitni chaudi karo
    if panel.shape[1] < vis.shape[1]:
        pad = np.full((ph, vis.shape[1] - panel.shape[1], 3), 30, np.uint8)
        panel = np.hstack([panel, pad])
    else:
        panel = panel[:, :vis.shape[1]]
    out = np.vstack([vis, panel])
    fname = os.path.join(DEBUG_DIR, f'debug_{tag}_{time.strftime("%H%M%S")}.png')
    cv2.imwrite(fname, out)

    # cells na mile to 'Click' ke aas-paas ka zoom crop bhi save karo
    if not res.get('cells') and res.get('click') is not None:
        cw = res['click']
        th = max(9, int(cw['h']))
        h_, w_ = arr.shape[:2]
        x0 = max(0, int(cw['x'] - 22 * th)); x1 = min(w_, int(cw['x'] + 14 * th))
        y0 = max(0, int(cw['y'] - 6 * th)); y1 = min(h_, int(cw['y'] + 10 * th))
        if x1 - x0 > 20 and y1 - y0 > 20:
            crop = arr[y0:y1, x0:x1]
            big = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
            big = cv2.cvtColor(big, cv2.COLOR_RGB2BGR)
            cv2.putText(big, "Click yahan mila - yahi area hai", (8, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            fname2 = os.path.join(DEBUG_DIR, f'debug_{tag}_area_{time.strftime("%H%M%S")}.png')
            cv2.imwrite(fname2, big)
            return fname + ' + ' + fname2
    return fname


def choose_box(res):
    """
    Kaunsa box click karna hai:
      - clue ka strong match mila -> wahi box
      - match dhundhla/koi nahi -> 3 boxes me se RANDOM ek
    Return: (cell_index, reason, score)
    """
    scores = res.get('scores') or []
    boxes = res.get('box_idx') or []
    if not boxes:
        return None, 'no_boxes', 0.0
    best_local = int(np.argmax(scores)) if scores else 0
    best_score = scores[best_local] if scores else 0.0
    if res.get('strong_match'):
        return boxes[best_local], 'match', best_score
    return random.choice(boxes), 'random', best_score


def print_scores(res):
    names = [f'Box{k+1}' for k in range(len(res['scores']))]
    parts = [f"{n}={s:.2f}" for n, s in zip(names, res['scores'])]
    log(f"🔍 {len(res['scores'])} boxes: " + '  '.join(parts) +
        f"  → best {names[res['best_local']]} ({res['best_score']:.2f})")
    if res['best_score'] < CONFIG['min_confidence']:
        log(f"{C.YELLOW}⚠️  Confidence kam hai — shayad sahi box na ho{C.RESET}")


def go_visible(frame_rgb, strip, detect_fn=None, allow_ocr=True):
    """
    'Go' dikh raha hai? 3 tareeke:
      1) chhota-crop OCR (3 settings)
      2) blue letters ko jodke (dilate) size check  <-- 'G'+'o' alag hote hain!
      3) bada blue button blob
    """
    arr = np.array(frame_rgb)
    H, W = arr.shape[:2]
    h = max(20, strip[3] - strip[1])
    x0 = max(0, strip[2]); x1 = min(W, strip[2] + int(3.0 * h))
    y0 = max(0, strip[1] - int(0.8 * h)); y1 = min(H, strip[3] + int(1.0 * h))
    if x1 - x0 < 10 or y1 - y0 < 10:
        return False

    # 🔵 PEHLE blue blob (bahut fast ~2ms) — 'Go' yahin pakda jata hai
    if _blue_go_like(arr[y0:y1, x0:x1], h):
        return True

    if not allow_ocr:
        return False

    # OCR sirf tab jab blob na mile (slow)
    crop = Image.fromarray(arr[y0:y1, x0:x1])
    fn = detect_fn or ocr_words
    for kw in ({'upscale': 2, 'psm': 11},):
        try:
            words = fn(crop, **kw)
        except TypeError:
            words = fn(crop)
        except Exception:
            words = []
        for w in words:
            t = _clean(w['text'])
            if t in ('go', 'g0') or (t.startswith('go') and len(t) <= 3):
                return True
    return False


def _blue_go_like(sub, h):
    """Blue 'Go'-jaisa text/button hai? 'G' aur 'o' alag hote hain -> pehle jodo."""
    if sub is None or sub.size == 0:
        return False
    a = sub.astype(np.int16)
    blue = ((a[:, :, 2] - a[:, :, 0] > 60) & (a[:, :, 2] - a[:, :, 1] > 40))
    if not blue.any():
        return False
    mask = blue.astype(np.uint8) * 255
    kx = max(3, int(0.35 * h))          # letters ke beech ka gap bhar do
    merged = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 3)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(merged)
    for i in range(1, n):
        if (st[i, cv2.CC_STAT_HEIGHT] >= 0.25 * h
                and st[i, cv2.CC_STAT_AREA] >= 0.015 * h * h
                and st[i, cv2.CC_STAT_WIDTH] >= 0.15 * h):
            return True
    return False


def _go_blob_cell(arr, cells, target_idx):
    """OCR 'Go' na mile to: right side ka kaun sa cell blue 'Go' jaisa hai."""
    if not cells:
        return None
    h = max(20, cells[0][3] - cells[0][1])
    for i in range(target_idx + 1, len(cells)):
        c = cells[i]
        if _blue_go_like(arr[c[1]:c[3], c[0]:c[2]], h):
            return i
    return None


# ==================== CLICK ====================
def click_cell(screen, cell, region=None, clicks=None, jitter=0):
    x1, y1, x2, y2 = cell
    if region:
        x1 += region[0]; x2 += region[0]; y1 += region[1]; y2 += region[1]
    px, py = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    if jitter:
        px += jitter
        py += jitter
    lx, ly = screen.to_logical(px, py)
    log(f"   🎯 target: screen ({px:.0f},{py:.0f}) -> click ({lx:.0f},{ly:.0f}) "
        f"[scale {screen.scale:.2f}x]")

    # screen ke bahar? (galat mapping pakadne ke liye)
    lim_w = getattr(screen, 'logi_w', 0) or getattr(screen, 'shot_w', 0)
    lim_h = getattr(screen, 'logi_h', 0) or getattr(screen, 'shot_h', 0)
    if lx < 0 or ly < 0 or (lim_w and lx >= lim_w) or (lim_h and ly >= lim_h):
        log(f"{C.RED}❌ click point screen ke bahar hai ({lx:.0f},{ly:.0f}) "
            f"— screen {lim_w}x{lim_h}. Click skip.{C.RESET}")
        return False

    pyautogui.moveTo(lx, ly, duration=0.2)
    time.sleep(CONFIG['click_delay'])

    # moveTo ne kaam kiya? (DPI galat ho to yahan pakda jayega)
    try:
        got = pyautogui.position()
        if abs(got[0] - lx) > 8 or abs(got[1] - ly) > 8:
            log(f"{C.YELLOW}⚠️  mouse ({got[0]},{got[1]}) par pahuncha, "
                f"expected ({int(lx)},{int(ly)}) — display scaling issue{C.RESET}")
    except Exception:
        pass

    n = CONFIG.get('clicks', 1) if clicks is None else clicks
    n = max(1, min(3, int(n)))
    for i in range(n):
        pyautogui.mouseDown()
        time.sleep(0.05)
        pyautogui.mouseUp()
        if i + 1 < n:
            time.sleep(0.08)
    log(f"{C.GREEN}🖱️  CLICK{(' x' + str(n)) if n > 1 else ''} "
        f"({int(lx)}, {int(ly)}){C.RESET}")
    return True


def calibrate(screen):
    """Screenshot <-> click mapping verify karo (kuch click nahi hota)."""
    print("\n🔧 CALIBRATION — mapping check (koi click nahi hoga)\n")
    try:
        sw, sh = pyautogui.size()
        shot = pyautogui.screenshot()
        print(f"  DPI mode          : {screen.dpi_mode}")
        print(f"  pyautogui.size()  : {sw} x {sh}")
        print(f"  screenshot        : {shot.size[0]} x {shot.size[1]}")
        print(f"  scale (shot/size) : {shot.size[0] / float(sw):.3f}")
        print(f"  active scale      : {screen.scale:.2f}x")
        start = pyautogui.position()
        print(f"  mouse start       : {start}")
        bad = 0
        for tx, ty in [(sw // 4, sh // 4), (sw // 2, sh // 2), (3 * sw // 4, 3 * sh // 4)]:
            pyautogui.moveTo(tx, ty)
            time.sleep(0.15)
            gx, gy = pyautogui.position()
            ok = abs(gx - tx) <= 3 and abs(gy - ty) <= 3
            bad += 0 if ok else 1
            print(f"  moveTo({tx},{ty}) -> ({gx},{gy})  {'OK' if ok else 'MISMATCH'}")
        pyautogui.moveTo(start[0], start[1])
        print("-" * 52)
        if bad == 0 and screen.scale == 1.0:
            print("  ✅ Mapping sahi lagti hai (scale 1.0, moves exact)")
        else:
            print(f"  ⚠️  {bad} move mismatch / scale {screen.scale:.2f} — yehi wajah ho sakti hai")
        _log_write(f"CALIBRATE: dpi={screen.dpi_mode} size={sw}x{sh} shot={shot.size} "
                   f"scale={screen.scale} mismatches={bad}")
    except Exception as e:
        print(f"  ❌ calibration fail: {e}")


def click_test(screen):
    """Clicks kaam kar rahe hain ya nahi — safe test (kahin random click nahi)."""
    print("\n🖱️  CLICK TEST")
    print("   Cursor abhi jahan hai wahin click hoga (3 second me).")
    print("   Pehle Notepad khol lo to best rahega.\n")
    for i in (3, 2, 1):
        print(f"   {i}...", flush=True)
        time.sleep(1.0)

    start = pyautogui.position()
    sw, sh = pyautogui.size()
    pyautogui.moveTo(sw // 2, sh // 2, duration=0.3)
    time.sleep(0.15)
    mid = pyautogui.position()
    pyautogui.moveTo(start[0], start[1], duration=0.3)
    time.sleep(0.15)
    back = pyautogui.position()

    log(f"screen  : logical {sw}x{sh}")
    log(f"start   : {start}")
    log(f"center  : moved to ({sw // 2}, {sh // 2}) -> actual {mid}")
    log(f"back    : returned -> actual {back}")
    ok_move = abs(mid[0] - sw // 2) <= 8 and abs(mid[1] - sh // 2) <= 8
    log(f"moveTo  : {'✅ sahi' if ok_move else '❌ galat (display scaling issue)'}")

    pyautogui.click()
    log(f"{C.GREEN}🖱️  click bheja {back} par{C.RESET}")
    log("Agar Notepad me cursor/text hila to clicks kaam kar rahe hain ✅")


# ==================== REGION PICKER ====================
def pick_point(label):
    print(f"\n{label}")
    print("   Mouse sahi jagah le jao, phir ENTER dabao")
    stop = threading.Event()

    def show():
        while not stop.is_set():
            x, y = pyautogui.position()
            sys.stdout.write(f"\r   📍 ({x}, {y})        ")
            sys.stdout.flush()
            time.sleep(0.08)
    t = threading.Thread(target=show, daemon=True)
    t.start()
    try:
        input()
    except KeyboardInterrupt:
        stop.set(); print(); sys.exit(0)
    stop.set(); t.join(timeout=0.3)
    x, y = pyautogui.position()
    print(f"\r   ✅ ({x}, {y})")
    return x, y


def pick_region():
    x1, y1 = pick_point("👉 Step 1: CAPTCHA ke TOP-LEFT corner par mouse le jao")
    x2, y2 = pick_point("👉 Step 2: BOTTOM-RIGHT corner par")
    x, y = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    if w < 50 or h < 40:
        print(f"{C.RED}❌ Region bahut chhota{W}{C.RESET}")
        sys.exit(1)
    with open(REGION_FILE, 'w') as f:
        f.write(f"{x},{y},{w},{h},#dpi")     # marker: coords DPI-aware hain
    return (x, y, w, h)


def load_region():
    if os.path.exists(REGION_FILE):
        try:
            with open(REGION_FILE) as f:
                toks = [t.strip() for t in f.read().strip().split(',')]
            nums = [int(t) for t in toks[:4]]
            marked = len(toks) > 4 and toks[4].startswith('#dpi')
            if not marked:
                # purana region (DPI-aware hone se pehle ka) -> bharosa nahi
                log(f"{C.YELLOW}⚠️  Purana region.txt mila — DPI mode badal gaya hai, "
                    f"ignore kar raha hoon. '--manual' se dobara select karo.{C.RESET}")
                return None
            return tuple(nums)
        except Exception:
            pass
    return None


def parse_region(s):
    try:
        p = [int(v) for v in s.split(',')]
        if len(p) != 4:
            raise ValueError
        return tuple(p)
    except ValueError:
        print(f"{C.RED}❌ Region format: x,y,w,h{C.RESET}")
        sys.exit(1)


# ==================== MODES ====================
def solve_now(screen, region, once=True, dry_run=False, debug=False):
    frame = screen.grab()
    res = analyse(frame, region=region)
    st = res['status']
    if st == 'no_click':
        log(f"{C.RED}❌ 'Click' nahi mila — CAPTCHA screen par khula hai?{C.RESET}")
        return False
    if st == 'no_strip':
        log(f"{C.RED}❌ Strip/boxes detect na hue{C.CYAN} → --manual se region select karo{C.RESET}")
        if STRIP_FAIL:
            log(f"   reason: {STRIP_FAIL}")
        if debug:
            log('   debug: ' + str(save_debug(frame, res, 'nostrip')))
        return False
    if st in ('no_boxes', 'no_target'):
        log(f"{C.RED}❌ {st}{C.RESET}")
        if debug:
            log('   debug: ' + str(save_debug(frame, res, st)))
        return False

    print_scores(res)
    if debug:
        log('   debug: ' + str(save_debug(frame, res, 'ok')))
    if st == 'wait_go':
        log(f"{C.YELLOW}⏳ 'Go' ka intezaar...{C.RESET}")
        return False
    pick_idx, reason, best_score = choose_box(res)
    if pick_idx is None or pick_idx == res.get('target_idx'):
        log(f"{C.RED}❌ koi box choose nahi hua{C.RESET}")
        return False
    box_no = res['box_idx'].index(pick_idx) + 1
    tag = 'match' if reason == 'match' else 'RANDOM — clue match nahi mila'
    if dry_run:
        log(f"{C.CYAN}🧪 dry-run: Box{box_no} [{tag}] ({best_score:.2f}) — click nahi kiya{C.RESET}")
        return True
    log(f"→ Box{box_no} [{tag}] (score {best_score:.2f})")
    click_cell(screen, res['cells'][pick_idx], region, CONFIG['clicks'])
    return True


BAD_STATES = ('no_click', 'no_strip', 'no_boxes', 'no_target')
STATE_HINT = {
    'no_click': " — CAPTCHA screen par lao (browser aage rakho)",
    'no_strip': " — boxes detect na hue; --manual se region select karo",
    'no_boxes': " — boxes na mile",
    'no_target': " — target shape na mila",
}


CACHE_VERSION = 2      # v2 = naya 4-cell layout; purana cache auto-ignore


def load_layout_cache(screen=None):
    """Pichli baar ka layout — isse start hote hi kaam shuru (full OCR nahi)."""
    try:
        with open(LAYOUT_CACHE) as f:
            d = json.load(f)
        if d.get('v') != CACHE_VERSION:
            return None       # purane layout ka cache (5-cell) -> phek do
        click = d.get('click')
        if not isinstance(click, dict):
            return None
        ts = d.get('ts', 0)
        if time.time() - ts > 900:      # 15 min purana -> bharosa nahi
            return None
        if screen is not None and d.get('size'):
            sw, sh = d['size']
            if abs(sw - screen.shot_w) > 4 or abs(sh - screen.shot_h) > 4:
                return None       # resolution badal gaya -> cache bekaar
        return {'click': click, 'box_rel': d.get('box_rel')}
    except Exception:
        return None


def save_layout_cache(layout, screen=None):
    try:
        d = {'v': CACHE_VERSION, 'click': layout['click'],
             'box_rel': layout.get('box_rel'),
             'ts': time.time(), 'saved': time.strftime('%Y-%m-%d %H:%M:%S')}
        if screen is not None:
            d['size'] = [screen.shot_w, screen.shot_h]
        with open(LAYOUT_CACHE, 'w') as f:
            json.dump(d, f)
    except Exception:
        pass


def run_auto(screen, region, dry_run=False, debug=False, go_required=True):
    mode = 'region' if region else 'full-screen auto-detect'
    print(f"{C.BLUE}{C.BOLD}👀 Monitor ON ({mode}) — 'Go' dikhte hi click{C.RESET}")
    print("   Stop: Ctrl+C  ya  mouse corner par\n")

    layout = None
    if region is None:
        cached = load_layout_cache(screen)
        if cached:
            layout = cached
            log(f"{C.CYAN}⚡ Saved layout se start (fast) — full OCR skip{C.RESET}")

    last_state = ''
    last_click = 0.0
    wait_since = time.time()
    stable_cell, stable_count = None, 0
    last_nogo_log = 0.0
    bad_streak = 0
    pending_sig = None      # click ke baad target shape (verify ke liye)
    pending_local = -1
    click_attempts = 0

    while True:
        try:
            frame = screen.grab()

            if layout is None:
                # ---- AUTO-DETECT: saare 'Click' candidates me se asli CAPTCHA ----
                res = analyse(frame, region=region, go_required=go_required, check_go=True)
                if res['status'] in BAD_STATES:
                    bad_streak += 1
                    if last_state != res['status']:
                        reason = (f" [{STRIP_FAIL}]"
                                  if res['status'] == 'no_strip' and STRIP_FAIL else '')
                        extra = ''
                        if res.get('n_candidates'):
                            extra = f" ({res['n_candidates']} 'click' words mile, koi strip nahi bani)"
                        log(f"{C.YELLOW}👀 {res['status']}"
                            f"{STATE_HINT.get(res['status'], '')}{reason}{extra}{C.RESET}")
                        last_state = res['status']
                        if debug:
                            log('   debug: ' + str(save_debug(frame, res, res['status'])))
                    bad_streak = 0
                    time.sleep(CONFIG['scan_interval'] if last_state != 'no_click' else 0.7)
                    continue

                layout = {'click': res['click'], 'box_rel': res.get('box_rel')}
                save_layout_cache(layout, screen)
                log(f"{C.GREEN}✅ CAPTCHA mil gaya — {len(res['scores'])} boxes{C.RESET}")
                print_scores(res)
                if debug:
                    log('   debug: ' + str(save_debug(frame, res, 'locate')))
            else:
                # ---- FAST TRACK: cached layout, ~10ms/frame ----
                # box_rel cache me nahi bhejte — har frame par cells se recompute
                # hota hai, taaki layout badalne par galat cell na chune
                res = analyse(frame, region=region, click_word=layout['click'],
                              check_go=True, go_required=go_required)
                if res['status'] in BAD_STATES:
                    bad_streak += 1
                    if bad_streak >= 3:
                        log(f"{C.CYAN}🔄 Layout nahi mila — dobara auto-detect{C.RESET}")
                        layout = None
                        bad_streak = 0
                    time.sleep(CONFIG['scan_interval'])
                    continue
                bad_streak = 0

            if res['status'] == 'wait_go':
                if last_state != 'wait_go':
                    if CONFIG['go_timeout'] > 0:
                        hint = f"({CONFIG['go_timeout']:.0f}s baad phir bhi click)"
                    else:
                        hint = "(sirf 'Go' dikhne par click hoga)"
                    log(f"{C.YELLOW}⏳ Timer chal raha hai — 'Go' ka intezaar {hint}{C.RESET}")
                    last_state = 'wait_go'
                    wait_since = time.time()

                waited = time.time() - wait_since
                if (CONFIG['go_timeout'] > 0 and waited > CONFIG['go_timeout']
                        and (time.time() - last_click) > 2.5):
                    _pi, _rs, _sc = choose_box(res)
                    if _pi is None:
                        time.sleep(CONFIG['scan_interval'])
                        continue
                    if (time.time() - last_nogo_log) > 5.0:
                        log(f"{C.YELLOW}⚠️  'Go' nahi mila ({waited:.0f}s) — "
                            f"phir bhi Box{res['box_idx'].index(_pi)+1} par click{C.RESET}")
                        last_nogo_log = time.time()
                    if debug:
                        log('   debug: ' + str(save_debug(frame, res, 'nogo')))
                    if dry_run:
                        log(f"{C.CYAN}🧪 dry-run: click roka gaya{C.RESET}")
                    else:
                        click_cell(screen, res['cells'][_pi], region, CONFIG['clicks'])
                        pending_sig = res.get('target_sig')
                        pending_local = _pi
                        click_attempts = 1
                        time.sleep(1.2)
                    last_click = time.time()
                    wait_since = time.time()
                    last_state = ''
                time.sleep(CONFIG['scan_interval'])
                continue

            # ---- click register hua? (wahi CAPTCHA dikh raha hai to retry) ----
            if pending_sig is not None and res.get('target_sig') is not None:
                same = iou(pending_sig, res['target_sig']) > 0.85
                if same:
                    if click_attempts < 3 and (time.time() - last_click) > 2.0:
                        log(f"{C.YELLOW}⚠️  Click register nahi hua — dobara try "
                            f"({click_attempts}/3){C.RESET}")
                        _pi, _rs, _sc = choose_box(res)
                        if not dry_run and _pi is not None:
                            click_cell(screen, res['cells'][_pi], region,
                                       CONFIG['clicks'], jitter=click_attempts * 7)
                        click_attempts += 1
                        last_click = time.time()
                        time.sleep(1.0)
                        continue
                    if click_attempts >= 3:
                        log(f"{C.RED}❌ 3 baar click kiya par CAPTCHA wahi hai — "
                            f"site/coordinates issue. --calibrate chalao.{C.RESET}")
                        pending_sig, click_attempts = None, 0
                else:
                    pending_sig, click_attempts = None, 0

            # ---- 'Go' dikha (timer khatam): TURANT click ----
            pick_idx, reason, best_score = choose_box(res)
            if pick_idx is None or pick_idx == res.get('target_idx'):
                time.sleep(CONFIG['scan_interval'])
                continue

            if (time.time() - last_click) > 2.5:
                box_no = res['box_idx'].index(pick_idx) + 1
                tag = ('match' if reason == 'match'
                       else 'RANDOM — clue ka match nahi mila')
                log(f"{C.GREEN}🟢 'Go' mila → Box{box_no} [{tag}] "
                    f"score {best_score:.2f}{C.RESET}")
                if debug:
                    log('   debug: ' + str(save_debug(frame, res, 'click')))
                if dry_run:
                    log(f"{C.CYAN}🧪 dry-run: click roka gaya{C.RESET}")
                else:
                    click_cell(screen, res['cells'][pick_idx], region, CONFIG['clicks'])
                last_click = time.time()
                pending_sig = res.get('target_sig')
                pending_local = pick_idx
                click_attempts = 1
                # layout rakho: agla CAPTCHA wahi jagah hota hai -> fast
                time.sleep(1.5)
                stable_cell, stable_count = None, 0
                last_state = ''

        except pyautogui.FailSafeException:
            raise
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"⚠️ error: {e}")
            time.sleep(0.8)

        time.sleep(CONFIG['scan_interval'])


# ==================== SELFTEST ====================
def selftest():
    """Environment report — jab kuch samajh na aaye to ye chalao."""
    import importlib
    print("=" * 56)
    print("  SELFTEST — environment report")
    print("=" * 56)
    info = [f"python      : {sys.version.split()[0]} ({platform.architecture()[0]})",
            f"os          : {platform.platform()}",
            f"file        : {os.path.abspath(__file__)}",
            f"cwd         : {os.getcwd()}",
            f"log file    : {LOG_FILE}"]
    ok = True
    for mod, pkg in [('numpy', 'numpy'), ('cv2', 'opencv-python'), ('PIL', 'pillow'),
                     ('pyautogui', 'pyautogui'), ('pytesseract', 'pytesseract')]:
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, '__version__', '?')
            info.append(f"{mod:12s}: OK  {ver}")
        except Exception as e:
            info.append(f"{mod:12s}: MISSING  ({e}) -> pip install {pkg}")
            ok = False
    tp = find_tesseract()
    info.append(f"tesseract   : {tp if tp else 'NOT FOUND -> https://github.com/UB-Mannheim/tesseract/wiki'}")
    if not tp:
        ok = False
    try:
        import pyautogui as pg
        sw, sh = pg.size()
        shot = pg.screenshot()
        info.append(f"screen      : logical {sw}x{sh}, screenshot {shot.size[0]}x{shot.size[1]}, "
                    f"scale {shot.size[0] / float(sw):.2f}x")
    except Exception as e:
        info.append(f"screen      : FAIL ({e})")
        ok = False
    for line in info:
        print(line)
    print("-" * 56)
    print("RESULT:", "✅ sab ready hai" if ok else "⚠️  kuch cheezein missing hain (upar dekho)")
    _log_write("SELFTEST:\n  " + "\n  ".join(info) + f"\n  RESULT ok={ok}")
    return ok


# ==================== MAIN ====================
def main():
    ap = argparse.ArgumentParser(description="Surf-Bash CAPTCHA clicker (shape matching)")
    ap.add_argument('--region', help='x,y,w,h (logical coords)')
    ap.add_argument('--manual', action='store_true', help='region select karo')
    ap.add_argument('--once', action='store_true', help='ek baar solve karke exit')
    ap.add_argument('--dry-run', action='store_true', help='sirf batao, click mat karo')
    ap.add_argument('--debug', action='store_true', help='debug/ me image save karo')
    ap.add_argument('--selftest', action='store_true',
                    help='sirf environment check karo (kuch nahi chalega)')
    ap.add_argument('--no-wait-go', action='store_true',
                    help="'Go' ka intezaar mat karo — boxes milte hi click")
    ap.add_argument('--go-timeout', type=float, default=CONFIG['go_timeout'],
                    help="itne second 'Go' na mile to phir bhi click (default 0 = sirf 'Go' par click)")
    ap.add_argument('--min-match', type=float, default=CONFIG['min_match'],
                    help='itne score se kam = clue match nahi (random click)')
    ap.add_argument('--clicks', type=int, default=1,
                    help='ek box par kitne clicks (1-3, default 1)')
    ap.add_argument('--calibrate', action='store_true',
                    help='screenshot/click mapping check (kuch click nahi)')
    ap.add_argument('--click-test', action='store_true',
                    help='clicks kaam kar rahe hain ya nahi — safe test')
    ap.add_argument('--interval', type=float, default=CONFIG['scan_interval'])
    ap.add_argument('--no-pause', action='store_true')
    args = ap.parse_args()

    CONFIG['scan_interval'] = args.interval
    CONFIG['debug'] = args.debug
    CONFIG['clicks'] = max(1, min(3, args.clicks))
    CONFIG['min_match'] = args.min_match
    CONFIG['go_timeout'] = max(0.0, args.go_timeout)

    if args.selftest:
        selftest()
        if not args.no_pause:
            try:
                input('\nENTER dabao...')
            except (EOFError, KeyboardInterrupt):
                pass
        return

    try:
        ensure_deps()
        ensure_tesseract()
        print(f"\n{C.BOLD}🎯 Surf-Bash CAPTCHA Clicker v2 (shape matching){C.RESET}")
        print("=" * 56)

        screen = Screen()

        if args.calibrate:
            calibrate(screen)
            return

        if args.click_test:
            click_test(screen)
            return

        region = None
        if args.region:
            region = parse_region(args.region)
            log(f"📌 Region (cmd): {region}")
        elif args.manual:
            region = load_region()
            if region:
                log(f"📌 Saved region: {region}  (naya chahiye to region.txt delete karo)")
            else:
                region = pick_region()
                log(f"📌 Region saved: {region}")
        else:
            log("📌 Mode: full-screen auto-detect (browser background me bhi)")

        if args.once:
            solve_now(screen, region, dry_run=args.dry_run, debug=args.debug)
        else:
            run_auto(screen, region, dry_run=args.dry_run, debug=args.debug,
                     go_required=not args.no_wait_go)

    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}⏹ Stop ho gaya.{C.RESET}")
    except pyautogui.FailSafeException:
        print(f"\n{C.YELLOW}⏹ Emergency stop (mouse corner par tha).{C.RESET}")
    finally:
        if not args.no_pause:
            try:
                input(f"\n{C.CYAN}Band karne ke liye ENTER dabao...{C.RESET}")
            except EOFError:
                pass


def _banner():
    """Startup info — debug ke liye zaroori."""
    _log_write('\n' + '=' * 60)
    _log_write(f'START {time.strftime("%Y-%m-%d %H:%M:%S")}')
    _log_write(f'python  : {sys.version.split()[0]} ({platform.architecture()[0]})')
    _log_write(f'os      : {platform.system()} {platform.release()}')
    _log_write(f'file    : {os.path.abspath(__file__)}')
    _log_write(f'cwd     : {os.getcwd()}')


if __name__ == '__main__':
    _banner()
    try:
        main()
    except SystemExit:
        pass
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}⏹ Stop.{C.RESET}")
    except BaseException:
        crash_report(*sys.exc_info())
        try:
            input('ENTER dabao...')
        except Exception:
            pass
