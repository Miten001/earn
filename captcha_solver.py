#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 Screen CAPTCHA Clicker
==========================
"Click" ke niche jo letter dikhe (jaise 'q'), use 3 boxes me find karke
jab "Go" aaye to us letter par auto-click karta hai.

Kaise kaam karta hai:
  1. Screen par CAPTCHA wali jagah select karo (drag karke)
  2. OCR se target letter padhta hai (Click ke niche wala)
  3. 3 boxes me wahi letter dhoondhta hai
  4. "Go" dikhte hi sahi box par mouse click kar deta hai

Setup:
    pip install -r requirements.txt
    + Tesseract OCR install karo: https://github.com/UB-Mannheim/tesseract/wiki

Run:
    python captcha_solver.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import sys

# ---------------- Dependencies check ----------------
try:
    import pyautogui
    from PIL import Image, ImageOps
    import pytesseract
except ImportError:
    print("❌ Missing packages! Pehle ye run karo:")
    print("   pip install -r requirements.txt")
    sys.exit(1)

pyautogui.FAILSAFE = True   # mouse ko screen corner par le jao = emergency stop
pyautogui.PAUSE = 0.05

# ---------------- Config ----------------
CONFIG = {
    "top_frac": 0.38,       # region ka top hissa  = "Click" + target letter area
    "bottom_frac": 0.78,    # iske niche ka hissa  = "Go" button area
    "scan_interval": 0.6,   # seconds me scan gap
    "click_delay": 0.3,     # click se pehle rukna
    "ocr_scale": 2,         # OCR se pehle image bada karo (accuracy ke liye)
}


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


def find_letter_box(boxes_img, target):
    """3 boxes me target letter kis box me hai — index (0/1/2) ya -1."""
    w, h = boxes_img.size
    bw = w // 3
    for i in range(3):
        box_img = boxes_img.crop((i * bw, 0, (i + 1) * bw, h))
        ch = ocr_single_char(preprocess(box_img))
        if ch and ch.lower() == target.lower():
            return i
    return -1


# ================= Region Selector =================
class RegionSelector:
    """Fullscreen overlay — drag karke CAPTCHA area select karo."""

    def __init__(self, callback):
        self.callback = callback
        self.start = None
        self.rect = None

        self.root = tk.Toplevel()
        self.root.title("Region select karo — drag karo, ESC = cancel")
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.35)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='black')

        self.canvas = tk.Canvas(self.root, bg='black', cursor='crosshair',
                                highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        self.canvas.bind('<ButtonPress-1>', self._press)
        self.canvas.bind('<B1-Motion>', self._drag)
        self.canvas.bind('<ButtonRelease-1>', self._release)
        self.root.bind('<Escape>', lambda e: self.root.destroy())

        # hint text
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2, 40,
            text="👆 CAPTCHA wali jagah par drag karke box banao  (ESC = cancel)",
            fill='yellow', font=('Arial', 18, 'bold'))

    def _press(self, e):
        self.start = (e.x, e.y)
        if self.rect:
            self.canvas.delete(self.rect)

    def _drag(self, e):
        if not self.start:
            return
        if self.rect:
            self.canvas.delete(self.rect)
        x1, y1 = self.start
        self.rect = self.canvas.create_rectangle(
            x1, y1, e.x, e.y, outline='lime', width=3)

    def _release(self, e):
        if not self.start:
            return
        x1, y1 = self.start
        x, y = min(x1, e.x), min(y1, e.y)
        w, h = abs(e.x - x1), abs(e.y - y1)
        self.root.destroy()
        if w > 50 and h > 50:
            self.callback((x, y, w, h))


