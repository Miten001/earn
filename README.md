# 🎯 Click & Find — CAPTCHA Letter Clicker

"Click" ke niche jo letter dikhe (jaise `q`), use 3 boxes me find karke jab **"Go"** aaye to us letter par **auto-click** karta hai.

## 📁 Files

| File | Kya hai |
|---|---|
| `clicker.bat` | **DOUBLE-CLICK KARO, BAS!** Python auto-install (winget), args passthrough, `launcher_log.txt` ⭐⭐⭐ |
| `clicker.py` | **v2** — graph-paper cells + rotation-tolerant shape matching + DPI fix (`--debug`, `--dry-run`) ⭐⭐ |
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
3. 📦 Packages (pyautogui, pillow, pytesseract, opencv, numpy) **auto-install**
4. 🔤 Tesseract OCR **auto-download + install** (Windows)
5. 🔍 CAPTCHA khud dhoondhega (full screen scan — kuch select nahi karna)
6. ✅ "Go" dikhte hi sahi box par click!

**Kuch bhi install/download karne ki zaroorat nahi — sirf double-click!**

> Note: Pehli baar internet chahiye (Python + packages download honge). Uske baad offline bhi chalega.

---

## ⭐⭐ SINGLE FILE Version (`clicker.py`) — v2 (Surf Bash ke liye)

Asli **Surf Bash** CAPTCHA ke liye banaya gaya hai jisme boxes **graph paper** hote hain
aur shapes **patli colored lines** (blue/green/red) se bante hain.

**Kya khaas hai:**
- 🎨 **Grid lines ignore** — sirf colored strokes pakadta hai (grid grayscale hota hai)
- 🧹 **Dots/dashes noise ignore** — morphology se sirf bold shape bachta hai
- 🔄 **Rotation tolerant** — target shape box me ghumaya hua ho to bhi match ho jata hai
- 🌗 **Adaptive borders** — Otsu + 6 thresholds (light/antialiased borders, chhota zoom — sab par kaam)
- 🎯 **Smart auto-detect** — page par jitne bhi "Click" words hain (ads me bhi), sab check karke
  wahi chunta hai jiske paas **asli strip + "Go"** hai — `--manual` ki zaroorat nahi
- ⚡ **Fast** — ek baar locate, phir ~15 ms/frame (Go blue-blob se, OCR nahi);
  `layout_cache.json` se agli baar **instant start**
- 🧭 **Layout auto-detect** — "Click" cell, boxes aur "Go" khud pehchanta hai
- 🔢 **3, 4, 5... boxes** — dividers se count hota hai
- 🌐 **Browser background me bhi** — poori screen scan karta hai, window focus ki zaroorat nahi
- 🖥️ **DPI-aware mode** — process ko per-monitor DPI-aware banata hai, isliye screenshot aur
  click dono **physical pixels** me hote hain → 125%/150% scaling par bhi click bilkul sahi jagah
- ⚡ **Fast tracking** — CAPTCHA ek baar milne par har frame me sirf chhota hissa check hota hai (~10 ms)

### Use

**Option A — Double-click karo:**
1. `clicker.py` (ya `clicker.bat`) par **double-click**
2. Tool screen scan karke CAPTCHA khud dhoondhega — kuch select nahi karna
3. ✅ "Go" dikhte hi sahi box par click. Stop: `Ctrl+C` ya mouse screen corner par

**Option B — CMD se:**
```bash
python clicker.py                  # auto-detect (full screen)
python clicker.py --once           # ek baar solve karke exit
python clicker.py --dry-run        # sirf batao kaunsa box, click NA karo
python clicker.py --debug          # debug/ folder me image save karo
python clicker.py --manual         # region select karo (auto-detect fail ho to)
python clicker.py --region 100,200,700,130
python clicker.py --click-test     # clicks kaam karte hain? (safe test)
python clicker.py --calibrate      # screenshot/click mapping check (kuch click nahi)
python clicker.py --no-wait-go     # 'Go' ka intezaar nahi, seedha click
python clicker.py --go-timeout 3   # 3s me Go na mile to phir bhi click
python clicker.py --clicks 2       # double-click kare
```

