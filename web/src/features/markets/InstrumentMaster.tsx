'use client';
import { useEffect, useState } from 'react';
import { researchFetch } from '../../api/index';
import { useApp } from '../../state/app';
import { Card } from '../../components/common/Page';
import { ExternalLink } from '../../components/common/ExternalLink';

type EvidenceClass = 'direct' | 'derived' | 'unverified';
type Source = { source_id: string; url: string; content_sha256: string; available_at: string; retrieved_at: string; licence: string; limitations: string[] };
type Identifier = {
  scheme: string; value: string; role: string; evidence_class: EvidenceClass; origin: string;
  stated_from: string | null; stated_to: string | null; derivation: string | null; listing_id: string | null;
  sources: Source[]; corroborated_by: string[];
};
type Route = { mic: string | null; provider: string | null; region: string | null; exchange: string | null; filings: string; financials: string; prices: string; status: string; requirement: string; basis?: string };
type Listing = {
  listing_id: string; ticker: string; mic: string | null; currency: string; asset_class: string; name: string;
  isin: string | null; isin_state: string; provider: string | null; provider_asset_id: string | null;
  valid_from: string | null; valid_to: string | null; lifecycle_anchor: string; route: Route; limitations: string[];
};
type Crosswalk = { isin: string; as_of: string; identifiers: Identifier[]; listings: Listing[]; routing: Route[]; counts: Record<EvidenceClass, number>; limitations: string[] };
type Coverage = { asset_kinds: { kind: string; identifier: string; isin: string; adapters: string[]; status: string; note: string }[]; mic_routes: Route[]; wikidata_contact_configured: boolean };

const obj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const isCrosswalk = (v: unknown): v is Crosswalk => obj(v) && typeof v.isin === 'string' && Array.isArray(v.identifiers) && Array.isArray(v.listings) && Array.isArray(v.routing) && obj(v.counts)
  && v.identifiers.every(r => obj(r) && typeof r.value === 'string' && ['direct', 'derived', 'unverified'].includes(String(r.evidence_class)) && Array.isArray(r.sources));
const isListings = (v: unknown): v is { items: Listing[] } => obj(v) && Array.isArray(v.items) && v.items.every(r => obj(r) && typeof r.listing_id === 'string' && obj(r.route));
const isCoverage = (v: unknown): v is Coverage => obj(v) && Array.isArray(v.asset_kinds) && Array.isArray(v.mic_routes);
const today = () => new Date().toISOString().slice(0, 10);

async function call(path: string, method: 'GET' | 'POST' = 'GET'): Promise<unknown> {
  const r = await researchFetch(path, { method });
  const body: unknown = await r.json().catch(() => null);
  if (!r.ok) {
    const message = obj(body) && obj(body.error) && typeof body.error.message === 'string' ? body.error.message : `HTTP ${r.status}`;
    throw new Error(message);
  }
  return body;
}

