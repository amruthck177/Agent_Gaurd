# AgentGuard Design Export — Screen Mapping

Generated: 2026-10-12 17:30 IST

**ZIP 1** (stitch_laptop.zip) → Laptop/desktop screens (wide sidebar layout)
**ZIP 2** (stitch_mobile.zip) → Mobile screens (narrow, bottom tab bar)

## Screen Map

| # | Screen ID | Laptop status | Laptop source | Mobile status | Mobile source |
|---|-----------|---------------|---------------|---------------|---------------|
| 01 | live-feed | FOUND | agentguard_live_feed/screen.png | FOUND | agentguard_mobile_live_feed/screen.png |
| 02 | drawer | FOUND | agentguard_blocked_payment_inspection_drawer/screen.png | FOUND | agentguard_mobile_blocked_payment_sheet/screen.png |
| 03 | mobile-approval | MISSING | _(laptop zip has no mobile approval screen)_ | FOUND | agentguard_mobile_alert_approval/screen.png |
| 04 | approvals | FOUND | agentguard_approvals_console/screen.png | FOUND | agentguard_mobile_approvals/screen.png |
| 05 | audit | FOUND | agentguard_audit_log/screen.png | FOUND | agentguard_mobile_audit_log/screen.png |
| 06 | policies | FOUND | agentguard_policies_console/screen.png | FOUND | agentguard_mobile_policies/screen.png |
| 07 | test-results | FOUND | agentguard_test_results/screen.png | FOUND | agentguard_mobile_test_results/screen.png |
| 08 | demo-panel | FOUND | agentguard_stage_demo_panel/screen.png | MISSING | _(mobile zip has no demo panel screen)_ |
| 09 | states | FOUND | agentguard_system_edge_states/screen.png | FOUND | agentguard_mobile_states_edge_cases/screen.png |

## Extra files (present in zip but not in the expected screen list)

| File | Zip | Notes |
|------|-----|-------|
| agentguard_desktop_security_console/screen.png | Laptop | Appears to be an alternate/overview desktop console view. Kept as EXTRA-desktop-security-console.desktop.png |
| sovereign_defense/DESIGN.md | Both | Stitch project metadata file — not a screen |

## Summary counts

| | Laptop | Mobile |
|---|---|---|
| Expected screens | 8 (no 03) | 9 |
| FOUND | 8 | 8 |
| MISSING | 0 | 1 (08-demo-panel) |
| EXTRA | 1 (desktop-security-console) | 0 |
