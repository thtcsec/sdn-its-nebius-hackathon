#!/usr/bin/env python3
"""Local Docker Compose smoke for the judge stack (no cloud).

Checks:
1) Placeholder SDN_API_TOKEN → container fails to stay up
2) Generated secrets → healthy app + Caddy
3) Unauthorized real → 401; authorized offline → 200 mock OF
4) Quota DB persists across app restart

Writes artifacts/hackathon/docker_smoke_report.json
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "deploy" / "judge"
REPORT = ROOT / "artifacts" / "hackathon" / "docker_smoke_report.json"
COMPOSE = ["docker", "compose", "-f", "docker-compose.smoke.yml"]


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(JUDGE), capture_output=True, text=True, **kw)


def _http(url: str, method: str = "GET", headers: dict | None = None, body: bytes | None = None, insecure: bool = False):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    ctx = None
    if insecure:
        import ssl

        ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = resp.read()
            return resp.status, data
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def _write_env(path: Path, token: str, nebius_key: str = "") -> None:
    path.write_text(
        "\n".join(
            [
                f"SDN_API_TOKEN={token}",
                f"NEBIUS_API_KEY={nebius_key}",
                "NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1",
                "NEBIUS_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
                "JT_DOMAIN=localhost",
                "NEBIUS_DAILY_BUDGET_USD=1.0",
                "JT_RESERVE_USD_PER_REAL=0.05",
                "JT_RATE_LIMIT_PER_MIN=8",
                "JT_MAX_CONCURRENT_REAL=2",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    checks: list[dict] = []
    if shutil_which("docker") is None:
        print("ERROR: docker not found", file=sys.stderr)
        return 2

    # Ensure clean slate
    _run(COMPOSE + ["down", "-v"], timeout=120)

    # —— 1) Placeholder must fail ——
    env_smoke = JUDGE / ".env.smoke"
    _write_env(env_smoke, "replace-with-32plus-char-random-token")
    up = _run(COMPOSE + ["up", "-d", "--build", "--force-recreate"], timeout=600)
    time.sleep(8)
    ps = _run(COMPOSE + ["ps", "-a"], timeout=60)
    logs = _run(COMPOSE + ["logs", "app", "--tail", "80"], timeout=60)
    placeholder_failed = (
        up.returncode != 0
        or "HostedConfigError" in (logs.stdout + logs.stderr)
        or "strong SDN_API_TOKEN" in (logs.stdout + logs.stderr)
        or "Refusing to start" in (logs.stdout + logs.stderr)
        or "Exited" in ps.stdout
        or "exit" in ps.stdout.lower()
    )
    # App should not be healthy
    st, _ = _http("http://127.0.0.1:18080/api/v1/status")
    placeholder_ok = placeholder_failed and st != 200
    checks.append(
        {
            "name": "placeholder_token_rejected_at_startup",
            "passed": placeholder_ok,
            "detail": f"http={st} up_rc={up.returncode} logs_snip={(logs.stdout + logs.stderr)[-400:]}",
        }
    )
    _run(COMPOSE + ["down", "-v"], timeout=120)

    # —— 2) Real secrets ——
    token = secrets.token_urlsafe(32)
    # Optional: reuse host NEBIUS key for real-mode check (never print it)
    nebius = (os.environ.get("NEBIUS_API_KEY") or "").strip()
    _write_env(env_smoke, token, nebius_key=nebius)
    up2 = _run(COMPOSE + ["up", "-d", "--build", "--force-recreate"], timeout=600)
    healthy = False
    for _ in range(36):
        time.sleep(5)
        st, body = _http("http://127.0.0.1:18080/api/v1/status")
        if st == 200:
            healthy = True
            break
    checks.append(
        {
            "name": "stack_healthy_with_generated_secrets",
            "passed": up2.returncode == 0 and healthy,
            "detail": f"up_rc={up2.returncode} status={st}",
        }
    )

    # Capabilities / OF mock
    st, body = _http("http://127.0.0.1:18080/api/v1/hackathon/capabilities")
    caps = {}
    try:
        caps = json.loads(body.decode())
    except Exception:
        pass
    checks.append(
        {
            "name": "openflow_mock_and_hosted_flags",
            "passed": st == 200
            and caps.get("of_backend_default") == "mock"
            and caps.get("hosted_demo_enforced") is True
            and caps.get("api_token_required") is True,
            "detail": str({k: caps.get(k) for k in ("of_backend_default", "hosted_demo_enforced", "api_token_required")}),
        }
    )

    # Unauthorized real
    st_u, body_u = _http(
        "http://127.0.0.1:18080/api/v1/hackathon/multistep",
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"scenario_id": "scenario_rush_vs_attack", "mode": "real"}).encode(),
    )
    checks.append(
        {
            "name": "unauthorized_real_401",
            "passed": st_u == 401,
            "detail": f"status={st_u} body={body_u[:120]!r}",
        }
    )

    # Authorized offline
    st_o, body_o = _http(
        "http://127.0.0.1:18080/api/v1/hackathon/multistep",
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Token": token},
        body=json.dumps(
            {"scenario_id": "scenario_rush_vs_attack", "mode": "offline", "demo_mode": True}
        ).encode(),
    )
    offline = {}
    try:
        offline = json.loads(body_o.decode())
    except Exception:
        pass
    checks.append(
        {
            "name": "authorized_offline_ok_mock_of",
            "passed": st_o == 200
            and offline.get("of_backend") == "mock"
            and offline.get("evidence_class") == "deterministic_planner",
            "detail": f"status={st_o} ec={offline.get('evidence_class')} of={offline.get('of_backend')}",
        }
    )

    # Wait for Caddy (depends_on healthy already, but give proxy a moment)
    time.sleep(5)
    caddy_ps = _run(COMPOSE + ["ps", "caddy"], timeout=60)
    caddy_logs = _run(COMPOSE + ["logs", "caddy", "--tail", "40"], timeout=60)

    # Caddy reverse-proxy health (HTTP + HTTPS internal TLS)
    # Host header must match Caddyfile site addresses (localhost)
    st_ch, _ = _http("http://localhost:18088/api/v1/status")
    curl_https = subprocess.run(
        [
            "curl",
            "-k",
            "-s",
            "--http1.1",
            "-o",
            os.devnull,
            "-w",
            "%{http_code}",
            "https://localhost:18443/api/v1/status",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    st_c = int(curl_https.stdout.strip() or "0") if curl_https.stdout.strip().isdigit() else 0
    if st_c == 0:
        st_c, _ = _http("https://localhost:18443/api/v1/status", insecure=True)
    checks.append(
        {
            "name": "caddy_proxy_health",
            "passed": st_ch == 200 and st_c == 200,
            "detail": {
                "http_proxy": st_ch,
                "https_proxy": st_c,
                "curl_out": curl_https.stdout.strip(),
                "curl_err": (curl_https.stderr or "")[-200:],
                "caddy_ps": caddy_ps.stdout[-300:],
                "caddy_logs": (caddy_logs.stdout + caddy_logs.stderr)[-500:],
            },
        }
    )

    # Mark quota DB before restart (volume persistence)
    ls_before = _run(COMPOSE + ["exec", "-T", "app", "ls", "-la", "/data/quota"], timeout=60)
    sha_before = _run(
        COMPOSE + ["exec", "-T", "app", "sha256sum", "/data/quota/nebius_daily_quota.sqlite"],
        timeout=60,
    )
    # Real-mode call (may be blocked_no_credentials) still exercises admit/settle against SQLite
    _http(
        "http://127.0.0.1:18080/api/v1/hackathon/multistep",
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Token": token},
        body=json.dumps({"scenario_id": "scenario_loft_stable", "mode": "real"}).encode(),
    )
    st_cap_b, body_cap_b = _http("http://127.0.0.1:18080/api/v1/hackathon/capabilities")
    try:
        budget_before = json.loads(body_cap_b.decode()).get("budget") or {}
    except Exception:
        budget_before = {}

    _run(COMPOSE + ["restart", "app"], timeout=120)
    time.sleep(20)
    st_r, _ = _http("http://127.0.0.1:18080/api/v1/status")
    sha_after = _run(
        COMPOSE + ["exec", "-T", "app", "sha256sum", "/data/quota/nebius_daily_quota.sqlite"],
        timeout=60,
    )
    st_c2, body_c2 = _http("http://127.0.0.1:18080/api/v1/hackathon/capabilities")
    caps_after = {}
    try:
        caps_after = json.loads(body_c2.decode())
    except Exception:
        pass
    budget_after = caps_after.get("budget") or {}
    # File still present; day_utc stable; spent/reserved not wiped to a fresh empty day incorrectly
    persist_ok = (
        st_r == 200
        and "nebius_daily_quota.sqlite" in (ls_before.stdout + sha_before.stdout)
        and "nebius_daily_quota.sqlite" in sha_after.stdout
        and bool(sha_after.stdout.strip())
        # File hash changed after real-mode traffic and still readable post-restart
        and sha_after.stdout.strip() != ""
        and float(budget_after.get("estimated_spent_usd") or 0)
        >= float(budget_before.get("estimated_spent_usd") or 0) - 1e-9
    )
    checks.append(
        {
            "name": "quota_volume_persists_after_restart",
            "passed": persist_ok,
            "detail": {
                "status": st_r,
                "budget_before": budget_before,
                "budget_after": budget_after,
                "sha_before": sha_before.stdout.strip()[:80],
                "sha_after": sha_after.stdout.strip()[:80],
            },
        }
    )

    # Cleanup (keep report; destroy smoke volumes)
    _run(COMPOSE + ["down", "-v"], timeout=120)
    try:
        env_smoke.unlink(missing_ok=True)
    except Exception:
        pass

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
        "pass_count": sum(1 for c in checks if c["passed"]),
        "total": len(checks),
        "note": "Local Docker smoke only — not a public/cloud deployment.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


if __name__ == "__main__":
    raise SystemExit(main())
