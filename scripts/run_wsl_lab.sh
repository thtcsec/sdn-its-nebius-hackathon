#!/usr/bin/env bash
# WSL lab launcher: OVS of_agent + ITS Mininet topo (headless).
# Usage (from Windows):
#   wsl -d Ubuntu -u root -- bash /mnt/d/tu_projects/sdn-its-resilience-ai/scripts/run_wsl_lab.sh 90
set +e
ROOT=/mnt/d/tu_projects/sdn-its-resilience-ai
DURATION="${1:-90}"
AGENT_PORT="${2:-8089}"
cd "$ROOT"

echo "=== SDN-ITS WSL lab ==="
echo "duration=${DURATION}s agent=:${AGENT_PORT}"
free -h | head -2

mn -c >/dev/null 2>&1
service openvswitch-switch start || true

# Start OF agent (ovs-ofctl HTTP bridge)
pkill -f wsl_of_agent.py 2>/dev/null
python3 "$ROOT/scripts/wsl_of_agent.py" --host 0.0.0.0 --port "$AGENT_PORT" >/tmp/wsl_of_agent.log 2>&1 &
AGENT_PID=$!
sleep 1
if curl -fsS "http://127.0.0.1:${AGENT_PORT}/health" >/dev/null; then
  echo "[+] of_agent OK pid=$AGENT_PID"
else
  echo "[!] of_agent failed — see /tmp/wsl_of_agent.log"
  cat /tmp/wsl_of_agent.log
fi

export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
echo "[*] Starting ITS Mininet topology (no remote controller; ovs-ofctl agent applies flows)"
python3 -m sdn_its.simulation.topology --controller_port 0 --duration "$DURATION" --no-cli
RC=$?

echo "[*] Stopping of_agent"
kill "$AGENT_PID" 2>/dev/null
mn -c >/dev/null 2>&1
free -h | head -2
echo "DONE rc=$RC"
exit 0
