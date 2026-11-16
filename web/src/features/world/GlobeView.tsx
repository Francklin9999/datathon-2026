'use client';
/**
 * WebGL globe (react-globe.gl, decision D-29). Imported ONLY through next/dynamic with `ssr: false`
 * from WorldGlobe.tsx: three.js needs `window`. It draws what it is given; it fetches nothing.
 *
 * Land is hexagons (neutral, or cobalt by the portfolio's weight in the country); events are spikes
 * whose height is their importance, fanned out when several share a spot; arcs join an event to the
 * exposed countries it names; the selected event pulses; earthquakes are dots sized by magnitude;
 * exposed countries carry a label with their weight. Hover text is passed up and rendered by React as
 * text: globe.gl's own HTML tooltips are off, so no source title is ever injected as HTML.
 *
 * Hover: the hexagons have gaps between them, so an invisible country shape sits just under them and
 * catches the pointer in the gaps; leaving a country is confirmed only after a short delay, so moving
 * across one country never flickers its caption. Islands too small for a hexagon get one, so events on
 * them do not seem to stand in the sea. Country labels move aside, whenever the view changes, so they
 * never cover an event spike.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Globe, { type GlobeMethods } from 'react-globe.gl';
import type { Lang } from '../../contracts/types';
import { countryCentroid, countryName, hexReadyCountries, outlineLabel, regionIso3, type CountryFeature } from '../../lib/geo';
import { islandHexes } from '../../lib/geoHex';
import type { InvestorMapEntry } from './investorMap';
import { insideBbox, viewportBounds, type GeographicArea } from '../../lib/world';
import {
  ATMOSPHERE_COLOR, CATEGORY_COLORS, LAND_HOVER_COLOR, PIN_RADIUS, REFERENCE_PIN_ALTITUDE, SPHERE_COLOR, exposureColor, labelOffset, pinColor,
  quakeRadius, spikeAltitude, spreadStacked, clusterPins, sourceGeometry, type GlobeHover, type GlobePin, type ScreenBox, type ScreenSpike,
} from './globeStyle';

export interface MapCommand { action: 'zoom-in' | 'zoom-out' | 'left' | 'right' | 'up' | 'down' | 'reset' | 'query'; sequence: number }
export interface GlobeViewProps {
  area: GeographicArea | null;
  command: MapCommand | null;
  onClusters: (count: number) => void;
  onViewport: (bbox: string) => void;
  onReady: () => void;
  pins: readonly GlobePin[];
  investors: readonly InvestorMapEntry[];
  selectedProfileId: string | null;
  selectedId: string | null;
  selectedGeometry: Record<string, unknown> | null;
  selectedCountry: string | null;
  countries: readonly CountryFeature[];
  /** Portfolio weight (percent) by ISO3 for the exposure layer; null = layer off. */
  exposure: ReadonlyMap<string, number> | null;
  rotate: boolean;
  /** Nothing to draw (stage off-screen, tab hidden, a sheet over the page): the render loop stops. */
  paused?: boolean;
  reducedMotion: boolean;
  lang: Lang;
  height: number;
  onPin: (pin: GlobePin) => void;
  onCountry: (iso3: string) => void;
  onHover: (hover: GlobeHover | null) => void;
  /** The person grabbed the globe: the stage stops the idle rotation. */
  onInteract: () => void;
}

interface Arc { id: string; startLat: number; startLng: number; endLat: number; endLng: number; color: [string, string]; selected: boolean }
interface Ring { lat: number; lng: number }
interface CountryLabel { iso3: string; lat: number; lng: number; name: string; value: string }

function solidTexture(color: string): string | null {
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 4; canvas.height = 4;
    const context = canvas.getContext('2d');
    if (!context) return null;
    context.fillStyle = color;
    context.fillRect(0, 0, 4, 4);
    return canvas.toDataURL('image/png');
  } catch {
    return null;
  }
}

/** Delay before the pointer counts as having left a country or a pin (ms). */
const HOVER_OUT_MS = 90;
const HIT_LAYER_COLOR = 'rgba(0,0,0,0)';
const noLabel = () => '';
const noSide = () => '';

const HEX_RESOLUTION = 3;
const LABEL_ALTITUDE = 0.03;

