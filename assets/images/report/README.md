# Report figures

Screenshots for `docs/IEDE_Project_Report_Prototype.docx`.

| File | Caption focus |
|------|----------------|
| `fig01_console_overview.png` | Nominal ops console |
| `fig02_ddos_containment.png` | DDoS → DROP + THROTTLE |
| `fig03_settings_drawer.png` | Settings / runtime config |
| `fig04_rush_hour_preserve.png` | Rush-hour FP avoidance |
| `fig05_replay_timeline.png` | Scenario replay |
| `fig06_topology_events.png` | Topology + event stream |

Regenerate (needs demo server on `:8080` + optional deps):

```bash
pip install -e ".[report]"
python scripts/capture_report_screens.py   # Playwright screenshots
python scripts/build_iede_report_docx.py   # → docs/IEDE_Project_Report_Prototype.docx
```
