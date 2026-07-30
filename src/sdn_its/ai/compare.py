import os
import sys
import time
import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Any, Tuple
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sdn_its.telemetry import TelemetryDataLoader, LABEL_MAPPING
from sdn_its.ai.tcn_gru import TCNGRUResilienceModel

# Baseline Architectural Variants for Benchmark Comparison

class VanillaRNNModel(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=32, num_classes=6):
        super().__init__()
        self.rnn = nn.RNN(input_dim, hidden_dim, batch_first=True)
        self.fc_recon = nn.Linear(hidden_dim, input_dim)
        self.classifier = nn.Linear(hidden_dim, num_classes)
        
    def forward(self, x):
        out, _ = self.rnn(x)
        last_out = out[:, -1, :]
        recon = self.fc_recon(out)
        logits = self.classifier(last_out)
        return recon, logits

class LSTMModel(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=32, num_classes=6):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.fc_recon = nn.Linear(hidden_dim, input_dim)
        self.classifier = nn.Linear(hidden_dim, num_classes)
        
    def forward(self, x):
        out, _ = self.lstm(x)
        last_out = out[:, -1, :]
        recon = self.fc_recon(out)
        logits = self.classifier(last_out)
        return recon, logits

class GRUOnlyModel(nn.Module):
    def __init__(self, input_dim=10, hidden_dim=32, num_classes=6):
        super().__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, batch_first=True)
        self.fc_recon = nn.Linear(hidden_dim, input_dim)
        self.classifier = nn.Linear(hidden_dim, num_classes)
        
    def forward(self, x):
        out, _ = self.gru(x)
        last_out = out[:, -1, :]
        recon = self.fc_recon(out)
        logits = self.classifier(last_out)
        return recon, logits

def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

def benchmark_models():
    print("=" * 85)
    print("  EMPIRICAL DEEP LEARNING ARCHITECTURE COMPARISON BENCHMARK")
    print("=" * 85)
    
    device = torch.device("cpu")
    loader = TelemetryDataLoader(seq_len=10, batch_size=32)
    train_dl, val_dl, test_dl = loader.get_synthetic_loaders(num_samples=1000)
    
    models = {
        "Vanilla RNN": VanillaRNNModel(input_dim=10, num_classes=len(LABEL_MAPPING)),
        "Standard LSTM": LSTMModel(input_dim=10, num_classes=len(LABEL_MAPPING)),
        "GRU Autoencoder": GRUOnlyModel(input_dim=10, num_classes=len(LABEL_MAPPING)),
        "Proposed TCN-GRU": TCNGRUResilienceModel(num_features=10, num_classes=len(LABEL_MAPPING))
    }
    
    # Load trained weights for TCN-GRU if exists
    ckpt_path = "models/checkpoints/tcn_gru_best.pt"
    if os.path.exists(ckpt_path):
        ckpt = torch.load(ckpt_path, map_location=device)
        models["Proposed TCN-GRU"].load_state_dict(ckpt["model_state_dict"])
    
    results = {}
    
    for name, model in models.items():
        model.to(device)
        model.eval()
        
        y_true_bin = []
        y_pred_bin = []
        latencies = []
        
        with torch.no_grad():
            for batch_x, batch_y in test_dl:
                batch_x = batch_x.to(device)
                
                t0 = time.perf_counter()
                x_hat, logits = model(batch_x)
                t1 = time.perf_counter()
                
                latencies.append((t1 - t0) * 1000.0 / batch_x.size(0))
                
                diff = batch_x - x_hat
                re_scores = torch.sum(diff ** 2, dim=(1, 2)).cpu().numpy()
                
                # Threshold calibration
                thresh = 0.5 if name != "Proposed TCN-GRU" else ckpt.get("tau_threshold", 53.12)
                pred_anom = (re_scores > thresh).astype(int)
                true_anom = (batch_y.cpu().numpy() > 0).astype(int)
                
                y_true_bin.extend(true_anom)
                y_pred_bin.extend(pred_anom)
                
        y_true_bin = np.array(y_true_bin)
        y_pred_bin = np.array(y_pred_bin)
        
        acc = accuracy_score(y_true_bin, y_pred_bin) * 100.0
        prec, rec, f1, _ = precision_recall_fscore_support(y_true_bin, y_pred_bin, average='binary', zero_division=0)
        
        results[name] = {
            "params": count_parameters(model),
            "acc": acc,
            "rec": rec * 100.0,
            "prec": prec * 100.0,
            "f1": f1 * 100.0,
            "latency": np.mean(latencies)
        }
        
    print(f"{'Architecture':<20} | {'Params':<10} | {'Accuracy':<10} | {'Recall':<10} | {'Precision':<10} | {'F1-Score':<10} | {'Latency/Pkt':<12}")
    print("-" * 92)
    for name, r in results.items():
        print(f"{name:<20} | {r['params']:<10} | {r['acc']:.2f}%{'':<3} | {r['rec']:.2f}%{'':<3} | {r['prec']:.2f}%{'':<3} | {r['f1']:.2f}%{'':<3} | {r['latency']:.3f} ms")
    print("=" * 92)

if __name__ == "__main__":
    benchmark_models()
