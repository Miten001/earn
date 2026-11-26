# 🎯 Click & Find — CAPTCHA Letter Clicker

"Click" ke niche jo letter dikhe (jaise `q`), use 3 boxes me find karke jab **"Go"** aaye to us letter par **auto-click** karta hai.

## 📁 Files

| File | Kya hai |
|---|---|
| `clicker.bat` | **DOUBLE-CLICK KARO, BAS!** Python bhi auto-install kar deta hai ⭐⭐⭐ |
| `clicker.py` | **Shape matching + auto-detect** — shapes/letters dono solve, browser background me bhi ⭐⭐ |
| `index.html` | Web GUI demo (browser me chalao — practice ke liye) |
| `cli_solver.py` | CMD-only version (letter OCR wala purana) |
| `captcha_solver.py` | GUI version (letter OCR wala purana) |
| `requirements.txt` | Python packages (clicker.py ko iski zaroorat nahi — khud install kar leta hai) |

---

## 🌐 Web GUI (practice/demo)

```bash
python3 -m http.server 8000
# browser me kholo: http://localhost:8000
```

- "Click" + target letter dikhta hai, 3 boxes me shapes hain
- **Go** dabao → animated cursor letter find karke click karta hai
- **New Round** / **Auto Find** buttons bhi hain

---

## ⭐⭐⭐ DOUBLE-CLICK Version (`clicker.bat`) — sabse easy!

**Sirf `clicker.bat` file download karo aur double-click karo — bas!**

Double-click karne par ye file khud sab kar legi:
1. 🐍 **Python check** — agar nahi hai to **auto-download + silent install** (python.org se)
2. 📄 `clicker.py` na mile to **GitHub se auto-download**
3. 📦 Packages (pyautogui, pillow, pytesseract) **auto-install**
4. 🔤 Tesseract OCR **auto-download + install** (Windows)
5. 🖱️ Region select karo (top-left → Enter, bottom-right → Enter)
6. ✅ "Go" aate hi sahi box par click!

**Kuch bhi install/download karne ki zaroorat nahi — sirf double-click!**

> Note: Pehli baar internet chahiye (Python + packages download honge). Uske baad offline bhi chalega.

---

## ⭐⭐ SINGLE FILE Version (`clicker.py`) — Shape Matching + Auto-Detect

**Naya version — letter OCR ki jagah SHAPE MATCHING (OpenCV):**
- 🎨 **Shapes bhi solve** honge (zigzag, spiral, triangle...), sirf letters nahi
- 🧭 **Layout auto-detect** — "Click" left/right/top kahin bhi ho, chalega
- 📦 **3, 4, 5... kitne bhi boxes** hon, sab handle honge (dividers se count hota hai)
- 🌐 **Browser background me ho to bhi** — poori screen scan karke CAPTCHA khud dhoondhta hai
- 📦 Python packages (pyautogui, pillow, pytesseract, **opencv-python**, numpy) pehli baar **auto-install**
- 🔤 Tesseract OCR (Windows) na mile to **auto-download + silent install**

### Use

**Option A — Double-click karo (auto-detect mode):**
1. `clicker.py` file par **double-click** karo (Python installed hona chahiye)
2. Tool poori screen scan karke CAPTCHA khud dhoondhega — kuch select nahi karna!
3. ✅ "Go" aate hi sahi box par click ho jayega. Band karne ke liye `Ctrl+C` ya mouse screen corner par

**Option B — CMD se:**
```bash
python clicker.py                 # auto-detect (full screen)
python clicker.py --once          # ek baar find & click karke exit
python clicker.py --manual        # region select karke chalao (auto-detect fail ho to)
python clicker.py --region 100,200,900,300
```

**Kaise kaam karta hai:**
```
Screen scan → OCR ("Click"/"Go" dhoondho) → dividers se boxes gino
→ target shape nikalo → har box se IoU match → "Go" aate hi CLICK 🖱️
```

---

## ⌨️ CMD-Only Version (`cli_solver.py`)

Koi GUI window nahi — sirf CMD/terminal me chalta hai. Sab output terminal me print hota hai.

