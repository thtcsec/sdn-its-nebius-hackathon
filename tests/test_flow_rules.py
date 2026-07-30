import os
import sys
import time
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdn_its.controller import FlowRuleManager
from sdn_its.mitigation import FlowRule


class TestFlowRules(unittest.TestCase):
    def test_flow_rule_expiration(self):
        rule = FlowRule(
            rule_id="TEST-1",
            dpid="0001",
            src_ip="10.0.0.1",
            dst_ip=None,
            action="DROP",
            priority=100,
            created_at=time.time() - 5.0,
            cooldown_seconds=3.0,
        )
        self.assertTrue(rule.is_expired)
        self.assertEqual(rule.remaining_cooldown, 0.0)

    def test_flow_manager_rules(self):
        mgr = FlowRuleManager(rollback_check_interval=0.2)
        rule_drop = mgr.create_drop_rule(dpid="0001", src_ip="10.0.0.15", cooldown=1.0)
        self.assertEqual(len(mgr.get_all_active_rules()), 1)
        self.assertEqual(rule_drop.action, "DROP")
        self.assertEqual(rule_drop.src_ip, "10.0.0.15")

        time.sleep(1.5)
        self.assertEqual(len(mgr.get_all_active_rules()), 0)
        self.assertEqual(len(mgr.rollback_history), 1)
        self.assertEqual(mgr.rollback_history[0]["rule_id"], rule_drop.rule_id)
        self.assertEqual(mgr.rollback_history[0]["revocation_reason"], "COOLDOWN_EXPIRED")

        mgr.stop()


if __name__ == "__main__":
    unittest.main()
