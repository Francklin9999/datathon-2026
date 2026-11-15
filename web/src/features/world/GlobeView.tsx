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
 * across one country never flickers its caption.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Globe, { type GlobeMethods } from 'react-globe.gl';
import type { Lang } from '../../contracts/types';
import { countryCentroid, countryName, hexReadyCountries, outlineLabel, type CountryFeature } from '../../lib/geo';
import {
  ATMOSPHERE_COLOR, CATEGORY_COLORS, LAND_HOVER_COLOR, SPHERE_COLOR, exposureColor, pinColor, quakeRadius,
  spikeAltitude, spreadStacked, type GlobePin,
} from './globeStyle';

export interface GlobeViewProps {
  pins: readonly GlobePin[];
  selectedId: string | null;
  selectedCountry: string | null;
  countries: readonly CountryFeature[];
  /** Portfolio weight (percent) by ISO3 for the exposure layer; null = layer off. */
  exposure: ReadonlyMap<string, number> | null;
  rotate: boolean;
  reducedMotion: boolean;
  lang: Lang;
  height: number;
  onPin: (pin: GlobePin) => void;
  onCountry: (iso3: string) => void;
  onHover: (text: string | null) => void;
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

const fmtPct = (value: number, lang: Lang) => `${new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', { maximumFractionDigits: 0 }).format(value)}${lang === 'fr' ? ' %' : '%'}`;

export default function GlobeView({
  pins, selectedId, selectedCountry, countries, exposure, rotate, reducedMotion, lang, height, onPin, onCountry, onHover, onInteract,
}: GlobeViewProps) {
  const globe = useRef<GlobeMethods | undefined>(undefined);
  const holder = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [ready, setReady] = useState(false);
  const [hoverIso, setHoverIso] = useState<string | null>(null);
  const sphere = useMemo(() => solidTexture(SPHERE_COLOR), []);
  const land = useMemo(() => hexReadyCountries(countries), [countries]);
  // Events sharing a spot are fanned out; the original pin is what goes back up on click.
  const placed = useMemo(() => spreadStacked(pins), [pins]);
  const original = useMemo(() => new Map(pins.map(pin => [pin.id, pin])), [pins]);

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
    if (!exposure) return [];
    const out: Arc[] = [];
    for (const pin of events) {
      for (const iso3 of pin.related ?? []) {
        const end = exposure.has(iso3) ? centroids.get(iso3) : undefined;
        if (!end || (Math.abs(end.lat - pin.lat) < 2 && Math.abs(end.lng - pin.lng) < 2)) continue;
        const color = CATEGORY_COLORS[pin.category ?? 'other'];
        out.push({ id: `${pin.id}>${iso3}`, startLat: pin.lat, startLng: pin.lng, endLat: end.lat, endLng: end.lng, color: [color, '#8EA6FF'], selected: pin.id === selectedId });
      }
    }
    return out;
  }, [events, exposure, centroids, selectedId]);

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

  // Idle rotation, slow, unless motion is reduced or the person took control.
  useEffect(() => {
    if (!ready || !globe.current) return;
    const controls = globe.current.controls();
    controls.autoRotate = rotate && !reducedMotion;
    controls.autoRotateSpeed = 0.35;
    controls.enableDamping = true;
  }, [rotate, reducedMotion, ready]);

  // Stop rotating as soon as the globe is grabbed.
  useEffect(() => {
    if (!ready || !globe.current) return undefined;
    const controls = globe.current.controls();
    const stop = () => onInteract();
    controls.addEventListener('start', stop);
    return () => controls.removeEventListener('start', stop);
  }, [ready, onInteract]);

  // Fly to the selected event or country.
  useEffect(() => {
    if (!ready || !globe.current) return;
    const pin = placed.find(item => item.id === selectedId);
    const target = pin ?? (selectedCountry ? centroids.get(selectedCountry) : undefined);
    if (target) globe.current.pointOfView({ lat: target.lat, lng: target.lng, altitude: 1.7 }, reducedMotion ? 0 : 900);
    // Only a change of selection moves the camera.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, selectedCountry, ready, reducedMotion]);

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
    onHover(name ? (weight ? `${name}: ${fmtPct(weight, lang)}` : name) : null);
  }, [leaveSoon, lang, exposure, onHover]);
  const hoverPin = useCallback((pin: object | null) => {
    if (!pin) { leaveSoon(); return; }
    window.clearTimeout(outTimer.current);
    const p = pin as GlobePin;
    if (hoverKey.current === `pin:${p.id}`) return;
    hoverKey.current = `pin:${p.id}`;
    setHoverIso(null);
    onHover(p.label);
  }, [leaveSoon, onHover]);
  const clickCountry = useCallback((feature: object) => {
    const iso3 = (feature as CountryFeature).iso3;
    if (iso3) onCountry(iso3);
  }, [onCountry]);
  const clickPin = useCallback((pin: object) => {
    const p = pin as GlobePin;
    onPin(original.get(p.id) ?? p);
  }, [onPin, original]);

  // ----- accessors (stable, so a hover does not make globe.gl recompute every layer) -----
  const hexAltitude = useCallback((feature: object) => ((feature as CountryFeature).iso3 === selectedCountry ? 0.018 : 0.006), [selectedCountry]);
  const hexColor = useCallback((feature: object) => {
    const iso3 = (feature as CountryFeature).iso3 ?? '';
    if (iso3 && (iso3 === hoverIso || iso3 === selectedCountry) && !exposure?.get(iso3)) return LAND_HOVER_COLOR;
    return exposureColor(exposure?.get(iso3) ?? undefined);
  }, [hoverIso, selectedCountry, exposure]);
  const pointColor = useCallback((pin: object) => pinColor(pin as GlobePin, selectedId), [selectedId]);
  const pointAltitude = useCallback((pin: object) => {
    const p = pin as GlobePin;
    return p.kind === 'event' ? spikeAltitude(p.weight) : p.kind === 'hazard' ? 0.008 : 0.02;
  }, []);
  const pointRadius = useCallback((pin: object) => {
    const p = pin as GlobePin;
    if (p.id === selectedId) return 0.55;
    return p.kind === 'event' ? 0.36 : p.kind === 'hazard' ? quakeRadius(p.magnitude) : 0.22;
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
    const el = document.createElement('div');
    el.className = 'globe-label';
    const name = document.createElement('span');
    name.textContent = l.name;
    const value = document.createElement('strong');
    value.textContent = l.value;
    el.append(name, value);
    return el;
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
          onGlobeReady={() => { globe.current?.pointOfView({ lat: home.lat, lng: home.lng - 25, altitude: 2.1 }, 0); setReady(true); }}
          // Land as hexagons, coloured by exposure
          hexPolygonsData={land as unknown as object[]}
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
          polygonsData={land as unknown as object[]}
          polygonCapColor={hitColor}
          polygonSideColor={noSide}
          polygonAltitude={0.003}
          // Small cap triangles: large flat ones would sag under the globe surface and miss the pointer
          polygonCapCurvatureResolution={2}
          polygonsTransitionDuration={0}
          polygonLabel={noLabel}
          onPolygonClick={clickCountry}
          onPolygonHover={hoverCountry}
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
          ringMaxRadius={4.5}
          ringPropagationSpeed={reducedMotion ? 0 : 2.4}
          ringRepeatPeriod={reducedMotion ? 0 : 1100}
          // Exposed countries carry their weight, as DOM labels built from text (no HTML is injected)
          htmlElementsData={labels}
          htmlLat="lat"
          htmlLng="lng"
          htmlAltitude={0.03}
          htmlElement={labelElement}
          htmlElementVisibilityModifier={labelVisibility}
        />
      )}
    </div>
  );
}
