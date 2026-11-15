'use client';
/** Page header, card and the selected-profile gate shared by every page. */
import type { ReactNode } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Empty, ErrorState, Loading } from './States';

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <header className="page-header">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1 className="serif page-title">{title}</h1>
      {children}
    </header>
  );
}

export function Card({ title, children, actions, id, className }: {
  title?: string; children: ReactNode; actions?: ReactNode; id?: string; className?: string;
}) {
  return (
    <section className={`card${className ? ` ${className}` : ''}`} {...(id ? { id, 'aria-labelledby': `${id}-title` } : {})}>
      {(title || actions) && (
        <div className="card-head">
          {title && <h2 className="card-title" {...(id ? { id: `${id}-title` } : {})}>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

/** Renders children only once profiles loaded and one is selected. */
export function ProfileGate({ children }: { children: (profile: Profile) => ReactNode }) {
  const { profile, profilesLoaded, profilesError, reloadProfiles, tr } = useApp();
  if (profilesError) {
    return <ErrorState error={profilesError} onRetry={reloadProfiles}
      title={tr({ en: 'Profiles could not be loaded. No figures are shown.', fr: 'Les profils n’ont pas pu être chargés. Aucun chiffre n’est affiché.' })} />;
  }
  if (!profilesLoaded) return <Loading label={tr({ en: 'Loading profiles…', fr: 'Chargement des profils…' })} />;
  if (!profile) return <Empty>{tr({ en: 'No profile is available for this session.', fr: 'Aucun profil n’est disponible pour cette session.' })}</Empty>;
  return <>{children(profile)}</>;
}
