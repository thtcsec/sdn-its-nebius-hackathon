"""
Lightweight temporal Transformer encoder baseline for flow-window classification.

Used as an ablation peer to TCN-GRU (not a drop-in replacement for edge deploy).
Reconstruction head mirrors the autoencoder setup so RE-based anomaly scoring stays comparable.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn


class TemporalTransformerModel(nn.Module):
    """Transformer-encoder AE + classifier over (B, T, F) telemetry windows."""

    def __init__(
        self,
        num_features: int = 10,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 128,
        num_classes: int = 5,
        dropout: float = 0.1,
        max_seq_len: int = 64,
    ):
        super().__init__()
        self.num_features = num_features
        self.d_model = d_model
        self.input_proj = nn.Linear(num_features, d_model)
        pe = self._sinusoidal_pe(max_seq_len, d_model)
        self.register_buffer("pos_encoding", pe, persistent=False)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.recon_head = nn.Linear(d_model, num_features)
        self.classifier = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, num_classes),
        )
        # Compat with TCN-GRU threshold helpers (optional use)
        self.register_buffer("mu_re", torch.tensor(0.0))
        self.register_buffer("std_re", torch.tensor(1.0))

    @staticmethod
    def _sinusoidal_pe(max_len: int, d_model: int) -> torch.Tensor:
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        return pe.unsqueeze(0)  # (1, T, D)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: (B, T, F)
        h = self.input_proj(x)
        t = h.size(1)
        h = h + self.pos_encoding[:, :t, :]
        h = self.encoder(h)
        recon = self.recon_head(h)
        logits = self.classifier(h[:, -1, :])
        return recon, logits

    @torch.no_grad()
    def calibrate_threshold(self, normal_x: torch.Tensor, k: float = 2.0) -> float:
        x_hat, _ = self.forward(normal_x)
        re = torch.sum((normal_x - x_hat) ** 2, dim=(1, 2))
        mu = re.mean()
        std = re.std(unbiased=False).clamp_min(1e-6)
        self.mu_re.copy_(mu)
        self.std_re.copy_(std)
        return float((mu + k * std).item())
