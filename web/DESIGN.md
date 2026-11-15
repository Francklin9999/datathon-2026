# Design system and interaction rules

**Owner:** T13. Direction set with an [unslop](https://github.com/heydamir/unslop) pass (unslop by Damir Sokolovsky, @heydamir, CC BY 4.0) on 2026-11-15, replacing the glass redesign of [2026-11-14](../docs/superpowers/specs/2026-11-14-glass-ui-design.md). Original reference: [prototype](../Datathon2026/aplomb-ui/project/Main.dc.html) (visual language only).

## Direction

- **Product:** tests hypothetical investment changes against a fictional investor's plan; every figure links to its source.
- **Character:** exact, sober, evidential.
- **World:** survey and audit instruments: the plumb line (the logo), the level, graph paper.
- **Moments:** the history chart and the plan-health verdict carry the colour; the chrome stays quiet.
- **Signature:** a sourced figure is set in Plex Mono with a dotted underline; clicking it opens its source.

## Themes and tokens

Light and dark on `html[data-theme]`, applied before first paint by the boot script in `src/lib/ui/theme.ts` (preference `aplomb.pref.theme`: `light`, `dark` or `system`). All values live in `src/styles/tokens.css`; components use tokens only.

| Role | Light | Dark | Use |
|---|---|---|---|
| `--bg` / `--deep` | `#FAFAFA` / `#F4F4F5` | `#141415` / `#0F0F10` | Page (one solid colour) / sidebar |
| `--surface` / `--raised` | `#FFFFFF` / `#F4F4F5` | `#19191B` / `#232325` | Cards / active rows, inputs, nested blocks |
| `--text` / `--text-2` / `--text-3` | `#171717` / `#525252` / `#666666` | `#EDEDED` / `#A1A1A6` / `#8E8E94` | Three text roles; `--text-3` for meta only |
| `--line` | text at 8 % | text at 8 % | Hairlines; depth comes from surface steps, not shadows |
| `--accent` | `#2F5BFF` | `#2F5BFF` | Cobalt: primary action, selection, the key line. A few percent of the screen |
| `--accent-text` / `--focus` | `#2444D6` / `#2F5BFF` | `#93AAFF` / `#93AAFF` | Links and sourced figures / focus ring |
| pass / tension / conflict / nee | green / amber / red / grey text | same, stepped for dark | Status only: coloured text with its icon, never a filled pill |
| `--chart-1` / `--chart-4` | cobalt / grey | light cobalt / grey | Tracked series / comparison (dashed) |
| `--cat-1…5` | aqua, blue, orange, violet, magenta | stepped for dark | Allocation identity (validated with the dataviz palette script) |

`tests/ui-contrast.test.ts` reads `tokens.css` and checks every text role, accent text and status colour at WCAG AA on every surface in both themes, white on the accent fills, and the focus ring at 3:1. Run it after any token change.

## Type and shape

IBM Plex Sans for the interface (14 px base), IBM Plex Mono for sourced figures, codes and meta, Fraunces only for page titles and the wordmark. Weights 400 and 500 (600 rare). Sentence case everywhere. Local `@fontsource` files (OFL), no build-time network. Radius by size: control 8, card 12, panel 14, tags 4. Spacing on a 4 px grid. Scrollbars are thin and neutral (`base.css`).

## Layout

- **Sidebar:** 248 px with labels, or a 64 px icon rail (toggle in the sidebar head, preference `aplomb.pref.sidebar`, applied before paint as `html[data-sidebar]`; labels stay for screen readers and as tooltips). It holds the fictional-investor switcher (a styled `Listbox`) and the navigation (one highlight per list, placed in list coordinates by `useSlidingPill`). On phones it becomes the left menu drawer.
- **Page header bar:** data date, currency and risk, the window control (pages other than Home), language and theme. The simulation disclaimer is a quiet line under it on every page.
- **Home dashboard:**
  - A **scope bar** drives every widget. The period is an app window or a custom date range (`window=custom&start&end`), and the API recomputes every window-based figure on it. The benchmark is requested from the API. Asset classes and a minimum weight narrow Allocation and Positions. The chart view (value, base 100, drawdown) re-expresses the plotted series. Fixed-horizon returns stay fixed and are labelled so. The scope is stored as `aplomb.pref.dashboard.scope.v1`.
  - **Widgets** sit on a 12-column grid of 32 px rows. In edit mode, a widget moves when dragged by its handle and resizes from its corner, snapping to columns and rows within its limits. Arrow keys on either handle do the same, with a live announcement. The layout is stored as `aplomb.pref.dashboard.layout.v1`, and Reset layout restores the default. Below 880 px of grid width the widgets stack in one column.

## Components

StatusBadge pairs icon and text, never colour alone. FactChip is a button whose accessible name always uses `display`; it may wrap a visual (`RollingText`). `Listbox` is a styled single-select (APG listbox: arrows, Home/End, typeahead, Escape returns focus); native `<select>` elements get `appearance: base-select` styling where supported. `SegmentedControl` is a radio group (one tab stop, arrows, 44 px hit areas, accessible name starts with the visible label). `DonutChart` ships a legend list with every value; the ring is `aria-hidden`. `LineChart` keeps legend and units outside the hover tooltip and has `SeriesTable` as its table view. `LimitationList compactAfter={n}` folds limitations after the first n. Inside a dashboard grid, `Card` reads `WidgetContext` and becomes a widget (handles only in edit mode).

Targets: 44 px hit areas (invisible `::after` where the visual is smaller). Focus ring 2 px `--focus`, 2 px offset. Drawers trap focus, close on Escape and return focus.

## Motion

One curve (`cubic-bezier(0.22, 1, 0.36, 1)`). Hover is a colour or surface change; press scales to 0.98. One short entrance on load (fade and 8 px rise, 50 ms stagger, on the panels themselves), figures that roll when they change, menus that fade in 4 px, drawers that slide. Nothing loops. Start states live only in `@keyframes` with `backwards` fill. Everything is off under `prefers-reduced-motion` and while the page is hidden (`html[data-motion="off"]`).

## Wording

Use "hypothetical scenario", "rule assumption", "historical in this sample", "financial impact not established". Boundary label: "Largest size before the first rule conflict", followed by evidence/tension status. Show currency and window next to figures, the data date near the page header, and the simulation disclaimer on every page. No trailing periods on labels and buttons, no exclamation marks. French may repeat English if cut, but never omit keys or show raw enum identifiers.

## Review

Check both themes, the collapsed sidebar, focus paths, AA contrast (`tests/ui-contrast.test.ts`), 375 / 768 / 1024 / 1440 px, long translated labels, no-data and custom-range error states, and keyboard move/resize in edit mode. Keep chart legends and units outside tooltips; every chart has a table or list alternative.
