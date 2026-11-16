'use client';
import type { ReactNode } from 'react';
import type { WorldPortfolioAssessment } from '../../contracts/types';
import { useApp } from '../../state/app';
import { countryLabel } from '../../lib/geo';
import { fmtDateTime, fmtPct } from '../../lib/format';
import { LINK_TYPE, THEME_TAG, labelOf } from '../../lib/labels';

/** One completed holdings screen, with the evidence and coverage returned by the API. */
export function PortfolioAssessment({ assessment, children }: {
  assessment: WorldPortfolioAssessment | null | undefined;
  children?: ReactNode;
}) {
  const { tr, lang, profile } = useApp();
  // An older API sends no assessment field at all: show the linked holdings it does return.
  if (profile && assessment === undefined) {
    return <section className="world-event-exposure" data-assessed="false"
      aria-label={tr({ en: 'Portfolio exposure', fr: 'Exposition du portefeuille' })}>
      <p className="eyebrow">{tr({ en: 'Portfolio exposure', fr: 'Exposition du portefeuille' })} · {profile.name}</p>
      {children}
      <p className="small muted">{tr({
        en: 'The full portfolio check needs a newer version of the API.',
        fr: 'La vérification complète du portefeuille nécessite une version plus récente de l’API.',
      })}</p>
    </section>;
  }
  if (!profile || !assessment || assessment.profileId !== profile.profileId) {
    return <section className="world-event-exposure" role="status" data-assessed="false">
      <p className="eyebrow">{tr({ en: 'Portfolio exposure', fr: 'Exposition du portefeuille' })}</p>
      <p className="small">{tr({
        en: 'The portfolio check could not be loaded. Refresh the data to retry.',
        fr: 'La vérification du portefeuille n’a pas pu être chargée. Actualisez les données pour réessayer.',
      })}</p>
    </section>;
  }
  const exposed = assessment.exposures.length > 0;
  return <section className="world-event-exposure" data-exposed={exposed} data-assessed="true"
    aria-label={tr({ en: 'Portfolio exposure assessment', fr: 'Évaluation de l’exposition du portefeuille' })}>
    <p className="eyebrow">{tr({ en: 'Portfolio exposure', fr: 'Exposition du portefeuille' })} · {profile.name}</p>
    <h4 className="world-exposure-title">{exposed
      ? tr({ en: 'Potential exposure identified', fr: 'Exposition potentielle repérée' })
      : tr({ en: 'No exposure identified', fr: 'Aucune exposition repérée' })}</h4>
    <p className="small">{tr({
      en: `${assessment.holdingsChecked} holdings checked`,
      fr: `${assessment.holdingsChecked} positions vérifiées`,
    })}{exposed && <> · <strong className="num">{fmtPct(assessment.matchedWeightPct, lang)}</strong> {tr({
      en: 'of the portfolio matched by the available evidence',
      fr: 'du portefeuille correspond aux éléments disponibles',
    })}</>}</p>
    {exposed ? <ul className="holdings-inline small" aria-label={tr({
      en: 'Linked holdings and portfolio weights', fr: 'Positions liées et poids dans le portefeuille',
    })}>
      {assessment.exposures.map(exposure => <li key={exposure.ticker}>
        <strong>{exposure.ticker}</strong> <span className="num">{fmtPct(exposure.weightPct, lang)}</span>
        <span className="muted"> · {labelOf(LINK_TYPE, exposure.linkType, lang)}</span>
      </li>)}
    </ul> : <p className="small muted">{tr({
      en: 'No holding matched the available issuer names, themes or listing countries.',
      fr: 'Aucune position ne correspond aux noms d’émetteurs, thèmes ou pays de cotation disponibles.',
    })}</p>}
    {assessment.limitations.map((limitation, index) => <p key={index} className="small muted">{tr(limitation)}</p>)}
    <details className="fold">
      <summary>{tr({ en: 'Assessment basis and coverage', fr: 'Fondement et couverture de l’évaluation' })}</summary>
      <dl>
        <div className="kv"><dt className="k">{tr({ en: 'Source countries checked', fr: 'Pays de la source vérifiés' })}</dt>
          <dd className="v">{assessment.relatedCountries.length
            ? assessment.relatedCountries.map(code => countryLabel(code, lang)).join(', ')
            : tr({ en: 'No source country could be resolved', fr: 'Aucun pays de source n’a pu être résolu' })}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Named securities checked', fr: 'Titres nommés vérifiés' })}</dt>
          <dd className="v">{assessment.relatedTickers.join(', ') || tr({
            en: 'No unambiguous issuer name recorded', fr: 'Aucun nom d’émetteur enregistré sans ambiguïté',
          })}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Theme proxies checked', fr: 'Thèmes indirects vérifiés' })}</dt>
          <dd className="v">{assessment.relatedThemes.length
            ? assessment.relatedThemes.map(theme => labelOf(THEME_TAG, theme, lang)).join(', ')
            : tr({ en: 'No supported theme recorded', fr: 'Aucun thème pris en charge enregistré' })}</dd></div>
        <div className="kv"><dt className="k">{tr({ en: 'Assessed', fr: 'Évalué' })}</dt>
          <dd className="v">{fmtDateTime(assessment.assessedAt, lang)}</dd></div>
      </dl>
      {exposed && (children ?? <ul className="small">{assessment.exposures.map(exposure => <li key={exposure.ticker}>
        <strong>{exposure.ticker}</strong> · {tr(exposure.note)}
      </li>)}</ul>)}
    </details>
  </section>;
}
