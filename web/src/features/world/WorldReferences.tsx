'use client';
import Link from 'next/link';
import type { AirportReference, Facility, Hazard } from '../../contracts/types';
import { ExternalLink } from '../../components/common/ExternalLink';
import { useApp } from '../../state/app';
import { countryLabel } from '../../lib/geo';
import { fmtDateTime, fmtNumber } from '../../lib/format';
import type { GlobePin } from './globeStyle';
import { PortfolioAssessment } from './PortfolioAssessment';

export function facilityPin(facility: Facility, capturedAt: string | null | undefined): GlobePin {
  return {
    id: `facility:${facility.facilityId}`, kind: 'facility', lat: facility.lat, lng: facility.lon,
    label: facility.name, countryLevel: false, weight: .2,
    reference: {
      sourceName: { en: 'ECCC GHGRP', fr: 'PDGES ECCC' }, sourceUrl: facility.sourceUrl,
      datasetId: 'emissions_facilities', countryIso3: facility.countryIso3, capturedAt: capturedAt ?? null,
      summary: {
        en: `Reported ${fmtNumber(facility.emissionsTco2e, 'en', 0)} tonnes CO₂e in ${facility.reportingYear}. Reporting company: ${facility.operator}.`,
        fr: `${fmtNumber(facility.emissionsTco2e, 'fr', 0)} tonnes éq. CO₂ déclarées en ${facility.reportingYear}. Société déclarante : ${facility.operator}.`,
      },
      assessment: facility.assessment ?? null,
    },
  };
}

export function hazardPin(hazard: Hazard): GlobePin {
  return {
    id: `hazard:${hazard.hazardId}`, kind: 'hazard', lat: hazard.lat, lng: hazard.lon,
    label: hazard.title, countryLevel: false, weight: .2,
    ...(typeof hazard.magnitude === 'number' ? { magnitude: hazard.magnitude } : {}),
    reference: {
      sourceName: { en: hazard.origin === 'usgs' ? 'USGS' : 'NASA FIRMS', fr: hazard.origin === 'usgs' ? 'USGS' : 'NASA FIRMS' },
      sourceUrl: hazard.sourceUrl, datasetId: 'natural_hazards', countryIso3: null,
      occurredAt: hazard.occurredAt,
      summary: hazard.type === 'earthquake' ? {
        en: `Reported earthquake${hazard.magnitude === null ? '' : ` of magnitude ${fmtNumber(hazard.magnitude, 'en', 1)}`}. The source point is the epicenter; damage and the affected area are not supplied.`,
        fr: `Séisme signalé${hazard.magnitude === null ? '' : ` de magnitude ${fmtNumber(hazard.magnitude, 'fr', 1)}`}. Le point de source est l’épicentre ; les dégâts et la zone touchée ne sont pas fournis.`,
      } : {
        en: 'Source wildfire record. The source point does not describe the fire perimeter or losses.',
        fr: 'Enregistrement de feu de forêt sourcé. Le point ne décrit ni le périmètre du feu ni les pertes.',
      },
      assessment: hazard.assessment ?? null,
    },
  };
}

export function airportPin(airport: AirportReference): GlobePin {
  return {
    id: airport.airportId, kind: 'airport', lat: airport.lat, lng: airport.lon,
    label: `${airport.ident} · ${airport.name}`, countryLevel: false, weight: .15,
    reference: {
      sourceName: { en: 'OurAirports', fr: 'OurAirports' }, sourceUrl: airport.sourceUrl,
      datasetId: 'world_airports', countryIso3: airport.countryIso3, capturedAt: airport.capturedAt,
      summary: {
        en: 'Large scheduled-service airport in the captured OurAirports registry. This static reference has no aircraft movements or current operating status.',
        fr: 'Grand aéroport avec service régulier dans le registre OurAirports capturé. Cette référence statique ne fournit ni mouvements aériens ni état opérationnel actuel.',
      },
      assessment: airport.assessment ?? null,
    },
  };
}

export function ReferenceDetail({ pin }: { pin: GlobePin }) {
  const { tr, lang } = useApp();
  const reference = pin.reference;
  if (!reference) return null;
  return <div className="world-event-details">
    <h3>{pin.label}</h3>
    <p className="small">{tr(reference.summary)}</p>
    <PortfolioAssessment assessment={reference.assessment} />
    <details className="fold">
      <summary>{tr({ en: 'Source and geographic reference', fr: 'Source et référence géographique' })}</summary>
      <dl>
        <div className="kv"><dt className="k">{tr({ en: 'Original source', fr: 'Source originale' })}</dt>
          <dd className="v"><ExternalLink href={reference.sourceUrl}>{tr(reference.sourceName)}</ExternalLink></dd></div>
        {reference.countryIso3 && <div className="kv"><dt className="k">{tr({ en: 'Source country', fr: 'Pays de la source' })}</dt>
          <dd className="v">{countryLabel(reference.countryIso3, lang)}</dd></div>}
        {reference.occurredAt && <div className="kv"><dt className="k">{tr({ en: 'Occurred', fr: 'Survenu le' })}</dt>
          <dd className="v">{fmtDateTime(reference.occurredAt, lang)}</dd></div>}
        {reference.capturedAt && <div className="kv"><dt className="k">{tr({ en: 'Captured', fr: 'Collecté' })}</dt>
          <dd className="v">{fmtDateTime(reference.capturedAt, lang)}</dd></div>}
        <div className="kv"><dt className="k">{tr({ en: 'Source coordinates', fr: 'Coordonnées de la source' })}</dt>
          <dd className="v num">{pin.lat}, {pin.lng}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Source passport', fr: 'Passeport de source' })}</dt>
          <dd className="v"><Link href={`/sources/?datasetId=${encodeURIComponent(reference.datasetId)}`}>{reference.datasetId}</Link></dd></div>
      </dl>
      {pin.kind === 'facility' && <p className="small muted">{tr({
        en: 'Annual facility-reported emissions excluding biomass CO₂. Reporting-company names do not establish ownership or a reviewed security relationship.',
        fr: 'Émissions annuelles déclarées par l’installation, hors CO₂ de biomasse. Les noms des sociétés déclarantes ne prouvent ni propriété ni relation boursière vérifiée.',
      })}</p>}
    </details>
  </div>;
}
