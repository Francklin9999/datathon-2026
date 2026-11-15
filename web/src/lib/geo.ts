/**
 * Geography helpers for the World Explorer (T15): a dependency-free TopoJSON decoder for the bundled
 * Natural Earth country outlines (web/public/geo/countries-110m.json) and the ISO 3166-1 code table
 * needed to link an outline to the API's ISO3 codes and to a localized country name.
 *
 * The code table is ISO 3166-1 (alpha-2, alpha-3, numeric), generated from the `codes.json` of
 * i18n-iso-countries 7.14.0 (MIT). Country names come from the browser's CLDR data (Intl.DisplayNames).
 */
import type { Lang } from '../contracts/types';

// 250 entries of 8 characters: alpha-2 (2) + alpha-3 (3) + numeric (3).
const ISO_TABLE = 'AFAFG004ALALB008DZDZA012ASASM016ADAND020AOAGO024AIAIA660AQATA010AGATG028ARARG032AMARM051AWABW533AUAUS036ATAUT040AZAZE031'
  + 'BSBHS044BHBHR048BDBGD050BBBRB052BYBLR112BEBEL056BZBLZ084BJBEN204BMBMU060BTBTN064BOBOL068BABIH070BWBWA072BVBVT074BRBRA076'
  + 'IOIOT086BNBRN096BGBGR100BFBFA854BIBDI108KHKHM116CMCMR120CACAN124CVCPV132KYCYM136CFCAF140TDTCD148CLCHL152CNCHN156CXCXR162'
  + 'CCCCK166COCOL170KMCOM174CGCOG178CDCOD180CKCOK184CRCRI188CICIV384HRHRV191CUCUB192CYCYP196CZCZE203DKDNK208DJDJI262DMDMA212'
  + 'DODOM214ECECU218EGEGY818SVSLV222GQGNQ226ERERI232EEEST233ETETH231FKFLK238FOFRO234FJFJI242FIFIN246FRFRA250GFGUF254PFPYF258'
  + 'TFATF260GAGAB266GMGMB270GEGEO268DEDEU276GHGHA288GIGIB292GRGRC300GLGRL304GDGRD308GPGLP312GUGUM316GTGTM320GNGIN324GWGNB624'
  + 'GYGUY328HTHTI332HMHMD334VAVAT336HNHND340HKHKG344HUHUN348ISISL352ININD356IDIDN360IRIRN364IQIRQ368IEIRL372ILISR376ITITA380'
  + 'JMJAM388JPJPN392JOJOR400KZKAZ398KEKEN404KIKIR296KPPRK408KRKOR410KWKWT414KGKGZ417LALAO418LVLVA428LBLBN422LSLSO426LRLBR430'
  + 'LYLBY434LILIE438LTLTU440LULUX442MOMAC446MGMDG450MWMWI454MYMYS458MVMDV462MLMLI466MTMLT470MHMHL584MQMTQ474MRMRT478MUMUS480'
  + 'YTMYT175MXMEX484FMFSM583MDMDA498MCMCO492MNMNG496MSMSR500MAMAR504MZMOZ508MMMMR104NANAM516NRNRU520NPNPL524NLNLD528NCNCL540'
  + 'NZNZL554NINIC558NENER562NGNGA566NUNIU570NFNFK574MPMNP580MKMKD807NONOR578OMOMN512PKPAK586PWPLW585PSPSE275PAPAN591PGPNG598'
  + 'PYPRY600PEPER604PHPHL608PNPCN612PLPOL616PTPRT620PRPRI630QAQAT634REREU638ROROU642RURUS643RWRWA646SHSHN654KNKNA659LCLCA662'
  + 'PMSPM666VCVCT670WSWSM882SMSMR674STSTP678SASAU682SNSEN686SCSYC690SLSLE694SGSGP702SKSVK703SISVN705SBSLB090SOSOM706ZAZAF710'
  + 'GSSGS239ESESP724LKLKA144SDSDN729SRSUR740SJSJM744SZSWZ748SESWE752CHCHE756SYSYR760TWTWN158TJTJK762TZTZA834THTHA764TLTLS626'
  + 'TGTGO768TKTKL772TOTON776TTTTO780TNTUN788TRTUR792TMTKM795TCTCA796TVTUV798UGUGA800UAUKR804AEARE784GBGBR826USUSA840UMUMI581'
  + 'UYURY858UZUZB860VUVUT548VEVEN862VNVNM704VGVGB092VIVIR850WFWLF876EHESH732YEYEM887ZMZMB894ZWZWE716AXALA248BQBES535CWCUW531'
  + 'GGGGY831IMIMN833JEJEY832MEMNE499BLBLM652MFMAF663RSSRB688SXSXM534SSSSD728XKXKK983';

