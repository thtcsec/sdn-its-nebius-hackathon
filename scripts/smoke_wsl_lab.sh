#!/usr/bin/env bash
# One-shot smoke: start agent+topo briefly, push a DROP via HTTP, dump flows.
set +e
ROOT=/mnt/d/tu_projects/sdn-its-resilience-ai
cd "$ROOT"
mn -c >/dev/null 2>&1
service openvswitch-switch start || true
pkill -f wsl_of_agent.py 2>/dev/null
python3 "$ROOT/scripts/wsl_of_agent.py" --port 8089 >/tmp/wsl_of_agent.log 2>&1 &
AGENT_PID=$!
export PYTHONPATH="$ROOT/src"
# Hold topo 45s in background
python3 -m sdn_its.simulation.topology --controller_port 0 --duration 45 --no-cli >/tmp/wsl_topo.log 2>&1 &
TOPO_PID=$!
sleep 8
echo "=== health ==="
curl -fsS http://127.0.0.1:8089/health || echo FAIL_HEALTH
echo
echo "=== push DROP ==="
curl -fsS -X POST http://127.0.0.1:8089/flow_mod \
  -H 'Content-Type: application/json' \
  -d '{"action":"ADD","dpid":"0000000000000001","src_ip":"10.0.0.15","of_action":"DROP","priority":200,"idle_timeout":20}'
echo
echo "=== dump s1 ==="
ovs-ofctl dump-flows s1 | head -20
echo "=== status ==="
curl -fsS http://127.0.0.1:8089/status | python3 -m json.tool | head -40
wait $TOPO_PID 2>/dev/null
kill $AGENT_PID 2>/dev/null
mn -c >/dev/null 2>&1
echo DONE
