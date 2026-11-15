'use client';
/**
 * WebGL globe (react-globe.gl, decision D-29). Imported ONLY through next/dynamic with `ssr: false`
 * from WorldGlobe.tsx: three.js needs `window`. It draws what it is given (country outlines, pins);
 * it fetches nothing. The ocean colour is a canvas-generated data URL, so no texture is downloaded.
 * Hover text is passed up and rendered by React as text, in the active language. globe.gl's own
 * tooltip (it writes HTML and defaults to a datum's `name`) is switched off for outlines and pins,
 * so no source title or outline name is ever injected as tooltip HTML.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import Globe, { type GlobeMethods } from 'react-globe.gl';
import type { Lang } from '../../contracts/types';
import { outlineLabel, type CountryFeature } from '../../lib/geo';
import { OCEAN_COLOR, PIN_COLORS, exposureColor, type GlobePin } from './globeStyle';

export interface GlobeViewProps {
  pins: readonly GlobePin[];
  selectedId: string | null;
  countries: readonly CountryFeature[];
  /** Portfolio weight (percent) by ISO3 for the exposure layer; null = layer off. */
  exposure: ReadonlyMap<string, number> | null;
  rotate: boolean;
  reducedMotion: boolean;
  /** Language of the hover caption for country outlines. */
  lang: Lang;
  onPin: (pin: GlobePin) => void;
  onCountry: (iso3: string) => void;
  onHover: (text: string | null) => void;
}

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

export default function GlobeView({
  pins, selectedId, countries, exposure, rotate, reducedMotion, lang, onPin, onCountry, onHover,
}: GlobeViewProps) {
  const globe = useRef<GlobeMethods | undefined>(undefined);
  const holder = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [ready, setReady] = useState(false);
  const ocean = useMemo(() => solidTexture(OCEAN_COLOR), []);

  useEffect(() => {
    const element = holder.current;
    if (!element) return undefined;
    const measure = () => setWidth(Math.floor(element.clientWidth));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Auto-rotation only when asked for and never under prefers-reduced-motion.
  useEffect(() => {
    if (!ready || !globe.current) return;
    const controls = globe.current.controls();
    controls.autoRotate = rotate && !reducedMotion;
    controls.autoRotateSpeed = 0.45;
  }, [rotate, reducedMotion, ready]);

  // Bring the selected pin into view (instant when motion is reduced).
  useEffect(() => {
    if (!ready || !globe.current || !selectedId) return;
    const pin = pins.find(item => item.id === selectedId);
    if (pin) globe.current.pointOfView({ lat: pin.lat, lng: pin.lng, altitude: 1.9 }, reducedMotion ? 0 : 700);
    // Only a change of selection moves the camera, not every re-thinning of the pins.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, ready, reducedMotion]);

  const height = Math.max(260, Math.min(520, Math.round(width * 0.82)));
  const pinColor = (pin: GlobePin) => (pin.id === selectedId ? PIN_COLORS.selected
    : pin.kind === 'facility' ? PIN_COLORS.facility
      : pin.kind === 'hazard' ? PIN_COLORS.hazard
        : pin.countryLevel ? PIN_COLORS.eventCountry : PIN_COLORS.event);

  return (
    <div ref={holder} className="globe-holder" style={{ height }}>
      {width > 0 && (
        <Globe
          ref={globe}
          width={width}
          height={height}
          backgroundColor="#141415"
          globeImageUrl={ocean}
          showAtmosphere
          atmosphereColor="#A1A1A6"
          atmosphereAltitude={0.12}
          // Init-only prop: no spin-and-zoom intro under prefers-reduced-motion (resolved before this mounts).
          animateIn={!reducedMotion}
          onGlobeReady={() => { globe.current?.pointOfView({ lat: 35, lng: -75, altitude: 1.9 }, 0); setReady(true); }}
          polygonsData={countries as unknown as object[]}
          polygonCapColor={feature => exposureColor(exposure?.get((feature as CountryFeature).iso3 ?? '') ?? undefined)}
          polygonSideColor={() => 'rgba(0,0,0,0)'}
          polygonStrokeColor={() => '#141415'}
          polygonAltitude={0.006}
          polygonsTransitionDuration={0}
          onPolygonClick={feature => { const iso3 = (feature as CountryFeature).iso3; if (iso3) onCountry(iso3); }}
          polygonLabel={() => ''}
          onPolygonHover={feature => onHover(feature ? outlineLabel(feature as CountryFeature, lang) : null)}
          pointsData={pins as unknown as object[]}
          pointLat="lat"
          pointLng="lng"
          pointColor={pin => pinColor(pin as GlobePin)}
          pointAltitude={0.014}
          pointRadius={pin => ((pin as GlobePin).id === selectedId ? 0.7 : 0.28 + 0.34 * Math.max(0, Math.min(1, (pin as GlobePin).weight)))}
          pointResolution={8}
          pointsMerge={false}
          pointsTransitionDuration={0}
          pointLabel={() => ''}
          onPointClick={pin => onPin(pin as GlobePin)}
          onPointHover={pin => onHover(pin ? (pin as GlobePin).label : null)}
        />
      )}
    </div>
  );
}
