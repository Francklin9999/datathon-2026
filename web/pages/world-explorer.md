# World Explorer — sourced events and exposure

**Owner:** T15. **Tier:** P1; facilities/hazards cut item 2. Route `/world-explorer/`. Backend: [world spec](../../backend/aplomb/world/SPEC.md).

## Data and layout

Fetch layers, event page and profile exposure. Desktop: globe with filter toolbar and event feed/country panel; mobile: feed first, optional globe. `react-globe.gl` runs only inside client component, loaded lazily, with WebGL-unavailable fallback. Globe is an alternate view of the feed, never the only way to select an event.

Filters: date interval <=366 days, categories, source/origin, country, ticker/theme and relevance. Paginate feed with stable cursor and display loaded vs total counts. Limit rendered pin count separately, label aggregation/thinning and offer filters/next page. Do not claim to show all worldwide news. Dates default to dataset coverage, not an invented current-day feed.

## Interactions

Click pin/feed item → event detail with verbatim source title, publisher/link, occurred/published dates, location precision and related events. Profile exposure lists named/proxy/verified links with basis and evidence. “Brief me” starts event_brief and shows actual timeline, audited explanation and impact-not-established statement unless a measured observation exists. Click country → known listing/ETF exposure plus top events and supported macro facts.

Layer toggles use availability and feature flags. Facilities: year/operator/reported tonnes and match confidence; hazards: source/time/magnitude. Proximity is not proof of holdings impact. Unknown country/exposure and partial ETF coverage remain visible as residual, not reassigned.

## Empty/failure states and verification

Unavailable layers disabled with reason, stale cache dated, upstream lookup failure does not erase cached feed. No WebGL shows accessible list/table. Keyboard feed selection opens same panel as globe; reduced motion stops auto-rotation. WUI-01 filters/cursors/counts, WUI-02 source/location precision, WUI-03 factual exposure basis, WUI-04 no invented impact, WUI-05 layer unavailable/cache stale, WUI-06 feed-only/mobile/reduced-motion. Build initially against labelled fixtures, then real cached batch before claiming integration.
