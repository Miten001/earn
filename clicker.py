#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 Screen CAPTCHA Clicker — Shape Matching + Auto-Detect version
=================================================================
"Click" ke niche jo shape/letter dikhe, use boxes me find karke jab
"Go" aaye to us par auto-click karta hai.

Naya kya hai (purane version se):
  - Letter OCR ki jagah SHAPE MATCHING (OpenCV) — shapes bhi solve honge
  - Layout auto-detect: "Click" left/right/top kahin bhi ho, chalega
  - 3, 4, 5... kitne bhi boxes hon, sab handle honge
  - Full-screen auto-detect: browser background me ho to bhi CAPTCHA dhoondhega

Setup (sab auto — kuch download nahi karna):
  - Python packages pehli baar auto-install (pyautogui, pillow, pytesseract,
    opencv-python, numpy)
  - Tesseract OCR (Windows) na mile to auto-download + install

Kaise chalao:
   1. Is file par DOUBLE-CLICK karo  (ya CMD me:  python clicker.py)
   2. Pehli baar setup hoga (packages + Tesseract) — thoda time lagega
   3. Tool poori screen scan karke CAPTCHA khud dhoondhega
   4. "Go" aate hi sahi box par click ho jayega 🖱️

Stop:  Ctrl+C   ya   mouse screen corner par le jao (emergency stop)

Options (CMD se):
   python clicker.py --once                 # ek baar find & click karke exit
   python clicker.py --manual              # region select karke chalao (auto-detect fail ho to)
   python clicker.py --region 100,200,900,300
   python clicker.py --no-pause            # band hone par Enter na puche
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

# Windows CMD par ANSI colors enable karo
if os.name == 'nt':
    os.system('')

