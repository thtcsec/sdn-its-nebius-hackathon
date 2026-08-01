"""
Optional Ryu OpenFlow 1.3 application for WSL2 / Linux lab.

Run (on Ubuntu/WSL2 with Ryu installed):
  ryu-manager src/sdn_its/controller/ryu_app.py

Then point the Flask demo at the same adapter via:
  set SDN_OF_BACKEND=ryu
  python -m api.app

This module imports Ryu only when executed under ryu-manager; on Windows
importing the module is safe (RyuApp becomes a no-op stub).
"""

from __future__ import annotations

from typing import Any

try:
    from ryu.base import app_manager
    from ryu.controller import ofp_event
    from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
    from ryu.ofproto import ofproto_v1_3

    RYU_AVAILABLE = True
except ImportError:  # Windows / CI without Ryu
    RYU_AVAILABLE = False
    app_manager = object  # type: ignore[assignment]


if RYU_AVAILABLE:

    class ITSResilienceRyuApp(app_manager.RyuApp):
        """Install table-miss + accept FlowRule-style DROP/OUTPUT mods from REST bridge."""

        OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.datapaths: dict[int, Any] = {}

        @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
        def switch_features_handler(self, ev):
            datapath = ev.msg.datapath
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            self.datapaths[datapath.id] = datapath
            # Table-miss → controller
            match = parser.OFPMatch()
            actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
            self._add_flow(datapath, 0, match, actions)
            self.logger.info("Switch connected dpid=%s", datapath.id)

        def _add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
            ofproto = datapath.ofproto
            parser = datapath.ofproto_parser
            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=inst,
                idle_timeout=idle_timeout,
                hard_timeout=hard_timeout,
            )
            datapath.send_msg(mod)

        def install_drop(self, dpid: int, ipv4_src: str, priority: int = 100, idle_timeout: int = 30):
            datapath = self.datapaths.get(dpid)
            if datapath is None:
                self.logger.warning("No datapath %s", dpid)
                return False
            parser = datapath.ofproto_parser
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=ipv4_src)
            self._add_flow(datapath, priority, match, actions=[], idle_timeout=idle_timeout)
            return True

        @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
        def _packet_in_handler(self, ev):
            # Telemetry hook point — count packet_ins for LOFT/DDoS features in lab
            msg = ev.msg
            self.logger.debug("packet_in dpid=%s len=%s", msg.datapath.id, msg.total_len)

else:

    class ITSResilienceRyuApp:  # type: ignore[no-redef]
        """Placeholder when Ryu is not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Ryu is not installed. On WSL2/Ubuntu: pip install ryu && "
                "ryu-manager src/sdn_its/controller/ryu_app.py"
            )
