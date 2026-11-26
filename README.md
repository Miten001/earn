# 🎯 Click & Find — CAPTCHA Letter Clicker

"Click" ke niche jo letter dikhe (jaise `q`), use 3 boxes me find karke jab **"Go"** aaye to us letter par **auto-click** karta hai.

## 📁 Files

| File | Kya hai |
|---|---|
| `index.html` | Web GUI demo (browser me chalao — practice ke liye) |
| `captcha_solver.py` | **Real screen automation** — asli screen par kaam karta hai |
| `requirements.txt` | Python packages |

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

## 🖥️ Real Screen Version (`captcha_solver.py`)

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

```
Screen capture → OCR (target letter) → OCR (3 boxes) → match? → "Go" dikha? → CLICK 🖱️
```
