# Benchmarks

Automated edge metrics live under `benchmark/`:

| Module | Metric |
|--------|--------|
| `benchmark/cpu.py` | CPU inference cost |
| `benchmark/latency.py` | Per-sample / IDL / \(T_{response}\) |
| `benchmark/memory.py` | Model size / footprint |
| `benchmark/throughput.py` | Samples/sec |

Training evaluation: `python -m sdn_its.ai.evaluate`  
Quantization: `python -m sdn_its.ai.quantize`  
Architecture comparison: `python -m sdn_its.ai.compare`

CI runs a lightweight sample-tensor latency job (`.github/workflows/benchmark.yml`) without Mininet.
