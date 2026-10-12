# AgentGuard 2.0: Visual Design Specification

Team LogicLords · DevHack 2026 · PS 2.1 AI Agent Safety and Control
Audience: anyone building or reviewing the UI (Stitch, Antigravity, React). This file is the single source of truth for how AgentGuard looks and behaves. **Precedence:** if a Stitch design already exists, the Stitch screenshots win for how things *look* (layout, spacing, colour shades). This file wins for behaviour, wording, states, responsive rules, the three decision labels and accessibility, because Stitch screenshots do not show those.

---

## 1. Design intent

AgentGuard is a **security console** that sits between AI agents and business tools. The owner is a small-business manager, not a developer. The UI must answer three questions in five seconds:

1. What did the agent try to do?
2. What did AgentGuard decide (ALLOW, ASK HUMAN, BLOCK)?
3. Why, and can I prove it later?

Principles:
- **Evidence over decoration.** Every decision shows the real parameters (recipient, amount), the rule that fired, and the audit record.
- **Exact-match story first.** The hero idea is "approved Supplier A, ₹5,000; the agent tried Supplier B; blocked; tool never ran". The UI makes the approved value and the attempted value sit side by side.
- **Honest labelling.** Simulated things say "Simulated". No fake production claims.
- **Never colour alone.** Every status has an icon and a text label.
- **Projector-safe.** Minimum 13px text, high contrast, large demo controls.

---

## 2. Design tokens

### 2.1 Colour (dark console, default)

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#0B1220` | Page background |
| `--surface` | `#121B2E` | Cards, panels |
| `--surface-2` | `#18233A` | Raised rows, hover |
| `--border` | `#24304A` | 1px borders, dividers |
| `--text` | `#E8ECF4` | Primary text |
| `--text-2` | `#9AA6BF` | Secondary text (min contrast 4.5:1 on `--bg`) |
| `--accent` | `#C8963E` | Primary buttons, active nav, key numbers |
| `--allow` | `#2E9E5B` | ALLOW |
| `--ask` | `#F2B705` | ASK HUMAN |
| `--block` | `#D64545` | BLOCK |
| `--info` | `#4C8DF6` | Neutral info, links |

Decision colours are fixed on every screen. Do not reuse green, amber or red for anything else (no red delete buttons that look like BLOCK, no green "save").

Tint backgrounds for chips and row edges: decision colour at 14% opacity, 2px left border at 100%.

Light theme (optional, same accent): `--bg #F6F7FA`, `--surface #FFFFFF`, `--border #D9DEE8`, `--text #101828`, `--text-2 #475467`. Decision colours darken slightly for contrast: allow `#1E7F5C`, ask `#B7791F`, block `#C62828`.

### 2.2 Typography

| Role | Font | Size / weight |
|---|---|---|
| UI | Inter | 14 body, 13 min, 16 card titles (600), 24 page titles (600) |
| Data (IDs, hashes, actions, JSON) | JetBrains Mono | 13 |
| Big numbers (stat cards) | Inter | 32 / 700, tabular figures |
| Demo panel | Inter | 18 body, 28 headings |

Currency always `₹` with Indian grouping (`₹80,000`, `₹1,25,000`). Hashes shown as first 6 + `…` + last 4 with a copy button.

### 2.3 Spacing, shape, elevation
- 8px grid. Card padding 20px. Gap between cards 16px. Page gutter 24px (16px on mobile).
- Radius: 12px cards, 8px inputs and chips, 999px pills.
- Borders over shadows. One glow only: `0 0 0 3px rgba(200,150,62,.25)` on focused gold elements and a soft pulse on the LIVE dot.
- Icons: outline, 20px, stroke 1.75 (Lucide set). Mapping: ALLOW `check-circle`, ASK HUMAN `clock`, BLOCK `shield-x`, audit `link`, approval `badge-check`, replay `repeat`, expiry `timer`, revoke `ban`.

### 2.4 Tailwind mapping (copy into `tailwind.config.js`)

