#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 Screen CAPTCHA Clicker — SINGLE FILE version (sabse easy!)
================================================================
"Click" ke niche jo letter dikhe (jaise 'q'), use 3 boxes me find karke
jab "Go" aaye to us letter par auto-click karta hai.

⭐ Ye file khud sab setup kar leti hai — kuch download/install nahi karna padta:
   - Python packages (pyautogui, pillow, pytesseract) pehli baar auto-install
   - Tesseract OCR (Windows) na mile to auto-download + install

Kaise chalao:
   1. Is file par DOUBLE-CLICK karo  (ya CMD me:  python clicker.py)
   2. Mouse ko CAPTCHA ke top-left corner par le jao → ENTER dabao
   3. Mouse ko bottom-right corner par le jao → ENTER dabao
   4. Bas! "Go" aate hi sahi box par click ho jayega 🖱️

Stop:  Ctrl+C   ya   mouse screen corner par le jao (emergency stop)

Options (CMD se):
   python clicker.py --once                 # ek baar find & click karke exit
   python clicker.py --pick                 # naya region select karo
   python clicker.py --region 100,200,460,300
   python clicker.py --no-pause             # band hone par Enter na puche
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
    "top_frac": 0.38,       # region ka top hissa  = "Click" + target letter area
    "bottom_frac": 0.78,    # iske niche ka hissa  = "Go" button area
    "scan_interval": 0.6,   # seconds me scan gap
    "click_delay": 0.3,     # click se pehle rukna
    "ocr_scale": 2,         # OCR se pehle image bada karo
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGION_FILE = os.path.join(SCRIPT_DIR, 'region.txt')

# Dependencies (main() me load hote hain — --help bina packages ke bhi kaam kare)
pyautogui = None
Image = ImageOps = pytesseract = None


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
    return _pg, _Img, _Ops, _pt


def ensure_deps():
    """Packages na mile to khud pip se install kar do."""
    global pyautogui, Image, ImageOps, pytesseract
    try:
        pyautogui, Image, ImageOps, pytesseract = _import_deps()
    except ImportError:
        missing = []
        for mod, pkg in [('pyautogui', 'pyautogui'),
                         ('PIL', 'pillow'),
                         ('pytesseract', 'pytesseract')]:
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
        pyautogui, Image, ImageOps, pytesseract = _import_deps()
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
    # 1) winget try karo
    if shutil.which('winget'):
        print("   winget se Tesseract install kar raha hoon...")
        subprocess.run(['winget', 'install', '--id', 'UB-Mannheim.TesseractOCR', '-e',
                        '--accept-source-agreements', '--accept-package-agreements'],
                       capture_output=True)
        p = find_tesseract()
        if p:
            return p
    # 2) GitHub se installer download karo
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


# ================= OCR helpers =================
def preprocess(img):
    """Grayscale + bada + contrast — OCR accuracy badhane ke liye."""
    img = img.convert('L')
    img = img.resize((img.width * CONFIG["ocr_scale"],
                      img.height * CONFIG["ocr_scale"]), Image.LANCZOS)
    return ImageOps.autocontrast(img)


