#!/usr/bin/env python3
"""Real Nebius Token Factory smoke test for NVIDIA Nemotron.

Evidence classes:
  - real_api: authenticated HTTP succeeded
  - blocked_no_credentials: NEBIUS_API_KEY missing (exit 2)
  - api_error: HTTP/provider failure (exit 1)

Never prints the API key. Never fabricates success.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from sdn_its.llm.nebius_client import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    NebiusAPIError,
    NebiusConfigError,
    NebiusTokenFactoryClient,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify real Nebius Nemotron inference")
    parser.add_argument("--model", default=os.environ.get("NEBIUS_MODEL") or DEFAULT_MODEL)
    parser.add_argument("--base-url", default=os.environ.get("NEBIUS_BASE_URL") or DEFAULT_BASE_URL)
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "hackathon" / "nebius_verify_last.json"),
        help="Write non-secret evidence JSON",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    record: dict = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "requested_model": args.model,
        "base_url": args.base_url,
        "evidence_class": None,
        "ok": False,
    }

    try:
        client = NebiusTokenFactoryClient(base_url=args.base_url, model=args.model)
        models = client.list_models()
        # Do not dump full catalog into artifact — only counts / ids sample
        data = models.get("data") if isinstance(models, dict) else None
        record["list_models"] = {
            "ok": True,
            "count": len(data) if isinstance(data, list) else None,
            "latency_ms": models.get("_client_latency_ms") if isinstance(models, dict) else None,
        }

        completion = client.chat_completions(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Reply with JSON only: "
                        '{"ping":"pong","model_family":"nemotron","ok":true}'
                    ),
                }
            ],
            temperature=0.0,
            max_tokens=64,
            response_format={"type": "json_object"},
        )
        record.update(
            {
                "ok": True,
                "evidence_class": "real_api",
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
        record["error"] = str(exc)
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record, indent=2))
        print("BLOCKER: set NEBIUS_API_KEY to run a real inference call.", file=sys.stderr)
        return 2
    except NebiusAPIError as exc:
        record["evidence_class"] = "api_error"
        record["error"] = str(exc)
        record["http_status"] = exc.status_code
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(json.dumps(record, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
