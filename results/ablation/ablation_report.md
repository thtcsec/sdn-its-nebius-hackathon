# Ablation: Architectures × k·σ

_Generated: 2026-07-30 10:54:26 UTC_

## Metrics

| Key | Value |
|-----|-------|
| `RNN.accuracy_cls` | 0.5167 |
| `RNN.precision` | 0.9667 |
| `RNN.recall` | 1.0000 |
| `RNN.f1` | 0.9831 |
| `RNN.tau` | 59.7763 |
| `RNN.latency_ms_per_sample` | 0.0146 |
| `RNN.params` | 1903 |
| `LSTM.accuracy_cls` | 0.7167 |
| `LSTM.precision` | 0.9667 |
| `LSTM.recall` | 1.0000 |
| `LSTM.f1` | 0.9831 |
| `LSTM.tau` | 66.2153 |
| `LSTM.latency_ms_per_sample` | 0.1216 |
| `LSTM.params` | 6127 |
| `GRU.accuracy_cls` | 0.1333 |
| `GRU.precision` | 0.9355 |
| `GRU.recall` | 1.0000 |
| `GRU.f1` | 0.9667 |
| `GRU.tau` | 61.7763 |
| `GRU.latency_ms_per_sample` | 0.0344 |
| `GRU.params` | 4719 |
| `TCN-GRU.accuracy_cls` | 0.5167 |
| `TCN-GRU.precision` | 0.9355 |
| `TCN-GRU.recall` | 1.0000 |
| `TCN-GRU.f1` | 0.9667 |
| `TCN-GRU.tau` | 66.2386 |
| `TCN-GRU.latency_ms_per_sample` | 0.3615 |
| `TCN-GRU.params` | 82287 |
| `tau_k=1.0.tau` | 58.9258 |
| `tau_k=1.0.f1` | 0.9508 |
| `tau_k=1.0.precision` | 0.9062 |
| `tau_k=1.0.recall` | 1.0000 |
| `tau_k=1.0.rush_false_block_rate` | 1.0000 |
| `tau_k=2.0.tau` | 66.2386 |
| `tau_k=2.0.f1` | 0.9667 |
| `tau_k=2.0.precision` | 0.9355 |
| `tau_k=2.0.recall` | 1.0000 |
| `tau_k=2.0.rush_false_block_rate` | 1.0000 |
| `tau_k=3.0.tau` | 73.5513 |
| `tau_k=3.0.f1` | 1.0000 |
| `tau_k=3.0.precision` | 1.0000 |
| `tau_k=3.0.recall` | 1.0000 |
| `tau_k=3.0.rush_false_block_rate` | 1.0000 |

## Method

Baselines quick-trained on synthetic telemetry; TCN-GRU loads checkpoint when present. Binary anomaly = RE > τ. Rush-hour false-block = fraction of RushHour windows over τ.


## Raw JSON

```json
{
  "RNN.accuracy_cls": 0.5166666666666667,
  "RNN.precision": 0.9666666666666667,
  "RNN.recall": 1.0,
  "RNN.f1": 0.9830508474576272,
  "RNN.tau": 59.77627691347522,
  "RNN.latency_ms_per_sample": 0.014627232303610072,
  "RNN.params": 1903,
  "LSTM.accuracy_cls": 0.7166666666666667,
  "LSTM.precision": 0.9666666666666667,
  "LSTM.recall": 1.0,
  "LSTM.f1": 0.9830508474576272,
  "LSTM.tau": 66.21528414017477,
  "LSTM.latency_ms_per_sample": 0.12157499973649724,
  "LSTM.params": 6127,
  "GRU.accuracy_cls": 0.13333333333333333,
  "GRU.precision": 0.9354838709677419,
  "GRU.recall": 1.0,
  "GRU.f1": 0.9666666666666667,
  "GRU.tau": 61.77626357713366,
  "GRU.latency_ms_per_sample": 0.03436941902431759,
  "GRU.params": 4719,
  "TCN-GRU.accuracy_cls": 0.5166666666666667,
  "TCN-GRU.precision": 0.9354838709677419,
  "TCN-GRU.recall": 1.0,
  "TCN-GRU.f1": 0.9666666666666667,
  "TCN-GRU.tau": 66.2385647455403,
  "TCN-GRU.latency_ms_per_sample": 0.36149821426079143,
  "TCN-GRU.params": 82287,
  "tau_k=1.0.tau": 58.92584756520809,
  "tau_k=1.0.f1": 0.9508196721311475,
  "tau_k=1.0.precision": 0.90625,
  "tau_k=1.0.recall": 1.0,
  "tau_k=1.0.rush_false_block_rate": 1.0,
  "tau_k=2.0.tau": 66.2385647455403,
  "tau_k=2.0.f1": 0.9666666666666667,
  "tau_k=2.0.precision": 0.9354838709677419,
  "tau_k=2.0.recall": 1.0,
  "tau_k=2.0.rush_false_block_rate": 1.0,
  "tau_k=3.0.tau": 73.5512819258725,
  "tau_k=3.0.f1": 1.0,
  "tau_k=3.0.precision": 1.0,
  "tau_k=3.0.recall": 1.0,
  "tau_k=3.0.rush_false_block_rate": 1.0
}
```
