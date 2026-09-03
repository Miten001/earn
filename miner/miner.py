#!/usr/bin/env python3
"""
24x7 Multi-Miner Launcher  —  Terminal + Browser GUI
=====================================================
Ek dashboard se kai miners / kai coins ek saath, 24 hour, auto-restart ke saath.

Supported miners (sab auto-download):
  xmrig      - CPU  : Monero (XMR) RandomX            [open source]
  srbminer   - CPU+GPU: 70+ algos (RandomX, KawPow, Autolykos2, GhostRider, ...)
  lolminer   - GPU  : Ergo, Kaspa-family, Ravencoin, Flux, ...  (AMD/NVIDIA)

Usage:
    python3 miner.py                 # terminal + GUI (http://localhost:8787)
    python3 miner.py --no-gui        # sirf terminal
Config: miner/config.json  (pehli baar run pe ban jaata hai)
"""
import argparse, json, os, platform, shutil, subprocess, sys, tarfile, threading, time, urllib.request, zipfile, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
BIN_DIR = os.path.join(HERE, "bin")
IS_WIN = platform.system() == "Windows"

# ---------------------------------------------------------------- miner definitions
XMRIG_V, SRB_V, LOL_V = "6.22.2", "2.9.7", "1.98"
MINERS = {
    "xmrig": {
        "exe": "xmrig.exe" if IS_WIN else "xmrig",
        "url": {
            "Windows": f"https://github.com/xmrig/xmrig/releases/download/v{XMRIG_V}/xmrig-{XMRIG_V}-msvc-win64.zip",
            "Linux":   f"https://github.com/xmrig/xmrig/releases/download/v{XMRIG_V}/xmrig-{XMRIG_V}-linux-static-x64.tar.gz",
            "Darwin":  f"https://github.com/xmrig/xmrig/releases/download/v{XMRIG_V}/xmrig-{XMRIG_V}-macos-x64.tar.gz",
        },
        "args": lambda m: ["-o", m["pool"], "-u", m["wallet"], "-p", m.get("worker", "w1"), "-k", "--print-time", "30"]
                          + (["--tls"] if m.get("tls") else []) + (["-t", str(m["threads"])] if m.get("threads") else [])
                          + m.get("extra", []),
        "speed_re": r"speed .*?(\d+(?:\.\d+)?) ",
        "share_re": r"accepted \((\d+)/(\d+)\)",
    },
    "srbminer": {
        "exe": "SRBMiner-MULTI.exe" if IS_WIN else "SRBMiner-MULTI",
        "url": {
            "Windows": f"https://github.com/doktor83/SRBMiner-Multi/releases/download/{SRB_V}/SRBMiner-Multi-{SRB_V.replace('.','-')}-win64.zip",
            "Linux":   f"https://github.com/doktor83/SRBMiner-Multi/releases/download/{SRB_V}/SRBMiner-Multi-{SRB_V.replace('.','-')}-Linux.tar.gz",
        },
        "args": lambda m: ["--algorithm", m["algo"], "--pool", m["pool"], "--wallet", m["wallet"],
                           "--password", m.get("worker", "w1"), "--disable-gpu" if m.get("cpu_only") else "--disable-cpu"]
                          + (["--cpu-threads", str(m["threads"])] if m.get("threads") else []) + m.get("extra", []),
        "speed_re": r"[Tt]otal:?\s+(\d+(?:\.\d+)?)\s*[kKmM]?[Hh]/s",
        "share_re": r"[Aa]ccepted:?\s*(\d+)",
    },
    "lolminer": {
        "exe": "lolMiner.exe" if IS_WIN else "lolMiner",
        "url": {
            "Windows": f"https://github.com/Lolliedieb/lolMiner-releases/releases/download/{LOL_V}/lolMiner_v{LOL_V}_Win64.zip",
            "Linux":   f"https://github.com/Lolliedieb/lolMiner-releases/releases/download/{LOL_V}/lolMiner_v{LOL_V}_Lin64.tar.gz",
        },
        "args": lambda m: ["--algo", m["algo"], "--pool", m["pool"], "--user", f"{m['wallet']}.{m.get('worker','w1')}"]
                          + m.get("extra", []),
        "speed_re": r"Total.*?(\d+(?:\.\d+)?)\s*[kKmMgG]?[Hh]/s",
        "share_re": r"Accepted.*?(\d+)",
    },
}

