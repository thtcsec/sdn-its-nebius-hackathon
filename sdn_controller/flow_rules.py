"""
flow_rules.py - OpenFlow 1.3 Flow Modification & Automated Rollback Manager

Handles OpenFlow flow_mod rule creation (drop, rate-limit, packet_in throttle)
and implements a safety-aware 3-stage mitigation policy with automated cooldown & rollback.

Mitigation Policy Stages:
1. Detect: Parse high-confidence anomaly alert from AI detection module.
2. Contain: Apply temporary flow_mod rule targeting offending source IP or RSU switch DPID.
3. Rollback: Automatically delete flow rule after cooldown timer expires to prevent permanent FP service loss.
"""

import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable


@dataclass
class FlowRule:
    """Dataclass representing an active SDN mitigation flow rule."""
    rule_id: str
    dpid: str
    src_ip: Optional[str]
    dst_ip: Optional[str]
    action: str  # "DROP", "RATE_LIMIT", "THROTTLE_PACKET_IN"
    priority: int
    created_at: float
    cooldown_seconds: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) >= self.cooldown_seconds
        
    @property
    def remaining_cooldown(self) -> float:
        return max(0.0, self.cooldown_seconds - (time.time() - self.created_at))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "dpid": self.dpid,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "action": self.action,
            "priority": self.priority,
            "created_at": self.created_at,
            "cooldown_seconds": self.cooldown_seconds,
            "remaining_cooldown_sec": round(self.remaining_cooldown, 1),
            "parameters": self.parameters
        }


class FlowRuleManager:
    """Manages active SDN flow rules, switch modifications, and automated rollback threads."""
    
    def __init__(self, rollback_check_interval: float = 5.0, of_push_callback: Optional[Callable] = None):
        self.active_rules: Dict[str, FlowRule] = {}
        self.rollback_history: List[Dict[str, Any]] = []
        self.rollback_check_interval = rollback_check_interval
        self.of_push_callback = of_push_callback  # Hook function to send OpenFlow / RESTCONF commands
        
        self.lock = threading.Lock()
        self.running = True
        
        # Start background rollback thread
        self.rollback_thread = threading.Thread(target=self._auto_rollback_loop, daemon=True)
        self.rollback_thread.start()

    def create_drop_rule(
        self, dpid: str, src_ip: str, dst_ip: Optional[str] = None, 
        priority: int = 200, cooldown: float = 60.0
    ) -> FlowRule:
        """Stage 2 Containment: Installs temporary DROP rule targeting malicious source IP."""
        rule_id = f"RULE-DROP-{uuid.uuid4().hex[:8]}"
        rule = FlowRule(
            rule_id=rule_id,
            dpid=dpid,
            src_ip=src_ip,
            dst_ip=dst_ip,
            action="DROP",
            priority=priority,
            created_at=time.time(),
            cooldown_seconds=cooldown
        )
        
        with self.lock:
            self.active_rules[rule_id] = rule
            
        print(f"[SDN FlowRuleManager] [+] Applied temporary DROP rule {rule_id} on DPID {dpid} for src_ip={src_ip} (cooldown: {cooldown}s)")
        
        if self.of_push_callback:
            self.of_push_callback(action="ADD", rule=rule)
            
        return rule

    def create_rate_limit_rule(
        self, dpid: str, src_ip: str, max_rate_kbps: int = 500, 
        priority: int = 180, cooldown: float = 60.0
    ) -> FlowRule:
        """Stage 2 Containment: Installs temporary RATE_LIMIT meter rule."""
        rule_id = f"RULE-RATELIMIT-{uuid.uuid4().hex[:8]}"
        rule = FlowRule(
            rule_id=rule_id,
            dpid=dpid,
            src_ip=src_ip,
            dst_ip=None,
            action="RATE_LIMIT",
            priority=priority,
            created_at=time.time(),
            cooldown_seconds=cooldown,
            parameters={"max_rate_kbps": max_rate_kbps}
        )
        
        with self.lock:
            self.active_rules[rule_id] = rule
            
        print(f"[SDN FlowRuleManager] [+] Applied RATE_LIMIT rule {rule_id} ({max_rate_kbps} kbps) on DPID {dpid} for src_ip={src_ip}")
        
        if self.of_push_callback:
            self.of_push_callback(action="ADD", rule=rule)
            
        return rule

    def create_packet_in_throttle_rule(
        self, dpid: str, priority: int = 250, cooldown: float = 30.0
    ) -> FlowRule:
        """Stage 2 Containment: Protects SDN controller from packet_in flood by placing default drop for unmatched flows."""
        rule_id = f"RULE-THROTTLE-{uuid.uuid4().hex[:8]}"
        rule = FlowRule(
            rule_id=rule_id,
            dpid=dpid,
            src_ip=None,
            dst_ip=None,
            action="THROTTLE_PACKET_IN",
            priority=priority,
            created_at=time.time(),
            cooldown_seconds=cooldown
        )
        
        with self.lock:
            self.active_rules[rule_id] = rule
            
        print(f"[SDN FlowRuleManager] [+] Applied PACKET_IN THROTTLE rule {rule_id} on DPID {dpid}")
        
        if self.of_push_callback:
            self.of_push_callback(action="ADD", rule=rule)
            
        return rule

    def revoke_rule(self, rule_id: str, reason: str = "MANUAL_REVOCATION") -> bool:
        """Stage 3 Rollback: Removes flow rule from switch and records in rollback history."""
        with self.lock:
            if rule_id not in self.active_rules:
                return False
            rule = self.active_rules.pop(rule_id)
            
        print(f"[SDN FlowRuleManager] [-] Rollback executed for rule {rule_id} ({rule.action}) on DPID {rule.dpid}. Reason: {reason}")
        
        history_entry = rule.to_dict()
        history_entry["revoked_at"] = time.time()
        history_entry["revocation_reason"] = reason
        self.rollback_history.append(history_entry)
        
        if self.of_push_callback:
            self.of_push_callback(action="DELETE", rule=rule)
            
        return True

    def get_all_active_rules(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [rule.to_dict() for rule in self.active_rules.values()]

    def _auto_rollback_loop(self):
        """Background loop monitoring cooldown timers for safety-aware automatic rollback."""
        while self.running:
            time.sleep(self.rollback_check_interval)
            expired_ids = []
            
            with self.lock:
                for rule_id, rule in self.active_rules.items():
                    if rule.is_expired:
                        expired_ids.append(rule_id)
                        
            for rid in expired_ids:
                self.revoke_rule(rid, reason="COOLDOWN_EXPIRED")

    def stop(self):
        self.running = False


if __name__ == "__main__":
    print("Testing FlowRuleManager cooldown and rollback logic...")
    mgr = FlowRuleManager(rollback_check_interval=1.0)
    rule = mgr.create_drop_rule(dpid="0000000000000001", src_ip="10.0.0.15", cooldown=3.0)
    
    print(f"Active rules immediately: {len(mgr.get_all_active_rules())}")
    time.sleep(4.0)
    print(f"Active rules after 4s (post cooldown): {len(mgr.get_all_active_rules())}")
    print(f"Rollback history entries: {len(mgr.rollback_history)}")
    mgr.stop()
    print("[OK] FlowRuleManager test complete!")
