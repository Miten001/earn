#!/usr/bin/env python3
"""
24x7 Monero (XMR) CPU Miner Launcher  —  Terminal + Browser GUI
================================================================
- XMRig (open source) ko auto-download karta hai (Linux / Windows / macOS)
- Miner ko 24 hour chalata hai; crash/exit ho to auto-restart
- Terminal me live hashrate, accepted shares, uptime dikhata hai
- Browser GUI dashboard: http://localhost:8787  (start/stop, live stats, log)

Usage:
    python3 miner.py                  # terminal + GUI dono
    python3 miner.py --no-gui         # sirf terminal
    python3 miner.py --wallet <XMR_ADDRESS> --pool pool.supportxmr.com:443 --threads 2

Config file: miner/config.json (pehli baar run pe ban jaata hai, wahan wallet daal do)
"""
import argparse, json, os, platform, shutil, subprocess, sys, tarfile, threading, time, urllib.request, zipfile, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
BIN_DIR = os.path.join(HERE, "xmrig")
XMRIG_VERSION = "6.22.2"

DEFAULT_CONFIG = {
    "wallet": "PASTE_YOUR_MONERO_WALLET_ADDRESS_HERE",
    "pool": "pool.supportxmr.com:443",
    "worker": "worker1",
    "threads": 0,            # 0 = auto (sab cores)
    "tls": True,
    "gui_port": 8787,
    "api_port": 8788,
    "restart_delay_sec": 10
}

# ---------------------------------------------------------------- config
def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"[!] Naya config banaya: {CONFIG_PATH}")
        print("    Usme apna Monero wallet address daalo, phir dobara run karo.")
    with open(CONFIG_PATH) as f:
        cfg = {**DEFAULT_CONFIG, **json.load(f)}
    return cfg

# ---------------------------------------------------------------- xmrig download
def xmrig_binary():
    exe = "xmrig.exe" if platform.system() == "Windows" else "xmrig"
    for root, _, files in os.walk(BIN_DIR):
        if exe in files:
            return os.path.join(root, exe)
    return None

