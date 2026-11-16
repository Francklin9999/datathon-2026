'use client';
/**
 * The World nav item: a small orthographic globe facing the focus country (state/useFocusCountry.ts),
 * which it fills in the accent colour. The globe turns to a new country once, over 600 ms on the
 * design curve, when animations are allowed (it jumps otherwise); it never spins on its own and is
 * re-projected only during that turn. Opening World expands it into the World stage with a view
 * transition (shared name `world-globe`, features/world/world.css) where the browser has one, else
 * with a short scale and fade. Without the outlines file the item shows the Earth icon.
 */
import { Earth } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import { useApp } from '../../state/app';
import { useFocusCountry } from '../../state/useFocusCountry';
import { countryCentroid, countryName, decodeCountries, type CountryFeature, type Topology } from '../../lib/geo';
import { animationsAllowed } from '../../lib/ui/theme';
import { easeCurve, geometryPath, graticule, linePath, lonDelta, project, type OrthoView } from '../../lib/ui/orthographic';
import type { NavEntry } from '../../lib/ui/nav';
import { NavLink } from './NavLink';

// ----- Outlines: fetched once per page load, shared by every mini globe -----

let outlines: Promise<CountryFeature[]> | null = null;

function loadOutlines(): Promise<CountryFeature[]> {
  outlines ??= fetch('/geo/countries-110m.json')
    .then(response => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json() as Promise<Topology>;
    })
    .then(topology => decodeCountries(topology))
    .catch((error: unknown) => { outlines = null; throw error; });
  return outlines;
}

type Outlines = { status: 'loading' } | { status: 'ready'; countries: CountryFeature[] } | { status: 'failed' };

function useOutlines(): Outlines {
  const [state, setState] = useState<Outlines>({ status: 'loading' });
  useEffect(() => {
    let live = true;
    loadOutlines().then(countries => { if (live) setState({ status: 'ready', countries }); }, () => { if (live) setState({ status: 'failed' }); });
    return () => { live = false; };
  }, []);
  return state;
}

// ----- Motion -----

/** Animations allowed now: the Animations setting, the system setting and a hidden page (lib/ui/theme.ts). */
function motionAllowed(): boolean {
  if (typeof document === 'undefined') return false;
  const html = document.documentElement;
  const reduce = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  return animationsAllowed(html.dataset.anim, reduce, document.hidden || html.dataset.motion === 'off');
}

const TURN_MS = 600;
/** The centre's latitude stays within this, so the globe never looks down on a pole. */
const MAX_TILT = 45;
/** Seen while the outlines load: roughly Canada, the default focus. */
const START: readonly [number, number] = [-96, 45];

