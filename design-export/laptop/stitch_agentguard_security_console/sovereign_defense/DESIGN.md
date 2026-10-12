---
name: Sovereign Defense
colors:
  surface: '#0c1321'
  surface-dim: '#0c1321'
  surface-bright: '#323949'
  surface-container-lowest: '#070e1c'
  surface-container-low: '#151b2a'
  surface-container: '#19202e'
  surface-container-high: '#232a39'
  surface-container-highest: '#2e3544'
  on-surface: '#dce2f6'
  on-surface-variant: '#d3c4b2'
  inverse-surface: '#dce2f6'
  inverse-on-surface: '#2a3040'
  outline: '#9c8f7e'
  outline-variant: '#4f4537'
  surface-tint: '#f4bd61'
  primary: '#f4bd61'
  on-primary: '#432c00'
  primary-container: '#c8963e'
  on-primary-container: '#4a3100'
  inverse-primary: '#7e5700'
  secondary: '#bbc6e4'
  on-secondary: '#253048'
  secondary-container: '#3e4962'
  on-secondary-container: '#adb8d6'
  tertiary: '#bac6e7'
  on-tertiary: '#24304a'
  tertiary-container: '#929ebd'
  on-tertiary-container: '#293550'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdead'
  primary-fixed-dim: '#f4bd61'
  on-primary-fixed: '#281900'
  on-primary-fixed-variant: '#604100'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#bbc6e4'
  on-secondary-fixed: '#101b32'
  on-secondary-fixed-variant: '#3c475f'
  tertiary-fixed: '#d8e2ff'
  tertiary-fixed-dim: '#bac6e7'
  on-tertiary-fixed: '#0e1b34'
  on-tertiary-fixed-variant: '#3b4662'
  background: '#0c1321'
  on-background: '#dce2f6'
  surface-variant: '#2e3544'
typography:
  stat-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-page:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-page-mobile:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  title-card:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-default:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-semibold:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  caption:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  caption-medium:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  code-default:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  code-bold:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

The design system projects sovereign authority, deterministic control, and rigorous auditability. It serves risk officers, compliance architects, and business operators who monitor autonomous AI agent execution. The emotional response must be total operational confidence—zero ambiguity, zero latency lag, and unflinching clarity.

The aesthetic fuses institutional fintech restraint with defensive cybersecurity density:
- **Tone:** Uncompromising, analytical, precise, and forensic.
- **Visual Stance:** Obsidian surfaces layered with micro-calibrated midnight blues, structured architectural borders, and an authoritative gold accent reserved strictly for sovereign system interactions and key metrics.
- **Rule of Non-Ambiguity:** AI decision outcomes (ALLOW, ASK HUMAN, BLOCK) are hyper-focused semantic primitives that strictly isolate meaning. They never cross-contaminate decorative or structural UI components.

## Colors

The palette enforces a non-negotiable semantic taxonomy across an ultra-dense dark canvas:

### Core Surfaces & Structures
- **Canvas Base:** `#0B1220` (Underlying structural bedrock)
- **Surface Level 1 (Panels, Cards, Tables):** `#121B2E`
- **Surface Level 2 (Active Rows, Nested Wells, Trays):** `#18233A`
- **Border / Divider:** `#24304A` (1px precise architectural keylines)

### Typography & Content
- **Text Primary:** `#E8ECF4` (High legibility, headers, primary data values)
- **Text Secondary:** `#9AA6BF` (Labels, metadata, timestamps, audit breadcrumbs)
- **Text Muted / Disabled:** `#56637D`

### Key System Accent
- **Sovereign Gold:** `#C8963E` (Reserved for primary command buttons, active navigation markers, key performance indicators, and focal stat figures)
- **Gold Hover / Focus:** `#DCAB54`
- **Gold Container Alpha:** `rgba(200, 150, 62, 0.12)`

### Strict Semantic Decision Primitives
These three colors are strictly quarantined. They must never be applied to generic UI, hover states, charts, or decorative elements:
- **ALLOW:** `#2E9E5B` (Paired with check-circle iconography) | Surface: `rgba(46, 158, 91, 0.12)`
- **ASK HUMAN:** `#F2B705` (Paired with clock / pending iconography) | Surface: `rgba(242, 183, 5, 0.12)`
- **BLOCK:** `#D64545` (Paired with shield-x iconography) | Surface: `rgba(214, 69, 69, 0.12)`

## Typography

The type system prioritizes structural hierarchy and scanning efficiency under incident response conditions.

- **Dual-Engine Type Hierarchy:**
  - `Inter` powers high-level UI controls, narrative text, metadata, and stat figures.
  - `JetBrains Mono` governs execution trace parameters, agent policy hashes, payload blobs, rule operators, and deterministic transaction statuses.
- **Tabular Figures:** All numeric displays—including `stat-lg`, monetary metrics, token counters, latency ms, and timestamp logs—must enforce `font-feature-settings: "tnum" 1` to prevent jitter during real-time streaming updates.
- **Telemetry Identifiers:** Model endpoints, UUIDs, and SHA-256 signatures rely on `code-sm` with slight tracking expansion to maintain optical separation at diminutive scales.

## Layout & Spacing

The layout philosophy operates on an unyielding 8px spatial grid, optimized for dense multi-pane mission control environments.

