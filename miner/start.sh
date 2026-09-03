#!/bin/bash
# Linux/macOS: 24x7 background me chalao (terminal band karne pe bhi chalta rahega)
cd "$(dirname "$0")"
nohup python3 miner.py "$@" > miner.log 2>&1 &
echo "Miner background me start ho gaya (PID $!). Log: miner/miner.log | GUI: http://localhost:8787"