# ================= Main App =================
class ClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎯 Screen CAPTCHA Clicker")
        self.root.geometry("520x640")
        self.root.resizable(False, False)

        self.region = None          # (x, y, w, h)
        self.monitoring = False
        self.thread = None
        self.last_target = ''
        self._preview_img = None

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        pad = {'padx': 10, 'pady': 6}

        title = ttk.Label(self.root, text="🎯 Screen CAPTCHA Clicker",
                          font=('Arial', 16, 'bold'))
        title.pack(pady=(12, 2))

        sub = ttk.Label(self.root, text='"Click" ke niche wala letter 3 boxes me find karke click karega',
                        font=('Arial', 9), foreground='gray')
        sub.pack(pady=(0, 8))

        # --- Step 1: Region ---
        f1 = ttk.LabelFrame(self.root, text="Step 1 — CAPTCHA area select karo", **pad)
        f1.pack(fill='x', **pad)
        ttk.Button(f1, text="🖱️  Screen par Drag karke Select karo",
                   command=self.select_region).pack(fill='x', pady=4)
        self.region_lbl = ttk.Label(f1, text="Region: abhi select nahi hua", foreground='red')
        self.region_lbl.pack()

        # --- Step 2: Controls ---
        f2 = ttk.LabelFrame(self.root, text="Step 2 — Control", **pad)
        f2.pack(fill='x', **pad)
        btn_row = ttk.Frame(f2)
        btn_row.pack(fill='x', pady=4)
        self.start_btn = ttk.Button(btn_row, text="▶ Start Auto (Go aate hi click)",
                                    command=self.start_monitor)
        self.start_btn.pack(side='left', padx=4)
        self.stop_btn = ttk.Button(btn_row, text="⏹ Stop", command=self.stop_monitor,
                                   state='disabled')
        self.stop_btn.pack(side='left', padx=4)
        ttk.Button(btn_row, text="🔍 Find & Click Now",
                   command=lambda: threading.Thread(target=self.find_and_click_once,
                                                    daemon=True).start()
                   ).pack(side='left', padx=4)

        # --- Status ---
        f3 = ttk.LabelFrame(self.root, text="Status", **pad)
        f3.pack(fill='x', **pad)
        self.target_lbl = ttk.Label(f3, text="Target letter: —", font=('Arial', 13, 'bold'))
        self.target_lbl.pack()
        self.state_lbl = ttk.Label(f3, text="Idle", font=('Arial', 11))
        self.state_lbl.pack()

        # --- Preview ---
        f4 = ttk.LabelFrame(self.root, text="Live Preview (selected region)", **pad)
        f4.pack(fill='both', expand=True, **pad)
        self.preview = tk.Canvas(f4, bg='#222', height=170)
        self.preview.pack(fill='both', expand=True)

        # --- Log ---
        f5 = ttk.LabelFrame(self.root, text="Log", **pad)
        f5.pack(fill='both', expand=True, **pad)
        self.log_box = tk.Text(f5, height=6, state='disabled', font=('Consolas', 9))
        self.log_box.pack(fill='both', expand=True)

        # --- Safety note ---
        ttk.Label(self.root,
                  text="⚠️ Emergency stop: mouse ko screen ke corner par le jao",
                  foreground='red', font=('Arial', 9, 'bold')).pack(pady=4)

    # ---------- Helpers ----------
    def log(self, msg):
        self.log_box.configure(state='normal')
        self.log_box.insert('end', f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def set_state(self, text, color='black'):
        self.state_lbl.configure(text=text, foreground=color)

    def select_region(self):
        self.log("Region select karne ke liye screen par drag karo...")
        RegionSelector(self._on_region_selected)

    def _on_region_selected(self, region):
        self.region = region
        x, y, w, h = region
        self.region_lbl.configure(text=f"Region: X={x} Y={y} W={w} H={h}",
                                  foreground='green')
        self.log(f"✅ Region set: X={x} Y={y} W={w} H={h}")

    # ---------- Screenshot + OCR ----------
    def capture(self):
        return pyautogui.screenshot(region=self.region)

    def read_target(self, img):
        w, h = img.size
        top = img.crop((0, 0, w, int(h * CONFIG["top_frac"])))
        return ocr_single_char(preprocess(top))

    def has_go(self, img):
        w, h = img.size
        bottom = img.crop((0, int(h * CONFIG["bottom_frac"]), w, h))
        return ocr_has_go(preprocess(bottom))

    def find_box(self, img, target):
        w, h = img.size
        boxes = img.crop((0, int(h * CONFIG["top_frac"]),
                          w, int(h * CONFIG["bottom_frac"])))
        return find_letter_box(boxes, target)

    def click_box(self, idx):
        x, y, w, h = self.region
        boxes_top = y + h * CONFIG["top_frac"]
        boxes_bottom = y + h * CONFIG["bottom_frac"]
        bw = w / 3
        cx = x + bw * idx + bw / 2
        cy = (boxes_top + boxes_bottom) / 2
        pyautogui.moveTo(cx, cy, duration=0.25)
        time.sleep(CONFIG["click_delay"])
        pyautogui.click()
        self.log(f"🖱️ Box {idx + 1} par click! ({int(cx)}, {int(cy)})")

    def update_preview(self, img):
        """Preview canvas me screenshot dikhao."""
        try:
            small = img.copy()
            small.thumbnail((480, 160))
            self._preview_img = tk.PhotoImage(
                image=small) if hasattr(tk, 'PhotoImage') else None
            # PIL -> tkinter: use ImageTk
            from PIL import ImageTk
            self._preview_img = ImageTk.PhotoImage(small)
            self.preview.delete('all')
            self.preview.create_image(0, 0, anchor='nw', image=self._preview_img)
        except Exception:
            pass

    # ---------- Find & Click (ek baar) ----------
    def find_and_click_once(self):
        if not self.region:
            self.log("❌ Pehle region select karo!")
            return
        try:
            img = self.capture()
            self.update_preview(img)

            target = self.read_target(img)
            if not target:
                self.log("❌ Target letter nahi padh paya — region check karo")
                self.set_state("Target letter nahi mila", 'red')
                return
            self.last_target = target
            self.target_lbl.configure(text=f"Target letter: {target}")
            self.log(f"🔤 Target letter: '{target}'")

            idx = self.find_box(img, target)
            if idx == -1:
                self.log(f"❌ '{target}' kisi box me nahi mila")
                self.set_state(f"'{target}' boxes me nahi mila", 'red')
                return

            self.set_state(f"✅ '{target}' Box {idx + 1} me mila — click kar raha hoon...",
                           'green')
            self.click_box(idx)
            self.set_state(f"✅ Click ho gaya! ('{target}' Box {idx + 1})", 'green')
        except Exception as e:
            self.log(f"❌ Error: {e}")
            self.set_state(f"Error: {e}", 'red')

    # ---------- Auto monitor (Go aate hi click) ----------
    def start_monitor(self):
        if not self.region:
            messagebox.showwarning("Region nahi hai",
                                   "Pehle Step 1 me CAPTCHA area select karo!")
            return
        self.monitoring = True
        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.set_state("👀 Monitor ON — 'Go' ka intezaar...", 'blue')
        self.log("▶ Auto monitor start — 'Go' dikhte hi click karega")
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop_monitor(self):
        self.monitoring = False
        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.set_state("⏹ Stopped", 'black')
        self.log("⏹ Monitor stop")

    def _monitor_loop(self):
        while self.monitoring:
            try:
                img = self.capture()
                self.update_preview(img)

                target = self.read_target(img)
                if target:
                    if target != self.last_target:
                        self.last_target = target
                        self.target_lbl.configure(text=f"Target letter: {target}")
                        self.log(f"🔤 Naya target: '{target}'")

                if target and self.has_go(img):
                    self.log("🟢 'Go' dikha! Letter find karke click karta hoon...")
                    idx = self.find_box(img, target)
                    if idx != -1:
                        self.click_box(idx)
                        self.set_state(f"✅ Go! '{target}' Box {idx + 1} par click ho gaya",
                                       'green')
                        self.log(f"✅ Done — '{target}' Box {idx + 1}")
                    else:
                        self.log(f"❌ '{target}' boxes me nahi mila")
                    # ek Go par ek hi click — thoda ruk jao
                    time.sleep(2)
            except Exception as e:
                self.log(f"❌ Error: {e}")
            time.sleep(CONFIG["scan_interval"])


# ================= Entry =================
if __name__ == "__main__":
    root = tk.Tk()
    app = ClickerApp(root)
    root.mainloop()
