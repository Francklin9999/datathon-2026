'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import type { Profile } from '../../contracts/types';
import { getApiClient } from '../../api';
import { asApiError, type ApiRequestError } from '../../api/errors';
import { Card } from '../../components/common/Page';
import { ErrorState } from '../../components/common/States';
import { fmtDateTime } from '../../lib/format';
import { useApp } from '../../state/app';

/** A confirmed playbook is editable, with each explanation retained in its review history. */
export function InvestmentPlaybook({ profile }: { profile: Profile }) {
  const { tr, lang, applyProfile, announce } = useApp();
  const [current, setCurrent] = useState(profile);
  const [editing, setEditing] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [principle, setPrinciple] = useState(profile.investorContext?.playbook?.principle ?? '');
  const [trigger, setTrigger] = useState(profile.investorContext?.playbook?.revisitTrigger ?? '');
  const [explanation, setExplanation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; }, [profile.profileId]);
  useEffect(() => { setCurrent(profile); }, [profile]);
  const playbook = current.investorContext?.playbook;
  const canReview = [principle, trigger, explanation].every(value => value.trim().length >= 10)
    && (principle.trim() !== playbook?.principle || trigger.trim() !== playbook?.revisitTrigger);
  const begin = () => {
    setPrinciple(playbook?.principle ?? ''); setTrigger(playbook?.revisitTrigger ?? '');
    setExplanation(''); setError(null); setReviewing(false); setEditing(true);
  };
  const save = async () => {
    if (!canReview || !reviewing) return;
    const request = ++generation.current;
    setBusy(true); setError(null);
    try {
      const saved = await getApiClient().updatePlaybook(current.profileId, {
        version: current.version, principle: principle.trim(), revisitTrigger: trigger.trim(), explanation: explanation.trim(),
      });
      applyProfile(saved);
      if (request !== generation.current) return;
      setCurrent(saved); setEditing(false); setReviewing(false);
      announce(tr({ en: 'Playbook saved.', fr: 'Guide enregistré.' }));
    } catch (e) { if (request === generation.current) setError(asApiError(e)); }
    finally { if (request === generation.current) setBusy(false); }
  };
  const reload = async () => {
    try { const latest = await getApiClient().profile(current.profileId); setCurrent(latest); applyProfile(latest); setError(null); setReviewing(false); }
    catch (e) { setError(asApiError(e)); }
  };
  return <Card id="playbook" title={tr({ en: 'Investment playbook', fr: 'Guide d’investissement' })}>
    {!playbook ? <p>{tr({ en: 'Complete Investor Lab to create a playbook for this profile.', fr: 'Terminez Investor Lab pour créer un guide pour ce profil.' })}{' '}
      <Link href={`/investor-lab/?mode=full&profileId=${encodeURIComponent(current.profileId)}`}>{tr({ en: 'Test this profile', fr: 'Tester ce profil' })}</Link></p> : <>
      <p><strong>{tr({ en: 'Decision principle', fr: 'Principe de décision' })}</strong><br />{playbook.principle}</p>
      <p><strong>{tr({ en: 'Revisit when', fr: 'Réexaminer lorsque' })}</strong><br />{playbook.revisitTrigger}</p>
      <p className="small muted">{tr({ en: 'Interest', fr: 'Centre d’intérêt' })}: {playbook.interest} · {tr({ en: 'Updated', fr: 'Mis à jour' })} {fmtDateTime(playbook.updatedAt, lang)}</p>
      {!editing && !current.isDefault && <button type="button" className="btn ghost btn-sm" onClick={begin}>{tr({ en: 'Edit playbook', fr: 'Modifier le guide' })}</button>}
      {editing && <form onSubmit={e => { e.preventDefault(); if (reviewing) void save(); else if (canReview) setReviewing(true); }}>
        {error && <ErrorState error={error}>{error.code === 'conflict' && <button type="button" className="btn ghost btn-sm" onClick={() => void reload()}>{tr({ en: 'Load latest version and keep my edits', fr: 'Charger la dernière version et conserver mes modifications' })}</button>}</ErrorState>}
        {!reviewing ? <>
          <div className="form-grid">
            <label className="field"><span>{tr({ en: 'Decision principle', fr: 'Principe de décision' })}</span><textarea value={principle} onChange={e => setPrinciple(e.target.value)} minLength={10} maxLength={2000} required /></label>
            <label className="field"><span>{tr({ en: 'When would you revisit it?', fr: 'Quand le réexamineriez-vous ?' })}</span><textarea value={trigger} onChange={e => setTrigger(e.target.value)} minLength={10} maxLength={2000} required /></label>
            <label className="field"><span>{tr({ en: 'Why are you changing it?', fr: 'Pourquoi le modifiez-vous ?' })}</span><textarea value={explanation} onChange={e => setExplanation(e.target.value)} minLength={10} maxLength={2000} required /></label>
          </div>
          <p className="small muted">{tr({ en: 'Use at least 10 characters in each field and change at least one setting.', fr: 'Utilisez au moins 10 caractères par champ et modifiez au moins un élément.' })}</p>
          <button className="btn btn-sm" type="submit" disabled={!canReview}>{tr({ en: 'Review changes', fr: 'Examiner les modifications' })}</button>{' '}
          <button className="btn ghost btn-sm" type="button" onClick={() => setEditing(false)}>{tr({ en: 'Cancel', fr: 'Annuler' })}</button>
        </> : <>
          <h3>{tr({ en: 'Confirm your changes', fr: 'Confirmez vos modifications' })}</h3>
          {[
            { label: tr({ en: 'Decision principle', fr: 'Principe de décision' }), before: playbook.principle, after: principle },
            { label: tr({ en: 'Revisit when', fr: 'Réexaminer lorsque' }), before: playbook.revisitTrigger, after: trigger },
          ].filter(change => change.before !== change.after.trim()).map(change => <div key={change.label}>
            <strong>{change.label}</strong>
            <dl className="form-grid">
              <div><dt className="small muted">{tr({ en: 'Current', fr: 'Actuel' })}</dt><dd>{change.before}</dd></div>
              <div><dt className="small muted">{tr({ en: 'Proposed', fr: 'Proposé' })}</dt><dd>{change.after}</dd></div>
            </dl>
          </div>)}
          <p><strong>{tr({ en: 'Your explanation', fr: 'Votre explication' })}</strong><br />{explanation}</p>
          <button className="btn btn-sm" type="submit" disabled={busy}>{tr({ en: 'Confirm and save', fr: 'Confirmer et enregistrer' })}</button>{' '}
          <button className="btn ghost btn-sm" type="button" disabled={busy} onClick={() => setReviewing(false)}>{tr({ en: 'Back to edit', fr: 'Retour aux modifications' })}</button>
        </>}
      </form>}
      {(playbook.reviews?.length ?? 0) > 0 && <details className="fold"><summary>{tr({ en: 'Review history', fr: 'Historique des révisions' })} ({playbook.reviews?.length})</summary>
        <p className="small muted">{tr({ en: 'The latest 30 confirmed reviews are retained.', fr: 'Les 30 dernières révisions confirmées sont conservées.' })}</p>
        <ul className="list-plain fold-body">{playbook.reviews?.slice().reverse().map((review, i) => <li key={`${review.labId}-${review.confirmedAt}-${i}`}>
          <strong>{review.labId.startsWith('edit_') ? tr({ en: 'Playbook edit', fr: 'Modification du guide' }) : tr({ en: 'Investor Lab review', fr: 'Révision Investor Lab' })}</strong>{' '}
          <span className="small muted">· {fmtDateTime(review.confirmedAt, lang)}</span>
          <p>{review.explanation}</p>
          {review.changes.length > 0 && <ul className="bullets small">{review.changes.map((change, j) => <li key={`${change.key}-${j}`}><strong>{change.label}:</strong> {change.before ?? '—'} → {change.after}{change.basis.length > 0 && <span className="muted"> ({change.basis.join('; ')})</span>}</li>)}</ul>}
          {!review.labId.startsWith('edit_') && <Link href={`/investor-lab/?lab=${encodeURIComponent(review.labId)}`}>{tr({ en: 'View Lab', fr: 'Voir le Lab' })}</Link>}
        </li>)}</ul>
      </details>}
    </>}
  </Card>;
}
