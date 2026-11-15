'use client';
/**
 * Audit report (T14): A01–A14 results by kind, struck/rewrite counts, guardrail ("Not applied"
 * when not configured, never implied executed) and ledger integrity metadata with copy/download.
 */
import { useState } from 'react';
import type { AuditReport, Run } from '../../contracts/types';
import { AUDIT_CHECK, labelOf } from '../../lib/labels';
import { fmtDateTime } from '../../lib/format';
import { useApp } from '../../state/app';

const KIND_LABEL = {
  code: { en: 'code', fr: 'code' },
  llm: { en: 'language model', fr: 'modèle de langage' },
  guardrail: { en: 'guardrail', fr: 'garde-fou' },
} as const;

const STATUS_TEXT = {
  passed: { en: 'Reported checks passed', fr: 'Vérifications rapportées réussies' },
  passed_with_strikes: { en: 'Passed with struck sentences', fr: 'Réussi avec phrases rayées' },
  failed: { en: 'Audit failed', fr: 'Audit échoué' },
} as const;

export function AuditPanel({ audit, run }: { audit: AuditReport; run: Run }) {
  const { tr, lang } = useApp();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`${audit.ledgerHash} ${audit.signedAt}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { setCopied(false); }
  };

  const download = () => {
    const bundle = {
      runId: run.runId, dataVersion: run.dataVersion, asOf: run.asOf,
      ledgerHash: audit.ledgerHash, signedAt: audit.signedAt,
      facts: run.facts, evidence: run.evidence, audit,
      note: 'Integrity metadata: the hash identifies this ledger; it is not proof that its contents are true.',
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `aplomb-ledger-${run.runId}.json`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  const pillClass = audit.status === 'failed' ? 'conflict' : audit.status === 'passed' ? 'pass' : 'tension';

  return (
    <div className="audit-panel">
      <p>
        <span className={`pill s-${pillClass}`}>{tr(STATUS_TEXT[audit.status])}</span>{' '}
        <span className="small muted">
          {tr({ en: 'Covers the checks below only.', fr: 'Ne couvre que les vérifications ci-dessous.' })}
        </span>
      </p>
      <p className="small">
        {audit.sentencesChecked} {tr({ en: 'sentence(s) checked', fr: 'phrase(s) vérifiée(s)' })}, {audit.sentencesStruck} {tr({ en: 'struck', fr: 'rayée(s)' })}, {audit.rewrites} {tr({ en: 'rewrite(s)', fr: 'réécriture(s)' })}
      </p>
      <p className="small">
        {tr({ en: 'Guardrail', fr: 'Garde-fou' })}:{' '}
        {audit.guardrail.applied
          ? <>{tr({ en: 'applied', fr: 'appliqué' })} · {audit.guardrail.action} {audit.guardrail.id && <span className="mono">{audit.guardrail.id}</span>}</>
          : <strong>{tr({ en: 'Not applied', fr: 'Non appliqué' })}</strong>}
        {' · '}{tr({ en: 'Model review', fr: 'Revue par modèle' })}:{' '}
        {audit.llmReview.model ? <span className="mono">{audit.llmReview.model}</span> : <strong>{tr({ en: 'Not applied', fr: 'Non appliquée' })}</strong>}
      </p>

      <div className="table-scroll" role="region" aria-label={tr({ en: 'Audit checks', fr: 'Vérifications d’audit' })} tabIndex={0}>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">{tr({ en: 'Check', fr: 'Vérification' })}</th>
              <th scope="col">{tr({ en: 'Result', fr: 'Résultat' })}</th>
              <th scope="col">{tr({ en: 'By', fr: 'Par' })}</th>
              <th scope="col">{tr({ en: 'Detail', fr: 'Détail' })}</th>
              <th scope="col">{tr({ en: 'Sentences', fr: 'Phrases' })}</th>
            </tr>
          </thead>
          <tbody>
            {audit.checks.map((check, i) => (
              <tr key={`${check.code}-${i}`} className={check.ok ? '' : 'row-conflict'}>
                <th scope="row"><span className="mono">{check.code}</span> <span className="small block muted">{labelOf(AUDIT_CHECK, check.code, lang)}</span></th>
                <td>{check.ok
                  ? <span className="pill s-pass"><span aria-hidden="true">✓ </span>{tr({ en: 'Passed', fr: 'Réussi' })}</span>
                  : <span className="pill s-conflict"><span aria-hidden="true">✕ </span>{tr({ en: 'Failed', fr: 'Échoué' })}</span>}</td>
                <td className="small">{tr(KIND_LABEL[check.kind])}</td>
                <td className="small">{check.detail}</td>
                <td className="small mono">{check.sentenceIds.length ? check.sentenceIds.map(id => <a key={id} href={`#sentence-${id}`}>{id} </a>) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {audit.llmReview.findings.length > 0 && (
        <>
          <h3 className="h4">{tr({ en: 'Model review findings', fr: 'Constats de la revue par modèle' })}</h3>
          <ul className="small">
            {audit.llmReview.findings.map((f, i) => <li key={i}><span className="mono">{f.sentenceId} {f.code}</span> — {f.issue}</li>)}
          </ul>
        </>
      )}

      <details className="fold">
        <summary>{tr({ en: 'Ledger integrity', fr: 'Intégrité du registre' })}</summary>
        <div className="fold-body">
        <p className="mono small break">{audit.ledgerHash}</p>
        <p className="small">{tr({ en: 'Signed', fr: 'Signé' })} {fmtDateTime(audit.signedAt, lang)}</p>
        <p className="small muted">{tr({ en: 'The hash lets anyone detect later changes to the facts and evidence. It is not proof that they are true.', fr: 'L’empreinte permet de détecter toute modification ultérieure des faits et preuves. Elle ne prouve pas qu’ils sont vrais.' })}</p>
        <div className="row-actions">
          <button type="button" className="btn ghost btn-sm" onClick={copy}>{copied ? tr({ en: 'Copied', fr: 'Copié' }) : tr({ en: 'Copy hash', fr: 'Copier l’empreinte' })}</button>
          <button type="button" className="btn ghost btn-sm" onClick={download}>{tr({ en: 'Download ledger bundle', fr: 'Télécharger le registre' })}</button>
        </div>
        </div>
      </details>
    </div>
  );
}
