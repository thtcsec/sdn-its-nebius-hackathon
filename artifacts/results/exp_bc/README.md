# Experiments B/C — camera-assisted fusion

```bash
python scripts/exp_bc_camera_fusion.py
```

Produces `exp_bc_fusion.json` with scenarios:

| Case | Camera | Network | Expect |
|------|--------|---------|--------|
| A legitimate surge | rush | DDoS label, distributed | preserve + FP corrected |
| B PacketIn flood | stable | DDoS, single-source | temporary DROP |
| C mixed | rush + ped | DDoS, single-source | isolate source only |

Synthetic analytics by default — claim is **explainable multimodal policy**, not detector mAP.
