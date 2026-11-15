# World Explorer — sourced events and exposure

**Owner:** T15. **Tier:** P1; facilities/hazards cut item 2. Route `/world-explorer/`. Backend: [world spec](../../backend/aplomb/world/SPEC.md).

## Data and layout

Fetch layers, all event pages for the selected filters and profile exposure. Desktop and mobile: globe with filter toolbar and an accessible event feed/country panel; the globe can be hidden. `react-globe.gl` runs only inside client component, loaded lazily, with WebGL-unavailable fallback. Globe is an alternate view of the feed, never the only way to select an event.

Default to “All data”: events and portfolio country weights plus up to 2,000 additional mapped provider observations. The provider query excludes duplicate core events and interleaves datasets and 15-degree geographic cells so large registries do not hide smaller feeds. Automatically retrieve four 500-record pages, then offer manual loading and topic/region filters. The selected source record retains a marker beyond the overview cap. References, news location mentions, alerts and sensor observations keep their distinct source meanings and dates; they are not all verified events. Feed lists show 100 records at a time.

Filters: date interval <=366 days, categories, source/origin, country, ticker/theme and optional portfolio relevance. Show all matching events by default, automatically following stable cursors with loading progress and a retry for partial failures. Offer every located event to the globe, grouping nearby pins at wider zooms; cap optional reference layers separately. Show the feed in batches of 100 with “Show more events.” Do not claim to show all worldwide news. Dates default to dataset coverage, not an invented current-day feed.

## Interactions

Hover an event pin → a small preview with the source title, category, recorded place/date/publisher and the feed’s portfolio-match flag. Hover pauses idle rotation. Click pin/feed item → a modal details sheet with the source report and a prominent “Potential exposure identified” or “No exposure identified” assessment from the event-detail API. Exposure lists matched holdings and weights with the basis and evidence available in a disclosure. Source dates, location precision and related events remain available. Dialogs trap focus, close with Escape or the backdrop, and return focus to the opener; event clicks leave full screen before opening the sheet. “Brief me” starts event_brief and shows actual timeline, audited explanation and impact-not-established statement unless a measured observation exists. Click country → known listing/ETF exposure plus top events and supported macro facts.

Source observation pins use topic colors and the same hover/popup interaction. Their popup shows the actual recorded summary, source, dates, precision and limitations. Every source record is assessed against all positive-weight positions using supported source names, themes and countries. Show “Potential exposure identified” or “No exposure identified,” the holdings checked and unique matched weight. The disclosure retains matching inputs, notes and calculation time. Actual missing source geography or holding listing countries remain visible, including alongside an empty result. A geographic or theme match identifies potential relevance and does not establish operational exposure or financial impact.

Layer toggles use availability and feature flags. Facilities: year/reporting company/reported tonnes and match confidence; hazards: source/time/magnitude; airports: current static registry reference. Each optional marker and its accessible table button opens a source and portfolio assessment popup. Every marker click leaves full screen before opening the popup. Optional layer cache keys include the profile version; profile changes clear selected source and reference popups. Proximity is not proof of holdings impact. Unknown country/exposure and partial ETF coverage remain visible as residual, not reassigned.

## Empty/failure states and verification

Unavailable layers disabled with reason, stale cache dated, upstream lookup failure does not erase cached feed. No WebGL shows accessible list/table. Keyboard feed selection opens same panel as globe; reduced motion stops auto-rotation. WUI-01 filters/cursors/counts, WUI-02 source/location precision, WUI-03 factual exposure basis, WUI-04 no invented impact, WUI-05 layer unavailable/cache stale, WUI-06 feed-only/mobile/reduced-motion. Build initially against labelled fixtures, then real cached batch before claiming integration.
