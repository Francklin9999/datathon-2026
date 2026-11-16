'use client';
/** Page header, card and the selected-profile gate shared by every page. */
import { ChevronRight, GripHorizontal } from 'lucide-react';
import { createContext, useContext, type CSSProperties, type ReactNode } from 'react';
import type { Profile } from '../../contracts/types';
import { useApp } from '../../state/app';
import { Empty, ErrorState, Loading } from './States';
import { Sheet, useSheet } from './Sheet';
import { useWidget } from '../ui/WidgetContext';
import { InfoTip } from '../ui/InfoTip';

const CardDetailsContext = createContext<((from: HTMLElement) => void) | null>(null);

/**
 * Inside a Card that has `details`: opens its details sheet from `from` (a visible "N more" button in
 * the body, beside "Details" in the header). Null elsewhere.
 */
export function useCardDetails(): ((from: HTMLElement) => void) | null {
  return useContext(CardDetailsContext);
}

/**
 * Page title with one useful sentence (children) on the left and the page's controls on the right.
 * There is no eyebrow above the title: the rail already names the page.
 */
export function PageHeader({ title, children, actions, tour }: {
  title: string; children?: ReactNode; actions?: ReactNode; tour?: string;
}) {
  return (
    <header className="page-header" {...(tour ? { 'data-tour': tour } : {})}>
      <div className="page-heading">
        <h1 className="page-title">{title}</h1>
        {children}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

/** What a card has no room for: shown in a details sheet opened from a button in its header. */
export interface CardDetails {
  /** Sheet title; defaults to the card title. */
  title?: string;
  /** Rendered only while the sheet is open. */
  render: () => ReactNode;
}

/**
 * Card. `section` names it in the page's section dock (needs an `id`); `info` folds a note behind an
 * "i" beside the title; `tour` anchors a tutorial step; `details` adds a small "Details" pill that opens
 * the rest in a sheet. Inside a dashboard grid the header is the grip (drag to move), the grabber at the top
 * edge is the keyboard handle and the corner handle resizes.
 */
export function Card({ title, children, actions, id, className, section, info, tour, details }: {
  title?: string; children: ReactNode; actions?: ReactNode; id?: string; className?: string;
  section?: string; info?: string; tour?: string; details?: CardDetails;
}) {
  const widget = useWidget();
  const { tr } = useApp();
  const sheet = useSheet();
  const movable = Boolean(widget?.movable);
  const classes = `card${widget ? ' widget' : ''}${widget?.bare ? ' card-bare' : ''}${className ? ` ${className}` : ''}`;
  // Inside a grid the widget gives the dock its id and label.
  const sectionId = id ?? (widget?.section ? `w-${widget.id}` : undefined);
  const sectionLabel = section ?? widget?.section;
  const widgetProps = widget ? {
    'data-widget': widget.id,
    ...(widget.dragging ? { 'data-dragging': 'true' } : {}),
    ...(widget.resizing ? { 'data-resizing': 'true' } : {}),
    style: { '--w': widget.w, '--h': widget.h } as CSSProperties,
  } : {};
  return (
    <section className={classes} {...(sectionId ? { id: sectionId, 'aria-labelledby': `${sectionId}-title` } : {})} {...widgetProps}
      {...(sectionLabel && sectionId ? { 'data-section': sectionLabel } : {})} {...(tour ? { 'data-tour': tour } : {})}>
      {widget && movable && (
        <button type="button" className="widget-grabber" onPointerDown={widget.onMovePointerDown} onKeyDown={widget.onMoveKeyDown}
          aria-label={`${tr({ en: 'Move', fr: 'Déplacer' })} ${widget.title}. ${tr({ en: 'Drag, or use the arrow keys.', fr: 'Glissez, ou utilisez les flèches.' })}`}
          title={tr({ en: 'Move', fr: 'Déplacer' })} data-tour="widget-move">
          <GripHorizontal aria-hidden="true" size={16} strokeWidth={2} />
        </button>
      )}
      {(title || actions || details) && (
        <div className="card-head" {...(widget && movable ? { onPointerDown: widget.onMovePointerDown } : {})}>
          {title && (
            <span className="card-title-row">
              <h2 className="card-title" {...(sectionId ? { id: `${sectionId}-title` } : {})}>{title}</h2>
              {info && <InfoTip text={info} align="start" />}
            </span>
          )}
          {(actions || details) && (
            <div className="card-actions">
              {actions}
              {details && (
                <button type="button" className="details-btn" aria-haspopup="dialog" data-tour="card-details"
                  {...(title ? { 'aria-label': `${tr({ en: 'Details', fr: 'Détails' })}, ${title}` } : {})}
                  onClick={event => sheet.show(event.currentTarget)}>
                  <span>{tr({ en: 'Details', fr: 'Détails' })}</span>
                  <ChevronRight aria-hidden="true" size={14} strokeWidth={2} />
                </button>
              )}
            </div>
          )}
        </div>
      )}
      <CardDetailsContext.Provider value={details ? sheet.show : null}>
        {widget ? <div className="widget-body">{children}</div> : children}
      </CardDetailsContext.Provider>
      {widget && movable && (
        <button type="button" className="widget-resize" onPointerDown={widget.onResizePointerDown} onKeyDown={widget.onResizeKeyDown}
          aria-label={`${tr({ en: 'Resize', fr: 'Redimensionner' })} ${widget.title}, ${widget.w} × ${widget.h}. ${tr({ en: 'Drag, or use the arrow keys.', fr: 'Glissez, ou utilisez les flèches.' })}`}
          title={tr({ en: 'Drag to resize', fr: 'Glisser pour redimensionner' })}>
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M11 4 L4 11 M11 8 L8 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
          </svg>
        </button>
      )}
      {details && (
        <Sheet open={sheet.open} origin={sheet.origin} onClose={sheet.hide} title={details.title ?? title ?? tr({ en: 'Details', fr: 'Détails' })}>
          {sheet.open && details.render()}
        </Sheet>
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