### Setup (ek baar)

```bash
pip install -r requirements.txt
# + Tesseract OCR install karo (upar wala link)
```

### Use

```bash
# Pehli baar — region select karega (mouse se, terminal me hi)
python cli_solver.py
```

1. Mouse ko CAPTCHA ke **top-left corner** par le jao → **Enter** dabao (position live dikhegi)
2. Mouse ko **bottom-right corner** par le jao → **Enter** dabao
3. Region `region.txt` me **save** ho jayega — agle run me dobara select nahi karna padega
4. Auto monitor ON ho jayega — "Go" aate hi click 🖱️, sab terminal me print hoga:
   ```
   [10:30:01] 🔤 Target letter: 'q'
   [10:30:05] 🟢 'Go' dikha! Letter find karke click karta hoon...
   [10:30:05] 🖱️  CLICK! Box 2 par (350, 280)
   [10:30:05] ✅ Done — 'q' Box 2 par click ho gaya!
   ```

### Commands

| Command | Kya karega |
|---|---|
| `python cli_solver.py` | Saved region use karke auto monitor start |
| `python cli_solver.py --pick` | Naya region select karo (saved ignore karke) |
| `python cli_solver.py --region 100,200,460,300` | Region seedha command line se do |
| `python cli_solver.py --once` | Ek baar find & click karke exit |
| `python cli_solver.py --interval 0.3` | Scan interval badlo (seconds) |
| `python cli_solver.py --help` | Saare options dikhao |

**Stop:** `Ctrl+C` dabao, ya mouse ko screen corner par le jao (emergency stop).

---

## 🖥️ GUI Version (`captcha_solver.py`)

Screen par asli CAPTCHA ke saath chalta hai — OCR se letter padhta hai aur mouse click karta hai.

### Setup

1. **Python packages:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Tesseract OCR install karo** (letter padhne ke liye zaroori hai):
   - **Windows:** https://github.com/UB-Mannheim/tesseract/wiki — installer download karke install karo. Agar `C:\Program Files\Tesseract-OCR\tesseract.exe` par nahi hai to `captcha_solver.py` me `pytesseract.pytesseract.tesseract_cmd` set karo.
   - **Mac:** `brew install tesseract`
   - **Linux:** `sudo apt install tesseract-ocr`

### Use

```bash
python captcha_solver.py
```

1. **Step 1** — "Screen par Drag karke Select karo" dabao → screen par CAPTCHA wali jagah par drag karke box banao
2. **Step 2** — "▶ Start Auto" dabao → tool har 0.6 sec me screen scan karega:
   - "Click" ke niche wala **target letter** OCR se padhega
   - 3 boxes me wahi letter dhoondhega
   - **"Go"** dikhte hi sahi box par **mouse click** kar dega
3. **"🔍 Find & Click Now"** — ek baar manually find & click karega (Go ka intezaar nahi karega)

### ⚠️ Safety

- **Emergency stop:** mouse ko screen ke **corner** par le jao → turant ruk jayega (pyautogui FAILSAFE)
- Pehli baar **"Find & Click Now"** se test karo, phir Auto mode use karo
- Region sahi select karo — top me "Click + letter", beech me 3 boxes, niche "Go" hona chahiye

### ⚙️ Tuning (agar letter galat padhe)

`captcha_solver.py` ke top par `CONFIG` hai:
- `top_frac` / `bottom_frac` — agar boxes/Go ka area galat cut ho raha hai to adjust karo
- `ocr_scale` — badhao (3) agar chhota letter hai
- `scan_interval` — scan kitni jaldi ho

---

## 🔄 Kaam kaise karta hai

**Naya (clicker.py — shape matching):**
```
Screen scan → OCR ("Click"/"Go" dhoondho) → dividers se boxes gino (3/4/5...)
→ target shape nikalo → har box se IoU match → "Go" dikha? → CLICK 🖱️
```

**Purana (cli_solver.py / captcha_solver.py — letter OCR):**
```
Screen capture → OCR (target letter) → OCR (boxes) → match? → "Go" dikha? → CLICK 🖱️
```