### Spatial Rhythms
- **Micro Spacing:** 4px (`space-xs`) for icon-to-label inline gaps; 8px (`space-sm`) for compact element pairings, badge interiors, and dense table row padding.
- **Component Padding:** 16px (`space-md`) within standard panel bodies, modal content wells, and filter bars.
- **Macro Layout Spacing:** 24px (`space-lg`) between card grid clusters; 32px (`space-xl`) separating page-level headers from core telemetry grids.

### Screen Adaptations
- **Desktop (>=1280px):** 12-column fluid grid system bounded by fixed navigation rails (compact 64px or expanded 240px). Gutters set to 24px (`gutter-desktop`), outer margin fixed to 32px (`margin-desktop`).
- **Tablet (768px - 1279px):** 8-column layout. Gutters compress to 16px (`gutter`), margins to 24px. Multi-column metric bars collapse into a 2x2 grid.
- **Mobile (<768px):** 4-column layout. Outer margins set to 16px (`margin`). Split-pane policy inspectors reflow into stacked, tabbed views.

## Elevation & Depth

The design system relies on planar tonal tiers and razor-sharp 1px structural outlines rather than heavy atmospheric diffusion:

1. **Base Plane (Z: 0):** `#0B1220`. Canvas foundation, persistent sidebar tracks, and terminal backplates.
2. **Surface Plane (Z: 1):** `#121B2E`. Enclosed by a 1px solid `#24304A` stroke. Applied to cards, inspection panels, tables, and metric modules. No ambient shadow is cast at rest.
3. **Interactive & Active Plane (Z: 2):** `#18233A`. Applied to hovered table rows, embedded payload trays, form inputs, and active card segments. Surrounded by `#24304A` or targeted accent lines.
4. **Floating Overlays (Z: 3):** `#121B2E` surface paired with an elevated drop shadow (`0 12px 32px -4px rgba(3, 7, 18, 0.65)`) and a crisply defined border of `1px solid #24304A`. Applied to popovers, flyout policy editors, and confirmation modals.
5. **Deterministic Focus & Highlight:** Focused inputs and active navigational links leverage a clean 1px stroke of Sovereign Gold (`#C8963E`) accompanied by a subtle `0 0 0 1px #C8963E` containment ring.

## Shapes

The interface balances sharp industrial discipline with refined corner radii:

- **Cards & Primary Modules:** Fixed at `12px` border radius (`rounded-lg`), establishing solid architectural modules without feeling excessively circular or recreational.
- **Inputs, Nested Containers, Action Buttons:** Fixed at `8px` (`roundedness: 2`), ensuring a cohesive mechanical footprint.
- **Status Badges & Decision Chips:** Pure pill radius (`9999px`) to immediately distinguish ephemeral runtime states from persistent layout structures.

## Components

### Buttons
- **Primary Sovereign:** Solid `#C8963E` background, `#0B1220` bold text. 8px radius, height 36px (compact) or 40px (standard). Hover: `#DCAB54`. Active: `#B58432`.
- **Secondary / Ghost:** Transparent surface with 1px solid `#24304A` border, `#E8ECF4` text. Hover: `#18233A` background, border shifts to `#9AA6BF`.
- **Destructive:** Used strictly for irreversible policy deletion (not standard BLOCK decisions). Transparent with `1px solid rgba(214, 69, 69, 0.4)`, text `#D64545`. Hover: `rgba(214, 69, 69, 0.1)`.

### Decision Chips (Badges)
Pill-shaped (`9999px` radius), strictly paired with clean 14px outline icons:
- **ALLOW:** Background `rgba(46, 158, 91, 0.12)`, border `1px solid rgba(46, 158, 91, 0.35)`, text `#2E9E5B`. Icon: `check-circle`.
- **ASK HUMAN:** Background `rgba(242, 183, 5, 0.12)`, border `1px solid rgba(242, 183, 5, 0.35)`, text `#F2B705`. Icon: `clock`.
- **BLOCK:** Background `rgba(214, 69, 69, 0.12)`, border `1px solid rgba(214, 69, 69, 0.35)`, text `#D64545`. Icon: `shield-x`.

### Metric & Stat Displays
- Surface `#121B2E`, 1px border `#24304A`, 12px radius, 16px internal padding.
- Metric values rendered in `stat-lg` (`32px` bold Inter, tabular-nums) in Sovereign Gold (`#C8963E`) or primary white (`#E8ECF4`).
- Upper label rendered in 13px Inter caption (`#9AA6BF`), with bottom audit delta in `JetBrains Mono` 11px.

### Inputs & Selectors
- Background `#18233A`, 1px border `#24304A`, 8px radius. Text `#E8ECF4`, placeholder `#56637D`.
- Focus state shifts border directly to `#C8963E` with an outer glow `box-shadow: 0 0 0 1px #C8963E`.

### Data Tables & Decision Streams
- Container: `#121B2E` with 12px outer radius.
- Header row: `#0B1220` with 1px border-bottom `#24304A`. 11px uppercase `JetBrains Mono` headers in `#9AA6BF`.
- Data rows: Alternating height 48px, horizontal divider `1px solid #24304A`. Hover state transitions background smoothly to `#18233A`.
- Monospace cells: Used for Agent IDs, Hash strings, and Tool names.

### Checkboxes & Radios
- Size: 16x16px, `#18233A` background, `1px solid #24304A` border, 4px radius (checkboxes) or circular (radios).
- Checked state: Fill `#C8963E`, checkmark icon in `#0B1220`.