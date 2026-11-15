# Design system and interaction rules

**Owner:** T13. Glass redesign spec: [2026-11-14 glass UI](../docs/superpowers/specs/2026-11-14-glass-ui-design.md). Original reference: [prototype](../Datathon2026/aplomb-ui/project/Main.dc.html) (visual language only, not its hardcoded metrics or missing support.js).

## Themes and tokens

Two themes, light and dark, on `html[data-theme]`. A boot script in `<head>` (`src/lib/ui/theme.ts`) applies the stored preference (`aplomb.pref.theme`: `light`, `dark` or `system`) before first paint; `system` follows `prefers-color-scheme` live. The toggle (`ThemeToggle`) cycles light → dark → system. All values live in `src/styles/tokens.css`; components use tokens only, never hex (brand gold in the logo is the one exception).

| Role | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#E3E9EE` | `#050E17` | Ambient base behind the glass |
| `--glass` | white 52 % | `rgba(16,30,44,.55)` | Top-level panels: sidebar, topbar, cards, KPI tiles |
| `--glass-strong` | `#FAFCFD` 86 % | `#0D1B27` 86 % | Drawers, tooltips |
| `--tile` | white 58 % | white 4.5 % | Nested items (flat tint, no blur) |
| `--text` / `--text-2` / `--text-3` | `#10202E` / `#3D4E5F` / `#536475` | `#EDF2F5` / `#AAB8C4` / `#8B9CAB` | Primary, secondary, muted |
| `--accent` → `--accent-2` | `#0B5E66` → `#12818A` | `#0F6A6F` → `#157F84` | Primary buttons, selected segments (white text) |
| `--accent-text` | `#08585F` | `#6CD4C9` | Links, proof chips |
| `--gold` / `--focus` | `#E3A53B` / `#D08B17` | `#E3A53B` / `#F2B84E` | Brand accent, focus ring, active-nav edge |
| pass / tension / conflict / nee | fg on tinted bg, see tokens | same, re-stepped for dark | Status only, always with icon + text |
| `--cat-1…5`, `--cat-other` | aqua, blue, orange, violet, magenta | same hues stepped for dark | Categorical identity (validated with the dataviz palette validator) |
| `--chart-1` / `--chart-4` | teal / slate | light teal / slate | Portfolio line / benchmark (dashed) |

Every text and badge token is checked at WCAG AA against its worst background (the glass over the brightest point of the ambient gold light) by `tests/ui-contrast.test.ts`, which reads `tokens.css` directly; focus ring and active-nav edge are checked at 3:1. Run it after any token change.

Opaque fallbacks: `@supports not (backdrop-filter)` and `prefers-reduced-transparency: reduce` turn glass into solid surfaces with the same hierarchy.

## Type and shape

Fraunces Variable (`opsz`, `SOFT`) for headings and large figures, IBM Plex Sans for UI, IBM Plex Mono only inside proof chips (the face means "this figure has a source"). Fonts are local `@fontsource` packages (OFL), so the build makes no network calls. Base text 15 px, line-height 1.5; page titles 28–44 px. Labels are sentence case (no tracked-out capitals). Radius follows hierarchy: panel 24, card 20, tile 16, control 12, chip 8, pill 999.

## Glass rules

Blur (`--glass-blur` 22 px, saturate 150 %) only on top-level panels; anything nested is a flat tint, so backdrop filters never stack. The ambient layer (`AmbientBackground`) is a fixed set of radial gradients: a soft vertical gold "plumb" shaft (the logo's plumb line) plus teal and blue haze, with a faint grain. Only `transform` animates there, very slowly, and never under reduced motion.

## Layout

Desktop: floating glass sidebar (248 px, 12 px inset) with the fictional-investor card (native `<select>` laid over the card), icon navigation and a sliding active pill with a gold edge; sticky glass topbar with data date, currency/risk, window segmented control (All / 1Y / 3Y / 5Y / YTD; full label as accessible name), language and theme; the disclaimer as a gold pill under it. Content max 1560 px. Home is a dashboard: KPI row, chart + allocation, largest positions + plan health, and a right rail (longer horizons, stress test, diversification) that folds under the grid below 1600 px. Mobile < 768 px: sidebar becomes a left drawer, the investor card moves into the topbar, the topbar scrolls away, cards go single-column, tables scroll horizontally inside their box, drawers are full width.

## Components

StatusBadge always includes text and icon, never colour alone. FactChip is a button with a readable value and an accessible "Show source for …" label; it can wrap a visual (e.g. `RollingText`) but its name always uses `display`. Large sourced figures (KPI, rail) keep the chip with a dashed underline instead of a box. RuleRow shows assumption label, value/threshold, status, missing reason and edit affordance only when editable. RunStep uses actual actor and duration; no pulsing fake progress. BriefSentence renders typed segments, struck text only in audit view. `SegmentedControl` is a radio group (one tab stop, arrows/Home/End; each segment a full 44 px target; accessible name starts with the visible label, e.g. "YTD, Year to date"). `DonutChart` always ships its meter-list legend with labels and values; the ring is `aria-hidden` and the legend is the text version. `LineChart` keeps legend and units outside the hover tooltip; `SeriesTable` is the table alternative. `LimitationList compactAfter={n}` shows the first n limitations and folds the rest into a disclosure.

Buttons and inputs: minimum 44 px target (small visuals get an invisible `::after` hit area); focus outline 2 px `--focus` with 2 px offset (the investor card shows it for keyboard focus only). Each route sets its own browser title (`%s · Aplomb`); `meta theme-color` follows the chosen theme. Native labels and controls where possible, inline errors plus summary, semantic headings and table headers, focus return and trap for drawers, Escape closes.

## Motion

Tokens from Arc library (MIT): ease-enter `cubic-bezier(0.16,1,0.3,1)`, ease-exit `cubic-bezier(0.7,0,0.84,0)`, durations 120 / 160 / 240 / 480 ms, spring `smooth` (0.4 s, no bounce) for drawers. Nav and segment highlights are one element per list, positioned in list coordinates (`useSlidingPill`, offsetLeft/Top) and moved with CSS transitions, so page scroll or a sticky parent can never make them jump. Motion answers actions or shows what changed: one entrance per display (fade + 8 px rise, 50 ms stagger), digits that roll in when figures arrive, the portfolio line drawing itself, meters growing, drawers sliding. Hover and press change colour/glow only (press may scale to 0.98). Segment highlights glide only for changes the person makes (restored preferences place them instantly); the nav highlight glides only after its first placement. Base styles are always the final visible state; start states live only in `@keyframes` with `backwards` fill. Entrance animations run on the panels themselves, never on a wrapper (an animated ancestor would cut the glass off from its backdrop). `prefers-reduced-motion` removes all of it (MotionConfig `reducedMotion="user"` for `motion`, media queries for CSS); a page opened in a hidden tab gets `html[data-motion="off"]` from the boot script until it becomes visible, so nothing freezes on a start frame. Announce terminal run/status changes through the polite live region without narrating polls.

## Wording

Use "hypothetical scenario", "rule assumption", "historical in this sample", "financial impact not established". Boundary label: "Largest size before the first rule conflict", followed by evidence/tension status. Show currency/window next to figures, data date near the page header, and the simulation disclaimer on every page. French may repeat English if cut, but never omit keys or show raw enum identifiers.

## Review

Check both themes, focus paths, AA contrast at actual sizes over the brightest ambient point, 375 / 768 / 1100 / 1440 / 1680 px, long translated labels, no-data cards, 40-position tables and very long source titles. Keep chart legends and units outside tooltips; provide a table or list alternative for every chart.
