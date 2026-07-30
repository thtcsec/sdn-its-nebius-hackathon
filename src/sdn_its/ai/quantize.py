import os
import sys
import time
import argparse
import torch
import torch.nn as nn
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sdn_its.telemetry import TelemetryDataLoader, LABEL_MAPPING
from sdn_its.ai.tcn_gru import TCNGRUResilienceModel
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

def measure_model_size_mb(path):
    if os.path.exists(path):
        return os.path.getsize(path) / (1024 * 1024)
    return 0.0

def run_quantization(checkpoint_path="models/checkpoints/tcn_gru_best.pt", seq_len=10):
    print("=" * 75)
    print("  MODEL QUANTIZATION & EDGE EFFICIENCY BENCHMARKING")
    print("=" * 75)
    
    device = torch.device("cpu") # Quantization benchmarks are done on CPU for Edge device emulation
    
    # 1. Load data
    loader = TelemetryDataLoader(seq_len=seq_len, batch_size=1) # batch_size=1 to benchmark single-sample edge inference
    _, _, test_dl = loader.get_synthetic_loaders(num_samples=1000)
    
    # 2. Load original model
    if not os.path.exists(checkpoint_path):
        print(f"[!] Checkpoint {checkpoint_path} not found. Please train the model first.")
        return
        
    print(f"[*] Loading original model from checkpoint: {checkpoint_path}")
    ckpt = torch.load(checkpoint_path, map_location=device)
    model = TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING))
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()
    
    tau_threshold = ckpt.get("tau_threshold", 0.5)
    
    # 3. Dynamic Quantization
    print("[*] Removing weight normalization hooks before quantization...")
    for m in list(model.modules()):
        try:
            nn.utils.remove_weight_norm(m)
        except ValueError:
            pass

    print("[*] Applying Dynamic PyTorch Quantization (float32 -> int8) to GRU and Linear layers...")
    quantized_model = torch.quantization.quantize_dynamic(
        model,
        {nn.Linear, nn.GRU},
        dtype=torch.qint8
    )
    quantized_model.eval()
    
    # Save quantized model
    save_dir = os.path.dirname(checkpoint_path)
    quantized_path = os.path.join(save_dir, "tcn_gru_quantized.pt")
    torch.save(quantized_model, quantized_path)
    print(f"[+] Saved quantized model to: {quantized_path}")
    
    # 4. Benchmarking
    def benchmark(eval_model, name):
        y_true_binary = []
        y_pred_binary = []
        inference_times_ms = []
        
        with torch.no_grad():
            for batch_x, batch_y in test_dl:
                batch_x = batch_x.to(device)
                
                # Time single sample inference
                t0 = time.perf_counter()
                x_hat, logits = eval_model(batch_x)
                t1 = time.perf_counter()
                
                inference_times_ms.append((t1 - t0) * 1000.0)
                
                # Reconstruction error
                diff = batch_x - x_hat
                re_scores = torch.sum(diff ** 2, dim=(1, 2)).cpu().numpy()
                is_anomaly_pred = (re_scores > tau_threshold).astype(int)
                
                is_anomaly_true = (batch_y.cpu().numpy() > 0).astype(int)
                
                y_true_binary.extend(is_anomaly_true)
                y_pred_binary.extend(is_anomaly_pred)
                
        y_true_binary = np.array(y_true_binary)
        y_pred_binary = np.array(y_pred_binary)
        
        acc = accuracy_score(y_true_binary, y_pred_binary)
        prec, rec, f1, _ = precision_recall_fscore_support(y_true_binary, y_pred_binary, average='binary', zero_division=0)
        avg_inf_ms = np.mean(inference_times_ms)
        
        return acc, prec, rec, f1, avg_inf_ms

    print("[*] Evaluating original model...")
    orig_acc, orig_prec, orig_rec, orig_f1, orig_latency = benchmark(model, "Original")
    
    print("[*] Evaluating quantized model...")
    quant_acc, quant_prec, quant_rec, quant_f1, quant_latency = benchmark(quantized_model, "Quantized")
    
    orig_size = measure_model_size_mb(checkpoint_path)
    quant_size = measure_model_size_mb(quantized_path)
    
    size_reduction = (orig_size - quant_size) / orig_size * 100.0
    latency_improvement = (orig_latency - quant_latency) / orig_latency * 100.0
    
    # 5. Output comparison results
    print("\n" + "=" * 75)
    print("  QUANTIZATION BENCHMARK SUMMARY")
    print("=" * 75)
    print(f"{'Metric':<30} | {'Original (FP32)':<15} | {'Quantized (INT8)':<15} | {'Change':<10}")
    print("-" * 80)
    print(f"{'Model Size (MB)':<30} | {orig_size:.3f} MB{'':<8} | {quant_size:.3f} MB{'':<8} | -{size_reduction:.1f}%")
    print(f"{'Single-Sample Latency (ms)':<30} | {orig_latency:.3f} ms{'':<8} | {quant_latency:.3f} ms{'':<8} | -{latency_improvement:.1f}%")
    print(f"{'Anomaly Accuracy (%)':<30} | {orig_acc*100:.2f}%{'':<9} | {quant_acc*100:.2f}%{'':<9} | {(quant_acc-orig_acc)*100:+.2f}%")
    print(f"{'Anomaly Recall (%)':<30} | {orig_rec*100:.2f}%{'':<9} | {quant_rec*100:.2f}%{'':<9} | {(quant_rec-orig_rec)*100:+.2f}%")
    print(f"{'Anomaly Precision (%)':<30} | {orig_prec*100:.2f}%{'':<9} | {quant_prec*100:.2f}%{'':<9} | {(quant_prec-orig_prec)*100:+.2f}%")
    print(f"{'Anomaly F1-Score (%)':<30} | {orig_f1*100:.2f}%{'':<9} | {quant_f1*100:.2f}%{'':<9} | {(quant_f1-orig_f1)*100:+.2f}%")
    print("=" * 75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantize TCN-GRU Model and benchmark performance")
    parser.add_argument("--checkpoint", type=str, default="models/checkpoints/tcn_gru_best.pt", help="Path to FP32 model checkpoint")
    args = parser.parse_args()
    
    run_quantization(checkpoint_path=args.checkpoint)