export function InstrumentMaster({ showCoinMetrics = false, showWikidata = false }: { showCoinMetrics?: boolean; showWikidata?: boolean }) {
  const { sessionId, tr } = useApp();
  const [isin, setIsin] = useState('');
  const [asOf, setAsOf] = useState(today);
  const [lei, setLei] = useState('');
  const [data, setData] = useState<Crosswalk | null>(null);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [asset, setAsset] = useState('btc');
  const [assets, setAssets] = useState<Listing[] | null>(null);
  const [assetStatus, setAssetStatus] = useState('');

  useEffect(() => {
    if (!sessionId) return;
    let live = true;
    call('/intelligence/master/coverage').then(b => { if (live && isCoverage(b)) setCoverage(b); }).catch(() => undefined);
    return () => { live = false; };
  }, [sessionId]);

  const classLabel = (c: EvidenceClass) => c === 'direct' ? tr({ en: 'Direct source', fr: 'Source directe' })
    : c === 'derived' ? tr({ en: 'Derived (stated rule)', fr: 'Dérivé (règle explicite)' })
    : tr({ en: 'Unverified community assertion', fr: 'Assertion communautaire non vérifiée' });

  async function load(code = isin.trim().toUpperCase()) {
    setBusy(true); setStatus(tr({ en: 'Loading…', fr: 'Chargement…' }));
    try {
      const body = await call(`/intelligence/master/crosswalk?${new URLSearchParams({ isin: code, as_of: asOf })}`);
      if (!isCrosswalk(body)) throw new Error('invalid response');
      setData(body);
      setStatus(`${body.identifiers.length} ${tr({ en: 'identifiers', fr: 'identifiants' })} · ${body.listings.length} ${tr({ en: 'listing records', fr: 'fiches de cotation' })}`);
    } catch (e) {
      setData(null);
      setStatus(`${tr({ en: 'Unavailable or invalid ISIN', fr: 'Indisponible ou ISIN invalide' })}: ${e instanceof Error ? e.message : ''}`);
    } finally { setBusy(false); }
  }

  async function runAdapter(path: string, label: string) {
    if (!data) return;
    setBusy(true); setStatus(`${label}…`);
    try {
      const body = await call(path, 'POST');
      const published = obj(body) && Array.isArray(body.published) ? body.published.length : 0;
      const state = obj(body) && typeof body.status === 'string' ? body.status : '';
      setBusy(false);
      await load(data.isin);
      setStatus(`${label}: ${state} · ${published} ${tr({ en: 'records published', fr: 'enregistrements publiés' })}`);
    } catch (e) {
      setBusy(false);
      setStatus(`${label}: ${tr({ en: 'unavailable', fr: 'indisponible' })} (${e instanceof Error ? e.message : ''})`);
    }
  }

  async function findAsset(publish: boolean) {
    setAssetStatus(tr({ en: 'Loading…', fr: 'Chargement…' })); setAssets(null);
    try {
      if (publish) await call(`/intelligence/master/adapters/coinmetrics/${encodeURIComponent(asset)}`, 'POST');
      const body = await call(`/intelligence/listings?${new URLSearchParams({ as_of: today(), provider: 'coinmetrics', provider_asset_id: asset })}`);
      if (!isListings(body)) throw new Error('invalid response');
      setAssets(body.items);
      setAssetStatus(body.items.length ? '' : tr({ en: 'No published record for this provider asset in this session.', fr: 'Aucune fiche publiée pour cet actif dans cette session.' }));
    } catch (e) {
      setAssetStatus(`${tr({ en: 'Unavailable', fr: 'Indisponible' })}: ${e instanceof Error ? e.message : ''}`);
    }
  }

  const sourceCell = (sources: Source[]) => sources.map(s => <div key={s.content_sha256 + s.source_id} className="small">
    <ExternalLink href={s.url}>{s.source_id}</ExternalLink>
    <br /><span className="muted">{tr({ en: 'Captured', fr: 'Capturé' })} {s.retrieved_at.slice(0, 19).replace('T', ' ')} UTC</span>
    <br /><span className="mono muted" title={s.content_sha256}>sha256:{s.content_sha256.slice(0, 12)}…</span>
  </div>);

  return <Card id="instrument-master" title={tr({ en: 'Instrument master and identifier crosswalk', fr: 'Référentiel d’instruments et table de correspondance' })}>
    <p>{tr({ en: 'Search an exact ISIN to see every recorded identifier with its source, evidence class, capture time and hash. A ticker or name alone never establishes identity. Coverage is limited to the captured example plus records published in this session by trusted adapters.', fr: 'Recherchez un ISIN exact pour voir chaque identifiant enregistré avec sa source, sa classe de preuve, son heure de capture et son empreinte. Un symbole ou un nom seul n’établit jamais l’identité. La couverture se limite à l’exemple capturé et aux fiches publiées dans cette session par des adaptateurs de confiance.' })}</p>
    <form onSubmit={e => { e.preventDefault(); void load(); }}>
      <label htmlFor="master-isin">ISIN</label>{' '}
      <input id="master-isin" value={isin} minLength={12} maxLength={12} onChange={e => setIsin(e.target.value)} required />{' '}
      <label htmlFor="master-asof">{tr({ en: 'As of', fr: 'En date du' })}</label>{' '}
      <input id="master-asof" type="date" value={asOf} max={today()} onChange={e => setAsOf(e.target.value)} required />{' '}
      <button className="btn" disabled={!sessionId || busy}>{tr({ en: 'Build crosswalk', fr: 'Construire la correspondance' })}</button>
    </form>
    <p role="status">{status}</p>

    {data && <>
      {showWikidata && <div className="tags">
        <button type="button" className="btn ghost" disabled={busy || coverage?.wikidata_contact_configured === false}
          onClick={() => void runAdapter(`/intelligence/master/adapters/wikidata?${new URLSearchParams({ isin: data.isin })}`, 'Wikidata')}>
          {tr({ en: 'Record Wikidata assertions (unverified)', fr: 'Enregistrer les assertions Wikidata (non vérifiées)' })}
        </button>{' '}
        {coverage?.wikidata_contact_configured === false && <span className="small muted">{tr({ en: 'Wikidata contact not configured.', fr: 'Contact Wikidata non configuré.' })}</span>}{' '}
        <a className="small" href="#wikidata-candidates">{tr({ en: 'Item candidates only', fr: 'Candidats d’éléments seulement' })}</a>
      </div>}
      <form className="tags" onSubmit={e => { e.preventDefault(); void runAdapter(`/intelligence/master/adapters/gleif-pair?${new URLSearchParams({ isin: data.isin, lei: lei.trim().toUpperCase() })}`, 'GLEIF'); }}>
        <label htmlFor="master-lei">LEI</label>{' '}
        <input id="master-lei" value={lei} minLength={20} maxLength={20} onChange={e => setLei(e.target.value)} required />{' '}
        <button className="btn ghost" disabled={busy}>{tr({ en: 'Verify exact ISIN–LEI pair with GLEIF', fr: 'Vérifier la paire exacte ISIN–LEI auprès de GLEIF' })}</button>
      </form>
      <p className="small muted">{tr({ en: 'A suggested LEI from an unverified row can be checked here; only an inspected matching GLEIF row is recorded as direct.', fr: 'Un LEI suggéré par une ligne non vérifiée peut être contrôlé ici ; seule une ligne GLEIF correspondante inspectée est enregistrée comme directe.' })}</p>

      <h3>{tr({ en: 'Identifier crosswalk', fr: 'Table de correspondance' })} — {data.isin} · {data.as_of}</h3>
      <p className="small">{(['direct', 'derived', 'unverified'] as const).map(c => <span key={c} className={`tag${c === 'direct' ? ' tag-strong' : c === 'unverified' ? ' tag-muted' : ''}`}>{classLabel(c)}: {data.counts[c] ?? 0}</span>)}</p>
      {data.identifiers.length === 0
        ? <p>{tr({ en: 'No identifier recorded for this ISIN at this cutoff. Absence is not proof that none exists.', fr: 'Aucun identifiant enregistré pour cet ISIN à cette date. L’absence ne prouve pas qu’il n’en existe pas.' })}</p>
        : <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Identifier crosswalk', fr: 'Table de correspondance' })}>
          <table className="data-table"><thead><tr>
            <th scope="col">{tr({ en: 'Identifier', fr: 'Identifiant' })}</th><th scope="col">{tr({ en: 'Value', fr: 'Valeur' })}</th>
            <th scope="col">{tr({ en: 'Role', fr: 'Rôle' })}</th><th scope="col">{tr({ en: 'Evidence class', fr: 'Classe de preuve' })}</th>
            <th scope="col">{tr({ en: 'Source, capture and hash', fr: 'Source, capture et empreinte' })}</th><th scope="col">{tr({ en: 'Stated validity', fr: 'Validité déclarée' })}</th>
            <th scope="col">{tr({ en: 'Notes', fr: 'Remarques' })}</th>
          </tr></thead><tbody>{data.identifiers.map((row, i) => <tr key={`${row.scheme}-${row.value}-${row.origin}-${i}`}>
            <td>{row.scheme}</td><td className="mono break">{row.value}</td><td>{row.role}</td>
            <td><span className={`tag${row.evidence_class === 'direct' ? ' tag-strong' : row.evidence_class === 'unverified' ? ' tag-muted' : ''}`}>{classLabel(row.evidence_class)}</span><br /><span className="small muted">{row.origin}</span></td>
            <td>{sourceCell(row.sources)}</td>
            <td className="small">{row.stated_from || row.stated_to ? `${row.stated_from ?? '?'} → ${row.stated_to ?? tr({ en: 'open', fr: 'ouvert' })}` : '—'}</td>
            <td className="small">{row.derivation && <>{row.derivation}<br /></>}
              {row.evidence_class === 'unverified' && (row.corroborated_by.length
                ? `${tr({ en: 'Matches direct source', fr: 'Concorde avec une source directe' })}: ${row.corroborated_by.join(', ')} (${tr({ en: 'class unchanged', fr: 'classe inchangée' })})`
                : tr({ en: 'Lead only; not identity proof.', fr: 'Piste seulement ; pas une preuve d’identité.' }))}
            </td>
          </tr>)}</tbody></table></div>}

      <h3>{tr({ en: 'Listing lifecycle', fr: 'Cycle de vie des cotations' })}</h3>
      {data.listings.length === 0
        ? <p>{tr({ en: 'No published listing record for this ISIN at this cutoff.', fr: 'Aucune fiche de cotation publiée pour cet ISIN à cette date.' })}</p>
        : <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Listing lifecycle', fr: 'Cycle de vie des cotations' })}>
          <table className="data-table"><thead><tr>
            <th scope="col">{tr({ en: 'Market', fr: 'Marché' })}</th><th scope="col">{tr({ en: 'Ticker', fr: 'Symbole' })}</th>
            <th scope="col">{tr({ en: 'Kind', fr: 'Type' })}</th><th scope="col">{tr({ en: 'Currency', fr: 'Devise' })}</th>
            <th scope="col">{tr({ en: 'Start → end', fr: 'Début → fin' })}</th><th scope="col">{tr({ en: 'Lifecycle anchor', fr: 'Ancre de cycle de vie' })}</th>
            <th scope="col">{tr({ en: 'Listing ID', fr: 'ID de cotation' })}</th>
          </tr></thead><tbody>{data.listings.map(l => <tr key={l.listing_id}>
            <td>{l.mic ?? l.provider}{l.route.exchange && <><br /><span className="small muted">{l.route.exchange}</span></>}</td>
            <td>{l.ticker}</td><td>{l.asset_class}</td><td>{l.currency}</td>
            <td className="small">{l.valid_from ?? tr({ en: 'start unverified', fr: 'début non vérifié' })} → {l.valid_to ?? tr({ en: 'no end recorded', fr: 'aucune fin enregistrée' })}</td>
            <td className="small mono break">{l.lifecycle_anchor}</td><td className="small mono break">{l.listing_id}</td>
          </tr>)}</tbody></table></div>}

      <h3>{tr({ en: 'Adapter routing by market', fr: 'Routage des adaptateurs par marché' })}</h3>
      {data.routing.length === 0 ? <p>{tr({ en: 'No market identifier recorded.', fr: 'Aucun identifiant de marché enregistré.' })}</p>
        : <ul>{data.routing.map(r => <li key={`${r.mic}-${r.basis}`}>
          <strong>{r.mic}</strong> {r.exchange && `· ${r.exchange}`} · {r.basis === 'listing_record' ? tr({ en: 'from listing record', fr: 'depuis une fiche de cotation' }) : tr({ en: 'from unverified candidate', fr: 'depuis un candidat non vérifié' })}
          <br /><span className="small">{tr({ en: 'Filings', fr: 'Dépôts' })}: {r.filings} · {tr({ en: 'Financials', fr: 'États financiers' })}: {r.financials} · {tr({ en: 'Prices', fr: 'Prix' })}: {r.prices}</span>
          <br /><span className="small muted">{r.requirement}</span>
        </li>)}</ul>}
      <ul className="small muted">{data.limitations.map(l => <li key={l}>{l}</li>)}</ul>
    </>}

    {showCoinMetrics && <><h3>{tr({ en: 'Assets without an ISIN', fr: 'Actifs sans ISIN' })}</h3>
    <p className="small">{tr({ en: 'Crypto, indices and commodities are identified by provider and exact provider asset ID. Only Coin Metrics Community (btc, eth) has an adapter; it requires the noncommercial licence flag.', fr: 'Les cryptoactifs, indices et matières premières sont identifiés par fournisseur et identifiant exact. Seul Coin Metrics Community (btc, eth) dispose d’un adaptateur ; il exige l’indicateur de licence non commerciale.' })}</p>
    <form onSubmit={e => { e.preventDefault(); void findAsset(false); }}>
      <label htmlFor="master-asset">Coin Metrics</label>{' '}
      <select id="master-asset" value={asset} onChange={e => setAsset(e.target.value)}><option value="btc">btc</option><option value="eth">eth</option></select>{' '}
      <button className="btn ghost" disabled={!sessionId}>{tr({ en: 'Find record', fr: 'Trouver la fiche' })}</button>{' '}
      <button type="button" className="btn ghost" disabled={!sessionId} onClick={() => void findAsset(true)}>{tr({ en: 'Publish from Coin Metrics', fr: 'Publier depuis Coin Metrics' })}</button>
    </form>
    <p role="status" className="small">{assetStatus}</p>
    {assets && assets.length > 0 && <ul>{assets.map(a => <li key={a.listing_id}>
      {a.provider}:{a.provider_asset_id} · {a.asset_class} · ISIN: {a.isin_state === 'exact' ? a.isin : tr({ en: 'not in source record', fr: 'absent de la source' })} · {tr({ en: 'Prices', fr: 'Prix' })}: {a.route.prices}
      <br /><span className="small mono">{a.listing_id}</span>
      <ul className="small muted">{a.limitations.map(l => <li key={l}>{l}</li>)}</ul>
    </li>)}</ul>}</>}

    {coverage && <details>
      <summary>{tr({ en: 'Coverage by asset kind and market', fr: 'Couverture par type d’actif et marché' })}</summary>
      <div className="table-scroll" role="region" tabIndex={0} aria-label={tr({ en: 'Coverage by asset kind', fr: 'Couverture par type d’actif' })}>
        <table className="data-table"><thead><tr><th scope="col">{tr({ en: 'Kind', fr: 'Type' })}</th><th scope="col">{tr({ en: 'Identifier', fr: 'Identifiant' })}</th><th scope="col">ISIN</th><th scope="col">{tr({ en: 'Adapters', fr: 'Adaptateurs' })}</th><th scope="col">{tr({ en: 'Status', fr: 'Statut' })}</th></tr></thead>
          <tbody>{coverage.asset_kinds.map(k => <tr key={k.kind}><td>{k.kind}</td><td className="small">{k.identifier}</td><td className="small">{k.isin}</td><td className="small">{k.adapters.join(', ') || '—'}</td><td className="small">{k.status}<br /><span className="muted">{k.note}</span></td></tr>)}</tbody></table>
      </div>
      <ul className="small">{coverage.mic_routes.map(r => <li key={r.mic}><strong>{r.mic}</strong> · {r.exchange} · {r.region} · {tr({ en: 'Filings', fr: 'Dépôts' })}: {r.filings} · {tr({ en: 'Prices', fr: 'Prix' })}: {r.prices}</li>)}</ul>
      <p className="small muted">{tr({ en: 'Markets not listed have no adapter and are never routed to SEC by default.', fr: 'Les marchés non listés n’ont pas d’adaptateur et ne sont jamais routés vers la SEC par défaut.' })}</p>
    </details>}
  </Card>;
}
