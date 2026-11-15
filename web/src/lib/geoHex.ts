/**
 * Hexagon helpers for the globe, kept apart from geo.ts so the hexagon library (h3-js, already a
 * dependency of the globe) is loaded only with the globe itself.
 */
import { cellToBoundary, latLngToCell, polygonToCells } from 'h3-js';
import { countryCentroid, type CountryFeature } from './geo';

/**
 * A hexagon map keeps only the hexagons whose centre falls inside the land, so an island smaller than
 * one hexagon (the Aleutians, most of the Pacific) would not be drawn at all and the events on it would
 * seem to stand in the sea. Each such island gets the one hexagon its centre falls in, returned as an
 * extra feature of the same country. Islands whose hexagon straddles the antimeridian are left out.
 */
export function islandHexes(countries: readonly CountryFeature[], res: number): CountryFeature[] {
  const out: CountryFeature[] = [];
  for (const feature of countries) {
    const parts = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
    const cells = new Set<string>();
    for (const part of parts) {
      if ((part[0]?.length ?? 0) < 4) continue;
      let covered: string[];
      try {
        covered = polygonToCells(part, res, true);
      } catch {
        continue;
      }
      if (covered.length > 0) continue;
      const centre = countryCentroid({ geometry: { type: 'Polygon', coordinates: part } });
      if (centre) cells.add(latLngToCell(centre.lat, centre.lng, res));
    }
    const hexagons: [number, number][][][] = [];
    for (const cell of cells) {
      const ring = cellToBoundary(cell, true) as [number, number][];
      const lons = ring.map(point => point[0]);
      if (Math.max(...lons) - Math.min(...lons) > 180) continue;
      hexagons.push([ring]);
    }
    if (hexagons.length > 0) out.push({ ...feature, geometry: { type: 'MultiPolygon', coordinates: hexagons } });
  }
  return out;
}