/** Camera target from the bounds of the validated France polygon; not a source point. */
function boundaryView(polygon: { geometry: Record<string, unknown> } | null): { lat: number; lng: number } | null {
  if (!polygon) return null;
  const coordinates = polygon.geometry.coordinates as number[][][] | number[][][][];
  const polygons = polygon.geometry.type === 'Polygon' ? [coordinates as number[][][]] : coordinates as number[][][][];
  let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
  for (const rings of polygons) for (const ring of rings) for (const [lon, lat] of ring) {
    if (lon === undefined || lat === undefined) continue;
    minLat = Math.min(minLat, lat); maxLat = Math.max(maxLat, lat);
    minLon = Math.min(minLon, lon); maxLon = Math.max(maxLon, lon);
  }
  return { lat: (minLat + maxLat) / 2, lng: (minLon + maxLon) / 2 };
}

/**
 * Moves each country label (its inner box, by CSS transform) to the nearest spot around its anchor that
 * covers no event spike on the visible side of the globe and no other label.
 */
function layoutLabels(globe: GlobeMethods, pins: readonly GlobePin[], labels: readonly CountryLabel[],
  elements: ReadonlyMap<string, HTMLElement>, selectedId: string | null): boolean {
  const camera = globe.camera().position;
  const radius = globe.getGlobeRadius();
  const facing = (lat: number, lng: number) => {
    const p = globe.getCoords(lat, lng, 0);
    return p.x * camera.x + p.y * camera.y + p.z * camera.z > radius * radius;
  };
  const spikes: ScreenSpike[] = [];
  for (const pin of pins) {
    if (pin.kind !== 'event' || !facing(pin.lat, pin.lng)) continue;
    const foot = globe.getScreenCoords(pin.lat, pin.lng, 0);
    const top = globe.getScreenCoords(pin.lat, pin.lng, spikeAltitude(pin.weight));
    const rim = globe.getScreenCoords(pin.lat + (pin.id === selectedId ? PIN_RADIUS.selected : PIN_RADIUS.event), pin.lng, 0);
    spikes.push({ ax: foot.x, ay: foot.y, bx: top.x, by: top.y, pad: Math.hypot(rim.x - foot.x, rim.y - foot.y) + 3 });
  }
  const taken: ScreenBox[] = [];
  let measured = true;
  for (const label of labels) {
    const el = elements.get(label.iso3);
    if (!el || !el.isConnected || !facing(label.lat, label.lng)) continue;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    if (!w || !h) { measured = false; continue; }
    const anchor = globe.getScreenCoords(label.lat, label.lng, LABEL_ALTITUDE);
    const { dx, dy } = labelOffset(anchor, { w, h }, spikes, taken);
    taken.push({ x: anchor.x + dx, y: anchor.y + dy, w, h });
    el.style.transform = `translate(${Math.round(dx)}px, ${Math.round(dy)}px)`;
  }
  return measured;
}

const fmtPct = (value: number, lang: Lang) => `${new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', { maximumFractionDigits: 0 }).format(value)}${lang === 'fr' ? ' %' : '%'}`;

