#!/usr/bin/env python
"""Run all micro-benchmarks and write results/benchmark_report.md."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmark import cpu, latency, latency_cdf, memory, throughput  # noqa: E402
from sdn_its.ai.report import write_markdown_report  # noqa: E402


def main():
    results = {
        "latency": latency.run(n_iters=40),
        "latency_cdf": {k: v for k, v in latency_cdf.run(n_iters=100).items() if k != "samples_ms"},
        "throughput": throughput.run(batch_size=32, n_batches=20),
        "cpu": cpu.run(n_iters=30),
        "memory": memory.run(),
    }
    out = ROOT / "results" / "benchmark_report.md"
    flat = {}
    for section, data in results.items():
        if isinstance(data, dict):
            for k, v in data.items():
                flat[f"{section}.{k}"] = v
        else:
            flat[section] = data
    path = write_markdown_report(flat, out, title="Edge Micro-benchmark Report")
    (ROOT / "results" / "benchmark.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"[+] {path}")


if __name__ == "__main__":
    main()