DEFAULT_CONFIG = {
    "gui_port": 8787,
    "restart_delay_sec": 10,
    "miners": [
        {"id": "xmr-cpu", "name": "Monero (CPU)", "miner": "xmrig", "enabled": True,
         "pool": "pool.supportxmr.com:443", "tls": True,
         "wallet": "PASTE_YOUR_XMR_WALLET", "worker": "pc1", "threads": 0},
        {"id": "rvn-gpu", "name": "Ravencoin (GPU)", "miner": "srbminer", "enabled": False,
         "algo": "kawpow", "pool": "stratum+tcp://rvn.2miners.com:6060",
         "wallet": "PASTE_YOUR_RVN_WALLET", "worker": "pc1", "cpu_only": False},
        {"id": "erg-gpu", "name": "Ergo (GPU)", "miner": "lolminer", "enabled": False,
         "algo": "AUTOLYKOS2", "pool": "erg.2miners.com:8888",
         "wallet": "PASTE_YOUR_ERG_WALLET", "worker": "pc1"},
        {"id": "xmr-cpu-2", "name": "Monero via SRBMiner (CPU)", "miner": "srbminer", "enabled": False,
         "algo": "randomx", "pool": "pool.supportxmr.com:443", "cpu_only": True,
         "wallet": "PASTE_YOUR_XMR_WALLET", "worker": "pc1", "threads": 0},
    ],
}

# ---------------------------------------------------------------- config
def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"[!] Naya config banaya: {CONFIG_PATH}\n    Usme apne wallet daalo, jo miner chahiye 'enabled': true karo, phir dobara run karo.")
    with open(CONFIG_PATH) as f:
        return {**DEFAULT_CONFIG, **json.load(f)}

# ---------------------------------------------------------------- download
def find_binary(kind):
    exe = MINERS[kind]["exe"]
    for root, _, files in os.walk(os.path.join(BIN_DIR, kind)):
        if exe in files:
            return os.path.join(root, exe)
    return None

def download(kind, log):
    url = MINERS[kind]["url"].get(platform.system())
    if not url:
        raise RuntimeError(f"{kind}: {platform.system()} supported nahi")
    d = os.path.join(BIN_DIR, kind); os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, url.rsplit("/", 1)[1])
    log(f"[*] {kind} download: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        log(f"[!] python download fail ({e}), curl try...")
        if not shutil.which("curl"):
            raise RuntimeError(f"Download fail. Manually {url} download karke {d}/ me extract karo")
        subprocess.run(["curl", "-sL", "--retry", "3", "-o", dest, url], check=True)
    if dest.endswith(".zip"):
        with zipfile.ZipFile(dest) as z: z.extractall(d)
    else:
        with tarfile.open(dest) as t: t.extractall(d)
    os.remove(dest)
    b = find_binary(kind)
    if not b: raise RuntimeError(f"{kind} extract fail")
    if not IS_WIN: os.chmod(b, 0o755)
    log(f"[+] {kind} ready: {b}")
    return b

# ---------------------------------------------------------------- one miner instance
class MinerProc:
    def __init__(self, m, restart_delay):
        self.m, self.kind, self.delay = m, m["miner"], restart_delay
        self.spec = MINERS[self.kind]
        self.proc, self.running, self.started = None, False, None
        self.log = deque(maxlen=200)
        self.stats = {"hashrate": 0.0, "accepted": 0, "rejected": 0, "restarts": 0, "error": ""}

    def start(self):
        if self.running: return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def _loop(self):
        while self.running:
            self.started = time.time()
            self._log(f"=== START {self.m['name']} [{self.kind}] -> {self.m['pool']} ===")
            try:
                b = find_binary(self.kind) or download(self.kind, self._log)
                cmd = [b] + self.spec["args"](self.m)
                self.stats["error"] = ""
                self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             text=True, errors="replace", cwd=os.path.dirname(b))
                for line in self.proc.stdout:
                    self._parse(line.rstrip())
            except Exception as e:
                self.stats["error"] = str(e); self._log(f"[ERROR] {e}")
            if self.running:
                self.stats["restarts"] += 1; self.stats["hashrate"] = 0.0
                self._log(f"[!] band ho gaya, {self.delay}s me restart...")
                time.sleep(self.delay)
        self.stats["hashrate"] = 0.0
        self._log("=== STOPPED ===")

    def _parse(self, line):
        self._log(line)
        m = re.search(self.spec["speed_re"], line)
        if m:
            try:
                v = float(m.group(1))
                unit = re.search(r"(\d+(?:\.\d+)?)\s*([kKmMgG]?)[Hh]/s", line[m.start():])
                mult = {"k": 1e3, "m": 1e6, "g": 1e9}.get((unit.group(2) if unit else "").lower(), 1)
                self.stats["hashrate"] = v * mult
            except ValueError: pass
        s = re.search(self.spec["share_re"], line)
        if s:
            self.stats["accepted"] = int(s.group(1))
            if s.lastindex and s.lastindex >= 2:
                self.stats["rejected"] = int(s.group(2)) - int(s.group(1))

    def _log(self, s):
        ts = time.strftime("%H:%M:%S")
        self.log.append(f"[{ts}] {s}")
        print(f"[{ts}] [{self.m['id']}] {s}", flush=True)

    def snapshot(self):
        return {**self.stats, "id": self.m["id"], "name": self.m["name"], "miner": self.kind,
                "pool": self.m["pool"], "wallet": self.m["wallet"], "running": self.running,
                "uptime": int(time.time() - self.started) if self.running and self.started else 0,
                "log": list(self.log)[-40:]}

