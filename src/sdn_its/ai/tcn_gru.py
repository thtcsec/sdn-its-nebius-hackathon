r"""
tcn_gru.py - PyTorch Implementation of Hybrid TCN-GRU Autoencoder & Classifier

Combines Temporal Convolutional Networks (TCN) for multi-scale time-series feature extraction
with a Gated Recurrent Unit (GRU) Autoencoder for normal telemetry reconstruction error scoring,
and a Softmax classification head for fault & intrusion category identification.

Mathematical Formulations (from IEDE Report):
1. Hidden Feature Representation: H_i(x) = ReLU(W_i^T x + b_i)
2. Reconstruction Error: RE(x) = ||x - \hat{x}||_2^2
3. Adaptive Decision Threshold: \tau = \mu_{RE} + k \cdot \sigma_{RE}
4. Multi-class Attack Probability: P(y = c | x) = exp(z_c) / \sum_{j=1}^C exp(z_j)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Any, List


class Chomp1d(nn.Module):
    """Trims trailing padding to enforce causal temporal convolutions."""
    def __init__(self, chomp_size: int):
        super(Chomp1d, self).__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, :-self.chomp_size].contiguous() if self.chomp_size > 0 else x


class TemporalBlock(nn.Module):
    """Single Residual Block in Temporal Convolutional Network (TCN)."""
    def __init__(self, n_inputs: int, n_outputs: int, kernel_size: int, stride: int, 
                 dilation: int, padding: int, dropout: float = 0.2):
        super(TemporalBlock, self).__init__()
        
        # Dilated Causal Conv 1
        self.conv1 = nn.utils.weight_norm(
            nn.Conv1d(n_inputs, n_outputs, kernel_size, stride=stride, padding=padding, dilation=dilation)
        )
        self.chomp1 = Chomp1d(padding)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)

        # Dilated Causal Conv 2
        self.conv2 = nn.utils.weight_norm(
            nn.Conv1d(n_outputs, n_outputs, kernel_size, stride=stride, padding=padding, dilation=dilation)
        )
        self.chomp2 = Chomp1d(padding)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)

        self.net = nn.Sequential(
            self.conv1, self.chomp1, self.relu1, self.dropout1,
            self.conv2, self.chomp2, self.relu2, self.dropout2
        )
        
        # 1x1 Conv residual matching layer if channels differ
        self.downsample = nn.Conv1d(n_inputs, n_outputs, 1) if n_inputs != n_outputs else None
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.net(x)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out + res)


class TemporalConvNet(nn.Module):
    """Multi-layer Dilated Temporal Convolutional Network."""
    def __init__(self, num_inputs: int, num_channels: List[int], kernel_size: int = 3, dropout: float = 0.2):
        super(TemporalConvNet, self).__init__()
        layers = []
        num_levels = len(num_channels)
        for i in range(num_levels):
            dilation_size = 2 ** i
            in_channels = num_inputs if i == 0 else num_channels[i-1]
            out_channels = num_channels[i]
            padding = (kernel_size - 1) * dilation_size
            layers.append(
                TemporalBlock(in_channels, out_channels, kernel_size, stride=1,
                              dilation=dilation_size, padding=padding, dropout=dropout)
            )
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Expected input shape: [batch_size, num_features, seq_len]
        return self.network(x)


class GRUAutoencoder(nn.Module):
    """Encoder-Decoder GRU for Sequence Reconstruction."""
    def __init__(self, input_dim: int, hidden_dim: int, num_layers: int = 1):
        super(GRUAutoencoder, self).__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.encoder = nn.GRU(input_dim, hidden_dim, num_layers, batch_first=True)
        self.decoder = nn.GRU(hidden_dim, hidden_dim, num_layers, batch_first=True)
        self.reconstruct_head = nn.Linear(hidden_dim, input_dim)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # x shape: [batch_size, seq_len, input_dim]
        batch_size, seq_len, _ = x.shape
        
        # Encode
        _, hidden = self.encoder(x)  # hidden: [num_layers, batch_size, hidden_dim]
        
        # Decoder input: repeat hidden state across time sequence
        decoder_input = hidden[-1].unsqueeze(1).repeat(1, seq_len, 1)
        dec_out, _ = self.decoder(decoder_input, hidden)
        
        # Reconstruct original input features
        x_hat = self.reconstruct_head(dec_out)
        return x_hat, hidden[-1]


class TCNGRUResilienceModel(nn.Module):
    """
    Hybrid TCN-GRU Network Resilience Model.
    
    Extracts multi-scale temporal features with TCN, reconstructs telemetry sequence via GRU Autoencoder,
    and classifies fault/attack categories via MLP classifier.
    """
    def __init__(
        self,
        num_features: int = 10,
        tcn_channels: List[int] = [32, 64],
        gru_hidden_dim: int = 64,
        num_classes: int = 5,
        kernel_size: int = 3,
        dropout: float = 0.2
    ):
        super(TCNGRUResilienceModel, self).__init__()
        
        self.num_features = num_features
        self.num_classes = num_classes
        
        # 1. TCN Feature Extractor
        self.tcn = TemporalConvNet(num_inputs=num_features, num_channels=tcn_channels, 
                                   kernel_size=kernel_size, dropout=dropout)
        
        # 2. GRU Autoencoder on top of TCN features
        tcn_output_dim = tcn_channels[-1]
        self.autoencoder = GRUAutoencoder(input_dim=tcn_output_dim, hidden_dim=gru_hidden_dim)
        
        # Feature dimension adjustment back to raw feature space for reconstruction error check
        self.tcn_decoder = nn.Linear(tcn_output_dim, num_features)
        
        # 3. Softmax Classification Head (P(y=c | x) = exp(z_c) / \sum exp(z_j))
        self.classifier = nn.Sequential(
            nn.Linear(gru_hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, num_classes)
        )
        
        # Calibrated RE threshold parameters
        self.register_buffer("mu_re", torch.tensor(0.0))
        self.register_buffer("std_re", torch.tensor(1.0))

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward Pass.
        
        Args:
            x: Input tensor of shape [batch_size, seq_len, num_features]
            
        Returns:
            x_hat: Reconstructed sequence [batch_size, seq_len, num_features]
            logits: Unnormalized class predictions [batch_size, num_classes]
        """
        batch_size, seq_len, num_features = x.shape
        
        # TCN expects [batch_size, channels, seq_len]
        x_tcn_in = x.transpose(1, 2)
        tcn_feats = self.tcn(x_tcn_in)  # [batch_size, tcn_channels[-1], seq_len]
        
        # Back to [batch_size, seq_len, tcn_channels[-1]] for GRU Autoencoder
        gru_in = tcn_feats.transpose(1, 2)
        gru_reconstructed_feats, latent_h = self.autoencoder(gru_in)
        
        # Reconstruct raw input space
        x_hat = self.tcn_decoder(gru_reconstructed_feats)
        
        # Classification prediction from latent GRU state
        logits = self.classifier(latent_h)
        
        return x_hat, logits

    def compute_reconstruction_error(self, x: torch.Tensor, x_hat: torch.Tensor) -> torch.Tensor:
        r"""
        Computes L2 squared norm reconstruction error: RE(x) = ||x - \hat{x}||_2^2
        Returns tensor of shape [batch_size].
        """
        diff = x - x_hat
        re_per_sample = torch.mean(torch.sum(diff ** 2, dim=(1, 2)))
        return re_per_sample

    def calibrate_threshold(self, normal_x: torch.Tensor, k: float = 2.0) -> float:
        r"""
        Calibrates adaptive decision threshold: \tau = \mu_{RE} + k \cdot \sigma_{RE}
        """
        self.eval()
        with torch.no_grad():
            x_hat, _ = self.forward(normal_x)
            diff = normal_x - x_hat
            sample_res = torch.sum(diff ** 2, dim=(1, 2))
            
            self.mu_re = torch.mean(sample_res)
            self.std_re = torch.std(sample_res)
            tau = (self.mu_re + k * self.std_re).item()
            return tau

    def predict_anomaly(self, x: torch.Tensor, k: float = 2.0) -> Dict[str, Any]:
        """
        Evaluates input sequence for anomaly scoring and multiclass fault classification.
        """
        self.eval()
        with torch.no_grad():
            x_hat, logits = self.forward(x)
            
            # Reconstruction error
            diff = x - x_hat
            re_scores = torch.sum(diff ** 2, dim=(1, 2))  # [batch_size]
            
            tau = (self.mu_re + k * self.std_re).item()
            is_anomaly = re_scores > tau
            
            # Probabilities P(y=c | x)
            probs = F.softmax(logits, dim=-1)
            pred_classes = torch.argmax(probs, dim=-1)
            
            return {
                "reconstruction_error": re_scores.cpu().numpy(),
                "threshold_tau": tau,
                "is_anomaly": is_anomaly.cpu().numpy(),
                "predicted_class": pred_classes.cpu().numpy(),
                "class_probabilities": probs.cpu().numpy()
            }


if __name__ == "__main__":
    # Sanity Check Script
    print("Testing TCNGRUResilienceModel PyTorch implementation...")
    model = TCNGRUResilienceModel(num_features=10, num_classes=5)
    dummy_input = torch.randn(32, 10, 10)  # batch=32, seq=10, features=10
    
    x_hat, logits = model(dummy_input)
    re_loss = model.compute_reconstruction_error(dummy_input, x_hat)
    
    print(f"[OK] Forward pass successful!")
    print(f"     Input shape:      {dummy_input.shape}")
    print(f"     Reconstructed:    {x_hat.shape}")
    print(f"     Class Logits:     {logits.shape}")
    print(f"     Sample RE Loss:   {re_loss.item():.4f}")
    
    # Test Anomaly Prediction
    tau = model.calibrate_threshold(dummy_input[:16])
    result = model.predict_anomaly(dummy_input)
    print(f"[OK] Calibrated threshold \\tau: {tau:.4f}")
    print(f"     Anomalies detected: {result['is_anomaly'].sum()} / 32")
