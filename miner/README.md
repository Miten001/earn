# ⛏️ 24×7 Multi-Miner — Terminal + GUI

Ek dashboard se **kai miners / kai coins ek saath**, 24 hour, crash pe auto-restart.

| Miner | Type | Coins |
|---|---|---|
| **XMRig** | CPU | Monero (XMR) |
| **SRBMiner-MULTI** | CPU + GPU (AMD/NVIDIA/Intel) | 70+ algos: RandomX (XMR), KawPow (RVN), Autolykos2 (ERG), GhostRider (RTM), ... |
| **lolMiner** | GPU (AMD/NVIDIA) | Ergo, Ravencoin, Flux, Kaspa-family, ... |

Sab miners **auto-download** hote hain `miner/bin/` me.

## Setup
1. Wallet banao jis coin ka mine karna hai (XMR: Cake Wallet / getmonero.org; RVN/ERG: exchange ya official wallet).
2. `python3 miner.py` ek baar chalao → `config.json` banega.
3. `config.json` me wallet paste karo aur jo miner chahiye `"enabled": true` karo:
   ```json
   "miners": [
     {"id": "xmr-cpu", "name": "Monero (CPU)", "miner": "xmrig", "enabled": true,
      "pool": "pool.supportxmr.com:443", "tls": true, "wallet": "4ABC...", "threads": 0},
     {"id": "rvn-gpu", "name": "Ravencoin (GPU)", "miner": "srbminer", "enabled": true,
      "algo": "kawpow", "pool": "stratum+tcp://rvn.2miners.com:6060", "wallet": "RXyz..."}
   ]
   ```
   Jitne chahiye utne entries add karo — CPU pe ek coin + GPU pe doosra coin ek saath chal sakta hai.
4. Chalao:
   - **Windows:** `start.bat` double-click
   - **Linux/macOS:** `python3 miner.py`
   - **Background 24×7 (Linux/Mac):** `bash start.sh` · stop: `bash stop.sh`
   - **Boot pe auto-start:** `xmr-miner.service` (systemd)
   - Sirf kuch miners: `python3 miner.py --only xmr-cpu,rvn-gpu`
   - Sirf terminal: `--no-gui`

**GUI: http://localhost:8787** — har miner ka card (hashrate, shares, uptime, restarts, live log), Start/Stop per-miner ya Start All / Stop All.

## Popular algos (SRBMiner `algo` field)
`randomx` (XMR) · `kawpow` (RVN) · `autolykos2` (ERG) · `ghostrider` (RTM) · `ethash` (ETC) · `verushash` (VRSC) · `yespowerr16` (YTN)  
lolMiner: `AUTOLYKOS2`, `KAWPOW`, `FLUX`, `ETCHASH`, `KARLSEN`, `NEXA`

## Pools
| Coin | Pool |
|---|---|
| XMR | pool.supportxmr.com:443 (tls) · gulf.moneroocean.stream:20128 |
| RVN | stratum+tcp://rvn.2miners.com:6060 · rvn.nanopool.org:12222 |
| ERG | erg.2miners.com:8888 · ergo.herominers.com:1180 |

## Zaroori baatein (sach)
- Normal PC: CPU se ₹5–60/din, purani GPU se thoda zyada. Bijli ka kharcha check karo — Gujarat me ~₹7/unit pe 200W rig = ~₹34/din sirf bijli.
- SRBMiner/lolMiner me dev fee hai (0.85–1%); XMRig default 1% (`"extra": ["--donate-level","1"]`).
- CPU+GPU 100% chalega — laptop pe `"threads": 2` rakho, GPU laptop pe mining mat karo.
- Antivirus in miners ko flag karega (false positive) — `miner/bin/` exclude karo.
- Sirf apne computer pe. Office/college/cloud free-tier pe = ban/illegal.
