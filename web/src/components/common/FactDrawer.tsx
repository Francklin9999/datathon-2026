'use client';
/**
 * Fact/evidence drill-down. Every chip carries the scope it was produced in (a run, a /check
 * preview, an overview response) so a reference always resolves inside its own namespace
 * (WEB-06, AT-07). Run facts use GET /runs/{id}/facts/{factId} for exact provenance and usage.
 */
import Link from 'next/link';
import {
  createContext, useCallback, useContext, useMemo, useState, type ReactNode,
} from 'react';
import type { Evidence, Fact, FactResponse, I18NText } from '../../contracts/types';
import { getApiClient } from '../../api/index';
import { useQuery } from '../../state/useQuery';
import { useApp } from '../../state/app';
import { CountUp } from '../../components/ui/CountUp';
import { Drawer } from './Drawer';
import { ErrorState, Loading, Unavailable } from './States';
import { EVIDENCE_TYPE, FACT_KIND, LIMITATION, VERIFICATION, WINDOW, labelOf } from '../../lib/labels';
import { fmtDate, fmtDateTime } from '../../lib/format';
import { splitLimitations } from '../../lib/ui/limitations';
import { ExternalLink } from './ExternalLink';

export type FactScope =
  | { kind: 'run'; runId: string; facts: Record<string, Fact>; evidence: Record<string, Evidence> }
  | { kind: 'local'; label: I18NText; facts: Record<string, Fact> }
  /**
   * Time Machine reveal ledger (POST /runs/{id}/reveal). A namespace of its own: a reveal fact ID is
   * resolved only in `RevealResult.facts`, never in the run's signed ledger (WEB-06, TMUI-03).
   */
  | { kind: 'reveal'; runId: string; until: string; facts: Record<string, Fact> };

export interface DrawerTarget { scope: FactScope; type: 'fact' | 'evidence'; id: string }

interface DrawerApi {
  current: DrawerTarget | null;
  openFact: (scope: FactScope, factId: string) => void;
  openEvidence: (scope: FactScope, evidenceId: string) => void;
  close: () => void;
}

const DrawerContext = createContext<DrawerApi | null>(null);
const ScopeContext = createContext<FactScope | null>(null);

export function useFactDrawer(): DrawerApi {
  const value = useContext(DrawerContext);
  if (!value) throw new Error('useFactDrawer outside FactDrawerProvider');
  return value;
}

export function FactScopeProvider({ scope, children }: { scope: FactScope; children: ReactNode }) {
  return <ScopeContext.Provider value={scope}>{children}</ScopeContext.Provider>;
}

export function useFactScope(): FactScope | null {
  return useContext(ScopeContext);
}

export function FactDrawerProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<DrawerTarget | null>(null);
  const openFact = useCallback((scope: FactScope, id: string) => setCurrent({ scope, type: 'fact', id }), []);
  const openEvidence = useCallback((scope: FactScope, id: string) => setCurrent({ scope, type: 'evidence', id }), []);
  const close = useCallback(() => setCurrent(null), []);
  const api = useMemo(() => ({ current, openFact, openEvidence, close }), [current, openFact, openEvidence, close]);
  return (
    <DrawerContext.Provider value={api}>
      {children}
      <FactDrawerView target={current} onClose={close} onOpenFact={openFact} />
    </DrawerContext.Provider>
  );
}

/** Clickable proof chip showing the backend-formatted value. */
/** `children` may restyle the visible value (e.g. RollingText); the accessible name always uses `display`. */
export function FactChip({ factId, display, scope: explicit, children }: { factId: string; display?: string; scope?: FactScope; children?: ReactNode }) {
  const contextual = useFactScope();
  const scope = explicit ?? contextual;
  const { openFact } = useFactDrawer();
  const { tr } = useApp();
  const fact = scope?.facts[factId];
  const text = display ?? (fact ? tr(fact.display) : factId);
  if (!scope) return <span className="mono">{text}</span>;
  const label = fact ? tr(fact.label) : factId;
  return (
    <button type="button" className="chip" onClick={() => openFact(scope, factId)}
      aria-label={`${tr({ en: 'Show source for', fr: 'Voir la source de' })} ${label}: ${text}`}>
      {children ?? <CountUp text={text} />}
    </button>
  );
}

export function EvidenceChip({ evidenceId, display }: { evidenceId: string; display: string }) {
  const scope = useFactScope();
  const { openEvidence } = useFactDrawer();
  const { tr } = useApp();
  if (!scope) return <span>{display}</span>;
  return (
    <button type="button" className="chip chip-evidence" onClick={() => openEvidence(scope, evidenceId)}
      aria-label={`${tr({ en: 'Show evidence', fr: 'Voir la preuve' })} ${evidenceId}: ${display}`}>
      {display}
    </button>
  );
}

