# Aplomb UI — always-movable widgets, no-scroll widgets and details sheets

**Date:** 2026-11-15 · **Builds on:** [Liquid Glass redesign](2026-11-15-liquid-glass-design.md) (PR #1) · **Design contract:** [web/DESIGN.md](../../../web/DESIGN.md)

## Requests (user)

1. Let people move the widgets. The layout editor hid moving behind a mode.
2. Make the widgets large enough to have no scrollbar; when a widget has a lot to show, add a small button that opens the details.
3. As little text as possible; keep the animations for a sense of fluidity.

A parallel Apple-style glass pass was written on the same day before the team's redesign landed. After the pull, the user chose to keep the team's visual system (shell, tours, globe and fonts depend on it) and to port these interactions onto it.

## Decisions

- **No edit mode.** A press on a header becomes a drag after 5 px of travel, so clicks and the header's own controls still work. The grabber at the top edge is the keyboard handle and a pointer handle for bare widgets (key figures). The corner handle shows on hover or focus. Reset layout replaces the editor button: always shown in the page header (so it can be found), inactive while the layout is already the default. The layout tour step now points at the grid.
- **Lift, slot, glide.** The dragged widget is placed with `transform` and lifted with the independent `scale` property, so the lift transitions while the drag follows the pointer. It takes denser glass while lifted, because the team's cards have no blur of their own and would show the widget beneath. Hit-testing uses layout offsets, not the gliding transforms, so neighbours never flip-flop. The other widgets move FLIP-style with the Web Animations API from where they are drawn, which also covers keyboard moves, resizes and reset.
- **Animations that survive reordering.** React re-inserts a moved node and the browser restarts its CSS animations. The widget entrance therefore runs through WAAPI. The team's in-widget entrances only apply while content is fresh:
  - rolling digits and drawn charts, re-keyed when their data changes, through `useFresh` and `data-fresh`;
  - donuts and bars, through a grid-level `data-fresh`.

  The animation setting (`html[data-anim]`) is honoured by the WAAPI code as by the CSS.
- **No scrolling.** `.widget-body` is `overflow: hidden`. Fixed row heights let Positions and Plan health count what fits (`fitCount`); the chart measures its container (`LineChart fill`). Defaults were set from 48h − 16 px per widget of h rows and checked in the browser.
- **Details sheet.** It is a modal sheet rather than an expanding widget: it keeps the grid stable and works the same on phones (bottom sheet). `useDialogFocus` is shared with the drawer and keeps a stack, so a source drawer opened from a sheet closes alone on Escape. These moved to sheets:
  - the history table and limitations;
  - the nearest-limit rules with figures, not-enough-evidence reasons, limitations and Open rules;
  - the full positions table with values;
  - the brief's steps, method, audit link and investigation links.
- **Phone overflow (found while checking the pull).** A hidden `InfoTip` note keeps its layout box, which widened six pages to 471 px at a 375 px viewport. On phones the note is now a fixed card at the bottom of the screen.

## Verification

- `npm run typecheck`: clean. `npm run test:contracts`: 203 passing, including `reorderTarget`, `isDefaultLayout` and `fitCount`. Two fail exactly as before the change: they need the repository `.venv`, whose base interpreter is missing on this machine.
- **Browser** (Chrome, live local API, every page at 1440 and 375 px in light and dark):
  - No widget scrolls (before: Positions and Plan health). No horizontal overflow on any page (before: six pages on phones).
  - No page errors.
  - Header drag lifts the widget, shows the slot, animates the neighbour, stores the order and shows Reset layout. A click does not drag.
  - The keyboard move keeps focus on the grabber; pointer resize works.
  - The sheet traps focus and returns it on Escape.