```js
theme: { extend: {
  colors: {
    bg: '#0B1220', surface: '#121B2E', surface2: '#18233A', line: '#24304A',
    ink: '#E8ECF4', ink2: '#9AA6BF', accent: '#C8963E',
    allow: '#2E9E5B', ask: '#F2B705', block: '#D64545', info: '#4C8DF6'
  },
  fontFamily: { sans: ['Inter','system-ui'], mono: ['JetBrains Mono','ui-monospace'] },
  borderRadius: { card: '12px' }
}}
```

---

## 3. Layout shell

- **Sidebar (240px, collapses to 72px icons under 1200px):** logo (shield mark + "AgentGuard"), nav: Live Feed, Approvals (amber count badge), Policies, Audit Log, Demo Panel. Footer chip: `Simulated MVP · mock tools`.
- **Top bar (64px):** agent selector (default `accounts-agent`), search, red-outline **Pause Agent** button, gateway status pill (`Gateway: online` green / `Gateway: unreachable, failing closed` red), avatar.
- **Global banner (slim, dismissible):** "Enforcement runs in code at the gateway, outside the AI. Errors fail closed."
- Content max width 1440px. Desktop first; mobile layout only for the approval screen and a read-only feed.

## 3B. Responsive behaviour (laptop and mobile, chosen by the viewer's screen)

The same React app adapts to the device. Do not build a separate mobile site. Breakpoints: **mobile < 768px**, **tablet 768 to 1199px**, **laptop >= 1200px**.

| Element | Laptop (>= 1200px) | Tablet (768 to 1199px) | Mobile (< 768px) |
|---|---|---|---|
| Navigation | Left sidebar 240px | Icon sidebar 72px | Bottom tab bar: Feed, Approvals, Audit, Policies, More |
| Top bar | Agent selector, search, Pause Agent, status pill, avatar | Same, search collapses to icon | Compact: logo, gateway pill, avatar; Pause Agent moves into More |
| Stat cards | 4 in a row | 2 x 2 | 2 x 2 |
| Data tables | Full tables, 52px rows | Tables scroll inside the card | Card lists (time, chip, action, reason, amount) |
| Event drawer | Right drawer 480px | Right drawer 420px | Full-height bottom sheet with drag handle |
| Approved vs Attempted block | Two columns | Two columns | Stacked: Approved above Attempted, mismatch row stays red |
| Filters | Inline row | Inline row | One "Filters" button opening a sheet |
| Buttons | 44px | 44px | Primary actions full width, 56px on approval and demo screens |
| Gutters | 24px | 24px | 16px plus safe-area padding |
| Demo Panel | Grid of cards plus live mini feed | Two-column grid | One column, sticky "Run the full story" |

Rules: the mobile approval page (`/m/:id`) is mobile-first and also works on a laptop (centred 420px column). The sidebar and bottom tab bar never show together. No horizontal page scroll at any width. Decision chips, wording, colours and the comparison block are identical across devices. Detect the layout with CSS breakpoints (Tailwind `md:` and `xl:`), not user-agent sniffing, so resizing a window also adapts.

---

## 4. Core components

### 4.1 Decision chip (identical everywhere)
Height 28px, radius 999px, icon left, label right, tinted background + 1px border in decision colour.
Labels are exactly `ALLOW`, `ASK HUMAN`, `BLOCK`. No synonyms ("Approved", "Denied", "Needs review") anywhere in UI, deck or logs.

### 4.2 Stat card
Label (13px, `--text-2`), number (32px), delta or sparkline. Four cards: Actions, Allowed, Needs approval, Blocked.

### 4.3 Action row
`time · agent · tool (mono) · target · amount · decision chip · reason`. Left 2px border in decision colour for ASK HUMAN and BLOCK. Row height 52px. Click opens the drawer.

### 4.4 Parameter comparison block (the hero component)
Two columns inside one card, used in the event drawer, the approvals page and the demo panel.

```
APPROVED                         ATTEMPTED
tool        payments.send        payments.send        ✓ match
recipient   Supplier A           Supplier B           ✗ MISMATCH   (red fill)
amount      ₹5,000               ₹5,000               ✓ match
expires     11:42 (in 06:12)     now 11:38            ✓ valid
approval    APR-0007 · unused    -                    ✓ unused
```
Rules: mismatching row gets a red tint and a `✗` icon plus the text "MISMATCH"; matching rows get a muted `✓`. Footer line: `Payment tool executions: 0` (large, bold, green when 0). This line is the visual proof for the checklist item "payment tool never executed".

