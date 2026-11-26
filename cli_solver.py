#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 Screen CAPTCHA Clicker — CMD Version (koi GUI nahi, sirf terminal)
======================================================================
"Click" ke niche jo letter dikhe (jaise 'q'), use 3 boxes me find karke
jab "Go" aaye to us letter par auto-click karta hai.

Setup (ek baar):
    pip install -r requirements.txt
    + Tesseract OCR install karo: https://github.com/UB-Mannheim/tesseract/wiki

Use:
    python cli_solver.py                      # interactive — region puchega
    python cli_solver.py --region 100,200,460,300   # seedha region do
    python cli_solver.py --once               # ek baar find & click karke exit
    python cli_solver.py --pick               # saved region ignore karke naya select karo

Stop:  Ctrl+C   ya   mouse ko screen corner par le jao (emergency stop)
"""

import argparse
import os
import sys
import threading
import time

# Windows CMD par ANSI colors enable karo
if os.name == 'nt':
    os.system('')

# ---------------- Dependencies check ----------------
# (main() me check hota hai taaki --help bina packages ke bhi kaam kare)
pyautogui = None
Image = ImageOps = pytesseract = None


def check_deps():
    global pyautogui, Image, ImageOps, pytesseract
    try:
        import pyautogui as _pg
        from PIL import Image as _Img, ImageOps as _Ops
        import pytesseract as _pt
    except ImportError:
        print("❌ Missing packages! Pehle ye run karo:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    pyautogui, Image, ImageOps, pytesseract = _pg, _Img, _Ops, _pt
    pyautogui.FAILSAFE = True   # mouse corner par = emergency stop
    pyautogui.PAUSE = 0.05

# ---------------- Config ----------------
CONFIG = {
    "top_frac": 0.38,       # region ka top hissa  = "Click" + target letter area
    "bottom_frac": 0.78,    # iske niche ka hissa  = "Go" button area
    "scan_interval": 0.6,   # seconds me scan gap
    "click_delay": 0.3,     # click se pehle rukna
    "ocr_scale": 2,         # OCR se pehle image bada karo
}

REGION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'region.txt')


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


# ================= Region selection (CMD only) =================
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
        print(f"\n{C.YELLOW}⏹ Cancel ho gaya. Bye!{C.RESET}")
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
        print(f"{C.RED}❌ Region bahut chhota hai (W={w}, H={h}). Dobara try karo.{C.RESET}")
        sys.exit(1)
    region = (x, y, w, h)
    # save kar do taaki agle run me dobara na select karna pade
    with open(REGION_FILE, 'w') as f:
        f.write(f"{x},{y},{w},{h}")
    print(f"{C.GREEN}✅ Region save ho gaya: X={x} Y={y} W={w} H={h}{C.RESET}")
    print(f"   (agle run me yehi use hoga — naya chahiye to --pick flag lagao)")
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
        description="🎯 Screen CAPTCHA Clicker — CMD version (no GUI)")
    parser.add_argument('--region', help='Region: x,y,w,h (jaise 100,200,460,300)')
    parser.add_argument('--pick', action='store_true',
                        help='Saved region ignore karke naya select karo')
    parser.add_argument('--once', action='store_true',
                        help='Ek baar find & click karke exit karo')
    parser.add_argument('--interval', type=float, default=CONFIG["scan_interval"],
                        help='Scan interval seconds (default 0.6)')
    args = parser.parse_args()

    check_deps()   # packages check (help ke baad, taaki --help hamesha kaam kare)

    print(f"{C.BOLD}🎯 Screen CAPTCHA Clicker (CMD version){C.RESET}")
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

    # --- Tesseract check (pehla OCR try) ---
    try:
        pytesseract.get_tesseract_version()
    except Exception:
        print(f"\n{C.RED}❌ Tesseract OCR nahi mila!{C.RESET}")
        print("   Install karo: https://github.com/UB-Mannheim/tesseract/wiki")
        print("   (Windows par install ke baad PATH me add karna ya tesseract_cmd set karna padega)")
        sys.exit(1)

    # --- Run ---
    if args.once:
        run_once(region)
    else:
        run_auto(region, args.interval)


if __name__ == "__main__":
    main()
