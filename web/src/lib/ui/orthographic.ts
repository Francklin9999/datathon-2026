/**
 * Orthographic projection for the navigation mini globe (components/shell/MiniGlobe.tsx): pure
 * functions that rotate a lon/lat point to a view centre, project it onto a disc and build SVG paths.
 * The back hemisphere (cos c < 0) is hidden. A ring that crosses the horizon keeps its hidden points
 * pushed out to the rim, so the outline follows the edge of the disc; a ring wholly behind is skipped.
 */

export type LonLat = readonly [number, number];

export interface OrthoView {
  /** Longitude at the centre of the disc, in degrees. */
  lambda0: number;
  /** Latitude at the centre of the disc, in degrees. */
  phi0: number;
  /** Disc radius, in SVG units. */
  r: number;
  /** Disc centre, in SVG units (y grows downward). */
  cx: number;
  cy: number;
}

export interface Projected { x: number; y: number; visible: boolean }

const RAD = Math.PI / 180;

/** The point's direction seen from the view centre: east (x), north (y) and depth (cos c, > 0 in front). */
export function rotate([lon, lat]: LonLat, lambda0: number, phi0: number): { x: number; y: number; cosC: number } {
  const phi = lat * RAD;
  const p0 = phi0 * RAD;
  const dl = (lon - lambda0) * RAD;
  const cosPhi = Math.cos(phi);
  return {
    x: cosPhi * Math.sin(dl),
    y: Math.cos(p0) * Math.sin(phi) - Math.sin(p0) * cosPhi * Math.cos(dl),
    cosC: Math.sin(p0) * Math.sin(phi) + Math.cos(p0) * cosPhi * Math.cos(dl),
  };
}

/** Projects lon/lat onto the disc. `visible` is false on the back hemisphere. */
export function project(point: LonLat, view: OrthoView): Projected {
  const { x, y, cosC } = rotate(point, view.lambda0, view.phi0);
  return { x: view.cx + view.r * x, y: view.cy - view.r * y, visible: cosC >= 0 };
}

const round = (value: number) => Math.round(value * 10) / 10;

/** A hidden point moved to the rim along its own direction from the centre (the horizon). */
function toRim(point: Projected, view: OrthoView): Projected {
  const dx = point.x - view.cx;
  const dy = point.y - view.cy;
  const length = Math.hypot(dx, dy);
  if (length < 1e-9) return point;
  return { x: view.cx + (dx / length) * view.r, y: view.cy + (dy / length) * view.r, visible: false };
}

/** SVG path of one closed ring, or null when none of it faces the viewer. */
export function ringPath(ring: readonly LonLat[], view: OrthoView): string | null {
  if (ring.length < 3) return null;
  const points = ring.map(point => project(point, view));
  if (!points.some(point => point.visible)) return null;
  const drawn = points.map(point => (point.visible ? point : toRim(point, view)));
  return `M${drawn.map(point => `${round(point.x)},${round(point.y)}`).join('L')}Z`;
}

/** SVG path of a polygon (outer ring and holes); empty when wholly hidden. */
export function polygonPath(rings: readonly (readonly LonLat[])[], view: OrthoView): string {
  return rings.map(ring => ringPath(ring, view)).filter((path): path is string => path !== null).join('');
}

export type OrthoGeometry =
  | { type: 'Polygon'; coordinates: readonly (readonly LonLat[])[] }
  | { type: 'MultiPolygon'; coordinates: readonly (readonly (readonly LonLat[])[])[] };

/** SVG path of a polygon or multipolygon (draw with fill-rule evenodd); empty when wholly hidden. */
export function geometryPath(geometry: OrthoGeometry, view: OrthoView): string {
  if (geometry.type === 'Polygon') return polygonPath(geometry.coordinates, view);
  return geometry.coordinates.map(polygon => polygonPath(polygon, view)).join('');
}

/** SVG path of an open line (a graticule line), broken where it passes behind the globe. */
export function linePath(line: readonly LonLat[], view: OrthoView): string {
  let path = '';
  let drawing = false;
  for (const point of line) {
    const p = project(point, view);
    if (!p.visible) { drawing = false; continue; }
    path += `${drawing ? 'L' : 'M'}${round(p.x)},${round(p.y)}`;
    drawing = true;
  }
  return path;
}

/** Meridians and parallels every `step` degrees, sampled every `sample` degrees. */
export function graticule(step = 30, sample = 5): LonLat[][] {
  const lines: LonLat[][] = [];
  for (let lon = -180; lon < 180; lon += step) {
    const line: LonLat[] = [];
    for (let lat = -90; lat <= 90; lat += sample) line.push([lon, lat]);
    lines.push(line);
  }
  for (let lat = -90 + step; lat < 90; lat += step) {
    const line: LonLat[] = [];
    for (let lon = -180; lon <= 180; lon += sample) line.push([lon, lat]);
    lines.push(line);
  }
  return lines;
}

/** Signed shortest turn from one longitude to another, in degrees (-180, 180]. */
export function lonDelta(from: number, to: number): number {
  const d = (((to - from) % 360) + 540) % 360 - 180;
  return d === -180 ? 180 : d;
}

/**
 * The design system's single curve, cubic-bezier(0.22, 1, 0.36, 1), as a function of time in [0, 1]
 * (x is solved by Newton steps, then bisection).
 */
export function easeCurve(t: number): number {
  if (t <= 0) return 0;
  if (t >= 1) return 1;
  const x1 = 0.22; const y1 = 1; const x2 = 0.36; const y2 = 1;
  const bez = (s: number, a: number, b: number) => 3 * a * s * (1 - s) ** 2 + 3 * b * s * s * (1 - s) + s ** 3;
  const slope = (s: number, a: number, b: number) => 3 * a * (1 - s) ** 2 + 6 * (b - a) * s * (1 - s) + 3 * (1 - b) * s * s;
  let s = t;
  for (let i = 0; i < 6; i++) {
    const dx = bez(s, x1, x2) - t;
    const d = slope(s, x1, x2);
    if (Math.abs(dx) < 1e-6) return bez(s, y1, y2);
    if (Math.abs(d) < 1e-6) break;
    s -= dx / d;
  }
  let lo = 0; let hi = 1; s = t;
  for (let i = 0; i < 30; i++) {
    const x = bez(s, x1, x2);
    if (Math.abs(x - t) < 1e-6) break;
    if (x < t) lo = s; else hi = s;
    s = (lo + hi) / 2;
  }
  return bez(s, y1, y2);
}
