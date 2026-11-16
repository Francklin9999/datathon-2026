'use client';
import { useId, useState } from 'react';
import { getApiClient } from '../../api/index';
import { ApiRequestError } from '../../api/errors';
import { ExternalLink } from '../../components/common/ExternalLink';
import { Card } from '../../components/common/Page';
import { Empty, Loading, Unavailable } from '../../components/common/States';
import type { RegionalResearchResponse } from '../../contracts/types';
import { useApp } from '../../state/app';

type Kind = RegionalResearchResponse['kind'];
/** GET /intelligence/regional, validated against the generated contract (1.6.0, research#7). */
type RegionalResult = RegionalResearchResponse;

const KINDS: Record<'JP' | 'KR', Kind[]> = { JP: ['prices', 'company', 'financials'], KR: ['filings', 'financials', 'ownership'] };

/** Thousands grouping on the exact decimal string; no float conversion. */
function grouped(value: string | null | undefined): string {
  if (value == null) return '—';
  const match = /^(-?)(\d+)(\.\d+)?$/.exec(value);
  if (!match) return value;
  return `${match[1]}${(match[2] ?? '').replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${match[3] ?? ''}`;
}

function signed(value: string | null | undefined): string {
  if (value == null) return '—';
  return value.startsWith('-') || value === '0' ? grouped(value) : `+${grouped(value)}`;
}

