# Design system and interaction rules

**Owner:** T13. Reference: [original prototype](../Datathon2026/aplomb-ui/project/Main.dc.html). Reuse its visual language, not its hardcoded metrics or missing support.js dependency.

## Tokens

| Token | Value | Use |
|---|---|---|
| canvas | `#F0F3F4` | Page background |
| surface | `#FFFFFF` | Cards/drawers |
| navy | `#0F2233` | Sidebar/hero |
| ink | `#12202F` | Main text |
| muted | `#4A5B6C` | Secondary text |
| border | `#D6DEE3` | Dividers/cards |
| teal | `#0B5E66` | Primary action/links |
| gold | `#E3A53B` | Focus/accent; dark text on gold |
| pass | `#145B2E` on `#E0F2E6` | Fit |
| tension | `#734300` on `#FFF0D2` | Tension |
| conflict | `#8A1B12` on `#FCE9E6` | Conflict |
| nee | `#334759` on `#E7ECF1` | Not enough evidence |

Fraunces for headings, IBM Plex Sans for UI, IBM Plex Mono/tabular numerals for proof chips and numeric tables. Fallback Georgia/system-ui/ui-monospace. Base text 15–16 px, line-height 1.5; responsive headline 26–40 px. Cards 16 px radius, controls 12 px, subtle border/shadow. Spacing scale 4,8,12,16,24,32,48. Dense data must retain readable labels/units.

## Layout

Desktop persistent navy sidebar ~232 px; main content max ~1440 px with 24–32 px gutters. Topbar holds page title, persona, window/currency and language. Mobile <768 px uses a menu drawer, single-column cards and horizontally scrollable labelled tables; no whole-page horizontal overflow. Evidence drawer is right-side ~480 px on desktop and a full-width modal on mobile.

## Components

StatusBadge always includes text/icon, never color alone. FactChip is a button with readable formatted value and accessible “Show source for …” label; drawer shows fact kind, method, dates, nObs, source/retrieval/version, limitations and inputs. RuleRow shows assumption label, value/threshold, status, missing reason and edit affordance only when editable. RunStep uses actual actor and duration; no pulsing completed fake agent progress. BriefSentence renders typed segments, with struck text confined to audit view.

Buttons and inputs minimum 44 px interaction target; focus outline gold with 2 px offset. Use native labels/form controls where possible, inline errors plus summary for failed submission, semantic headings/table headers, focus return/trap for drawers, Escape close. Respect reduced motion; disable globe rotation and animate only when informative. Announce terminal run/status changes through a polite live region without narrating every poll.

## Wording

Use “hypothetical scenario,” “rule assumption,” “historical in this sample,” “financial impact not established.” Boundary label: “Largest size before the first rule conflict,” followed by evidence/tension status. Show currency/window next to figures, dataAsOf near page header, and simulation disclaimer persistently. French may repeat English if cut, but never omit keys or show raw enum identifiers.

## Review

Check focus paths, text contrast for actual sizes, 375/768/1440 px widths, long translated labels, no-data cards, 40-position tables and very long source titles. Keep chart legend and units outside tooltips too; provide an accessible table/feed alternative for charts and globe.