const ALPHA2_BY_ALPHA3 = new Map<string, string>();
const ALPHA3_BY_NUMERIC = new Map<string, string>();
for (let i = 0; i + 8 <= ISO_TABLE.length; i += 8) {
  const alpha2 = ISO_TABLE.slice(i, i + 2);
  const alpha3 = ISO_TABLE.slice(i + 2, i + 5);
  ALPHA2_BY_ALPHA3.set(alpha3, alpha2);
  ALPHA3_BY_NUMERIC.set(ISO_TABLE.slice(i + 5, i + 8), alpha3);
}

/** ISO 3166-1 numeric ("124" or 124) → alpha-3 ("CAN"); null when the code is not in ISO 3166-1. */
export function iso3FromNumeric(numeric: string | number | null | undefined): string | null {
  if (numeric === null || numeric === undefined || numeric === '') return null;
  return ALPHA3_BY_NUMERIC.get(String(numeric).padStart(3, '0')) ?? null;
}

export function isKnownIso3(code: string): boolean {
  return ALPHA2_BY_ALPHA3.has(code);
}

/**
 * Localized country name for an ISO3 code, from the runtime's CLDR data. Codes outside ISO 3166-1
 * (an "unknown" bucket, a region the API invented a code for) return null: the caller shows the
 * code as returned instead of guessing a country.
 */
export function countryName(iso3: string, lang: Lang): string | null {
  const alpha2 = ALPHA2_BY_ALPHA3.get(iso3);
  if (!alpha2 || alpha2 === 'XK') return null;
  try {
    const name = new Intl.DisplayNames([lang === 'fr' ? 'fr-CA' : 'en-CA'], { type: 'region' }).of(alpha2);
    return name && name !== alpha2 ? name : null;
  } catch {
    return null;
  }
}

/** "Canada (CAN)" when the code is a known country; the bare code otherwise. */
export function countryLabel(iso3: string, lang: Lang): string {
  const name = countryName(iso3, lang);
  return name ? `${name} (${iso3})` : iso3;
}

// ----- TopoJSON → GeoJSON (only what the bundled world-atlas file uses) -----

type Position = [number, number];
type TopoArcs = number[][];
interface TopoGeometry {
  type: string;
  arcs?: unknown;
  id?: string | number;
  properties?: Record<string, unknown> | null;
}
export interface Topology {
  type: 'Topology';
  arcs: number[][][];
  transform?: { scale: [number, number]; translate: [number, number] };
  objects: Record<string, { type: string; geometries?: TopoGeometry[] }>;
}

export interface CountryFeature {
  /** ISO3 when the outline's numeric id is in ISO 3166-1; null for Natural Earth areas without one. */
  iso3: string | null;
  /** Natural Earth English name; shown only through `outlineLabel`, as the fallback for an outline without a nameable ISO code. */
  name: string;
  geometry: { type: 'Polygon'; coordinates: Position[][] } | { type: 'MultiPolygon'; coordinates: Position[][][] };
}

/**
 * The three Natural Earth outlines of the bundled file that have no ISO 3166-1 code, by their name
 * in that file. They cannot be named through Intl.DisplayNames, so both languages are written here.
 */
const OUTLINE_NAMES: Record<string, Record<Lang, string>> = {
  'N. Cyprus': { en: 'Northern Cyprus', fr: 'Chypre du Nord' },
  Somaliland: { en: 'Somaliland', fr: 'Somaliland' },
  Kosovo: { en: 'Kosovo', fr: 'Kosovo' },
};

/**
 * Caption of a country outline in the active language: the same "Name (ISO3)" label as the feed and
 * the tables when the runtime can name the code, otherwise the outline's own name (translated for
 * the areas without an ISO code). Null when the outline has no usable name at all.
 */
export function outlineLabel(feature: Pick<CountryFeature, 'iso3' | 'name'>, lang: Lang): string | null {
  if (feature.iso3 && countryName(feature.iso3, lang)) return countryLabel(feature.iso3, lang);
  return OUTLINE_NAMES[feature.name]?.[lang] ?? (feature.name || null);
}

function decodeArc(topology: Topology, index: number): Position[] {
  const reversed = index < 0;
  const arc = topology.arcs[reversed ? ~index : index] ?? [];
  const points: Position[] = [];
  const t = topology.transform;
  let x = 0;
  let y = 0;
  for (const point of arc) {
    const px = point[0] ?? 0;
    const py = point[1] ?? 0;
    if (t) {
      x += px; y += py;
      points.push([x * t.scale[0] + t.translate[0], y * t.scale[1] + t.translate[1]]);
    } else {
      points.push([px, py]);
    }
  }
  return reversed ? points.reverse() : points;
}

