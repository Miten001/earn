#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 Surf-Bash CAPTCHA Clicker — v2 (graph-paper + shape matching)
================================================================
"Click" ke niche jo shape hai, wahi shape boxes me dhoondho, aur "Go"
dikhte hi us box par click kar do.

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
import tempfile
import threading
import time
import traceback
import urllib.request

if os.name == 'nt':
    os.system('')  # Windows CMD me ANSI colors

CONFIG = {
    "scan_interval": 0.45,
    "click_delay": 0.25,
    "min_confidence": 0.22,     # isse kam = "pata nahi" (log me warning)
    "debug": False,
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGION_FILE = os.path.join(SCRIPT_DIR, 'region.txt')
DEBUG_DIR = os.path.join(SCRIPT_DIR, 'debug')
LOG_FILE = os.path.join(SCRIPT_DIR, 'clicker_log.txt')

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
class Screen:
    """Screenshot physical px me leta hai; click logical coords me jata hai.
    High-DPI (125%/150%) par ye scale zaroori hai — warna click galat jagah!"""

    def __init__(self):
        self.scale = 1.0
        try:
            sw, _sh = pyautogui.size()
            shot = pyautogui.screenshot()
            if sw:
                self.scale = shot.size[0] / float(sw)
        except Exception:
            self.scale = 1.0
        if abs(self.scale - 1.0) > 0.05:
            log(f"{C.YELLOW}🖥️  Display scaling detect hui: {self.scale:.2f}x "
                f"(clicks adjust ho jayenge){C.RESET}")

    def grab(self):
        img = pyautogui.screenshot().convert('RGB')
        return img

    def to_logical(self, px, py):
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


def detect_strip(gray, click_w):
    """
    'Click' word ke aas-paas CAPTCHA strip dhoondho.
    Return: (cells, strip_rect)  cells = [(x1,y1,x2,y2), ...] left se right
    """
    H, W = gray.shape
    th = max(8, int(click_w['h']))
    cx = int(click_w['x'] + click_w['w'] / 2)
    cy = int(click_w['y'] + click_w['h'] / 2)

    # 1) Horizontal borders — strip ki patli lines (moti dark bars ignore)
    wx0 = max(0, cx - int(10 * th)); wx1 = min(W, cx + int(5 * th))
    wy0 = max(0, cy - int(8 * th)); wy1 = min(H, cy + int(8 * th))
    sub = gray[wy0:wy1, wx0:wx1]
    if sub.size == 0:
        return [], None
    rows = (sub < 125).mean(axis=1)

    # patli lines = groups jinki thickness <= 4 px (browser bar 8px+ hata do)
    thin = []
    i = 0
    while i < len(rows):
        if rows[i] > 0.5:
            j = i
            while j < len(rows) and rows[j] > 0.5:
                j += 1
            if 1 <= (j - i) <= 4:
                thin.append(int(round(wy0 + (i + j - 1) / 2.0)))
            i = j
        else:
            i += 1
    if len(thin) < 2:
        return [], None

    # Click text ke sabse nazdeek upar/niche wali lines = strip ke borders
    above = [y for y in thin if y < cy]
    below = [y for y in thin if y > cy]
    if not above or not below:
        return [], None
    top = max(above)          # text ke just upar
    bottom = min([y for y in below if y > top + 2.0 * th], default=None)
    if bottom is None:
        bottom = max(below)
    if bottom - top < 2.5 * th:
        return [], None

    # 2) Vertical dividers (poori screen me, sirf band ke andar)
    band = gray[top + 2:bottom - 1, :]
    if band.size == 0:
        return [], None
    cols = (band < 125).mean(axis=0)
    dividers = _group_line_positions(cols > 0.75)
    if len(dividers) < 2:
        return [], None

    # 3) Click wale cell se start karke chain banao
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
    while lo - 1 >= 0 and 0.55 * cell_w <= dividers[lo] - dividers[lo - 1] <= 1.7 * cell_w:
        lo -= 1
    while hi + 1 < len(dividers) and 0.55 * cell_w <= dividers[hi + 1] - dividers[hi] <= 1.7 * cell_w:
        hi += 1

    cells = [(dividers[k] + 2, top + 3, dividers[k + 1] - 2, bottom - 2)
             for k in range(lo, hi)]
    strip = (dividers[lo], top, dividers[hi], bottom)
    return cells, strip


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

    if click_word is not None:
        click_w, go_w = click_word, None
        words = words or []
    else:
        if words is None:
            words = locate_words(Image.fromarray(arr))
        click_w = find_word(words, 'click')
        go_w = find_word_exact(words, 'go', min_conf_h=10)
    if click_w is None:
        return {'status': 'no_click', 'words': words}

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
        box_idx = [i for i in range(len(cells))
                   if i != target_idx and not cell_has_word(cells[i], go_w)]
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
    return {
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
    return fname


def print_scores(res):
    names = [f'Box{k+1}' for k in range(len(res['scores']))]
    parts = [f"{n}={s:.2f}" for n, s in zip(names, res['scores'])]
    log(f"🔍 {len(res['scores'])} boxes: " + '  '.join(parts) +
        f"  → best {names[res['best_local']]} ({res['best_score']:.2f})")
    if res['best_score'] < CONFIG['min_confidence']:
        log(f"{C.YELLOW}⚠️  Confidence kam hai — shayad sahi box na ho{C.RESET}")


def go_visible(frame_rgb, strip, detect_fn=None):
    """Strip ke right me 'Go' dikh raha hai? (chhota crop OCR + blue-blob fallback)"""
    arr = np.array(frame_rgb)
    H, W = arr.shape[:2]
    h = max(20, strip[3] - strip[1])
    x0 = max(0, strip[2]); x1 = min(W, strip[2] + int(2.6 * h))
    y0 = max(0, strip[1] - int(0.6 * h)); y1 = min(H, strip[3] + int(0.8 * h))
    if x1 - x0 < 10 or y1 - y0 < 10:
        return False
    crop = Image.fromarray(arr[y0:y1, x0:x1])
    fn = detect_fn or ocr_words
    for w in fn(crop, upscale=2, psm=11):
        t = _clean(w['text'])
        if t == 'go' or t == 'g0' or (t.startswith('go') and len(t) <= 3):
            return True
    # fallback: bada blue blob (Go button/text)
    sub = arr[y0:y1, x0:x1].astype(np.int16)
    blue = ((sub[:, :, 2] - sub[:, :, 0] > 60) & (sub[:, :, 2] - sub[:, :, 1] > 40))
    n, lab, st, _ = cv2.connectedComponentsWithStats(blue.astype(np.uint8))
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > 0.12 * h * h and st[i, cv2.CC_STAT_HEIGHT] > 0.35 * h:
            return True
    return False


# ==================== CLICK ====================
def click_cell(screen, cell, region=None):
    x1, y1, x2, y2 = cell
    if region:
        x1 += region[0]; x2 += region[0]; y1 += region[1]; y2 += region[1]
    px, py = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    lx, ly = screen.to_logical(px, py)
    pyautogui.moveTo(lx, ly, duration=0.2)
    time.sleep(CONFIG['click_delay'])
    pyautogui.click()
    log(f"{C.GREEN}🖱️  CLICK ({int(lx)}, {int(ly)}){C.RESET}")


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
        f.write(f"{x},{y},{w},{h}")
    return (x, y, w, h)


def load_region():
    if os.path.exists(REGION_FILE):
        try:
            with open(REGION_FILE) as f:
                p = [int(v) for v in f.read().strip().split(',')]
            if len(p) == 4:
                return tuple(p)
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
    if dry_run:
        log(f"{C.CYAN}🧪 dry-run: Box{res['best_local']+1} par click karta, par nahi kiya{C.RESET}")
        return True
    click_cell(screen, res['best_cell'], region)
    return True


BAD_STATES = ('no_click', 'no_strip', 'no_boxes', 'no_target')
STATE_HINT = {
    'no_click': " — CAPTCHA screen par lao (browser aage rakho)",
    'no_strip': " — boxes detect na hue; --manual se region select karo",
    'no_boxes': " — boxes na mile",
    'no_target': " — target shape na mila",
}


def run_auto(screen, region, dry_run=False, debug=False):
    mode = 'region' if region else 'full-screen auto-detect'
    print(f"\n{C.BLUE}{C.BOLD}👀 Monitor ON ({mode}) — 'Go' dikhte hi click{C.RESET}")
    print("   Stop: Ctrl+C  ya  mouse corner par\n")

    layout = None          # cached 'Click' word (fast tracking ke liye)
    last_state = ''
    last_click = 0.0
    stable_cell, stable_count = None, 0

    while True:
        try:
            frame = screen.grab()

            if layout is None:
                # --- LOCATE: poori screen OCR (slow, sirf ek baar) ---
                res = analyse(frame, region=region)
                if res['status'] in BAD_STATES:
                    if last_state != res['status']:
                        log(f"{C.YELLOW}👀 {res['status']}{STATE_HINT.get(res['status'], '')}{C.RESET}")
                        last_state = res['status']
                        if debug:
                            log('   debug: ' + str(save_debug(frame, res, res['status'])))
                    time.sleep(CONFIG['scan_interval'])
                    continue
                layout = {'click': res['click'], 'box_rel': res.get('box_rel')}
                log(f"{C.GREEN}✅ CAPTCHA mil gaya — {len(res['scores'])} boxes{C.RESET}")
                print_scores(res)
                if debug:
                    log('   debug: ' + str(save_debug(frame, res, 'locate')))
            else:
                # --- TRACK: cached layout se fast (OCR full-screen nahi) ---
                res = analyse(frame, region=region, click_word=layout['click'],
                              box_rel=layout.get('box_rel'), check_go=True)
                if res['status'] in BAD_STATES:
                    if last_state != res['status']:
                        log(f"{C.YELLOW}👀 layout kho gaya — dobara dhoondh raha hoon{C.RESET}")
                        last_state = res['status']
                    layout = None
                    time.sleep(CONFIG['scan_interval'])
                    continue

            if res['status'] == 'wait_go':
                if last_state != 'wait_go':
                    log(f"{C.YELLOW}⏳ 'Go' ka intezaar...{C.RESET}")
                    last_state = 'wait_go'
                stable_cell, stable_count = None, 0
                time.sleep(CONFIG['scan_interval'])
                continue

            # --- 'Go' mila: 2 frame stable hone par click (misclick se bacho) ---
            if res['best_local'] == stable_cell:
                stable_count += 1
            else:
                stable_cell, stable_count = res['best_local'], 1

            if stable_count >= 2 and (time.time() - last_click) > 2.5:
                log(f"{C.GREEN}🟢 'Go' mila → Box{res['best_local']+1} "
                    f"(score {res['best_score']:.2f}){C.RESET}")
                if debug:
                    log('   debug: ' + str(save_debug(frame, res, 'click')))
                if dry_run:
                    log(f"{C.CYAN}🧪 dry-run: click roka gaya{C.RESET}")
                else:
                    click_cell(screen, res['best_cell'], region)
                last_click = time.time()
                time.sleep(1.2)        # page settle hone do
                layout = None          # next captcha ke liye dobara locate
                stable_cell, stable_count = None, 0

        except pyautogui.FailSafeException:
            raise
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"⚠️ error: {e}")
            time.sleep(0.8)

        time.sleep(CONFIG['scan_interval'])


# ==================== MAIN ====================
def main():
    ap = argparse.ArgumentParser(description="Surf-Bash CAPTCHA clicker (shape matching)")
    ap.add_argument('--region', help='x,y,w,h (logical coords)')
    ap.add_argument('--manual', action='store_true', help='region select karo')
    ap.add_argument('--once', action='store_true', help='ek baar solve karke exit')
    ap.add_argument('--dry-run', action='store_true', help='sirf batao, click mat karo')
    ap.add_argument('--debug', action='store_true', help='debug/ me image save karo')
    ap.add_argument('--interval', type=float, default=CONFIG['scan_interval'])
    ap.add_argument('--no-pause', action='store_true')
    args = ap.parse_args()

    CONFIG['scan_interval'] = args.interval
    CONFIG['debug'] = args.debug

    try:
        ensure_deps()
        ensure_tesseract()
        print(f"\n{C.BOLD}🎯 Surf-Bash CAPTCHA Clicker v2 (shape matching){C.RESET}")
        print("=" * 56)

        screen = Screen()

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
            run_auto(screen, region, dry_run=args.dry_run, debug=args.debug)

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