# ---------------- Config ----------------
CONFIG = {
    "scan_interval": 0.5,   # seconds me scan gap
    "click_delay": 0.3,     # click se pehle rukna
    "min_box_w": 40,        # box ki min width (px)
    "min_shape_area": 80,   # shape ki min area (empty box pehchanne ke liye)
    "iou_threshold": 0.12,  # isse kam match = bharosa nahi
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGION_FILE = os.path.join(SCRIPT_DIR, 'region.txt')

# Dependencies (main() me load hote hain — --help bina packages ke bhi kaam kare)
pyautogui = None
Image = ImageOps = pytesseract = None
cv2 = np = None


# ---------------- Terminal colors ----------------
class C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def ts():
    return time.strftime('%H:%M:%S')


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


# ================= AUTO SETUP (packages + Tesseract) =================
def _import_deps():
    import pyautogui as _pg
    from PIL import Image as _Img, ImageOps as _Ops
    import pytesseract as _pt
    import cv2 as _cv
    import numpy as _np
    return _pg, _Img, _Ops, _pt, _cv, _np


def ensure_deps():
    """Packages na mile to khud pip se install kar do."""
    global pyautogui, Image, ImageOps, pytesseract, cv2, np
    try:
        pyautogui, Image, ImageOps, pytesseract, cv2, np = _import_deps()
    except ImportError:
        missing = []
        for mod, pkg in [('pyautogui', 'pyautogui'),
                         ('PIL', 'pillow'),
                         ('pytesseract', 'pytesseract'),
                         ('cv2', 'opencv-python'),
                         ('numpy', 'numpy')]:
            try:
                __import__(mod)
            except ImportError:
                missing.append(pkg)
        print(f"{C.YELLOW}📦 Pehli baar setup ho raha hai — {', '.join(missing)} install kar raha hoon...{C.RESET}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
        except subprocess.CalledProcessError:
            print(f"{C.RED}❌ Install fail ho gaya. Internet check karo, phir dobara chalao.{C.RESET}")
            sys.exit(1)
        pyautogui, Image, ImageOps, pytesseract, cv2, np = _import_deps()
        print(f"{C.GREEN}✅ Packages install ho gaye!{C.RESET}")
    pyautogui.FAILSAFE = True   # mouse corner par = emergency stop
    pyautogui.PAUSE = 0.05


def find_tesseract():
    """Tesseract ka exe dhoondho (PATH ya common jagah)."""
    p = shutil.which('tesseract')
    if p:
        return p
    candidates = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe'),
        '/usr/bin/tesseract',
        '/usr/local/bin/tesseract',
        '/opt/homebrew/bin/tesseract',
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def download_tesseract_windows():
    """Windows par Tesseract auto-download + silent install."""
    if shutil.which('winget'):
        print("   winget se Tesseract install kar raha hoon...")
        subprocess.run(['winget', 'install', '--id', 'UB-Mannheim.TesseractOCR', '-e',
                        '--accept-source-agreements', '--accept-package-agreements'],
                       capture_output=True)
        p = find_tesseract()
        if p:
            return p
    print("   GitHub se installer download kar raha hoon...")
    try:
        with urllib.request.urlopen(
                'https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest',
                timeout=30) as resp:
            data = json.load(resp)
        url = None
        for asset in data.get('assets', []):
            name = asset.get('name', '')
            if 'w64-setup' in name and name.endswith('.exe'):
                url = asset['browser_download_url']
                break
        if not url:
            return None
        installer = os.path.join(tempfile.gettempdir(), 'tesseract-setup.exe')
        print(f"   Downloading... ({os.path.basename(url)})")
        urllib.request.urlretrieve(url, installer)
        print("   Install kar raha hoon (silent, thoda time lagega)...")
        subprocess.run([installer, '/S'], timeout=300)
        return find_tesseract()
    except Exception as e:
        print(f"   Download/install fail: {e}")
        return None


def ensure_tesseract():
    """Tesseract na mile to auto-install karo, phir path set karo."""
    path = find_tesseract()
    if not path and os.name == 'nt':
        print(f"{C.YELLOW}🔤 Tesseract OCR nahi mila — auto-download kar raha hoon...{C.RESET}")
        path = download_tesseract_windows()
    if not path:
        print(f"\n{C.RED}❌ Tesseract OCR nahi mil paya!{C.RESET}")
        print("   Manual install karo: https://github.com/UB-Mannheim/tesseract/wiki")
        print("   (Windows: installer chalao, phir dobara clicker.py chalao)")
        sys.exit(1)
    pytesseract.pytesseract.tesseract_cmd = path
    print(f"{C.GREEN}✅ Tesseract ready: {path}{C.RESET}")


# ================= OCR (Click / Go dhoondho) =================
def ocr_words(img):
    """OCR se words + positions nikalo."""
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = []
    for i in range(len(data['text'])):
        text = data['text'][i].strip().lower()
        if text:
            words.append({
                'text': text,
                'x': data['left'][i], 'y': data['top'][i],
                'w': data['width'][i], 'h': data['height'][i],
            })
    return words


def find_word(words, target):
    """'click' ya 'go' wala word dhoondho (substring match)."""
    for w in words:
        if target in w['text']:
            return w
    return None


# ================= Cell detection (dividers se boxes) =================
def detect_cells(img):
    """Vertical dividers se cells nikalo. Returns list of (x1,y1,x2,y2)."""
    gray = np.array(img.convert('L'))
    H, W = gray.shape

    # 1) Horizontal borders se boxes ka vertical band
    row_dark = (gray < 100).mean(axis=1)
    h_rows = np.where(row_dark > 0.4)[0]
    if len(h_rows) >= 2:
        top, bottom = int(h_rows[0]), int(h_rows[-1])
    else:
        top, bottom = 0, H

    # 2) Band ke andar vertical dividers
    band = gray[top:bottom, :]
    col_dark = (band < 100).mean(axis=0)
    is_div = col_dark > 0.7

    dividers = []
    i = 0
    while i < W:
        if is_div[i]:
            j = i
            while j < W and is_div[j]:
                j += 1
            dividers.append((i + j - 1) / 2)
            i = j
        else:
            i += 1

    # 3) Cells banao
    bounds = [0] + dividers + [W]
    cells = []
    for k in range(len(bounds) - 1):
        bx1, bx2 = int(bounds[k]) + 3, int(bounds[k+1]) - 3
        if bx2 - bx1 > CONFIG["min_box_w"]:
            cells.append((bx1, top + 3, bx2, bottom - 3))
    return cells


def cell_contains(cell, word):
    """Cell me word ka center hai ya nahi."""
    cx = word['x'] + word['w'] / 2
    cy = word['y'] + word['h'] / 2
    return cell[0] <= cx <= cell[2] and cell[1] <= cy <= cell[3]


# ================= Shape extraction + matching =================
def shape_mask(crop_rgb, thresh=50):
    """Background color se distance = shape. (Pastel colors bhi pakdega.)"""
    flat = crop_rgb.reshape(-1, 3)
    bg = np.median(flat, axis=0)
    dist = np.sqrt(((crop_rgb - bg) ** 2).sum(axis=2))
    mask = (dist > thresh).astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 5)
    # sirf sabse bada component (dots/noise gayab)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if num <= 1:
        return None
    idx = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    if stats[idx, cv2.CC_STAT_AREA] < CONFIG["min_shape_area"]:
        return None  # khali box
    return np.where(labels == idx, 255, 0).astype(np.uint8)


def shape_sig(mask, size=64):
    """Mask se bbox crop + aspect-preserving resize signature."""
    coords = cv2.findNonZero(mask)
    if coords is None:
        return None
    x, y, w, h = cv2.boundingRect(coords)
    shape = mask[y:y+h, x:x+w]
    s = max(w, h)
    canvas = np.zeros((s, s), dtype=np.uint8)
    canvas[(s-h)//2:(s-h)//2+h, (s-w)//2:(s-w)//2+w] = shape
    return cv2.resize(canvas, (size, size), interpolation=cv2.INTER_AREA)


def iou(a, b):
    ab, bb = a > 128, b > 128
    inter = (ab & bb).sum()
    union = (ab | bb).sum()
    return float(inter / union) if union > 0 else 0.0


def extract_cell_sig(img_np, cell, mask_words=None):
    """Ek cell se shape signature nikalo. mask_words = Click/Go text mask karne ke liye."""
    x1, y1, x2, y2 = cell
    crop = img_np[y1:y2, x1:x2].copy()
    if mask_words:
        for w in mask_words:
            # word bbox ko background color se bhar do
            wx1 = max(0, w['x'] - x1)
            wy1 = max(0, w['y'] - y1)
            wx2 = min(crop.shape[1], w['x'] - x1 + w['w'])
            wy2 = min(crop.shape[0], w['y'] - y1 + w['h'])
            if wx2 > wx1 and wy2 > wy1:
                crop[wy1:wy2, wx1:wx2] = 240
    mask = shape_mask(crop)
    if mask is None:
        return None
    return shape_sig(mask)


# ================= Solve pipeline =================
def solve_frame(img):
    """
    Ek frame solve karo.
    Returns dict: {status, box_rect, score, scores, ...}
    status: 'go' (click ready), 'wait' (Go nahi), 'no_click', 'no_boxes', 'no_target'
    """
    img_np = np.array(img.convert('RGB')).astype(np.float32)
    words = ocr_words(img)
    click = find_word(words, 'click')
    go = find_word(words, 'go')

    if not click:
        return {'status': 'no_click'}

    cells = detect_cells(img)
    if not cells:
        return {'status': 'no_boxes'}

    # Cells classify karo: target (Click wala), Go wala, boxes (baaki)
    box_cells = []
    for cell in cells:
        if cell_contains(cell, click):
            continue  # target cell
        if go and cell_contains(cell, go):
            continue  # Go cell
        box_cells.append(cell)

    if not box_cells:
        return {'status': 'no_boxes'}

    # Target shape (Click cell se, Click text mask karke)
    target_cell = None
    for cell in cells:
        if cell_contains(cell, click):
            target_cell = cell
            break
    if target_cell is None:
        # Click kisi cell me nahi — Click ke aas-paas window se shape nikalo
        cx, cy = click['x'], click['y']
        target_cell = (max(0, cx - 60), max(0, cy - 10),
                       cx + click['w'] + 60, cy + click['h'] + 200)

    target_sig = extract_cell_sig(img_np, target_cell, mask_words=[click])
    if target_sig is None:
        return {'status': 'no_target'}

    # Har box se match
    scores = []
    for cell in box_cells:
        sig = extract_cell_sig(img_np, cell)
        scores.append(iou(target_sig, sig) if sig is not None else 0.0)

    best_idx = int(np.argmax(scores))
    best_score = scores[best_idx]

    result = {
        'status': 'go' if go else 'wait',
        'box_rect': box_cells[best_idx],
        'score': best_score,
        'scores': scores,
        'n_boxes': len(box_cells),
    }
    return result


def click_rect(rect):
    x1, y1, x2, y2 = rect
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    pyautogui.moveTo(cx, cy, duration=0.25)
    time.sleep(CONFIG["click_delay"])
    pyautogui.click()
    log(f"🖱️  CLICK! ({int(cx)}, {int(cy)})")


# ================= Region picker (manual mode) =================
def pick_point(label):
    """Mouse position live dikhate hue Enter par point lock karo."""
    print(f"\n{label}")
    print("   Mouse ko sahi jagah le jao... position live dikhegi, ready ho to ENTER dabao")
    stop = threading.Event()

    def show_pos():
        while not stop.is_set():
            x, y = pyautogui.position()
            sys.stdout.write(f"\r   📍 Position: ({x}, {y})          ")
            sys.stdout.flush()
            time.sleep(0.08)

    t = threading.Thread(target=show_pos, daemon=True)
    t.start()
    try:
        input()
    except KeyboardInterrupt:
        stop.set()
        print(f"\n{C.YELLOW}⏹ Cancel ho gaya.{C.RESET}")
        sys.exit(0)
    stop.set()
    t.join(timeout=0.3)
    x, y = pyautogui.position()
    print(f"\r   ✅ Locked: ({x}, {y})")
    return x, y


def pick_region_interactive():
    print(f"\n{C.CYAN}{C.BOLD}🖱️  Region select karo (CAPTCHA wali jagah){C.RESET}")
    x1, y1 = pick_point("👉 Step 1: Mouse ko CAPTCHA ke TOP-LEFT corner par le jao")
    x2, y2 = pick_point("👉 Step 2: Mouse ko BOTTOM-RIGHT corner par le jao")
    x, y = min(x1, x2), min(y1, y2)
    w, h = abs(x2 - x1), abs(y2 - y1)
    if w < 50 or h < 50:
        print(f"{C.RED}❌ Region bahut chhota hai (W={w}, H={h}). Dobara chalao.{C.RESET}")
        sys.exit(1)
    region = (x, y, w, h)
    with open(REGION_FILE, 'w') as f:
        f.write(f"{x},{y},{w},{h}")
    print(f"{C.GREEN}✅ Region save ho gaya: X={x} Y={y} W={w} H={h}{C.RESET}")
    return region


def load_saved_region():
    if os.path.exists(REGION_FILE):
        try:
            with open(REGION_FILE) as f:
                parts = [int(p) for p in f.read().strip().split(',')]
            if len(parts) == 4:
                return tuple(parts)
        except Exception:
            pass
    return None


def parse_region(s):
    try:
        parts = [int(p) for p in s.split(',')]
        if len(parts) != 4:
            raise ValueError
        return tuple(parts)
    except ValueError:
        print(f"{C.RED}❌ Galat region format! Sahi format: x,y,w,h  (jaise 100,200,900,300){C.RESET}")
        sys.exit(1)


# ================= Modes =================
def get_frame(region):
    """Full screen screenshot; region diya ho to crop. Returns (img, ox, oy)."""
    full = pyautogui.screenshot()
    if region:
        x, y, w, h = region
        return full.crop((x, y, x + w, y + h)), x, y
    return full, 0, 0


def run_once(region):
    """Ek baar solve karke (Go ho ya na ho) best box par click."""
    img, ox, oy = get_frame(region)
    r = solve_frame(img)
    if r['status'] == 'no_click':
        log(f"{C.RED}❌ 'Click' nahi mila — screen par CAPTCHA dikh raha hai?{C.RESET}")
        return
    if r['status'] in ('no_boxes', 'no_target'):
        log(f"{C.RED}❌ {r['status']} — boxes/target nahi mile{C.RESET}")
        return
    log(f"🔍 {r['n_boxes']} boxes mile. Scores: {[round(s, 2) for s in r['scores']]}")
    log(f"✅ Best match: Box {r['scores'].index(r['score']) + 1} (IoU={r['score']:.2f})")
    x1, y1, x2, y2 = r['box_rect']
    click_rect((x1 + ox, y1 + oy, x2 + ox, y2 + oy))
    log(f"{C.GREEN}✅ Done!{C.RESET}")


def run_auto(region, interval):
    """Auto monitor — 'Go' dikhte hi click. Ctrl+C se stop."""
    mode = "full-screen auto-detect" if region is None else f"region {region}"
    print(f"\n{C.BLUE}{C.BOLD}👀 Auto monitor ON ({mode}) — 'Go' ka intezaar...{C.RESET}")
    print(f"   Stop: Ctrl+C   ya   mouse screen corner par le jao\n")
    last_status = ''
    try:
        while True:
            img, ox, oy = get_frame(region)
            r = solve_frame(img)

            if r['status'] == 'no_click':
                if last_status != 'no_click':
                    log("👀 'Click' ka intezaar... (CAPTCHA screen par lao)")
                    last_status = 'no_click'
            elif r['status'] in ('no_boxes', 'no_target'):
                if last_status != r['status']:
                    log(f"⚠️ {r['status']} — layout check karo")
                    last_status = r['status']
            else:
                if last_status != 'found':
                    log(f"🔍 {r['n_boxes']} boxes mile. Best IoU={r['score']:.2f}")
                    last_status = 'found'
                if r['status'] == 'go':
                    log(f"{C.GREEN}🟢 'Go' dikha! Click karta hoon...{C.RESET}")
                    x1, y1, x2, y2 = r['box_rect']
                    click_rect((x1 + ox, y1 + oy, x2 + ox, y2 + oy))
                    log(f"{C.GREEN}✅ Done! (IoU={r['score']:.2f}){C.RESET}")
                    time.sleep(2)  # ek Go par ek hi click
                    last_status = ''

            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}⏹ Stop ho gaya. Bye!{C.RESET}")


# ================= Entry =================
def main():
    parser = argparse.ArgumentParser(
        description="🎯 Screen CAPTCHA Clicker — shape matching + auto-detect")
    parser.add_argument('--region', help='Region: x,y,w,h (jaise 100,200,900,300)')
    parser.add_argument('--manual', action='store_true',
                        help='Region select karke chalao (auto-detect fail ho to)')
    parser.add_argument('--once', action='store_true',
                        help='Ek baar find & click karke exit karo')
    parser.add_argument('--interval', type=float, default=CONFIG["scan_interval"],
                        help='Scan interval seconds (default 0.5)')
    parser.add_argument('--no-pause', action='store_true',
                        help='Band hone par Enter na puche (double-click ke liye pause default hai)')
    args = parser.parse_args()

    try:
        ensure_deps()        # packages auto-install (pehli baar)
        ensure_tesseract()   # Tesseract auto-download (Windows)

        print(f"\n{C.BOLD}🎯 Screen CAPTCHA Clicker (shape matching){C.RESET}")
        print("=" * 52)

        # --- Region decide karo ---
        region = None
        if args.region:
            region = parse_region(args.region)
            print(f"📌 Region (command line se): X={region[0]} Y={region[1]} W={region[2]} H={region[3]}")
        elif args.manual:
            saved = load_saved_region()
            if saved:
                print(f"📌 Saved region: X={saved[0]} Y={saved[1]} W={saved[2]} H={saved[3]}")
                print(f"   (naya select karna ho to region.txt delete karo)")
                region = saved
            else:
                region = pick_region_interactive()
        else:
            print(f"📌 Mode: Full-screen auto-detect (browser background me ho to bhi chalega)")
            print(f"   (manual region chahiye to --manual lagao)")

        # --- Run ---
        if args.once:
            run_once(region)
        else:
            run_auto(region, args.interval)

    finally:
        # Double-click se chalaya ho to window turant band na ho
        if not args.no_pause:
            try:
                input(f"\n{C.CYAN}Band karne ke liye ENTER dabao...{C.RESET}")
            except EOFError:
                pass


if __name__ == "__main__":
    main()
