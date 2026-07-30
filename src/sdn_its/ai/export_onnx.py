"""Export TCN-GRU to ONNX and TorchScript."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import torch

from sdn_its.ai.infer import load_model
from sdn_its.utils.paths import PROJECT_ROOT


def export_onnx(
    checkpoint: str = "models/checkpoints/tcn_gru_best.pt",
    out_path: str = "models/exported/onnx/tcn_gru.onnx",
    opset: int = 17,
    seq_len: int = 10,
    num_features: int = 10,
) -> dict[str, Any]:
    device = torch.device("cpu")
    ckpt = checkpoint if Path(checkpoint).is_absolute() else str(PROJECT_ROOT / checkpoint)
    out = Path(out_path if Path(out_path).is_absolute() else PROJECT_ROOT / out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    model, tau = load_model(ckpt, device)
    model.eval()
    dummy = torch.randn(1, seq_len, num_features, dtype=torch.float32)

    torch.onnx.export(
        model,
        dummy,
        str(out),
        input_names=["telemetry_window"],
        output_names=["reconstruction", "logits"],
        dynamic_axes={
            "telemetry_window": {0: "batch"},
            "reconstruction": {0: "batch"},
            "logits": {0: "batch"},
        },
        opset_version=opset,
        dynamo=False,
    )
    meta = {
        "format": "onnx",
        "path": str(out.relative_to(PROJECT_ROOT)),
        "bytes": out.stat().st_size,
        "tau": tau,
        "opset": opset,
        "input_shape": [1, seq_len, num_features],
    }
    (out.with_suffix(".json")).write_text(
        __import__("json").dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


def export_torchscript(
    checkpoint: str = "models/checkpoints/tcn_gru_best.pt",
    out_path: str = "models/exported/torchscript/tcn_gru.ts",
    seq_len: int = 10,
    num_features: int = 10,
) -> dict[str, Any]:
    device = torch.device("cpu")
    ckpt = checkpoint if Path(checkpoint).is_absolute() else str(PROJECT_ROOT / checkpoint)
    out = Path(out_path if Path(out_path).is_absolute() else PROJECT_ROOT / out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    model, tau = load_model(ckpt, device)
    model.eval()
    dummy = torch.randn(1, seq_len, num_features, dtype=torch.float32)
    scripted = torch.jit.trace(model, dummy)
    scripted.save(str(out))
    meta = {
        "format": "torchscript",
        "path": str(out.relative_to(PROJECT_ROOT)),
        "bytes": out.stat().st_size,
        "tau": tau,
        "input_shape": [1, seq_len, num_features],
    }
    (out.with_suffix(".json")).write_text(
        __import__("json").dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


def main():
    parser = argparse.ArgumentParser(description="Export TCN-GRU to ONNX / TorchScript")
    parser.add_argument("--checkpoint", default="models/checkpoints/tcn_gru_best.pt")
    parser.add_argument("--format", choices=("onnx", "torchscript", "both"), default="both")
    parser.add_argument("--opset", type=int, default=17)
    args = parser.parse_args()
    if args.format in ("onnx", "both"):
        try:
            print("[+] ONNX:", export_onnx(args.checkpoint, opset=args.opset))
        except Exception as exc:
            print(f"[!] ONNX skipped: {exc}")
    if args.format in ("torchscript", "both"):
        print("[+] TorchScript:", export_torchscript(args.checkpoint))


if __name__ == "__main__":
    main()