# ---------------------------------------------------------------- GUI
HTML = """<!doctype html><html><head><meta charset=utf-8><title>Multi-Miner Dashboard</title>
<style>
body{font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:20px}
h1{margin:0 0 4px;font-size:22px}.sub{color:#8a8f9c;margin-bottom:16px}
.tot{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}.tot div{background:#1a1d24;border-radius:10px;padding:12px 18px}
.tot b{display:block;font-size:11px;color:#8a8f9c}.tot span{font-size:22px;font-weight:600}
.m{background:#1a1d24;border-radius:12px;padding:16px;margin-bottom:14px;border-left:4px solid #555}
.m.on{border-color:#3ddc84}.m.err{border-color:#ff5c5c}
.hd{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.hd h2{margin:0;font-size:17px}.tag{font-size:11px;background:#2a2e38;padding:2px 8px;border-radius:6px;color:#aab;margin-left:8px}
.st{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:12px 0}
.st div b{display:block;font-size:11px;color:#8a8f9c}.st div span{font-size:18px;font-weight:600}
button{background:#2d6cdf;color:#fff;border:0;padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px;margin-left:6px}
button.stop{background:#d9463e}.gn{color:#3ddc84}.rd{color:#ff5c5c}
pre{background:#000;padding:10px;border-radius:8px;height:150px;overflow:auto;font-size:11px;margin:0}
small{color:#8a8f9c;word-break:break-all}.err{color:#ff8c8c;font-size:12px}
</style></head><body>
<h1>⛏️ Multi-Miner 24×7 Dashboard</h1>
<div class=sub>XMRig · SRBMiner · lolMiner — sab ek jagah. Miners add/remove: <code>config.json</code></div>
<div class=tot>
<div><b>ACTIVE MINERS</b><span id=tA>-</span></div>
<div><b>TOTAL ACCEPTED SHARES</b><span id=tS>-</span></div>
<div><b>TOTAL RESTARTS</b><span id=tR>-</span></div>
<div><b>&nbsp;</b><button onclick="act('all','start')">▶ Start All</button><button class=stop onclick="act('all','stop')">■ Stop All</button></div>
</div>
<div id=list></div>
<script>
const open={};
async function act(id,a){await fetch('/api/'+a+'/'+id,{method:'POST'});poll()}
function fmt(s){return Math.floor(s/3600)+'h '+Math.floor(s%3600/60)+'m '+s%60+'s'}
function hr(h){return h>=1e6?(h/1e6).toFixed(2)+' MH/s':h>=1e3?(h/1e3).toFixed(2)+' kH/s':h.toFixed(1)+' H/s'}
async function poll(){try{const d=await (await fetch('/api/stats')).json();
let A=0,S=0,R=0;const L=document.getElementById('list');
const pos={};[...L.querySelectorAll('pre')].forEach(p=>pos[p.id]=p.scrollTop+p.clientHeight>=p.scrollHeight-10);
L.innerHTML=d.map(m=>{if(m.running)A++;S+=m.accepted;R+=m.restarts;
return `<div class="m ${m.error?'err':m.running?'on':''}"><div class=hd><h2>${m.name}<span class=tag>${m.miner}</span>
<span class=tag ${m.running?'style="color:#3ddc84"':''}>${m.running?'RUNNING':'STOPPED'}</span></h2>
<div><button onclick="act('${m.id}','start')">▶ Start</button><button class=stop onclick="act('${m.id}','stop')">■ Stop</button></div></div>
<div class=st><div><b>HASHRATE</b><span>${hr(m.hashrate)}</span></div><div><b>ACCEPTED</b><span class=gn>${m.accepted}</span></div>
<div><b>REJECTED</b><span class=rd>${m.rejected}</span></div><div><b>UPTIME</b><span>${fmt(m.uptime)}</span></div><div><b>RESTARTS</b><span>${m.restarts}</span></div></div>
<small>Pool: ${m.pool} · Wallet: ${m.wallet}</small>${m.error?`<div class=err>⚠ ${m.error}</div>`:''}
<pre id="log-${m.id}">${m.log.join('\\n')}</pre></div>`}).join('');
[...L.querySelectorAll('pre')].forEach(p=>{if(pos[p.id]!==false)p.scrollTop=p.scrollHeight});
tA.textContent=A+' / '+d.length;tS.textContent=S;tR.textContent=R}catch(e){}}
setInterval(poll,2000);poll()
</script></body></html>"""