def ocr_single_char(img):
    """Ek akshar padho (target letter / box letter)."""
    cfg = ('--psm 10 -c tessedit_char_whitelist='
           'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
    text = pytesseract.image_to_string(img, config=cfg).strip()
    return text[:1] if text else ''


def ocr_has_go(img):
    """Bottom area me 'Go' likha hai ya nahi."""
    text = pytesseract.image_to_string(img, config='--psm 6').strip().lower()
    return 'go' in text


def read_target(img):
    w, h = img.size
    top = img.crop((0, 0, w, int(h * CONFIG["top_frac"])))
    return ocr_single_char(preprocess(top))


def has_go(img):
    w, h = img.size
    bottom = img.crop((0, int(h * CONFIG["bottom_frac"]), w, h))
    return ocr_has_go(preprocess(bottom))


def find_box(img, target):
    """3 boxes me target letter kis box me hai — index (0/1/2) ya -1."""
    w, h = img.size
    boxes = img.crop((0, int(h * CONFIG["top_frac"]),
                      w, int(h * CONFIG["bottom_frac"])))
    bw = w // 3
    for i in range(3):
        box_img = boxes.crop((i * bw, 0, (i + 1) * bw, boxes.height))
        ch = ocr_single_char(preprocess(box_img))
        if ch and ch.lower() == target.lower():
            return i
    return -1


def click_box(region, idx):
    x, y, w, h = region
    boxes_top = y + h * CONFIG["top_frac"]
    boxes_bottom = y + h * CONFIG["bottom_frac"]
    bw = w / 3
    cx = x + bw * idx + bw / 2
    cy = (boxes_top + boxes_bottom) / 2
    pyautogui.moveTo(cx, cy, duration=0.25)
    time.sleep(CONFIG["click_delay"])
    pyautogui.click()
    log(f"🖱️  CLICK! Box {idx + 1} par ({int(cx)}, {int(cy)})")


# ================= Region selection =================
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
    print(f"   (agle run me yehi use hoga — naya chahiye to --pick lagao)")
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
        print(f"{C.RED}❌ Galat region format! Sahi format: x,y,w,h  (jaise 100,200,460,300){C.RESET}")
        sys.exit(1)


# ================= Modes =================
def run_once(region):
    """Ek baar find & click karke exit."""
    log("🔍 Ek baar scan kar raha hoon...")
    img = pyautogui.screenshot(region=region)
    target = read_target(img)
    if not target:
        log(f"{C.RED}❌ Target letter nahi padh paya — region check karo{C.RESET}")
        return
    log(f"🔤 Target letter: '{target}'")
    idx = find_box(img, target)
    if idx == -1:
        log(f"{C.RED}❌ '{target}' kisi box me nahi mila{C.RESET}")
        return
    log(f"{C.GREEN}✅ '{target}' Box {idx + 1} me mila!{C.RESET}")
    click_box(region, idx)
    log(f"{C.GREEN}✅ Done!{C.RESET}")


def run_auto(region, interval):
    """Auto monitor — 'Go' dikhte hi click. Ctrl+C se stop."""
    print(f"\n{C.BLUE}{C.BOLD}👀 Auto monitor ON — 'Go' ka intezaar...{C.RESET}")
    print(f"   Stop karne ke liye: Ctrl+C   ya   mouse screen corner par le jao\n")
    last_target = ''
    try:
        while True:
            img = pyautogui.screenshot(region=region)

            target = read_target(img)
            if target and target != last_target:
                last_target = target
                log(f"🔤 Target letter: '{target}'")

            if target and has_go(img):
                log(f"{C.GREEN}🟢 'Go' dikha! Letter find karke click karta hoon...{C.RESET}")
                idx = find_box(img, target)
                if idx != -1:
                    click_box(region, idx)
                    log(f"{C.GREEN}✅ Done — '{target}' Box {idx + 1} par click ho gaya!{C.RESET}")
                else:
                    log(f"{C.RED}❌ '{target}' boxes me nahi mila{C.RESET}")
                time.sleep(2)   # ek Go par ek hi click

            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}⏹ Stop ho gaya. Bye!{C.RESET}")


# ================= Entry =================
def main():
    parser = argparse.ArgumentParser(
        description="🎯 Screen CAPTCHA Clicker — single file, auto-setup")
    parser.add_argument('--region', help='Region: x,y,w,h (jaise 100,200,460,300)')
    parser.add_argument('--pick', action='store_true',
                        help='Saved region ignore karke naya select karo')
    parser.add_argument('--once', action='store_true',
                        help='Ek baar find & click karke exit karo')
    parser.add_argument('--interval', type=float, default=CONFIG["scan_interval"],
                        help='Scan interval seconds (default 0.6)')
    parser.add_argument('--no-pause', action='store_true',
                        help='Band hone par Enter na puche (double-click ke liye pause default hai)')
    args = parser.parse_args()

    try:
        ensure_deps()        # packages auto-install (pehli baar)
        ensure_tesseract()   # Tesseract auto-download (Windows)

        print(f"\n{C.BOLD}🎯 Screen CAPTCHA Clicker{C.RESET}")
        print("=" * 48)

        # --- Region decide karo ---
        if args.region:
            region = parse_region(args.region)
            print(f"📌 Region (command line se): X={region[0]} Y={region[1]} W={region[2]} H={region[3]}")
        elif args.pick:
            region = pick_region_interactive()
        else:
            saved = load_saved_region()
            if saved:
                print(f"📌 Saved region use ho raha hai: X={saved[0]} Y={saved[1]} W={saved[2]} H={saved[3]}")
                print(f"   (naya select karna ho to --pick lagao)")
                region = saved
            else:
                region = pick_region_interactive()

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
