'use client';
/**
 * Guided tours: which tour runs and at which step, the stored progress (welcome answered, tours
 * finished) and the first-visit welcome. Tours render in a portal on <body>, above every layer, and
 * focus returns to where it was when a tour ends.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useApp } from '../../state/app';
import { readPref, writePref } from '../../lib/session';
import { EMPTY_PROGRESS, markDone, parseProgress, type Tour, type TourProgress } from '../../lib/tour/engine';
import { ALL_TOURS, BASIC_TOUR } from './tours';
import { TourOverlay } from './TourOverlay';

const PROGRESS_PREF = 'tour.v1';

interface TourContextValue {
  tours: readonly Tour[];
  progress: TourProgress;
  activeId: string | null;
  start: (tourId: string) => void;
}

const TourContext = createContext<TourContextValue | null>(null);

export function useTours(): TourContextValue {
  const value = useContext(TourContext);
  if (!value) throw new Error('useTours outside TourProvider');
  return value;
}

function Welcome({ onStart, onLater }: { onStart: () => void; onLater: () => void }) {
  const { tr } = useApp();
  const primary = useRef<HTMLButtonElement | null>(null);
  useEffect(() => { primary.current?.focus(); }, []);
  return (
    <div className="tour-welcome-layer" onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); onLater(); } }}>
      <div className="tour-welcome glass-pop" role="dialog" aria-modal="true" aria-labelledby="tour-welcome-title" aria-describedby="tour-welcome-body">
        <span className="tour-welcome-orb" aria-hidden="true" />
        <h2 id="tour-welcome-title" className="tour-title">{tr({ en: 'New here? Take the one-minute tour', fr: 'Première visite ? Suivez la visite d’une minute' })}</h2>
        <p id="tour-welcome-body" className="tour-body">
          {tr({ en: 'See how to pick an investor, read the dashboard and test a move. You can replay it any time from the ? button.', fr: 'Voyez comment choisir un investisseur, lire le tableau de bord et tester un mouvement. Vous pourrez la relancer avec le bouton ?.' })}
        </p>
        <div className="tour-actions">
          <button type="button" className="btn ghost btn-sm" onClick={onLater}>{tr({ en: 'Later', fr: 'Plus tard' })}</button>
          <button ref={primary} type="button" className="btn btn-sm" onClick={onStart}>{tr({ en: 'Start the tour', fr: 'Commencer la visite' })}</button>
        </div>
      </div>
    </div>
  );
}

export function TourProvider({ children }: { children: ReactNode }) {
  const { phase, profile, announce, tr } = useApp();
  const [progress, setProgress] = useState<TourProgress>(EMPTY_PROGRESS);
  const [loaded, setLoaded] = useState(false);
  const [active, setActive] = useState<{ tour: Tour; index: number } | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  useEffect(() => { setProgress(parseProgress(readPref(PROGRESS_PREF))); setLoaded(true); }, []);
  const save = useCallback((next: TourProgress) => { setProgress(next); writePref(PROGRESS_PREF, JSON.stringify(next)); }, []);

  const start = useCallback((tourId: string) => {
    const tour = ALL_TOURS.find(t => t.id === tourId);
    if (!tour) return;
    returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setActive({ tour, index: 0 });
  }, []);

  const end = useCallback((finished: boolean) => {
    setActive(current => {
      if (current && finished) {
        save(markDone(progress, current.tour.id));
        announce(tr({ en: 'Tutorial finished', fr: 'Tutoriel terminé' }));
      } else if (!progress.welcomed) {
        save({ ...progress, welcomed: true });
      }
      return null;
    });
    // Return focus after the overlay is gone; the page itself when the opener has gone (the welcome).
    setTimeout(() => {
      const el = returnFocus.current;
      (el && document.contains(el) ? el : document.getElementById('main'))?.focus({ preventScroll: true });
    }, 0);
  }, [progress, save, announce, tr]);

  const showWelcome = loaded && !progress.welcomed && !active && phase === 'ready' && profile !== null;
  const value = useMemo<TourContextValue>(() => ({ tours: ALL_TOURS, progress, activeId: active?.tour.id ?? null, start }), [progress, active, start]);

  return (
    <TourContext.Provider value={value}>
      {children}
      {typeof document !== 'undefined' && active && createPortal(
        <TourOverlay key={active.tour.id} tour={active.tour} index={active.index}
          onIndex={index => setActive(current => (current ? { ...current, index } : current))}
          onClose={() => end(false)} onFinish={() => end(true)} />,
        document.body,
      )}
      {typeof document !== 'undefined' && showWelcome && createPortal(
        <Welcome onStart={() => { save({ ...progress, welcomed: true }); start(BASIC_TOUR.id); }}
          onLater={() => save({ ...progress, welcomed: true })} />,
        document.body,
      )}
    </TourContext.Provider>
  );
}
