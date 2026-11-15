# Design system and interaction rules

**Owner:** T13. Direction set on 2026-11-15 by the [Liquid Glass redesign](../docs/superpowers/specs/2026-11-15-liquid-glass-design.md), which replaces the [unslop pass](../docs/superpowers/specs/2026-11-15-unslop-dashboard-design.md) of the same day. Reference: three dashboard captures supplied by the user (Reports, Good morning, Activity), adapted to Aplomb's palette and pages.

## Direction

- **Product:** tests hypothetical investment changes against a fictional investor's plan; every figure links to its source.
- **Character:** calm, exact, evidential, light to use.
- **Material:** frosted glass panes floating over a fixed ambient field (fine graph paper, the survey world of the plumb-line logo, under two still pools of cobalt and aqua light).
- **Moment:** the fictional value is the one cobalt tile; the history chart, the plan verdict and the correlation heatmap carry the colour. The chrome stays graphite.
- **Signature:** a sourced figure has a dotted underline; clicking it opens its source.
- **Less to read:** one useful sentence under each title; notes live behind an "i" (`InfoTip`) or in a folded `<details className="fold">`; technical identifiers (run, request, model, dataset version, hash) only under "Technical details" or on Evidence and System.

## Themes and tokens

Light and dark on `html[data-theme]`, applied before first paint by the boot script in `src/lib/ui/theme.ts` (preference `aplomb.pref.theme`: `light`, `dark` or `system`). All values live in `src/styles/tokens.css`.

