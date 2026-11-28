# 🎯 Click & Find — CAPTCHA Letter Clicker

Clue box (sabse aakhri) me jo shape hota hai, wahi shape **pehle 3 boxes** me dhoondh ke
**"GO"** dikhne par usi waqt **auto-click** karta hai. Match na mile to 3 me se random box click hota hai.

## 📁 Files

| File | Kya hai |
|---|---|
| `clicker.bat` | **DOUBLE-CLICK KARO, BAS!** Python auto-install (winget), args passthrough, `launcher_log.txt` ⭐⭐⭐ |
| `clicker.py` | **v2** — graph-paper cells + rotation-tolerant shape matching + DPI fix (`--debug`, `--dry-run`) ⭐⭐ |
| `requirements.txt` | Python packages ki list (clicker.py khud install kar leta hai — manual ke liye) |

> 🧹 Purane letter-OCR versions (`cli_solver.py`, `captcha_solver.py`) aur web demo
> (`index.html`) hata diye gaye hain — ab sirf `clicker.py` + `clicker.bat` hi maintain hota hai.

---

## ⭐⭐⭐ DOUBLE-CLICK Version (`clicker.bat`) — sabse easy!

**Sirf `clicker.bat` file download karo aur double-click karo — bas!**

Double-click karne par ye file khud sab kar legi:
1. 🐍 **Python check** — agar nahi hai to **auto-download + silent install** (python.org se)
2. 📄 `clicker.py` na mile to **GitHub se auto-download**
3. 📦 Packages (pyautogui, pillow, pytesseract, opencv, numpy) **auto-install**
4. 🔤 Tesseract OCR **auto-download + install** (Windows)
5. 🔍 CAPTCHA khud dhoondhega (full screen scan — kuch select nahi karna)
6. ⏳ Timer khud padhega (9 → 8 → 7 …), aur **"GO" likhte hi turant** click

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
- ⚡ **Fast** — ek baar locate, phir **~50–120 ms/frame**; timer/GO sirf blue blobs se
  padha jata hai (per-frame OCR **nahi**), `layout_cache.json` se agli baar **instant start**
- 🎯 **Turant click** — "GO" pehli baar dikha, usi frame me click (**GO → click ≈ 20–50 ms**),
  mouse move 0.05s + chhota click delay
- 🧭 **Layout auto-detect** — "Click" cell, boxes aur "Go" khud pehchanta hai
- 🔢 **3, 4, 5... boxes** — dividers se count hota hai; **aakhri (clue) box kabhi click nahi hota**
- 🧩 **Clue box = sabse aakhri** — usme laal "Click" + ek shape hota hai; pehle 3 boxes me wahi
  shape dhoondh ke click hota hai. Shape **match na mile to 3 me se koi ek random** box click hota hai
- ⏱️ **Timer slot padhta hai** — jahan bada blue **"9"** (countdown) dikhta hai, wahi
  jagah baad me **"GO"** ban jati hai. Tool digit aur "GO" me farq karta hai:
  digit = ruk jao, **"GO" = turant click**. Apna koi 11s timer nahi lagaya jata
- 🛡️ **False "GO" fix** — countdown ka blue digit, clue cell ka bada "G", ya ad ka
  "Go" — inme se koi bhi ab GO nahi maana jata (sirf timer wali jagah dekhi jati hai)
- 🕳️ **Blind click** — agar CAPTCHA hi detect na ho (page badal gaya / galat page) to
  4s baad khud seedha click kar deta hai (GO ka intezaar nahi). 5 blind clicks ke baad
  ruk jata hai. `--no-blind` se band
- 🧱 **no_strip fallback** — lines halki/blur ho to page ke background color se strip
  aur cells nikale jate hain (aakhri rasta)
- 🚫 **Ad banner safe** — page ke ads (jo CAPTCHA jaisa dikhte hain) cells me count nahi hote
- 🌐 **Browser background me bhi** — poori screen scan karta hai, window focus ki zaroorat nahi
- 🖥️ **DPI-aware mode** — process ko per-monitor DPI-aware banata hai, isliye screenshot aur
  click dono **physical pixels** me hote hain → 125%/150% scaling par bhi click bilkul sahi jagah
