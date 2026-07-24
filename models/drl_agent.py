import os
import sys
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
from typing import Tuple, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class DQNSetwork(nn.Module):
    """
    Deep Q-Network for SDN V2X Dynamic Action Selection.
    State Space: [RSU_CPU_Load, PacketIn_Rate, Link_Bandwidth_Util, Reconstruction_Error, Anomaly_Confidence] (5 dims)
    Action Space: 
      0: NORMAL_FORWARDING
      1: DYNAMIC_RATE_LIMIT (Throttle bandwidth to 50%)
      2: V2X_PATH_REROUTE (Redirect legitimate vehicle traffic to backup RSU s2)
      3: TARGETED_FLOW_ISOLATION (Apply temporary drop rule)
    """
    def __init__(self, state_dim: int = 5, action_dim: int = 4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim)
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)

class DRLResilienceAgent:
    """
    Deep Reinforcement Learning Agent for Closed-Loop SDN Orchestration.
    """
    def __init__(self, state_dim: int = 5, action_dim: int = 4, lr: float = 0.001, gamma: float = 0.95):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = 0.1 # Exploration rate
        
        self.policy_net = DQNSetwork(state_dim, action_dim)
        self.target_net = DQNSetwork(state_dim, action_dim)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr)
        self.memory = deque(maxlen=2000)
        self.action_names = [
            "NORMAL_FORWARDING",
            "DYNAMIC_RATE_LIMIT",
            "V2X_PATH_REROUTE",
            "TARGETED_FLOW_ISOLATION"
        ]

    def select_action(self, state: np.ndarray) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        
        with torch.no_grad():
            state_t = torch.FloatTensor(state).unsqueeze(0)
            q_values = self.policy_net(state_t)
            return int(torch.argmax(q_values, dim=1).item())

    def get_action_name(self, action_idx: int) -> str:
        return self.action_names[action_idx]

    def compute_reward(self, state: np.ndarray, action: int) -> float:
        # state: [cpu_load, packet_in_rate, bandwidth_util, re_score, confidence]
        cpu_load, pkt_in_rate, bw_util, re_score, confidence = state
        
        is_anomaly = re_score > 53.12
        
        if is_anomaly:
            if action in [1, 3]: # Rate Limit or Isolation
                return +10.0 # High positive reward for containing threat
            elif action == 2: # Reroute
                return +5.0
            else:
                return -15.0 # High penalty for doing nothing under attack
        else: # Benign Traffic
            if action == 0:
                return +8.0 # High reward for keeping normal service uninterrupted
            elif action == 2:
                return +4.0 # Reroute is acceptable
            else:
                return -10.0 # Penalty for unnecessary rate limiting or dropping (False Positive disruption)

if __name__ == "__main__":
    agent = DRLResilienceAgent()
    sample_state = np.array([0.45, 12.0, 0.35, 12.4, 0.1], dtype=np.float32) # Normal state
    action = agent.select_action(sample_state)
    reward = agent.compute_reward(sample_state, action)
    print(f"[+] DRL Agent test state: Action={agent.get_action_name(action)}, Reward={reward:.1f}")