| Role | Light | Dark | Use |
|---|---|---|---|
| `--bg` / `--deep` | `#ECEFF5` / `#E3E7EF` | `#0B0D12` / `#101218` | Page / wells (opaque) |
| `--surface` / `--raised` | `#FFFFFF` / `#F2F4F8` | `#1A1C23` / `#22252D` | Opaque composites of the glass; fallbacks |
| `--glass-panel` / `--glass-card` / `--glass-pop` | white at 50 / 72 / 82 % | graphite at 55 / 55 / 86 % | Page panel / cards / menus, drawers, tooltips |
| `--chrome` | graphite at 80 % | lifted graphite at 66 % | Top bar, rail, dock (text `--chrome-text`) |
| `--ink-fill` | `#18191E` | `#F2F3F6` | Selected segment, `.btn.ink` (the template's dark pills) |
| `--text` / `--text-2` / `--text-3` | `#171717` / `#4B4B52` / `#5F5F67` | `#EDEDF0` / `#A6A7AF` / `#92939B` | Three text roles; `--text-3` for meta only |
| `--accent` | `#2F5BFF` | `#2F5BFF` | Cobalt: main action, tracked series, the value tile |
| pass / tension / conflict / nee | green / amber / red / grey | stepped for dark | Status: text with its icon on a faint tint |
| `--cat-1…5` | aqua, blue, orange, violet, magenta | stepped for dark | Allocation identity |

The correlation heatmap uses its own diverging scale in `src/lib/ui/corr.ts` (cobalt −1, neutral 0, orange +1; OKLab interpolation; black or white cell text, whichever contrasts more). `tests/ui-contrast.test.ts` checks every text role and status colour at WCAG AA on the opaque surfaces in both themes; `tests/corr-scale.test.ts` checks every heatmap step.

## Glass

`.glass` (page panel), `.glass-pop` (popovers) and `.chrome` (floating chrome) paint their fill and `backdrop-filter` on `::before` and a specular rim on `::after`, behind the content in an isolated stacking context, so menus opened inside them can still frost the page. Cards inside the panel are translucent without their own blur. Under `prefers-reduced-transparency`, without `backdrop-filter` support, or in forced colours, every pane falls back to an opaque surface.

## Type and shape

Instrument Sans (variable weight and width, local `@fontsource-variable/instrument-sans`) for everything; IBM Plex Mono only for identifiers in technical details. Titles 650 weight, tight tracking; figures in tabular numerals. Sentence case. Radius by size: panel 28, card 20, control 12, chips and buttons fully round.

## Layout

- **Top bar** (floating, sticky): investor switcher, **Ask Aplomb** (text sent to Decide as `?q=`, interpreted once; `/` focuses it; where the browser has speech recognition a microphone dictates into the field, one utterance per press, cobalt while listening, Escape cancels; the words are only filled in, never sent on their own), the simulation note (short on the bar, full text for assistive technology), Help (tutorials) and Settings (language, theme, profiles, data date).
- **Rail** (floating, left): the eight pages (Strategies after Decide) and Sources as icons with tooltips; the bottom arrow shows labels (`aplomb.pref.sidebar`, `html[data-sidebar='expanded']`). Phones use the menu drawer instead.
- **Page panel:** title and one sentence on the left, the period control and main action on the right (`PageHeader actions`).
- **Section dock** (floating, bottom): every element in `<main>` with `data-section` and an `id` (via `Card section=…` or a dashboard widget's `section`), shown from three sections, with scroll spy; the cobalt + tests a move. Hidden on phones.
- **Home:** scope bar (period or custom range, benchmark, asset classes, minimum weight, chart view); Reset layout sits in the page header, always shown, inactive while the layout is the default over a 12-column grid of widgets (`aplomb.pref.dashboard.layout.v1`); key figures are four tiles with the value tile in cobalt. Details: [movable widgets and details sheets](../docs/superpowers/specs/2026-11-15-movable-widgets-details-design.md).
  - **Always arrangeable, no edit mode.** Grab a widget by its header: after 5 px of travel it lifts (scale 1.025, denser glass, deeper shadow) and follows the pointer, a recessed slot shows where it will land, the others glide out of its way, and it settles into the slot on release. A plain click on the header stays a click. The grabber at the top edge (on hover or focus) is the keyboard handle (arrows, Home/End); the corner handle resizes within the widget's limits (arrows too). Every change is announced. Below 880 px of grid width the widgets stack and do not move.
  - **A widget never scrolls.** It shows its essentials and adapts to its size: Positions shows the rows that fit, then "+N"; Plan health adds the rules nearest their limit as room allows; the chart fills the widget. Tables, limitations, method, the full brief and its steps open from ⤢ in a details sheet. Minimum sizes still hold the essentials.

## Strategies

[Strategies](page-specs/strategies.md) shows standing automations (rebalancing, regular contributions, risk guard) simulated on history next to the untouched holdings. Each kind has one colour, used only for its icon and its action labels: rebalance cobalt, contributions green, risk guard amber. Figures compare with "untouched" in a quiet second line; the strategy's figure turns green or red only when it is clearly better or worse. The Automations widget on Home shows each active strategy's next action; "Due now" is the only emphasis. Proposals only, said once on the page and in the widget's note.

## Guided tours

`src/lib/tour/engine.ts` (placement, mask, progress; tested in `tests/tour-logic.test.ts`), `src/features/tour/` (provider, overlay, help menu, scripts). Steps point at `data-tour="…"` attributes, open their page, wait up to 4 s for their element and skip optional ones that never appear. A welcome offers the basic tour once (`aplomb.pref.tour.v1`); the ? button replays it and lists one tutorial per use case. Keys: arrows, Enter, Escape; focus stays in the bubble and returns afterwards.

## Components

StatusBadge pairs icon and text. FactChip is a button whose accessible name uses `display`. `Listbox` is the APG listbox; `SegmentedControl` a radio group with a gliding ink pill; `InfoTip` an "i" whose note is also the button's description; `RunsTable` the shared list of analyses with state filter chips. `DonutChart` legends carry bars and every value; `LineChart` keeps legend and units outside the tooltip and has `SeriesTable`. Targets are 44 px (invisible `::after` where smaller); focus ring 2 px `--focus`, 2 px offset. `Card details={{ render }}` adds ⤢ and its `Sheet` (a centred glass panel, a bottom sheet on phones, growing out of the button that opened it). Dialogs (`Drawer`, `Sheet`) share `useDialogFocus`: focus moves in, Tab is trapped, Escape closes, focus returns to the opener, and the page does not scroll behind; open dialogs form a stack, so a source drawer opened from a sheet closes alone. Both render in a portal after mount (fact scopes still apply). `LineChart fill` sizes the chart to its container and `compact` puts the unit in the legend. On phones an `InfoTip` note is a fixed card at the bottom of the screen, so a hidden note can never widen the page.

## Motion

One curve (`cubic-bezier(0.22, 1, 0.36, 1)`). Pills glide (rail, dock, segments), figures roll when they change, menus rise 4 px, drawers slide, sheets grow from their button, the tour bubble glides between steps. One entrance on load; dashboard widgets enter through the Web Animations API and glide FLIP-style whenever their position changes (drag, keys, resize, reset), interruptible mid-flight. Browsers restart CSS animations on a node React re-inserts, so in-widget entrances are keyed to fresh content: `data-fresh` on rolling digits and drawn charts (`useFresh`), and on the grid for donuts and bars. Moving a widget never replays them. Nothing loops. Everything is off under `prefers-reduced-motion` and while the page is hidden (`html[data-motion="off"]`).

## Wording

Use "hypothetical scenario", "rule assumption", "historical in this sample", "financial impact not established" and the boundary label "Largest size before the first rule conflict". Say "analysis", not "run"; "steps", not "execution trace". The simulation note is on every page (top bar) and in every brief. No trailing periods on labels and buttons, no exclamation marks, no raw enum or code shown as a label.

## Review

Check both themes, the expanded and collapsed rail, focus paths (sheet → source drawer → back) and tours by keyboard, that no Home widget scrolls at its default and minimum sizes, header drag (a click stays a click), AA contrast, 375 / 768 / 1024 / 1440 px, reduced motion and reduced transparency, long French labels, and no-data, error and feature-off states.