function decodeRing(topology: Topology, arcs: number[]): Position[] {
  const ring: Position[] = [];
  arcs.forEach((index, i) => {
    const points = decodeArc(topology, index);
    // Consecutive arcs share their joint: drop the duplicated first point.
    ring.push(...(i === 0 ? points : points.slice(1)));
  });
  return ring;
}

/** Decode the country outlines of a world-atlas topology. Throws on a shape it does not understand. */
export function decodeCountries(topology: Topology, objectName = 'countries'): CountryFeature[] {
  const object = topology?.objects?.[objectName];
  if (topology?.type !== 'Topology' || !Array.isArray(topology.arcs) || !object?.geometries) {
    throw new Error(`Not a TopoJSON topology with a "${objectName}" object`);
  }
  const features: CountryFeature[] = [];
  for (const geometry of object.geometries) {
    const name = typeof geometry.properties?.name === 'string' ? geometry.properties.name : '';
    const iso3 = iso3FromNumeric(geometry.id);
    if (geometry.type === 'Polygon') {
      const rings = (geometry.arcs as TopoArcs).map(ring => decodeRing(topology, ring));
      features.push({ iso3, name, geometry: { type: 'Polygon', coordinates: rings } });
    } else if (geometry.type === 'MultiPolygon') {
      const polygons = (geometry.arcs as TopoArcs[]).map(polygon => polygon.map(ring => decodeRing(topology, ring)));
      features.push({ iso3, name, geometry: { type: 'MultiPolygon', coordinates: polygons } });
    }
  }
  return features;
}

/**
 * A representative point of a country for arcs and labels: the area-weighted centroid of its largest
 * outer ring. Longitudes of a ring that crosses the antimeridian are unwrapped first (Fiji, Russia).
 */
export function countryCentroid(feature: Pick<CountryFeature, 'geometry'>): { lat: number; lng: number } | null {
  const rings = feature.geometry.type === 'Polygon'
    ? [feature.geometry.coordinates[0] ?? []]
    : feature.geometry.coordinates.map(polygon => polygon[0] ?? []);
  let best: { lat: number; lng: number; area: number } | null = null;
  for (const ring of rings) {
    if (ring.length < 3) continue;
    const lons = ring.map(p => p[0] ?? 0);
    const wraps = Math.max(...lons) - Math.min(...lons) > 180;
    const pts = ring.map(p => [wraps && (p[0] ?? 0) < 0 ? (p[0] ?? 0) + 360 : (p[0] ?? 0), p[1] ?? 0] as const);
    let area = 0; let cx = 0; let cy = 0;
    for (let i = 0; i < pts.length; i++) {
      const [x0, y0] = pts[i]!;
      const [x1, y1] = pts[(i + 1) % pts.length]!;
      const cross = x0 * y1 - x1 * y0;
      area += cross; cx += (x0 + x1) * cross; cy += (y0 + y1) * cross;
    }
    if (Math.abs(area) < 1e-9) continue;
    const lng = cx / (3 * area);
    const point = { lat: cy / (3 * area), lng: lng > 180 ? lng - 360 : lng, area: Math.abs(area) / 2 };
    if (!best || point.area > best.area) best = point;
  }
  return best ? { lat: best.lat, lng: best.lng } : null;
}

/**
 * Outlines safe to cut into hexagons: polygons whose outer ring has no width or no height (a
 * degenerate island in the 110 m atlas) make the hexagon library throw, so they are dropped.
 */
export function hexReadyCountries(countries: readonly CountryFeature[]): CountryFeature[] {
  const usable = (polygon: Position[][]) => {
    const ring = polygon[0] ?? [];
    if (ring.length < 4) return false;
    const lons = ring.map(p => p[0] ?? 0);
    const lats = ring.map(p => p[1] ?? 0);
    return Math.max(...lons) - Math.min(...lons) > 1e-6 && Math.max(...lats) - Math.min(...lats) > 1e-6;
  };
  const out: CountryFeature[] = [];
  for (const feature of countries) {
    if (feature.geometry.type === 'Polygon') {
      if (usable(feature.geometry.coordinates)) out.push(feature);
    } else {
      const polygons = feature.geometry.coordinates.filter(usable);
      if (polygons.length > 0) out.push({ ...feature, geometry: { type: 'MultiPolygon', coordinates: polygons } });
    }
  }
  return out;
}
