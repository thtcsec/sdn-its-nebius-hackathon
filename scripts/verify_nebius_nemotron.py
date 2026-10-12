#!/usr/bin/env python3
"""Real Nebius Token Factory smoke test for NVIDIA Nemotron.

Loads credentials from repository-root ``.env`` via ``sdn_its.utils.env``
(process env vars take precedence). Never prints the API key.

Evidence classes:
  - real_api: authenticated HTTP succeeded
  - blocked_no_credentials: NEBIUS_API_KEY missing (exit 2)
  - api_error: HTTP/provider failure (exit 1) — see error_class
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sdn_its.utils.env import ensure_repo_env, nebius_config_summary  # noqa: E402
from sdn_its.llm.nebius_client import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    NebiusAPIError,
    NebiusConfigError,
    NebiusTokenFactoryClient,
    resolve_base_url,
    resolve_model,
)


def main() -> int:
    ensure_repo_env()
    parser = argparse.ArgumentParser(description="Verify real Nebius Nemotron inference")
    parser.add_argument("--model", default=None, help="Override NEBIUS_MODEL / default")
    parser.add_argument("--base-url", default=None, help="Override NEBIUS_BASE_URL / default")
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "nebius_verify_last.json"),
        help="Write non-secret evidence JSON",
    )
    args = parser.parse_args()

    model = resolve_model(args.model)
    base_url = resolve_base_url(args.base_url)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    record: dict = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "requested_model": model,
        "base_url": base_url,
        "config": nebius_config_summary(),
        "evidence_class": None,
        "ok": False,
    }

    try:
        client = NebiusTokenFactoryClient(base_url=base_url, model=model)
        models = client.list_models()
        data = models.get("data") if isinstance(models, dict) else None
        ids: list[str] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id"):
                    ids.append(str(item["id"]))
        nemotron_ids = [i for i in ids if "nemotron" in i.lower()]
        record["list_models"] = {
            "ok": True,
            "count": len(ids) if ids else (len(data) if isinstance(data, list) else None),
            "latency_ms": models.get("_client_latency_ms") if isinstance(models, dict) else None,
            "requested_model_listed": model in ids if ids else None,
            "nemotron_ids_sample": nemotron_ids[:12],
        }

        completion = client.chat_completions(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Return exactly this JSON object and nothing else: "
                        '{"ping":"pong","model_family":"nemotron","ok":true}'
                    ),
                }
            ],
            temperature=0.0,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        record.update(
            {
                "ok": True,
                "evidence_class": "real_api",
                "http_status": completion.request_meta.get("http_status"),
                "completion_id": completion.raw_id,
                "response_model": completion.model,
                "finish_reason": completion.finish_reason,
                "usage": completion.usage,
                "latency_ms": completion.latency_ms,
                "estimated_cost_usd": completion.estimated_cost_usd(),
                "content_preview": (completion.content or "")[:200],
            }
        )
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps({k: record[k] for k in record if k != "content_preview"}, indent=2))
        print("content_preview:", record["content_preview"])
        print(f"wrote {out_path}")
        return 0
    except NebiusConfigError as exc:
        record["evidence_class"] = "blocked_no_credentials"
        record["error_class"] = getattr(exc, "error_class", "config")
        record["error"] = str(exc)
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record, indent=2))
        print("BLOCKER: set NEBIUS_API_KEY in repo-root .env or process env.", file=sys.stderr)
        return 2
    except NebiusAPIError as exc:
        record["evidence_class"] = "api_error"
        record["error_class"] = exc.error_class
        record["error"] = str(exc)
        record["http_status"] = exc.status_code
        record["error_body_redacted"] = exc.body
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