### 4.5 Reason line
Icon + one plain sentence from a fixed vocabulary:
- `Recipient changed after approval`
- `Amount changed after approval`
- `Approval expired`
- `Approval revoked`
- `Approval already used (replay)`
- `Agent lacks write permission`
- `Destructive database operation prohibited`
- `Payment exceeds ₹10,000 limit: human approval required`
- `Gateway unavailable: failed closed`

### 4.6 Audit chain cell
Record number, short hash, short previous hash, with a thin vertical connector linking consecutive rows. Broken link renders red with an alert icon and the text `Chain broken at record #N`.

### 4.7 Approval card
Title ("Payment ₹5,000 to Supplier A"), chips (Over limit, New payee when relevant), countdown, the parameter block in "approved" mode, buttons **Approve** (gold) and **Reject** (red outline), and **Revoke** on already-approved cards.

### 4.8 Buttons
Primary gold (`--accent`, dark text), secondary outline, destructive red outline, min height 44px (56px on mobile approval and demo panel). Focus ring 2px gold.

### 4.9 Empty, loading, error states
Skeleton rows for tables; empty state is a shield-check icon with "Nothing waiting for you"; API error shows a red banner with "Gateway unreachable. All actions are being blocked until it returns." Never show a blank screen.

---

## 5. Screens

### 5.1 Live Feed (`/`)
- Stat cards row.
- Main (2/3): "Agent activity" table with pulsing LIVE dot, columns Time, Action, Target, Amount, Decision, Reason. Live via WebSocket; new rows slide in 150ms.
- Right (1/3): decision-mix donut or 24h trend, and an Alerts list led by the latest BLOCK with "View why".

### 5.2 Event drawer (right side, 480px)
Header: big decision chip + action title. Sections in order:
1. **Why** (reason lines, rule id, who decided: Policy / Approval check / Human).
2. **Parameter comparison block** (4.4) when an approval is involved.
3. **Execution outcome:** `Tool executed: No` / `Yes` and the tool call counter.
4. **Agent request:** raw JSON in a mono block, secrets masked.
5. **Audit record:** `#1043 · hash 9f3a…c21 · prev 7b1e…04d` with copy.
Footer: Pause agent (red outline), Close. No "allow anyway" button. That absence is deliberate and should be stated in the deck.

### 5.3 Approvals (`/approvals`)
Tabs: Pending, Approved, Rejected, Expired, Revoked. Pending card per 4.7. Approved cards show state `unused`, `used`, or `revoked` and a live countdown. Right column: phone-style preview of what the approver sees (labelled "Simulated").

### 5.4 Mobile approval (`/m/:id`, 390px)
Messaging-app styled and labelled "Simulated chat". Header with language switch `English | हिंदी | ಕನ್ನಡ`. One message bubble in the active language, then a raw-action card (tool, recipient, amount, risk), the line "This is the real action, not the agent's explanation.", countdown chip, and two full-width 56px buttons Approve / Reject. After tapping: "Approved. Valid for 10 minutes for exactly this action." or "Rejected. Nothing was paid."
Language support is simulated static strings in the MVP. Do not describe it as live WhatsApp or SMS.

### 5.5 Policies (`/policies`)
Core (implemented): readable list of rules per agent and per task with decision chip, e.g. payments > ₹10,000 → ASK HUMAN; `reader-agent` write → BLOCK; `DROP TABLE` → BLOCK; unknown external email domain → ASK HUMAN. Edit via form (tool, condition, decision).
Optional: plain-English box that compiles to rules. Show it only if built; otherwise omit the section, do not leave a dead panel.

### 5.6 Audit Log (`/audit`)
Integrity hero card with two variants, Verified (green: "1,043 records, chain intact") and Broken (red: "Chain broken at record #812"). Buttons: **Verify integrity** (gold), **Export CSV**. Filters: date, agent, decision, search. Table: #, Time, Agent, Action, Decision, Reason, Decided by, Hash, Prev hash. Secrets never appear in any column.

### 5.7 Demo Panel (`/demo`)
Large cards, 18px text, designed for a projector. See section 7 for the exact script. Includes the status pill `Agent mode: Scripted (offline-safe)` and buttons `Reset demo data`, `Simulate tamper`.