export function RegionalResearch({ allowedRegions = ['JP', 'KR'] }: { allowedRegions?: ('JP' | 'KR')[] }) {
  const { tr, sessionId } = useApp();
  const prefix = useId();
  const [region, setRegion] = useState<'JP' | 'KR'>(allowedRegions[0] ?? 'KR');
  const [kind, setKind] = useState<Kind>((allowedRegions[0] ?? 'KR') === 'KR' ? 'filings' : 'prices');
  const [fiscalYear, setFiscalYear] = useState(String(new Date().getUTCFullYear() - 1));
  const [reportCode, setReportCode] = useState('11011');
  const [statementType, setStatementType] = useState('CFS');
  const [identifier, setIdentifier] = useState('');
  const initialJapan=allowedRegions[0]==='JP';
  const [start, setStart] = useState(new Date(Date.now() - (initialJapan?319:30) * 86400000).toISOString().slice(0, 10));
  const [end, setEnd] = useState(new Date(Date.now() - (initialJapan?138:0) * 86400000).toISOString().slice(0, 10));
  const [result, setResult] = useState<RegionalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const kindLabel = (value: Kind) => ({
    prices: tr({ en: 'Daily prices', fr: 'Prix quotidiens' }),
    company: tr({ en: 'Listed issue information', fr: 'Informations sur le titre coté' }),
    filings: tr({ en: 'Company and filings', fr: 'Société et déclarations' }),
    financials: tr({ en: 'Financial statements', fr: 'États financiers' }),
    ownership: tr({ en: 'Major shareholder and executive ownership', fr: 'Actionnaires principaux et dirigeants' }),
  })[value];

  const categoryLabel = (value: string) => ({
    major_shareholder: tr({ en: 'Major shareholding report', fr: 'Déclaration d’actionnaire important' }),
    executive_or_major_holder: tr({ en: 'Executive / major holder', fr: 'Dirigeant / actionnaire principal' }),
    large_volume_holding: tr({ en: 'Large volume holding', fr: 'Participation importante' }),
  } as Record<string, string>)[value] ?? value;

  function reset() { setResult(null); setError(null); }

  async function search() {
    if (!sessionId || !identifier || !start || !end) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const financialsQuery = region === 'KR' && kind === 'financials'
        ? { report_code: reportCode, statement_type: statementType, ...(fiscalYear ? { fiscal_year: fiscalYear } : {}) }
        : {};
      setResult(await getApiClient().regionalResearch({ region, identifier, start, end, kind, ...financialsQuery }));
    } catch (e) {
      // An HTTP error answer: the provider failed (503/upstream_unavailable) or the request was refused.
      // No answer, or a body that is not the contract: the source could not be queried.
      const status = e instanceof ApiRequestError ? e.status : 0;
      const code = e instanceof ApiRequestError ? e.code : null;
      const answered = status >= 400;
      setError(answered && (status === 503 || code === 'upstream_unavailable')
        ? tr({ en: 'The provider did not return a usable response. Try again later.', fr: 'Le fournisseur n’a pas renvoyé de réponse exploitable. Réessayez plus tard.' })
        : answered
          ? tr({ en: 'The request was rejected. Check the identifier, dates and report selection.', fr: 'La requête a été refusée. Vérifiez l’identifiant, les dates et le rapport choisi.' })
          : tr({ en: 'The source could not be queried. Try again later.', fr: 'La source ne peut être interrogée. Réessayez plus tard.' }));
    } finally { setLoading(false); }
  }

  const financials = result?.financials ?? [];
  const ownership = result?.ownership ?? [];
  const isEmpty = result?.status === 'ok' && !result.prices.length && !result.filings.length && !result.company
    && !financials.length && !ownership.length;

  return <Card title={tr({ en: 'Regional source research', fr: 'Recherche dans les sources régionales' })}>
    <p className="small">{tr({ en: 'Query Japanese (J-Quants) or Korean (OpenDART) official sources with an exact provider identifier. Tickers and names are never matched. Access depends on configured credentials and usage rights.', fr: 'Interrogez les sources officielles japonaises (J-Quants) ou coréennes (OpenDART) avec un identifiant exact du fournisseur. Aucun rapprochement par ticker ou par nom. L’accès dépend des identifiants et droits configurés.' })}</p>
    <div className="field"><label htmlFor={prefix+'-regional-region'}>{tr({ en: 'Provider region', fr: 'Région du fournisseur' })}</label>
      <select disabled={loading} id={prefix+'-regional-region'} value={region} onChange={e => { const next = e.target.value as 'JP' | 'KR'; setRegion(next); setKind(next === 'JP' ? 'prices' : 'filings'); setIdentifier(''); reset(); }}>
        {allowedRegions.includes('JP') && <option value="JP">Japan · J-Quants</option>}{allowedRegions.includes('KR') && <option value="KR">Korea · OpenDART</option>}
      </select></div>
    <div className="field"><label htmlFor={prefix+'-regional-kind'}>{tr({ en: 'Research type', fr: 'Type de recherche' })}</label>
      <select disabled={loading} id={prefix+'-regional-kind'} value={kind} onChange={e => { setKind(e.target.value as Kind); reset(); }}>
        {KINDS[region].map(value => <option key={value} value={value}>{kindLabel(value)}</option>)}
      </select></div>
    <div className="field"><label htmlFor={prefix+'-regional-id'}>{region === 'JP' ? tr({ en: 'Five-character J-Quants issue code', fr: 'Code J-Quants à cinq caractères' }) : tr({ en: 'Eight-digit OpenDART corporate code', fr: 'Code d’entreprise OpenDART à huit chiffres' })}</label>
      <input disabled={loading} id={prefix+'-regional-id'} value={identifier} maxLength={region === 'JP' ? 5 : 8} onChange={e => { setIdentifier(e.target.value.toUpperCase().trim()); reset(); }} /></div>
    {region==='JP'&&<p className="small muted">{tr({en:'J-Quants coverage depends on your plan. The default uses a past interval because free access may be delayed.',fr:'La couverture J-Quants dépend de votre forfait. La période initiale est passée car l’accès gratuit peut être différé.'})}</p>}
    <div className="field"><label htmlFor={prefix+'-regional-start'}>{kind === 'company' ? tr({ en: 'From (range check only)', fr: 'Du (contrôle de plage)' }) : tr({ en: 'From', fr: 'Du' })}</label><input disabled={loading} type="date" id={prefix+'-regional-start'} value={start} onChange={e => { setStart(e.target.value); reset(); }} /></div>
    <div className="field"><label htmlFor={prefix+'-regional-end'}>{kind === 'company' ? tr({ en: 'As of', fr: 'À la date du' }) : tr({ en: 'To', fr: 'Au' })}</label><input disabled={loading} type="date" id={prefix+'-regional-end'} value={end} onChange={e => { setEnd(e.target.value); reset(); }} /></div>
    {region === 'KR' && kind === 'financials' && <>
      <div className="field"><label htmlFor={prefix+'-regional-fiscal-year'}>{tr({ en: 'Fiscal year', fr: 'Exercice financier' })}</label><input disabled={loading} id={prefix+'-regional-fiscal-year'} inputMode="numeric" pattern="[0-9]{4}" maxLength={4} value={fiscalYear} placeholder={end.slice(0, 4)} onChange={e => { setFiscalYear(e.target.value); reset(); }} /></div>
      <div className="field"><label htmlFor={prefix+'-regional-report-code'}>{tr({ en: 'Report period', fr: 'Période du rapport' })}</label><select disabled={loading} id={prefix+'-regional-report-code'} value={reportCode} onChange={e => { setReportCode(e.target.value); reset(); }}><option value="11011">{tr({ en: 'Annual', fr: 'Annuel' })}</option><option value="11013">{tr({ en: 'First quarter', fr: 'Premier trimestre' })}</option><option value="11012">{tr({ en: 'Half year', fr: 'Semestriel' })}</option><option value="11014">{tr({ en: 'Third quarter', fr: 'Troisième trimestre' })}</option></select></div>
      <div className="field"><label htmlFor={prefix+'-regional-statement-type'}>{tr({ en: 'Statement basis', fr: 'Base des états' })}</label><select disabled={loading} id={prefix+'-regional-statement-type'} value={statementType} onChange={e => { setStatementType(e.target.value); reset(); }}><option value="CFS">{tr({ en: 'Consolidated', fr: 'Consolidé' })}</option><option value="OFS">{tr({ en: 'Separate', fr: 'Individuel' })}</option></select></div>
    </>}
    <button className="btn" type="button" disabled={loading || !sessionId || !identifier || !start || !end} onClick={() => void search()}>{tr({ en: 'Query source', fr: 'Interroger la source' })}</button>

    {loading && <Loading label={tr({ en: 'Querying the provider…', fr: 'Interrogation du fournisseur…' })} />}
    {error && <p role="alert">{error}</p>}
    {result?.status === 'unavailable' && <Unavailable title={tr({ en: `${result.provider} is unavailable`, fr: `${result.provider} est indisponible` })}>
      {tr({ en: 'Credentials and operator-confirmed usage rights are not configured for this provider. No data was requested.', fr: 'Les identifiants et les droits d’utilisation confirmés par l’opérateur ne sont pas configurés. Aucune donnée n’a été demandée.' })}
    </Unavailable>}

    {result?.status === 'ok' && <div>
      <p className="small">
        {(result.sourceUrls ?? [result.sourceUrl]).map((url, i) => <span key={url}>{i > 0 && ' · '}<ExternalLink href={url}>{i === 0 ? result.provider : url.split('/').pop()}</ExternalLink></span>)}
        {' · '}{result.identifierType}: <span className="mono">{result.identifier}</span>
        {' · '}{tr({ en: 'captured', fr: 'capturé' })} {result.retrievedAt}
        {result.datasetVersion && <> · <span className="mono">{result.datasetVersion.slice(0, 22)}</span></>}
      </p>
      <div className="small break mono">
        {Object.entries(result.sourceHashes ?? (result.sourceSha256 ? { source: result.sourceSha256 } : {})).map(([name, sha]) => <p key={name}>{name} · SHA-256 {sha}</p>)}
        {result.companySourceSha256 && <p>{tr({ en: 'Company', fr: 'Entreprise' })} · SHA-256 {result.companySourceSha256}</p>}
      </div>
      {result.partial
        ? <p role="status"><strong>{tr({ en: 'Partial: first page only — the provider reported more pages that were not retrieved.', fr: 'Partiel : première page uniquement — le fournisseur indique d’autres pages non récupérées.' })}</strong></p>
        : <p className="small muted">{tr({ en: 'The provider reported no further pages for this request.', fr: 'Le fournisseur n’indique pas d’autres pages pour cette requête.' })}</p>}

      {result.company && <dl className="small">
        <dt>{tr({ en: 'Company (provider-reported)', fr: 'Société (selon le fournisseur)' })}</dt>
        <dd>{[result.company.name, result.company.englishName].filter(Boolean).join(' · ') || '—'}{result.company.stockCode && ` (${result.company.stockCode})`}</dd>
        {result.company.marketName && <><dt>{tr({ en: 'Market segment', fr: 'Segment de marché' })}</dt><dd>{result.company.marketName} <span className="mono">{result.company.marketCode}</span></dd></>}
        {result.company.sector33Name && <><dt>{tr({ en: '33-sector', fr: 'Secteur (33)' })}</dt><dd>{result.company.sector33Name} <span className="mono">{result.company.sector33Code}</span></dd></>}
        {result.company.sector17Name && <><dt>{tr({ en: '17-sector', fr: 'Secteur (17)' })}</dt><dd>{result.company.sector17Name} <span className="mono">{result.company.sector17Code}</span></dd></>}
        {result.company.scaleCategory && <><dt>{tr({ en: 'Scale category', fr: 'Catégorie de taille' })}</dt><dd>{result.company.scaleCategory}</dd></>}
        {result.company.marginName && <><dt>{tr({ en: 'Margin / loan flag', fr: 'Marge / prêt' })}</dt><dd>{result.company.marginName}</dd></>}
        {result.company.asOf && <><dt>{tr({ en: 'Information as of', fr: 'Informations au' })}</dt><dd>{result.company.asOf}</dd></>}
      </dl>}

      {result.prices.length > 0 && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Daily prices', fr: 'Prix quotidiens' })}><table className="data-table"><thead><tr><th>Date</th><th>{tr({ en: 'Close', fr: 'Clôture' })}</th><th>{tr({ en: 'Adjusted close', fr: 'Clôture ajustée' })}</th></tr></thead><tbody>{result.prices.map(p => <tr key={p.date}><td>{p.date}</td><td>{p.close ?? '—'} {p.currency}</td><td>{p.adjustedClose ?? '—'} {p.currency}</td></tr>)}</tbody></table></div>}

      {result.filings.length > 0 && <ul>{result.filings.map(f => <li key={f.receiptNumber}>{f.date} · <ExternalLink href={f.url}>{f.title}</ExternalLink></li>)}</ul>}

      {financials.length > 0 && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Financial statements', fr: 'États financiers' })}>
        {result.fiscalYear && <p className="small">{tr({ en: 'Fiscal year', fr: 'Exercice' })} {result.fiscalYear} · {tr({ en: 'report code', fr: 'code de rapport' })} {result.reportCode} · {result.statementType}</p>}
        <table className="data-table"><thead><tr>
          <th>{tr({ en: 'Period', fr: 'Période' })}</th><th>{tr({ en: 'Account', fr: 'Compte' })}</th><th>{tr({ en: 'Section', fr: 'Section' })}</th>
          <th>{tr({ en: 'Value', fr: 'Valeur' })}</th><th>{tr({ en: 'Unit', fr: 'Unité' })}</th><th>{tr({ en: 'Disclosed / receipt', fr: 'Publication / réception' })}</th>
        </tr></thead><tbody>{financials.map((f, i) => <tr key={`${f.disclosureNumber ?? f.receiptNumber}-${f.section}-${f.accountId}-${i}`}>
          <td>{f.period ?? '—'}{(f.periodStart || f.periodEnd) && <div className="small muted">{f.periodStart ?? '?'} → {f.periodEnd ?? '?'}</div>}</td>
          <td>{f.accountName ?? '—'}{f.accountDetail && <div className="small muted">{f.accountDetail}</div>}<div className="small muted mono">{f.accountId}</div></td>
          <td>{f.sectionName ?? f.section ?? '—'}{f.classification === 'forecast' && <div className="small">{tr({ en: 'company forecast', fr: 'prévision société' })}</div>}</td>
          <td className="num">{grouped(f.value)}
            {f.cumulativeValue != null && <div className="small muted">{tr({ en: 'cumulative', fr: 'cumulé' })} {grouped(f.cumulativeValue)}</div>}
            {f.priorValue != null && <div className="small muted">{f.priorPeriod ?? tr({ en: 'prior', fr: 'précédent' })}: {grouped(f.priorValue)}</div>}</td>
          <td>{f.unit ?? '—'}</td>
          <td>{f.disclosedAt ?? f.disclosedDate ?? tr({ en: 'date not in source', fr: 'date absente de la source' })}
            <div className="small muted mono">{f.url ? <ExternalLink href={f.url}>{f.receiptNumber ?? f.disclosureNumber}</ExternalLink> : (f.disclosureNumber ?? f.receiptNumber)}</div>
            {f.documentType && <div className="small muted">{f.documentType}</div>}</td>
        </tr>)}</tbody></table></div>}

      {ownership.length > 0 && <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Ownership disclosures', fr: 'Déclarations de propriété' })}>
        <table className="data-table"><thead><tr>
          <th>{tr({ en: 'Reporter', fr: 'Déclarant' })}</th><th>{tr({ en: 'Report', fr: 'Déclaration' })}</th><th>{tr({ en: 'Shares', fr: 'Actions' })}</th>
          <th>{tr({ en: 'Change', fr: 'Variation' })}</th><th>{tr({ en: 'Ratio', fr: 'Part' })}</th><th>{tr({ en: 'Receipt date', fr: 'Date de réception' })}</th>
        </tr></thead><tbody>{ownership.map((o, i) => <tr key={`${o.category}-${o.receiptNumber ?? o.documentId}-${i}`}>
          <td>{o.reporter ?? '—'}{o.position && <div className="small muted">{o.position}</div>}</td>
          <td>{categoryLabel(o.category)}{o.reportType && <div className="small muted">{o.reportType}</div>}{o.reason && <div className="small muted">{o.reason}</div>}{o.amendment && <div className="small">{tr({ en: 'amendment', fr: 'modification' })}</div>}</td>
          <td className="num">{grouped(o.shares)}</td>
          <td className="num">{signed(o.sharesChange)}{o.ratioChangePct != null && <div className="small muted">{signed(o.ratioChangePct)} pp</div>}</td>
          <td className="num">{o.ratioPct != null ? `${o.ratioPct}%` : '—'}</td>
          <td>{o.filedAt ?? o.filed}<div className="small muted mono">{o.url ? <ExternalLink href={o.url}>{o.receiptNumber}</ExternalLink> : o.documentId}</div></td>
        </tr>)}</tbody></table></div>}

      {isEmpty && <Empty>{tr({ en: 'The provider returned no records for this selection.', fr: 'Le fournisseur n’a renvoyé aucun résultat pour cette sélection.' })}</Empty>}
      {result.limitations && result.limitations.length > 0 && <details className="small"><summary>{tr({ en: 'Source limitations (provider notes, English)', fr: 'Limites de la source (notes, en anglais)' })}</summary>
        <ul>{result.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>}
    </div>}
  </Card>;
}