export default function GlobeView({
  pins, investors, selectedProfileId, selectedId, selectedGeometry: standaloneGeometry, selectedCountry, countries, exposure, rotate, paused = false, reducedMotion, lang, height, onPin, onCountry, onHover, onInteract, area, command, onClusters, onViewport, onReady,
}: GlobeViewProps) {
  const globe = useRef<GlobeMethods | undefined>(undefined);
  const holder = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [ready, setReady] = useState(false);
  const [hoverIso, setHoverIso] = useState<string | null>(null);
  const [altitude, setAltitude] = useState(2.1);
  const sphere = useMemo(() => solidTexture(SPHERE_COLOR), []);
  const land = useMemo(() => hexReadyCountries(countries), [countries]);
  // Hexagons: the land, plus one hexagon for each island too small to hold one.
  const hexLand = useMemo(() => [...land, ...islandHexes(land, HEX_RESOLUTION)], [land]);
  // Events sharing a spot are fanned out; the original pin is what goes back up on click.
  const grouped = useMemo(() => clusterPins(pins, altitude, selectedId), [pins, altitude, selectedId]);
  const placed = useMemo(() => spreadStacked(grouped), [grouped]);
  useEffect(() => { onClusters(grouped.filter(pin => pin.kind === 'cluster').length); }, [grouped, onClusters]);
  const original = useMemo(() => new Map(pins.map(pin => [pin.id, pin])), [pins]);
  const selectedGeometry = useMemo(() => sourceGeometry(standaloneGeometry ?? pins.find(pin => pin.id === selectedId)?.geometry), [standaloneGeometry, pins, selectedId]);
  const polygonData = useMemo(() => [...land, ...(selectedGeometry.polygon ? [selectedGeometry.polygon] : [])], [land, selectedGeometry]);

  useEffect(() => {
    const element = holder.current;
    if (!element) return undefined;
    const measure = () => setWidth(Math.floor(element.clientWidth));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const centroids = useMemo(() => {
    const map = new Map<string, { lat: number; lng: number }>();
    for (const feature of countries) {
      if (!feature.iso3 || map.has(feature.iso3)) continue;
      const point = countryCentroid(feature);
      if (point) map.set(feature.iso3, point);
    }
    return map;
  }, [countries]);

  const events = useMemo(() => placed.filter(pin => pin.kind === 'event'), [placed]);

  // Arcs: from an event to each country it names where the portfolio has weight (not to its own spot).
  const arcs = useMemo<Arc[]>(() => {
    const out: Arc[] = [];
    for (const investor of investors) for (const wallet of investor.wallets) {
      if (wallet.lat === investor.home.lat && wallet.lon === investor.home.lon) continue;
      out.push({ id: `wallet:${investor.profileId}:${wallet.accountId}`, startLat: investor.home.lat, startLng: investor.home.lon,
        endLat: wallet.lat, endLng: wallet.lon, color: ['#F8D47A', '#6AE0CF'], selected: investor.profileId === selectedProfileId });
    }
    if (!exposure) return out;
    for (const pin of events) {
      for (const iso3 of (pin.related ?? []).map(code => regionIso3(code))) {
        const end = exposure.has(iso3) ? centroids.get(iso3) : undefined;
        if (!end || (Math.abs(end.lat - pin.lat) < 2 && Math.abs(end.lng - pin.lng) < 2)) continue;
        const color = CATEGORY_COLORS[pin.category ?? 'other'];
        out.push({ id: `${pin.id}>${iso3}`, startLat: pin.lat, startLng: pin.lng, endLat: end.lat, endLng: end.lng, color: [color, '#8EA6FF'], selected: pin.id === selectedId });
      }
    }
    return out;
  }, [events, exposure, centroids, selectedId, investors, selectedProfileId]);

  const rings = useMemo<Ring[]>(() => {
    const pin = placed.find(item => item.id === selectedId);
    return pin ? [{ lat: pin.lat, lng: pin.lng }] : [];
  }, [placed, selectedId]);

  const labels = useMemo<CountryLabel[]>(() => {
    if (!exposure) return [];
    return [...exposure.entries()]
      .filter(([, weight]) => weight >= 1)
      .map(([iso3, weight]) => {
        const point = centroids.get(iso3);
        return point ? { iso3, ...point, name: countryName(iso3, lang) ?? iso3, value: fmtPct(weight, lang) } : null;
      })
      .filter((label): label is CountryLabel => label !== null);
  }, [exposure, centroids, lang]);

  // ----- labels move aside from the spikes whenever the view or the data changes -----
  const labelEls = useRef(new Map<string, HTMLElement>());
  const layoutInputs = useRef({ placed, labels, selectedId, version: 0 });
  useEffect(() => {
    layoutInputs.current = { placed, labels, selectedId, version: layoutInputs.current.version + 1 };
  }, [placed, labels, selectedId]);
  useEffect(() => {
    if (!ready) return undefined;
    let frame = 0;
    let last = '';
    const tick = () => {
      frame = requestAnimationFrame(tick);
      const g = globe.current;
      if (!g) return;
      const { placed: pins, labels: items, selectedId: selected, version } = layoutInputs.current;
      const c = g.camera().position;
      const key = `${c.x.toFixed(2)},${c.y.toFixed(2)},${c.z.toFixed(2)}|${version}|${width}x${height}`;
      if (key === last) return;
      if (layoutLabels(g, pins, items, labelEls.current, selected)) last = key;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [ready, width, height]);

  // Idle rotation, slow, unless motion is reduced or the person took control.
  useEffect(() => {
    if (!ready || !globe.current) return;
    const controls = globe.current.controls();
    controls.autoRotate = rotate && !reducedMotion;
    controls.autoRotateSpeed = 0.35;
    controls.enableDamping = !reducedMotion;
  }, [rotate, reducedMotion, ready]);

  // Stop the render loop while nobody can see the globe; resume where it was.
  useEffect(() => {
    const g = globe.current;
    if (!ready || !g) return;
    if (paused) g.pauseAnimation();
    else g.resumeAnimation();
  }, [paused, ready]);

  // Stop rotating as soon as the globe is grabbed.
  useEffect(() => {
    if (!ready || !globe.current) return undefined;
    const controls = globe.current.controls();
    const stop = () => onInteract();
    controls.addEventListener('start', stop);
    return () => controls.removeEventListener('start', stop);
  }, [ready, onInteract]);

  // A polygon-only record uses its bounds to position the camera, without a map pin.
  useEffect(() => {
    if (!ready || !globe.current) return;
    const pin = placed.find(item => item.id === selectedId);
    const boundary = standaloneGeometry ? boundaryView(selectedGeometry.polygon) : null;
    const target = boundary ?? pin ?? (selectedCountry ? centroids.get(selectedCountry) : undefined);
    if (boundary) onInteract();
    if (target) globe.current.pointOfView({ lat: target.lat, lng: target.lng, altitude: boundary ? 0.8 : 1.7 }, reducedMotion ? 0 : 900);
    // Only a change of selection moves the camera.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, selectedCountry, standaloneGeometry, ready, reducedMotion, centroids]);

  useEffect(() => {
    if (!ready || !globe.current || !area) return;
    onInteract();
    globe.current.pointOfView({ lat: area.lat, lng: area.lng, altitude: area.altitude }, reducedMotion ? 0 : 600);
  }, [area, ready, reducedMotion, onInteract]);
  useEffect(() => {
    if (!ready || !globe.current || !command) return;
    if (command.action === 'query') {
      const points: { lat: number; lng: number }[] = [];
      for (let x = 0; x <= 24; x++) for (let y = 0; y <= 24; y++) {
        const point = globe.current.toGlobeCoords(width * x / 24, height * y / 24);
        if (point) points.push(point);
      }
      const bbox = viewportBounds(points);
      if (bbox) onViewport(bbox);
      return;
    }
    const point = globe.current.pointOfView();
    const step = Math.max(5, point.altitude * 12);
    const target = command.action === 'reset' ? { lat: 15, lng: 0, altitude: 2.1 } : {
      lat: Math.max(-85, Math.min(85, point.lat + (command.action === 'up' ? step : command.action === 'down' ? -step : 0))),
      lng: ((point.lng + (command.action === 'right' ? step : command.action === 'left' ? -step : 0) + 540) % 360) - 180,
      altitude: Math.max(.35, Math.min(4, point.altitude * (command.action === 'zoom-in' ? .7 : command.action === 'zoom-out' ? 1.4 : 1))),
    };
    globe.current.pointOfView(target, reducedMotion ? 0 : 350);
  }, [command, ready, reducedMotion, width, height, onViewport]);

  // ----- hover -----
  // globe.gl reports hex -> gap -> hex as out/in pairs: the "out" waits HOVER_OUT_MS and is cancelled by
  // any "in"; an "in" on the country already hovered changes nothing.
  const hoverKey = useRef<string | null>(null);
  const outTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(outTimer.current), []);
  const leaveSoon = useCallback(() => {
    window.clearTimeout(outTimer.current);
    outTimer.current = window.setTimeout(() => { hoverKey.current = null; setHoverIso(null); onHover(null); }, HOVER_OUT_MS);
  }, [onHover]);
  const hoverCountry = useCallback((feature: object | null) => {
    const f = feature as CountryFeature | null;
    if (!f) { leaveSoon(); return; }
    window.clearTimeout(outTimer.current);
    const name = outlineLabel(f, lang);
    const key = `country:${f.iso3 ?? name ?? ''}`;
    if (hoverKey.current === key) return;
    hoverKey.current = key;
    setHoverIso(f.iso3 ?? null);
    const weight = f.iso3 ? exposure?.get(f.iso3) : undefined;
    onHover(name ? { label: weight ? `${name}: ${fmtPct(weight, lang)}` : name } : null);
  }, [leaveSoon, lang, exposure, onHover]);
  const hoverPin = useCallback((pin: object | null) => {
    if (!pin) { leaveSoon(); return; }
    window.clearTimeout(outTimer.current);
    const p = pin as GlobePin;
    if (hoverKey.current === `pin:${p.id}`) return;
    hoverKey.current = `pin:${p.id}`;
    setHoverIso(null);
    const anchor = globe.current?.getScreenCoords(p.lat, p.lng, p.kind === 'event' ? spikeAltitude(p.weight) : p.kind === 'investor' ? 0.08 : REFERENCE_PIN_ALTITUDE);
    onHover({ label: p.label, pin: original.get(p.id) ?? p, ...(anchor ? { x: anchor.x, y: anchor.y } : {}), width });
  }, [leaveSoon, onHover, original, width]);
  const clickCountry = useCallback((feature: object) => {
    const iso3 = (feature as CountryFeature).iso3;
    if (iso3) onCountry(iso3);
  }, [onCountry]);
  const clickPin = useCallback((pin: object) => {
    const p = pin as GlobePin;
    if (p.kind === 'cluster') {
      onInteract();
      globe.current?.pointOfView({ lat: p.lat, lng: p.lng, altitude: .8 }, reducedMotion ? 0 : 500);
      return;
    }
    onPin(original.get(p.id) ?? p);
  }, [onPin, original, onInteract, reducedMotion]);

  // ----- accessors (stable, so a hover does not make globe.gl recompute every layer) -----
  const hexAltitude = useCallback((feature: object) => ((feature as CountryFeature).iso3 === selectedCountry ? 0.018 : 0.006), [selectedCountry]);
  const hexColor = useCallback((feature: object) => {
    const iso3 = (feature as CountryFeature).iso3 ?? '';
    const center = iso3 ? centroids.get(iso3) : null;
    if (area && center && insideBbox(center.lat, center.lng, area.bbox) && !exposure?.get(iso3)) return '#4B709C';
    if (iso3 && (iso3 === hoverIso || iso3 === selectedCountry) && !exposure?.get(iso3)) return LAND_HOVER_COLOR;
    return exposureColor(exposure?.get(iso3) ?? undefined);
  }, [hoverIso, selectedCountry, exposure, area, centroids]);
  const pointColor = useCallback((pin: object) => pinColor(pin as GlobePin, selectedId), [selectedId]);
  const pointAltitude = useCallback((pin: object) => {
    const p = pin as GlobePin;
    return p.kind === 'event' ? spikeAltitude(p.weight) : p.kind === 'investor' ? 0.08 : REFERENCE_PIN_ALTITUDE;
  }, []);
  const pointRadius = useCallback((pin: object) => {
    const p = pin as GlobePin;
    if (p.id === selectedId) return PIN_RADIUS.selected;
    if (p.kind === 'investor') return p.investorLocation?.selected ? 0.7 : 0.5;
    if (p.kind === 'wallet') return p.investorLocation?.selected ? 0.5 : 0.35;
    if (p.kind === 'cluster') return Math.min(1.1, .35 + Math.log2(p.members?.length ?? 1) * .12);
    return p.kind === 'event' ? PIN_RADIUS.event : p.kind === 'hazard' ? quakeRadius(p.magnitude) : PIN_RADIUS.facility;
  }, [selectedId]);
  const arcColor = useCallback((arc: object) => (arc as Arc).color, []);
  const arcStroke = useCallback((arc: object) => ((arc as Arc).selected ? 0.9 : 0.35), []);
  const arcDashLength = useCallback((arc: object) => ((arc as Arc).selected ? 0.35 : 1), []);
  const arcDashGap = useCallback((arc: object) => ((arc as Arc).selected ? 0.18 : 0), []);
  const arcDashAnimateTime = useCallback((arc: object) => ((arc as Arc).selected && !reducedMotion ? 1800 : 0), [reducedMotion]);
  const ringColor = useCallback(() => (t: number) => `rgba(255,255,255,${Math.max(0, 1 - t)})`, []);
  const hitColor = useCallback(() => HIT_LAYER_COLOR, []);
  const labelElement = useCallback((label: object) => {
    const l = label as CountryLabel;
    // globe.gl positions the anchor; the label inside it is moved aside from the spikes.
    const anchor = document.createElement('div');
    anchor.className = 'globe-label-anchor';
    const el = document.createElement('div');
    el.className = 'globe-label';
    const name = document.createElement('span');
    name.textContent = l.name;
    const value = document.createElement('strong');
    value.textContent = l.value;
    el.append(name, value);
    anchor.append(el);
    labelEls.current.set(l.iso3, el);
    return anchor;
  }, []);
  const labelVisibility = useCallback((el: HTMLElement, visible: boolean) => { el.style.opacity = visible ? '1' : '0'; }, []);

  // First view: over the country holding the most of the portfolio.
  const home = useMemo(() => {
    const top = exposure ? [...exposure.entries()].sort((a, b) => b[1] - a[1])[0] : undefined;
    return (top && centroids.get(top[0])) ?? { lat: 35, lng: -80 };
  }, [exposure, centroids]);

  return (
    <div ref={holder} className="globe-canvas" style={{ height }}>
      {width > 0 && (
        <Globe
          ref={globe}
          width={width}
          height={height}
          backgroundColor="rgba(0,0,0,0)"
          globeImageUrl={sphere}
          showAtmosphere
          atmosphereColor={ATMOSPHERE_COLOR}
          atmosphereAltitude={0.2}
          animateIn={!reducedMotion}
          onGlobeReady={() => { globe.current?.pointOfView({ lat: home.lat, lng: home.lng - 25, altitude: 2.1 }, 0); setReady(true); onReady(); }}
          onZoom={point => setAltitude(point.altitude)}
          // Land as hexagons, coloured by exposure
          hexPolygonsData={hexLand as unknown as object[]}
          hexPolygonResolution={3}
          hexPolygonMargin={0.28}
          hexPolygonUseDots={false}
          hexPolygonAltitude={hexAltitude}
          hexPolygonColor={hexColor}
          hexPolygonLabel={noLabel}
          hexPolygonsTransitionDuration={reducedMotion ? 0 : 400}
          onHexPolygonClick={clickCountry}
          onHexPolygonHover={hoverCountry}
          // Invisible country shapes just under the hexagons: they catch the pointer in the gaps
          polygonsData={polygonData as unknown as object[]}
          polygonCapColor={feature => feature === selectedGeometry.polygon ? 'rgba(106,224,207,0.15)' : hitColor()}
          polygonStrokeColor={feature => feature === selectedGeometry.polygon ? '#6AE0CF' : 'rgba(0,0,0,0)'}
          polygonSideColor={noSide}
          polygonAltitude={feature => feature === selectedGeometry.polygon ? 0.02 : 0.003}
          // Small cap triangles: large flat ones would sag under the globe surface and miss the pointer
          polygonCapCurvatureResolution={2}
          polygonsTransitionDuration={0}
          polygonLabel={noLabel}
          onPolygonClick={feature => { if (feature !== selectedGeometry.polygon) clickCountry(feature); }}
          onPolygonHover={feature => { if (feature !== selectedGeometry.polygon) hoverCountry(feature); }}
          pathsData={selectedGeometry.paths}
          pathPoints={path => path as number[][]}
          pathPointLat={point => (point as number[])[1]!}
          pathPointLng={point => (point as number[])[0]!}
          pathPointAlt={0.02}
          pathColor={() => '#6AE0CF'}
          pathStroke={1.5}
          pathTransitionDuration={0}
          // Events as spikes (height = importance); facilities and earthquakes as low dots
          pointsData={placed as unknown as object[]}
          pointLat="lat"
          pointLng="lng"
          pointColor={pointColor}
          pointAltitude={pointAltitude}
          pointRadius={pointRadius}
          pointResolution={12}
          pointsMerge={false}
          pointsTransitionDuration={reducedMotion ? 0 : 700}
          pointLabel={noLabel}
          onPointClick={clickPin}
          onPointHover={hoverPin}
          // Links from events to exposed countries
          arcsData={arcs}
          arcStartLat="startLat"
          arcStartLng="startLng"
          arcEndLat="endLat"
          arcEndLng="endLng"
          arcColor={arcColor}
          arcStroke={arcStroke}
          arcAltitudeAutoScale={0.45}
          arcDashLength={arcDashLength}
          arcDashGap={arcDashGap}
          arcDashAnimateTime={arcDashAnimateTime}
          arcsTransitionDuration={reducedMotion ? 0 : 900}
          arcLabel={noLabel}
          // The selected event pulses (above the invisible country shapes)
          ringsData={rings}
          ringAltitude={0.009}
          ringColor={ringColor}
          ringMaxRadius={3}
          ringPropagationSpeed={reducedMotion ? 0 : 2.4}
          ringRepeatPeriod={reducedMotion ? 0 : 1100}
          // Exposed countries carry their weight, as DOM labels built from text (no HTML is injected)
          htmlElementsData={labels}
          htmlLat="lat"
          htmlLng="lng"
          htmlAltitude={LABEL_ALTITUDE}
          htmlElement={labelElement}
          htmlElementVisibilityModifier={labelVisibility}
        />
      )}
    </div>
  );
}