/** The view centre: jumps to the first target, then turns to each new one (or jumps when motion is off). */
function useTurn(target: readonly [number, number] | null): readonly [number, number] {
  const [centre, setCentre] = useState<readonly [number, number]>(target ?? START);
  const current = useRef(centre);
  const placed = useRef(target !== null);
  const lon = target?.[0];
  const lat = target?.[1];
  useEffect(() => {
    if (lon === undefined || lat === undefined) return undefined;
    const to: readonly [number, number] = [lon, lat];
    const from = current.current;
    const jump = () => { current.current = to; setCentre(to); };
    if (!placed.current || !motionAllowed()) { placed.current = true; jump(); return undefined; }
    const dLon = lonDelta(from[0], to[0]);
    const dLat = to[1] - from[1];
    if (Math.abs(dLon) < 0.5 && Math.abs(dLat) < 0.5) { jump(); return undefined; }
    let frame = 0;
    const start = performance.now();
    const step = (now: number) => {
      const k = easeCurve(Math.min(1, (now - start) / TURN_MS));
      const next: readonly [number, number] = [from[0] + dLon * k, from[1] + dLat * k];
      current.current = next;
      setCentre(next);
      if (k < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [lon, lat]);
  return centre;
}

// ----- Drawing -----

const GRATICULE = graticule(30, 6);
const VIEW_SIZE = 100;

function focusPoint(feature: CountryFeature | undefined): readonly [number, number] | null {
  const centroid = feature ? countryCentroid(feature) : null;
  return centroid ? [centroid.lng, Math.max(-MAX_TILT, Math.min(MAX_TILT, centroid.lat))] : null;
}

/** The globe drawing (decorative: the link carries the name). */
export function MiniGlobe({ iso3, className }: { iso3: string; className?: string }) {
  const geography = useOutlines();
  const countries = geography.status === 'ready' ? geography.countries : null;
  const focus = countries?.find(country => country.iso3 === iso3);
  const target = useMemo(() => (countries ? (focusPoint(focus) ?? START) : null), [countries, focus]);
  const centre = useTurn(target);
  const drawing = useMemo(() => {
    const view: OrthoView = { lambda0: centre[0], phi0: centre[1], r: VIEW_SIZE / 2 - 3, cx: VIEW_SIZE / 2, cy: VIEW_SIZE / 2 };
    const grid = GRATICULE.map(line => linePath(line, view)).join('');
    if (!countries) return { view, grid, land: '', highlight: '', dot: null };
    let land = '';
    let highlight = '';
    for (const country of countries) {
      const path = geometryPath(country.geometry, view);
      if (country === focus) highlight = path; else land += path;
    }
    const centroid = focus ? countryCentroid(focus) : null;
    const projected = centroid ? project([centroid.lng, centroid.lat], view) : null;
    return { view, grid, land, highlight, dot: projected?.visible ? projected : null };
  }, [centre, countries, focus]);

  if (geography.status === 'failed') return <Earth className={className} aria-hidden="true" size={20} strokeWidth={1.75} />;
  const { view } = drawing;
  return (
    <svg className={`mini-globe${className ? ` ${className}` : ''}`} viewBox={`0 0 ${VIEW_SIZE} ${VIEW_SIZE}`} aria-hidden="true" focusable="false">
      <circle className="globe-sphere" cx={view.cx} cy={view.cy} r={view.r} />
      <path className="globe-grid" d={drawing.grid} />
      {drawing.land && <path className="globe-land" d={drawing.land} fillRule="evenodd" />}
      {drawing.highlight && <path className="globe-focus" d={drawing.highlight} fillRule="evenodd" />}
      {/* Small countries vanish at this size: a dot marks the focus too. */}
      {drawing.dot && <circle className="globe-focus" cx={drawing.dot.x} cy={drawing.dot.y} r={4} />}
      <circle className="globe-rim" cx={view.cx} cy={view.cy} r={view.r} />
    </svg>
  );
}

// ----- The World nav item -----

type ViewTransitionDocument = Document & { startViewTransition?: (update: () => Promise<void>) => unknown };

/**
 * The World link with the mini globe. Uses useSearchParams (useFocusCountry): render inside <Suspense>,
 * with `WorldNavFallback` as the fallback. `expand` plays the expand effect (the rail; not the phone menu).
 */
export function WorldNavLink({ item, active, pill, index, onNavigate, expand }: {
  item: NavEntry; active: boolean; pill: boolean; index: number; onNavigate?: () => void; expand: boolean;
}) {
  const { tr, lang } = useApp();
  const router = useRouter();
  const pathname = usePathname() ?? '/';
  const { iso3, known } = useFocusCountry();
  const link = useRef<HTMLAnchorElement | null>(null);
  const pending = useRef<(() => void) | null>(null);
  const href = known ? `${item.href}?country=${iso3}` : item.href;
  const name = countryName(iso3, lang) ?? iso3;
  const label = tr(item.label);

  // The new page is in place: end the view transition, or drop the fallback effect.
  useEffect(() => {
    pending.current?.();
    pending.current = null;
    const globe = link.current?.querySelector<HTMLElement>('.mini-globe');
    if (globe) delete globe.dataset.expanding;
  }, [pathname]);

  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    onNavigate?.();
    if (!expand || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (pathname.startsWith(item.href.replace(/\/$/, '')) || !motionAllowed()) return;
    const globe = link.current?.querySelector<SVGSVGElement>('.mini-globe');
    if (!globe) return;
    event.preventDefault();
    const doc = document as ViewTransitionDocument;
    if (typeof doc.startViewTransition === 'function') {
      // Old snapshot: the mini globe carries the shared name; new snapshot: the World stage does.
      globe.style.setProperty('view-transition-name', 'world-globe');
      doc.startViewTransition(() => new Promise<void>(resolve => {
        const done = () => { globe.style.removeProperty('view-transition-name'); pending.current = null; resolve(); };
        pending.current = done;
        router.push(href);
        window.setTimeout(() => { if (pending.current === done) done(); }, 1000);
      }));
      return;
    }
    globe.dataset.expanding = 'true';
    window.setTimeout(() => router.push(href), 160);
  };

  return (
    <NavLink item={item} href={href} active={active} pill={pill} index={index} linkRef={link} onClick={onClick}
      title={`${label} · ${name}`} ariaLabel={`${label}, ${name}`}
      icon={<MiniGlobe iso3={iso3} className="nav-icon nav-globe" />} />
  );
}

/** The World link before the address can be read (static render): the Earth icon, no country. */
export function WorldNavFallback({ item, active, pill, index, onNavigate }: {
  item: NavEntry; active: boolean; pill: boolean; index: number; onNavigate?: () => void;
}) {
  return (
    <NavLink item={item} active={active} pill={pill} index={index} {...(onNavigate ? { onClick: () => onNavigate() } : {})}
      icon={<Earth className="nav-icon" aria-hidden="true" size={20} strokeWidth={1.75} />} />
  );
}
