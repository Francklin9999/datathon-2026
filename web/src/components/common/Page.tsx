'use client';
/** Page header, card and the selected-profile gate shared by every page. */
import { GripVertical } from 'lucide-react';
import type { CSSProperties, ReactNode } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Empty, ErrorState, Loading } from './States';
import { useWidget } from '../ui/WidgetContext';

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
  const widget = useWidget();
  const { tr } = useApp();
  const classes = `card${widget ? ' widget' : ''}${className ? ` ${className}` : ''}`;
  const widgetProps = widget ? {
    'data-widget': widget.id,
    ...(widget.dragging ? { 'data-dragging': 'true' } : {}),
    ...(widget.resizing ? { 'data-resizing': 'true' } : {}),
    style: { '--w': widget.w, '--h': widget.h } as CSSProperties,
  } : {};
  return (
    <section className={classes} {...(id ? { id, 'aria-labelledby': `${id}-title` } : {})} {...widgetProps}>
      {(title || actions || widget?.editing) && (
        <div className="card-head">
          {widget?.editing && (
            <button type="button" className="widget-handle" onPointerDown={widget.onMovePointerDown} onKeyDown={widget.onMoveKeyDown}
              aria-label={`${tr({ en: 'Move', fr: 'Déplacer' })} ${widget.title}. ${tr({ en: 'Drag, or use the arrow keys.', fr: 'Glissez, ou utilisez les flèches.' })}`}
              title={tr({ en: 'Drag to move', fr: 'Glisser pour déplacer' })}>
              <GripVertical aria-hidden="true" size={16} strokeWidth={1.5} />
            </button>
          )}
          {title && <h2 className="card-title" {...(id ? { id: `${id}-title` } : {})}>{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {widget ? <div className="widget-body">{children}</div> : children}
      {widget?.editing && (
        <button type="button" className="widget-resize" onPointerDown={widget.onResizePointerDown} onKeyDown={widget.onResizeKeyDown}
          aria-label={`${tr({ en: 'Resize', fr: 'Redimensionner' })} ${widget.title}, ${widget.w} × ${widget.h}. ${tr({ en: 'Drag, or use the arrow keys.', fr: 'Glissez, ou utilisez les flèches.' })}`}
          title={tr({ en: 'Drag to resize', fr: 'Glisser pour redimensionner' })}>
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M11 4 L4 11 M11 8 L8 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
          </svg>
        </button>
      )}
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
