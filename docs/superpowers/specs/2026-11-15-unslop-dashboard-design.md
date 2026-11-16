# Aplomb UI — unslop pass, configurable dashboard and data scope

**Date:** 2026-11-15 · **Follows:** 2026-11-14 glass UI · **Design contract:** [web/DESIGN.md](../../../web/DESIGN.md)

## Requests (user)

1. Remove what reads as AI-generated design: coloured pill badges and rounded colour bars, glass, ambient gradients. Use a solid background and replace navy/gold with one vivid primary colour.
2. Style the fictional-investor dropdown.
3. Make the left menu expandable and collapsible.
4. Style every scrollbar.
5. Let people move dashboard widgets anywhere and resize them, within limits.
6. Add a data scope to the dashboard (for example 1 Jan 2023 → 1 Jan 2026) that every widget follows, plus other criteria useful to analysts.
7. At the end, run the [unslop](https://github.com/heydamir/unslop) skill over the whole front end. unslop is by Damir Sokolovsky (@heydamir) and licensed CC BY 4.0.

The user was then unavailable and asked for the recommended options. Both choices below were recommended and confirmed by the user before they left.

## Decisions

- **Direction (unslop):**
  - Character: exact, sober, evidential.
  - World: survey and audit instruments.
  - Moments: the history chart and the plan verdict.
  - Signature: sourced figures in mono with a dotted underline.
  - Graphite neutral ramp, solid background, **cobalt `#2F5BFF`** accent. Cobalt was chosen over orange and emerald because it does not collide with the amber and green status colours.
- **Status:** coloured text with its icon. No filled pills and no bars in Plan health; counts are shown as figures.
- **Custom period, backend:** `backend/aplomb/profiles/service.py` now accepts `window=custom&start&end` for overview, performance and frontier. Plus one line in `optimizer/frontier.py`, with unit and HTTP tests. The engine and the API contract already supported custom windows; only the service rejected them.
- **Scope boundary:** a custom period is a dashboard scope, not the global window. Decision Desk, runs and the other pages keep preset windows, which all their endpoints support. Presets selected in the scope bar update the global window.
- **Honest criteria:**
  - Period and benchmark: every figure comes from the API for that scope.
  - Asset classes and minimum weight: narrow only the holdings widgets (Allocation, Positions), and this is written under the scope bar.
  - Chart view (value, base 100, drawdown): re-expresses the plotted series.
  - Period change: labelled "read from the plotted series".
  - Fixed horizons (YTD, 1/3/5 years, 2022 replay): labelled as fixed.
- **Layout engine:** built in house, no new dependency. It is an ordered list of widgets on 12 columns × 32 px rows, with per-widget size limits.
  - Pointer: drag by the handle; the other widgets reflow. Resize snaps from the corner.
  - Keyboard: arrows on either handle, with a live announcement.
  - Stored as a UI preference; one column below 880 px of grid width.
- **Dropdown:** a styled `Listbox` following the APG listbox pattern for the investor switcher. Other native selects get `appearance: base-select` styling where the browser supports it.
- **Sidebar:** 248 px or a 64 px rail. The preference is applied before paint, labels stay for screen readers and as tooltips, and the width is not animated.

## Approaches considered

| Area | Chosen | Rejected because |
|---|---|---|
| Widget layout | In-house grid with pure, tested layout logic | `react-grid-layout`: a new dependency in a manifest another track owns, and free-placement compaction is more than this dashboard needs |
| Custom period | Server recomputation (small service change) | Client-side recomputation from the series: figures without provenance, against the product rule |
| Investor dropdown | Custom listbox | Native `<select>` only: its list cannot be styled in every browser |

## Verification

- **Unit tests:** layout, scope, series, listbox keyboard and window query (`tests/dashboard-logic.test.ts`, `tests/ui-logic.test.ts`).
- **Contrast:** a WCAG AA guard that reads `tokens.css` (`tests/ui-contrast.test.ts`).
- **Backend:** pytest for custom windows.
- **Browser:**
  - Custom range 2023-01-01 → 2026-01-01 gives volatility 5.6 % and drawdown 5.5 %, matching the engine.
  - SPY benchmark is dashed, with +87.7 % over the range.
  - Base 100 view, and the Equity filter (47 %, 7 of 11 positions).
  - Drag, pointer resize and keyboard resize, all stored and announced.
  - Collapsed rail with the investor menu.
  - No horizontal overflow on any page at 375, 1024 or 1280 px.
- **Build:** the static export builds.