def download_xmrig():
    sysname, arch = platform.system(), platform.machine().lower()
    base = f"https://github.com/xmrig/xmrig/releases/download/v{XMRIG_VERSION}/"
    if sysname == "Linux":
        name = f"xmrig-{XMRIG_VERSION}-linux-static-x64.tar.gz"
    elif sysname == "Windows":
        name = f"xmrig-{XMRIG_VERSION}-msvc-win64.zip"
    elif sysname == "Darwin":
        name = f"xmrig-{XMRIG_VERSION}-macos-{'arm64' if 'arm' in arch else 'x64'}.tar.gz"
    else:
        sys.exit(f"Unsupported OS: {sysname}")
    os.makedirs(BIN_DIR, exist_ok=True)
    dest = os.path.join(BIN_DIR, name)
    print(f"[*] XMRig download ho raha hai: {base + name}")
    try:
        req = urllib.request.Request(base + name, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        print(f"[!] Python download fail ({e}), curl se try kar rahe hain...")
        if shutil.which("curl"):
            subprocess.run(["curl", "-L", "--retry", "3", "-o", dest, base + name], check=True)
        else:
            sys.exit(f"Download fail. Manually download karke {BIN_DIR}/ me extract karo: {base + name}")
    if name.endswith(".zip"):
        with zipfile.ZipFile(dest) as z: z.extractall(BIN_DIR)
    else:
        with tarfile.open(dest) as t: t.extractall(BIN_DIR)
    os.remove(dest)
    b = xmrig_binary()
    if not b:
        sys.exit("XMRig extract nahi hua")
    if sysname != "Windows":
        os.chmod(b, 0o755)
    print(f"[+] XMRig ready: {b}")
    return b

# ---------------------------------------------------------------- miner state
class Miner:
    def __init__(self, cfg):
        self.cfg = cfg
        self.proc = None
        self.running = False
        self.log = deque(maxlen=300)
        self.stats = {"hashrate": 0.0, "accepted": 0, "rejected": 0, "started": None, "restarts": 0}
        self.lock = threading.Lock()

    def cmd(self):
        c = self.cfg
        b = xmrig_binary() or download_xmrig()
        args = [b, "-o", c["pool"], "-u", c["wallet"], "-p", c["worker"], "-k",
                "--http-host", "127.0.0.1", "--http-port", str(c["api_port"]), "--print-time", "30"]
        if c["tls"]: args.append("--tls")
        if c["threads"]: args += ["-t", str(c["threads"])]
        return args

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
            self.stats["started"] = time.time()
            self._log(f"=== Miner start: {self.cfg['pool']}  wallet={self.cfg['wallet'][:12]}... ===")
            try:
                self.proc = subprocess.Popen(self.cmd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in self.proc.stdout:
                    self._parse(line.rstrip())
            except Exception as e:
                self._log(f"[ERROR] {e}")
            if self.running:
                self.stats["restarts"] += 1
                self._log(f"[!] Miner band ho gaya, {self.cfg['restart_delay_sec']}s me restart...")
                time.sleep(self.cfg["restart_delay_sec"])
        self._log("=== Miner stopped ===")

    def _parse(self, line):
        self._log(line)
        m = re.search(r"speed .*?(\d+(?:\.\d+)?) ", line)          # "speed 10s/60s/15m 812.3 n/a n/a H/s"
        if "speed" in line and m:
            try: self.stats["hashrate"] = float(m.group(1))
            except ValueError: pass
        if "accepted" in line:
            m2 = re.search(r"\((\d+)/(\d+)\)", line)
            if m2:
                self.stats["accepted"] = int(m2.group(1))
                self.stats["rejected"] = int(m2.group(2)) - int(m2.group(1))

    def _log(self, s):
        ts = time.strftime("%H:%M:%S")
        with self.lock:
            self.log.append(f"[{ts}] {s}")
        print(f"[{ts}] {s}", flush=True)

    def snapshot(self):
        up = int(time.time() - self.stats["started"]) if self.stats["started"] and self.running else 0
        with self.lock:
            return {**self.stats, "running": self.running, "uptime": up,
                    "pool": self.cfg["pool"], "wallet": self.cfg["wallet"], "log": list(self.log)[-80:]}

# ---------------------------------------------------------------- GUI
HTML = """<!doctype html><html><head><meta charset=utf-8><title>XMR Miner Dashboard</title>
<style>
body{font-family:system-ui,sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:20px}
h1{margin:0 0 16px;font-size:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.card{background:#1a1d24;border-radius:10px;padding:14px}.card b{display:block;font-size:12px;color:#8a8f9c;margin-bottom:6px}
.card span{font-size:24px;font-weight:600}.on{color:#3ddc84}.off{color:#ff5c5c}
button{background:#2d6cdf;color:#fff;border:0;padding:10px 18px;border-radius:8px;cursor:pointer;font-size:14px;margin-right:8px}
button.stop{background:#d9463e}pre{background:#000;padding:12px;border-radius:10px;height:380px;overflow:auto;font-size:12px;margin-top:16px}
small{color:#8a8f9c}
</style></head><body>
<h1>⛏️ Monero CPU Miner — 24×7 Dashboard</h1>
<div class=grid>
<div class=card><b>STATUS</b><span id=st>-</span></div>
<div class=card><b>HASHRATE</b><span id=hr>-</span></div>
<div class=card><b>ACCEPTED SHARES</b><span id=acc>-</span></div>
<div class=card><b>REJECTED</b><span id=rej>-</span></div>
<div class=card><b>UPTIME</b><span id=up>-</span></div>
<div class=card><b>AUTO-RESTARTS</b><span id=rs>-</span></div>
</div>
<p><small>Pool: <span id=pool></span> &nbsp;|&nbsp; Wallet: <span id=wal></span></small></p>
<button onclick="act('start')">▶ Start</button><button class=stop onclick="act('stop')">■ Stop</button>
<pre id=log></pre>
<script>
async function act(a){await fetch('/api/'+a,{method:'POST'});poll()}
function fmt(s){return Math.floor(s/3600)+'h '+Math.floor(s%3600/60)+'m '+s%60+'s'}
async function poll(){try{const d=await (await fetch('/api/stats')).json();
st.textContent=d.running?'RUNNING':'STOPPED';st.className=d.running?'on':'off';
hr.textContent=d.hashrate.toFixed(1)+' H/s';acc.textContent=d.accepted;rej.textContent=d.rejected;
up.textContent=fmt(d.uptime);rs.textContent=d.restarts;pool.textContent=d.pool;wal.textContent=d.wallet;
const l=document.getElementById('log');const atB=l.scrollTop+l.clientHeight>=l.scrollHeight-10;
l.textContent=d.log.join('\\n');if(atB)l.scrollTop=l.scrollHeight}catch(e){}}
setInterval(poll,2000);poll()
</script></body></html>"""

def make_handler(miner):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def _send(self, code, body, ctype="text/html"):
            self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers()
            self.wfile.write(body.encode() if isinstance(body, str) else body)
        def do_GET(self):
            if self.path == "/api/stats":
                self._send(200, json.dumps(miner.snapshot()), "application/json")
            else:
                self._send(200, HTML)
        def do_POST(self):
            if self.path == "/api/start": miner.start()
            elif self.path == "/api/stop": miner.stop()
            self._send(200, "{}", "application/json")
    return H

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wallet"); ap.add_argument("--pool"); ap.add_argument("--threads", type=int)
    ap.add_argument("--no-gui", action="store_true"); ap.add_argument("--port", type=int)
    a = ap.parse_args()
    cfg = load_config()
    if a.wallet: cfg["wallet"] = a.wallet
    if a.pool: cfg["pool"] = a.pool
    if a.threads is not None: cfg["threads"] = a.threads
    if a.port: cfg["gui_port"] = a.port
    if "PASTE_YOUR" in cfg["wallet"]:
        sys.exit("[X] Wallet address set nahi hai. miner/config.json me 'wallet' daalo ya --wallet use karo.")

    miner = Miner(cfg)
    miner.start()
    if not a.no_gui:
        srv = ThreadingHTTPServer(("0.0.0.0", cfg["gui_port"]), make_handler(miner))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"[+] GUI dashboard: http://localhost:{cfg['gui_port']}")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Band kar rahe hain..."); miner.stop(); time.sleep(1)

if __name__ == "__main__":
    main()