def make_handler(miners):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _send(self, body, ctype="text/html"):
            self.send_response(200); self.send_header("Content-Type", ctype); self.end_headers()
            self.wfile.write(body.encode())
        def do_GET(self):
            if self.path == "/api/stats":
                self._send(json.dumps([m.snapshot() for m in miners]), "application/json")
            else:
                self._send(HTML)
        def do_POST(self):
            parts = self.path.strip("/").split("/")       # api/start/<id>
            if len(parts) == 3 and parts[0] == "api":
                action, mid = parts[1], parts[2]
                for m in miners:
                    if mid in ("all", m.m["id"]):
                        (m.start if action == "start" else m.stop)()
            self._send("{}", "application/json")
    return H

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-gui", action="store_true"); ap.add_argument("--port", type=int)
    ap.add_argument("--only", help="sirf ye miner id(s) chalao, comma separated")
    a = ap.parse_args()
    cfg = load_config()
    if a.port: cfg["gui_port"] = a.port
    only = set(a.only.split(",")) if a.only else None

    miners = [MinerProc(m, cfg["restart_delay_sec"]) for m in cfg["miners"]]
    if not miners: sys.exit("[X] config.json me koi miner nahi hai")
    for mp in miners:
        want = mp.m.get("enabled", True) if only is None else mp.m["id"] in only
        if want and "PASTE_YOUR" in mp.m["wallet"]:
            print(f"[X] '{mp.m['id']}' ka wallet set nahi hai (config.json) — skip"); continue
        if want: mp.start()
    if not any(m.running for m in miners):
        print("[!] Koi miner start nahi hua. config.json me wallet + enabled:true check karo.")
        if a.no_gui: sys.exit(1)

    if not a.no_gui:
        srv = ThreadingHTTPServer(("0.0.0.0", cfg["gui_port"]), make_handler(miners))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"[+] GUI dashboard: http://localhost:{cfg['gui_port']}")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Sab band kar rahe hain...")
        for m in miners: m.stop()
        time.sleep(1)

if __name__ == "__main__":
    main()
