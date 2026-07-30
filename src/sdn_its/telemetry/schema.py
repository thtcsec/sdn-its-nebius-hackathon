"""Shared telemetry schema constants."""

FEATURE_COLUMNS = [
    "flow_duration",
    "packet_rate",
    "byte_rate",
    "pkt_iat_mean",
    "pkt_iat_std",
    "packet_len_mean",
    "packet_in_count",
    "tcp_flags_syn_count",
    "flow_active_ratio",
    "rsu_channel_occupancy",
]

LABEL_MAPPING = {
    0: "Normal",
    1: "DDoS_PacketIn_Flood",
    2: "LOFT_LowRate_Attack",
    3: "RSU_Link_Fault",
    4: "RushHour_Burst",
}