### 5.8 Test results (`/tests`, optional but strong for judges)
Table of the 30+ cases (id, scenario, expected, actual, tool executed, pass/fail) and a metrics header: cases run, mismatch detection rate, false-block rate, unauthorized executions, average and p95 added latency, audit integrity. Numbers come from `benchmarks/results.json`, never typed by hand.

---

## 6. Interaction and motion
- New feed rows: slide + fade, 150ms. BLOCK rows flash a red edge once for 600ms.
- Countdown timers tick every second; at 00:00 the card flips to Expired without reload.
- No auto-playing animation longer than 1s. Respect `prefers-reduced-motion`.
- Optimistic UI is not used for decisions. The UI shows only what the gateway returned.

---

## 7. Hero demo choreography (screen by screen)

Used for the live pitch and the video. Each step names the screen state.

1. **Setup.** Demo Panel: click "Reset demo data". Feed empty, audit chain length 1 (genesis).
2. **Request.** Agent asks to pay Supplier A ₹5,000. Gateway returns ASK HUMAN (new payee or policy).
3. **Approve.** Mobile approval screen: Approve. Approval card appears: APR-0001, Supplier A, ₹5,000, expires in 10:00, unused.
4. **Valid run.** Agent executes with APR-0001, exact params. Chip ALLOW, `Payment tool executions: 1`, approval flips to `used`.
5. **Attack.** New approval APR-0002 for Supplier A ₹5,000. The "attacker" changes recipient to Supplier B and executes. Parameter block shows `recipient: Supplier A → Supplier B ✗ MISMATCH`. Chip BLOCK. Reason `Recipient changed after approval`. `Payment tool executions: 0`.
6. **Proof.** Open the audit record for the block. Show hash and prev hash. Click Verify integrity: green.
7. **Tamper.** Click Simulate tamper, then Verify: red `Chain broken at record #N`.
8. **Close.** Show the Test results page: counts and rates from the real run.

Order note: show the valid action first so the audience sees the system is not just a blocker.

---

## 8. Slide and diagram style (for the PPT)
Deck uses the official DevHost template. Keep its headings and slide order. Palette inside the deck: navy `#1B2A49`, blue `#2F6FBF`, green `#1E7F5C`, amber `#E69500`, red `#C62828`, Calibri. Decision chips in the deck use the same three labels and colours as the UI. Every feature is tagged **Implemented**, **Simulated**, or **Roadmap**. Architecture diagram has at most five boxes in one line plus an audit strip below.

---

## 9. Accessibility and quality bar
- WCAG AA contrast on all text; decision chips pass against their tinted backgrounds.
- Keyboard: all actions reachable, visible focus ring, drawer traps focus and closes on Esc.
- Screen reader: chips have `aria-label="Decision: BLOCK"`; live feed uses `aria-live="polite"`.
- Touch targets at least 44px (56px on approval and demo screens).
- Layout verified at 1440, 1280, 1024 and 390 widths. No horizontal page scroll on mobile.
- Language switch changes text only; layout must not shift between English, Hindi and Kannada (allow 40% longer strings).

---

## 10. Stitch and Antigravity usage
- Paste the master prompt from `AgentGuard_Stitch_Master_Prompts.md`, then generate screens in this order: Live Feed, Mobile approval, Approvals, Audit, Demo Panel, Policies, Drawer.
- Add this to every screen prompt: "Include a parameter comparison block showing APPROVED vs ATTEMPTED values with a red MISMATCH row, and a line `Payment tool executions: 0`." The older prompts predate 2.0 and lack it.
- In Antigravity, attach this `design.md` and `plan.md` as workspace rules so generated React follows the tokens and the exact decision vocabulary.

---

## 11. Do and don't

| Do | Don't |
|---|---|
| Show approved vs attempted values side by side | Hide parameters behind "suspicious activity" text |
| Use exactly ALLOW / ASK HUMAN / BLOCK | Invent extra statuses |
| Label simulated parts | Imply real payments, WhatsApp or SMS |
| Show real numbers from the test run | Type benchmark values by hand |
| Keep one gold accent | Add more accent colours |
| Mask secrets in every view | Print tokens or keys in raw requests |
