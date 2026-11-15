# Bundled geography

`countries-110m.json` is the unmodified `countries-110m.json` of the npm package
[`world-atlas` 2.0.2](https://github.com/topojson/world-atlas) (TopoJSON, about 108 kB).

- Geometry: Natural Earth 1:110m Admin 0 country boundaries. Natural Earth data is in the
  **public domain** (https://www.naturalearthdata.com/about/terms-of-use/).
- Packaging: `world-atlas` is published under the **ISC** licence, Copyright 2013-2019 Michael Bostock.
  Permission to use, copy, modify, and/or distribute this software for any purpose with or without
  fee is hereby granted, provided that the above copyright notice and this permission notice appear
  in all copies. The software is provided "as is" without warranty of any kind.

The World Explorer globe (`src/features/world/GlobeView.tsx`) fetches this file from the site's own
origin and decodes it with `src/lib/geo.ts`. No texture, tile or geography file is fetched from a
third party at runtime. Outlines are a display aid; they carry no claim about borders.
