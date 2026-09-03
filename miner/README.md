# ⛏️ 24×7 Monero (XMR) CPU Miner — Terminal + GUI

Real crypto mining jo 24 hour chalti rahe. XMRig (open-source miner) use karta hai,
crash hone par auto-restart, aur browser me live dashboard.

## Setup (3 step)
1. **Monero wallet banao** — [getmonero.org](https://www.getmonero.org/downloads/) ya Cake Wallet app.
   Address `4...` ya `8...` se shuru hota hai (95 characters).
2. `config.json` me wallet paste karo (pehli baar `python3 miner.py` run karne pe file ban jaati hai):
   ```json
   { "wallet": "4ABC...", "pool": "pool.supportxmr.com:443", "threads": 0 }
   ```
3. Chalao:
   - **Windows:** `start.bat` double-click
   - **Linux/macOS terminal:** `python3 miner.py`
   - **Linux background 24×7:** `bash start.sh`  (stop: `bash stop.sh`)
   - **Boot pe auto-start:** `xmr-miner.service` dekho

GUI: **http://localhost:8787** — hashrate, shares, uptime, Start/Stop, live log.
Sirf terminal chahiye: `python3 miner.py --no-gui`

## Earnings check
Pool dashboard pe wallet address daalo: https://supportxmr.com  
Min payout 0.1 XMR (normal laptop pe kai hafte lag sakte hain).

## Zaroori baatein (sach)
- Normal PC/laptop: ~500–5000 H/s ≈ ₹5–₹60/din. Bijli ka kharcha isse zyada ho sakta hai.
- CPU 100% chalega, garam hoga — laptop pe `"threads": 2` rakho.
- Antivirus XMRig ko flag kar sakta hai (false positive, kyunki malware bhi ise use karta hai). Folder ko exclude karo.
- Sirf apne khud ke computer pe chalao. Kisi aur ke system/office/cloud free-tier pe mining = ban/illegal.

## Pools (koi bhi chuno)
| Pool | Address |
|---|---|
| SupportXMR | pool.supportxmr.com:443 |
| MoneroOcean | gulf.moneroocean.stream:20128 |
| Nanopool | xmr-eu1.nanopool.org:14433 |
| 2Miners | xmr.2miners.com:2222 |