- ⚡ **Fast tracking** — CAPTCHA ek baar milne par har frame me sirf chhota hissa check hota hai (~10 ms)

### Use

**Option A — Double-click karo:**
1. `clicker.py` (ya `clicker.bat`) par **double-click**
2. Tool screen scan karke CAPTCHA khud dhoondhega — kuch select nahi karna
3. ⏳ Timer chalta hai — tool tab tak sirf shape dhoondhta hai (click nahi)
4. 🟢 **"GO"** dikhte hi usi waqt click. Stop: `Ctrl+C` ya mouse screen corner par

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
python clicker.py --go-timeout 3   # 3s me Go na mile to phir bhi click (default: sirf Go par)
python clicker.py --wait 5         # extra safety: 5s tak click nahi (default 0 = off)
python clicker.py --no-blind       # CAPTCHA na mile to bhi click mat karo
python clicker.py --blind-after 2  # 2s tak detect na ho to seedha click
python clicker.py --min-match 0.4  # match ka threshold (kam = zyada "match" maanega)
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
| **`no_strip` — boxes detect na hue** | `layout_cache.json` delete karke dobara chalao (naya version purana cache khud ignore karta hai) (agar page layout badla ho). Phir bhi na ho to `--manual` |
| **Window khulte hi band ho jati hai** | Naya `clicker.bat` use karo (CRLF + har path par pause). Ya CMD me: `cmd /k python clicker.py --debug` — window kabhi band nahi hogi |
| Error ki detail chahiye | Usi folder me **`clicker_log.txt`** kholo — poori traceback, Python version, OS sab save hota hai |
| Bilkul kuch nahi hota | `python clicker.py --debug --once` chalao → `debug/` folder me png aayegi. Wo bhejo, usse pata chalega kahan atka |
| "no_strip" / boxes na mile | `--manual` lagao aur poora CAPTCHA strip select karo |
| Galat box click ho raha | `--dry-run` se check karo, phir `debug/` wali image bhejo (scores usme dikhte hain) |
| Log me `[RANDOM — clue ka match nahi mila]` | Clue jaisa shape kisi box me nahi mila, isliye 3 me se random box clicka (design ke hisaab se normal) |
| Clue box (aakhri) click ho raha | Aisa nahi hona chahiye — `debug/` image bhejo, cells ka partition galat detect hua hai |
| **GO aane ke baad click late hota hai** | Fix: timer/GO ab sirf blue-blob geometry se padha jata hai (per-frame OCR hataya), GO ke liye polling 0.1s. `--interval 0.1` se aur tez |
| Click bahut late ho raha | `--go-timeout 0` (default) rakho — click sirf "GO" dikhne par hota hai |
| **Timer ke andar hi click ho jata hai** | Fix ho gaya — countdown digit (9,8,7) ab timer maana jata hai, GO nahi. `--debug` se `debug/` image bhejo agar phir bhi ho |
| **Log me `no_strip` aata hai** | Ab background-color fallback hai; phir bhi aaye to `--manual` se region select karo |
| **`🕳️ seedha click` bahut baar** | `--no-blind` lagao, ya `--manual` se region do (tab detection pakki ho jati hai) |
| **Time khatam hone par click** | Fix: retry ab poore CAPTCHA ka fingerprint dekhta hai (pehle sirf shape) |
| **`no_target` aata tha** | Fix ho gaya — clue shape na mile to bhi 3 me se random box click hota hai |
| Click galat jagah | display scaling ho sakti hai — tool auto-detect karta hai, log me "Display scaling detect hui" dikhega |
| "Go" na pehchane | "Go" button ka screenshot bhejo — blue-blob fallback tune karenge |

### Kaise kaam karta hai
```
Screen scan → OCR ("Click" dhoondho) → borders se strip + cells nikalo
→ CLUE cell (sabse aakhri, jisme laal "Click" + shape) ka bold shape = TARGET
→ pehle 3 boxes ka bold shape → target ko 0-360° ghumake best IoU
→ clear winner? → wahi box  |  match dhundhla/koi nahi? → 3 me se RANDOM box
→ timer ke dauraan sirf search … "GO" dikha? → USI FRAME me CLICK 🖱️
→ clue cell (aakhri) kabhi click nahi hota
```

---
