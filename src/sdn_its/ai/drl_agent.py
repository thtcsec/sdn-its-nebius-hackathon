"""DRL agent for Detect→Contain→Rollback action selection with replay training."""

from __future__ import annotations

import random
from collections import deque
from typing import Deque, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim


class DQNNetwork(nn.Module):
    """
    Deep Q-Network for SDN V2X dynamic action selection.
    State: [RSU_CPU, PacketIn_Rate, Link_BW_Util, RE, Confidence]
    Actions: NORMAL | RATE_LIMIT | REROUTE | ISOLATE
    """

    def __init__(self, state_dim: int = 5, action_dim: int = 4):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# Back-compat alias (typo in earlier revisions)
DQNSetwork = DQNNetwork


class DRLResilienceAgent:
    """Closed-loop DRL agent with experience replay + target network."""

    ACTION_NAMES = [
        "NORMAL_FORWARDING",
        "DYNAMIC_RATE_LIMIT",
        "V2X_PATH_REROUTE",
        "TARGETED_FLOW_ISOLATION",
    ]

    def __init__(
        self,
        state_dim: int = 5,
        action_dim: int = 4,
        lr: float = 1e-3,
        gamma: float = 0.95,
        epsilon: float = 0.15,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.995,
        memory_size: int = 5000,
        batch_size: int = 32,
        target_sync: int = 50,
        tau_threshold: float = 53.12,
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_sync = target_sync
        self.tau_threshold = tau_threshold
        self._steps = 0

        self.policy_net = DQNNetwork(state_dim, action_dim)
        self.target_net = DQNNetwork(state_dim, action_dim)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=lr)
        self.memory: Deque[Tuple[np.ndarray, int, float, np.ndarray, bool]] = deque(maxlen=memory_size)
        self.action_names = list(self.ACTION_NAMES)
        self.train_losses: List[float] = []

    def select_action(self, state: np.ndarray, explore: bool = True) -> int:
        if explore and random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        with torch.no_grad():
            state_t = torch.as_tensor(state, dtype=torch.float32).unsqueeze(0)
            q_values = self.policy_net(state_t)
            return int(torch.argmax(q_values, dim=1).item())

    def get_action_name(self, action_idx: int) -> str:
        return self.action_names[action_idx]

    def compute_reward(self, state: np.ndarray, action: int, tau: Optional[float] = None) -> float:
        cpu_load, pkt_in_rate, bw_util, re_score, confidence = state
        thr = self.tau_threshold if tau is None else float(tau)
        is_anomaly = re_score > thr
        if is_anomaly:
            if action in (1, 3):
                return 10.0 + 2.0 * float(confidence)
            if action == 2:
                return 5.0
            return -15.0
        if action == 0:
            return 8.0
        if action == 2:
            return 4.0
        return -10.0  # false-positive disruption

    def remember(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool = False,
    ) -> None:
        self.memory.append(
            (
                np.asarray(state, dtype=np.float32),
                int(action),
                float(reward),
                np.asarray(next_state, dtype=np.float32),
                bool(done),
            )
        )

    def train_step(self) -> Optional[float]:
        if len(self.memory) < self.batch_size:
            return None
        batch = random.sample(self.memory, self.batch_size)
        states = torch.as_tensor(np.stack([b[0] for b in batch]), dtype=torch.float32)
        actions = torch.as_tensor([b[1] for b in batch], dtype=torch.int64).unsqueeze(1)
        rewards = torch.as_tensor([b[2] for b in batch], dtype=torch.float32)
        next_states = torch.as_tensor(np.stack([b[3] for b in batch]), dtype=torch.float32)
        dones = torch.as_tensor([b[4] for b in batch], dtype=torch.float32)

        q_values = self.policy_net(states).gather(1, actions).squeeze(1)
        with torch.no_grad():
            next_q = self.target_net(next_states).max(1)[0]
            targets = rewards + self.gamma * next_q * (1.0 - dones)

        loss = nn.functional.mse_loss(q_values, targets)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy_net.parameters(), 5.0)
        self.optimizer.step()

        self._steps += 1
        if self._steps % self.target_sync == 0:
            self.target_net.load_state_dict(self.policy_net.state_dict())
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        val = float(loss.item())
        self.train_losses.append(val)
        return val

    def train_episodes(self, episodes: int = 50, steps_per_ep: int = 40) -> dict:
        """Synthetic closed-loop training for demo / exp05."""
        rewards_hist = []
        for _ in range(episodes):
            state = self._sample_state(attack=False)
            ep_reward = 0.0
            for t in range(steps_per_ep):
                attack = t > steps_per_ep // 3 and t < 2 * steps_per_ep // 3
                state = self._sample_state(attack=attack)
                action = self.select_action(state)
                reward = self.compute_reward(state, action)
                next_state = self._sample_state(attack=attack)
                done = t == steps_per_ep - 1
                self.remember(state, action, reward, next_state, done)
                self.train_step()
                ep_reward += reward
                state = next_state
            rewards_hist.append(ep_reward)
        return {
            "episodes": episodes,
            "mean_reward": float(np.mean(rewards_hist)) if rewards_hist else 0.0,
            "final_epsilon": self.epsilon,
            "memory": len(self.memory),
            "steps": self._steps,
        }

    def _sample_state(self, attack: bool) -> np.ndarray:
        if attack:
            return np.array(
                [
                    np.random.uniform(0.6, 0.95),
                    np.random.uniform(80, 400),
                    np.random.uniform(0.5, 0.9),
                    np.random.uniform(self.tau_threshold * 1.1, self.tau_threshold * 2.0),
                    np.random.uniform(0.7, 0.99),
                ],
                dtype=np.float32,
            )
        return np.array(
            [
                np.random.uniform(0.2, 0.5),
                np.random.uniform(5, 30),
                np.random.uniform(0.2, 0.45),
                np.random.uniform(5, self.tau_threshold * 0.5),
                np.random.uniform(0.05, 0.3),
            ],
            dtype=np.float32,
        )

    def save(self, path: str) -> None:
        torch.save(
            {
                "policy": self.policy_net.state_dict(),
                "target": self.target_net.state_dict(),
                "epsilon": self.epsilon,
                "tau_threshold": self.tau_threshold,
            },
            path,
        )

    def load(self, path: str) -> None:
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        self.policy_net.load_state_dict(ckpt["policy"])
        self.target_net.load_state_dict(ckpt.get("target", ckpt["policy"]))
        self.epsilon = float(ckpt.get("epsilon", self.epsilon))
        self.tau_threshold = float(ckpt.get("tau_threshold", self.tau_threshold))


if __name__ == "__main__":
    agent = DRLResilienceAgent()
    stats = agent.train_episodes(episodes=5, steps_per_ep=20)
    print("[+] DRL smoke train:", stats)
    s = agent._sample_state(attack=True)
    a = agent.select_action(s, explore=False)
    print(f"    action={agent.get_action_name(a)} reward={agent.compute_reward(s, a):.1f}")
