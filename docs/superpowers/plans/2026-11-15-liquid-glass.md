# Liquid Glass redesign — progress

Design and scope: [2026-11-15-liquid-glass-design.md](../specs/2026-11-15-liquid-glass-design.md). Branch `feat/liquid-glass`; every checkpoint is committed and pushed, then one PR to `main` (a push to `main` redeploys the live site).

To resume after an interruption: read this file, take the first unchecked item, and run `npm run typecheck` and `npm run test:contracts` from `web/` before committing.

- [x] 1. Branch, design spec and this progress file
- [x] 2. Foundations: tokens, fonts, ambient background, glass material, shell (top bar, command bar, nav rail, page panel, section dock, single disclaimer, settings)
- [x] 3. Shared components: cards, buttons, segmented controls, listboxes, tables and filter chips, status, drawers, states, charts
- [x] 4. Home following the template, plus Home cleanup
- [ ] 5. Portfolio (correlation heatmap), Decision Desk, Evidence & Audit: cleanup, style, dock sections
- [ ] 6. World Explorer, Time Machine, Agents & System, Profiles, Sources: cleanup, style, dock sections
- [ ] 7. Tour engine, basic tour, Help menu
- [ ] 8. Advanced tutorials
- [ ] 9. DESIGN.md rewrite, tests, full verification, PR

## Notes

- Checkpoints 2 and 3 landed together: the segmented control moved from shell.css to components.css, so the shell could not ship without the component layer.
- Rail default is now the collapsed icon rail; `html[data-sidebar='expanded']` shows labels (boot script and `useSidebarState` inverted).
- SVG refraction on the chrome is deferred to the polish pass (step 9); the glass uses blur, saturation and a specular rim.
- New shared pieces: `InfoTip` (fold a note behind an "i"), `Card` props `section` (dock entry), `info`, `tour`; `PageHeader` props `actions`, `tour`; classes `.fold` (details), `.filter-chips`/`.fchip`, `.btn.ink`, `.tech-details`.