export function LimitationList({ codes, title, compactAfter }: { codes: readonly string[]; title?: string; compactAfter?: number }) {
  const { lang, tr } = useApp();
  if (codes.length === 0) return null;
  const { shown, folded } = splitLimitations(codes, compactAfter);
  return (
    <div className="limitations">
      <p className="eyebrow">{title ?? tr({ en: 'Limitations', fr: 'Limites' })}</p>
      {shown.length > 0 && (
        <ul className="bullets small">
          {shown.map(code => <li key={code}>{labelOf(LIMITATION, code, lang)}</li>)}
        </ul>
      )}
      {folded.length > 0 && (
        <details className="limitations-more small">
          <summary>{shown.length > 0
            ? tr({ en: `${folded.length} more limitations`, fr: `${folded.length} autres limites` })
            : tr({ en: `Show ${folded.length} limitations`, fr: `Afficher ${folded.length} limites` })}</summary>
          <ul className="bullets">
            {folded.map(code => <li key={code}>{labelOf(LIMITATION, code, lang)}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}

function FactDrawerView({ target, onClose, onOpenFact }: {
  target: DrawerTarget | null; onClose: () => void; onOpenFact: (scope: FactScope, id: string) => void;
}) {
  const { tr } = useApp();
  const title = target?.type === 'evidence'
    ? `${tr({ en: 'Evidence', fr: 'Preuve' })} ${target.id}`
    : target?.scope.kind === 'reveal'
      ? `${tr({ en: 'Reveal fact', fr: 'Fait de révélation' })} ${target.id}`
      : `${tr({ en: 'Fact', fr: 'Fait' })} ${target?.id ?? ''}`;
  return (
    <Drawer open={target !== null} title={title} onClose={onClose}>
      {target?.type === 'fact' && <FactBody key={`${target.scope.kind}|${target.id}`} scope={target.scope} factId={target.id} onOpenFact={onOpenFact} />}
      {target?.type === 'evidence' && <EvidenceBody scope={target.scope} evidenceId={target.id} />}
    </Drawer>
  );
}

function ScopeNote({ scope }: { scope: FactScope }) {
  const { tr } = useApp();
  return (
    <p className="scope-note small">
      {scope.kind === 'run' && tr({ en: 'From the ledger of this analysis.', fr: 'Tiré du registre de cette analyse.' })}
      {scope.kind === 'reveal' && (
        <>
          {tr({ en: 'Revealed outcome, observed up to', fr: 'Résultat révélé, observé jusqu’au' })} {scope.until}.{' '}
          {tr({ en: 'It was not available to the decision.', fr: 'Il n’était pas disponible pour la décision.' })}
        </>
      )}
      {scope.kind === 'local' && tr(scope.label)}
    </p>
  );
}

function FactBody({ scope, factId, onOpenFact }: {
  scope: FactScope; factId: string; onOpenFact: (scope: FactScope, id: string) => void;
}) {
  const { tr } = useApp();
  const runId = scope.kind === 'run' ? scope.runId : null;
  const remote = useQuery<FactResponse>(
    runId ? `fact|${runId}|${factId}` : null,
    signal => getApiClient().fact(runId ?? '', factId, signal),
  );
  if (scope.kind === 'run') {
    if (remote.error) {
      return (
        <>
          <ScopeNote scope={scope} />
          <ErrorState error={remote.error} onRetry={remote.reload}
            {...(remote.error.code === 'not_found'
              ? { title: tr({ en: 'This fact is not in this run’s ledger.', fr: 'Ce fait n’est pas dans le registre de cette exécution.' }) }
              : {})} />
        </>
      );
    }
    if (!remote.data) return <><ScopeNote scope={scope} /><Loading /></>;
    return (
      <>
        <ScopeNote scope={scope} />
        <FactDetail response={remote.data} showUsage onOpenInput={id => onOpenFact(scope, id)} />
      </>
    );
  }
  const fact = scope.facts[factId];
  if (!fact) {
    return (
      <>
        <ScopeNote scope={scope} />
        <Unavailable title={scope.kind === 'reveal'
          ? tr({ en: 'This fact is not in the reveal ledger. It is not looked up in the run’s ledger.', fr: 'Ce fait n’est pas dans le registre de révélation. Il n’est pas recherché dans le registre de l’exécution.' })
          : tr({ en: 'This fact is not in this response.', fr: 'Ce fait n’est pas dans cette réponse.' })} />
      </>
    );
  }
  const response: FactResponse = {
    fact,
    inputs: fact.inputs.flatMap(id => (scope.facts[id] ? [scope.facts[id]] : [])),
    usedBy: { sentenceIds: [], ruleIds: [] },
  };
  return (
    <>
      <ScopeNote scope={scope} />
      <FactDetail response={response} showUsage={false} onOpenInput={id => onOpenFact(scope, id)} />
    </>
  );
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return <div className="kv"><dt className="k">{k}</dt><dd className="v">{children}</dd></div>;
}

export function FactDetail({ response, showUsage, onOpenInput }: {
  response: FactResponse; showUsage: boolean; onOpenInput: (id: string) => void;
}) {
  const { tr, lang } = useApp();
  const { fact } = response;
  const params = Object.entries(fact.method.params);
  return (
    <div>
      <p className="fact-label">{tr(fact.label)}</p>
      <p className="fact-value">{tr(fact.display)}</p>
      <dl>
        <Row k={tr({ en: 'How it is computed', fr: 'Calcul' })}>{tr(fact.method.description)}</Row>
        <Row k={tr({ en: 'Period', fr: 'Période' })}>
          {fact.window ? labelOf(WINDOW, fact.window.code, lang) : '—'}
          {fact.period && <>, {fmtDate(fact.period.start, lang)} → {fmtDate(fact.period.end, lang)}</>}
        </Row>
        <Row k={tr({ en: 'Data as of', fr: 'Données au' })}>{fmtDate(fact.asOf, lang)}</Row>
        <Row k={tr({ en: 'Verification', fr: 'Vérification' })}>{labelOf(VERIFICATION, fact.verification.status, lang)}</Row>
      </dl>

      <h3 className="h4">{tr({ en: 'Sources', fr: 'Sources' })}</h3>
      {fact.sources.length === 0
        ? <p className="muted small">{tr({ en: 'No dataset source (input or assumption).', fr: 'Aucune source de données (saisie ou hypothèse).' })}</p>
        : (
          <ul className="source-list">
            {fact.sources.map((s, i) => (
              <li key={`${s.datasetId}-${i}`} className="small">
                <strong>{s.sourceName}</strong>
                <span className="block">{tr({ en: 'Retrieved', fr: 'Récupéré le' })} {fmtDate(s.retrievedOn, lang)}, {tr({ en: 'licence', fr: 'licence' })} {s.licence}
                  {s.rowsRead !== null && <>, {s.rowsRead} {tr({ en: 'rows', fr: 'lignes' })}</>}</span>
                <span className="block">
                  <Link href={`/sources/?datasetId=${encodeURIComponent(s.datasetId)}&dataVersion=${encodeURIComponent(s.dataVersion)}`}>
                    {tr({ en: 'Open dataset passport', fr: 'Ouvrir le passeport du jeu de données' })}
                  </Link>
                  {s.sourceUrl && <>{' '}<ExternalLink href={s.sourceUrl}>{tr({ en: 'Provider', fr: 'Fournisseur' })}</ExternalLink></>}
                </span>
              </li>
            ))}
          </ul>
        )}

      <LimitationList codes={fact.limitations} />

      <details className="fold">
        <summary>{tr({ en: 'Technical details', fr: 'Détails techniques' })}</summary>
        <div className="fold-body">
      <dl>
        <Row k={tr({ en: 'Kind', fr: 'Nature' })}>{labelOf(FACT_KIND, fact.kind, lang)}</Row>
        <Row k={tr({ en: 'Unit', fr: 'Unité' })}>{fact.unit}{fact.currency ? `, ${fact.currency}` : ''}</Row>
        <Row k={tr({ en: 'Subject', fr: 'Sujet' })}>
          <span className="mono">{fact.subject.type}:{fact.subject.id}</span>, {fact.subject.variant}
        </Row>
        <Row k={tr({ en: 'Available at', fr: 'Disponible le' })}>{fact.availableAt ? fmtDateTime(fact.availableAt, lang) : '—'}</Row>
        <Row k={tr({ en: 'Method', fr: 'Méthode' })}>
          <span className="mono">{fact.method.id}</span>
          {params.length > 0 && (
            <span className="block small mono">{params.map(([k, v]) => `${k}=${String(v)}`).join(', ')}</span>
          )}
        </Row>
        <Row k={tr({ en: 'Observations', fr: 'Observations' })}>{fact.nObs ?? '—'}</Row>
        <Row k={tr({ en: 'Key', fr: 'Clé' })}><span className="mono small break">{fact.key}</span></Row>
        {fact.verification.checks.length > 0 && (
          <Row k={tr({ en: 'Checks', fr: 'Contrôles' })}>
            <ul className="small">
              {fact.verification.checks.map((c, i) => (
                <li key={`${c.code}-${i}`}><span aria-hidden="true">{c.ok ? '✓ ' : '✕ '}</span>
                  <span className="mono">{c.code}</span> {c.ok ? tr({ en: 'passed', fr: 'réussi' }) : tr({ en: 'failed', fr: 'échoué' })}: {c.detail}</li>
              ))}
            </ul>
          </Row>
        )}
        <Row k={tr({ en: 'Sources', fr: 'Sources' })}>
          <span className="mono small break">{fact.sources.map(s => `${s.datasetId} ${s.dataVersion}`).join(', ') || '—'}</span>
        </Row>
      </dl>
      <h3 className="h4">{tr({ en: 'Inputs (one level)', fr: 'Intrants (un niveau)' })}</h3>
      {fact.inputs.length === 0
        ? <p className="muted small">{tr({ en: 'None.', fr: 'Aucun.' })}</p>
        : (
          <ul className="input-list">
            {fact.inputs.map(id => {
              const input = response.inputs.find(f => f.id === id);
              return (
                <li key={id}>
                  <button type="button" className="linklike" onClick={() => onOpenInput(id)}>
                    <span className="mono">{id}</span>{' '}
                    {input ? `${tr(input.label)} — ${tr(input.display)}` : tr({ en: '(not returned)', fr: '(non retourné)' })}
                  </button>
                </li>
              );
            })}
          </ul>
        )}

      {showUsage && (
        <>
          <h3 className="h4">{tr({ en: 'Used by', fr: 'Utilisé par' })}</h3>
          <p className="small">
            {tr({ en: 'Sentences', fr: 'Phrases' })}: <span className="mono">{response.usedBy.sentenceIds.join(', ') || '—'}</span>
            <br />
            {tr({ en: 'Rules', fr: 'Règles' })}: <span className="mono">{response.usedBy.ruleIds.join(', ') || '—'}</span>
          </p>
        </>
      )}
        </div>
      </details>
    </div>
  );
}

function EvidenceBody({ scope, evidenceId }: { scope: FactScope; evidenceId: string }) {
  const { tr, lang } = useApp();
  const evidence = scope.kind === 'run' ? scope.evidence[evidenceId] : undefined;
  if (!evidence) {
    return (
      <>
        <ScopeNote scope={scope} />
        <Unavailable title={tr({ en: 'This evidence item is not in this analysis.', fr: 'Cette preuve n’est pas dans cette analyse.' })} />
      </>
    );
  }
  const quoteVerified = evidence.verification.checks.some(c => c.code === 'A08' && c.ok);
  return (
    <div>
      <ScopeNote scope={scope} />
      <p className="fact-label">{tr(evidence.claim)}</p>
      {evidence.quote !== null && (
        <blockquote className="quote">
          {evidence.quote}
          <footer className="small muted">
            {quoteVerified
              ? tr({ en: 'Quote found in the cached source document.', fr: 'Citation retrouvée dans le document source en cache.' })
              : tr({ en: 'Quote not verified against the cached document.', fr: 'Citation non vérifiée dans le document en cache.' })}
          </footer>
        </blockquote>
      )}
      <dl>
        <Row k={tr({ en: 'Title', fr: 'Titre' })}>{evidence.title}</Row>
        <Row k={tr({ en: 'Publisher', fr: 'Éditeur' })}>{evidence.publisher}</Row>
        <Row k={tr({ en: 'Type', fr: 'Type' })}>{labelOf(EVIDENCE_TYPE, evidence.type, lang)} · {tr({ en: 'tier', fr: 'niveau' })} {evidence.tier}</Row>
        <Row k={tr({ en: 'Published', fr: 'Publié' })}>{evidence.publishedAt ? fmtDate(evidence.publishedAt, lang) : tr({ en: 'Date not stated', fr: 'Date non indiquée' })}</Row>
        <Row k={tr({ en: 'Retrieved', fr: 'Récupéré' })}>{fmtDateTime(evidence.retrievedAt, lang)}</Row>
        <Row k={tr({ en: 'Licence', fr: 'Licence' })}>{evidence.licence}</Row>
        <Row k={tr({ en: 'Verification', fr: 'Vérification' })}>
          {labelOf(VERIFICATION, evidence.verification.status, lang)}
          <ul className="small">
            {evidence.verification.checks.map((c, i) => (
              <li key={`${c.code}-${i}`}><span aria-hidden="true">{c.ok ? '✓ ' : '✕ '}</span><span className="mono">{c.code}</span> — {c.detail}</li>
            ))}
          </ul>
        </Row>
        <Row k="URL"><ExternalLink href={evidence.url}>{evidence.url}</ExternalLink></Row>
      </dl>
    </div>
  );
}