### 🩺 Pehle `--selftest` chalao (environment check)

Kuch bhi samajh na aaye to:
```cmd
clicker.bat --selftest
```
Ye batata hai: Python version, kaunse packages missing hain, Tesseract mila ya nahi,
screen ka size + DPI scaling. Kuch install nahi karta — sirf report deta hai.

### 🖱️ Bat ke saath options bhi chalte hain

`clicker.bat` argument aage pass karta hai:
```cmd
clicker.bat --debug            :: debug/ me images
clicker.bat --dry-run          :: click nahi karega, sirf bataayega
clicker.bat --manual           :: region select
clicker.bat --selftest         :: environment report
```

### 📄 Do log files (window band ho jaye to bhi)

| File | Kya hota hai |
|---|---|
| `launcher_log.txt` | Bat ka har step: folder, Python kahan mila, download, exit code |
| `clicker_log.txt` | Python ka poora output + crash traceback |

Dono usi folder me bante hain jahan `clicker.py` hai.

### 🔧 Kuch kaam na kare to (troubleshooting)

| Problem | Kya karo |
|---|---|
| **Galat jagah click ho raha** | `--calibrate` chalao (kuch click nahi karega, sirf mapping report). Purana `region.txt` delete karo — DPI mode badla hai |
| **Click ho raha par CAPTCHA nahi ja raha** | Tool khud 3 baar retry karta hai (thoda alag point par). Phir bhi na ho to `--clicks 2` |
| **Click nahi ho raha** | `--click-test` chalao (Notepad khol ke) — clicks kaam kar rahe hain ya nahi pata chalega. Phir `--no-wait-go` ya `--go-timeout 3` try karo |
| **`no_strip` — boxes detect na hue** | `layout_cache.json` delete karke dobara chalao (agar page layout badla ho). Phir bhi na ho to `--manual` |
| **Window khulte hi band ho jati hai** | Naya `clicker.bat` use karo (CRLF + har path par pause). Ya CMD me: `cmd /k python clicker.py --debug` — window kabhi band nahi hogi |
| Error ki detail chahiye | Usi folder me **`clicker_log.txt`** kholo — poori traceback, Python version, OS sab save hota hai |
| Bilkul kuch nahi hota | `python clicker.py --debug --once` chalao → `debug/` folder me png aayegi. Wo bhejo, usse pata chalega kahan atka |
| "no_strip" / boxes na mile | `--manual` lagao aur poora CAPTCHA strip select karo |
| Galat box click ho raha | `--dry-run` se check karo, phir `debug/` wali image bhejo (scores usme dikhte hain) |
| Click galat jagah | display scaling ho sakti hai — tool auto-detect karta hai, log me "Display scaling detect hui" dikhega |
| "Go" na pehchane | "Go" button ka screenshot bhejo — blue-blob fallback tune karenge |

### Kaise kaam karta hai
```
Screen scan → OCR ("Click" dhoondho) → patli borders se strip + cells nikalo
→ Click wale cell me se bold shape = TARGET
→ har box ka bold shape nikalo → target ko 0-360° ghumake best IoU
→ sabse zyada score wala box → "Go" dikha? → CLICK 🖱️
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

**Naya (clicker.py v2 — graph-paper shape matching):**
```
Screen scan → OCR ("Click") → borders se strip + cells
→ Click cell ka bold shape = TARGET
→ har box ka bold shape → target ko 0-360° ghumake best IoU
→ "Go" dikha? → CLICK 🖱️
```

**Purana (cli_solver.py / captcha_solver.py — letter OCR):**
```
Screen capture → OCR (target letter) → OCR (boxes) → match? → "Go" dikha? → CLICK 🖱️
```
