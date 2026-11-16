'use client';
/** The "?" button of the top bar: replay the basic tour or open the short tour of any page (every tour is listed). */
import { useId } from 'react';
import { Check, CircleHelp, PlayCircle } from 'lucide-react';
import { useApp } from '../../state/app';
import { ChromeMenu } from '../../components/shell/TopBar';
import type { Tour } from '../../lib/tour/engine';
import { useTours } from './TourProvider';

export function HelpMenu() {
  const { tr } = useApp();
  const { tours, progress, start } = useTours();
  const pagesHead = useId();
  const [basics, ...pages] = tours;
  return (
    <ChromeMenu label={tr({ en: 'Help and tutorials', fr: 'Aide et tutoriels' })} tour="help" wide
      icon={<CircleHelp aria-hidden="true" size={18} strokeWidth={1.75} />}>
      {close => {
        const item = (tour: Tour, main: boolean) => {
          const done = progress.done.includes(tour.id);
          return (
            <li key={tour.id}>
              <button type="button" className={`help-item${main ? ' help-item-main' : ''}`} onClick={() => { close(); start(tour.id); }}>
                <span className="help-icon" aria-hidden="true">{done ? <Check size={16} strokeWidth={2} /> : <PlayCircle size={16} strokeWidth={1.75} />}</span>
                <span className="help-text">
                  <span className="help-title">{tr(tour.title)}</span>
                  <span className="help-sub">{tr(tour.summary)}{done ? ` ${tr({ en: '(done)', fr: '(fait)' })}` : ''}</span>
                </span>
              </button>
            </li>
          );
        };
        return (
          <>
            <p className="help-head">{tr({ en: 'Tutorials', fr: 'Tutoriels' })}</p>
            {basics && <ul className="help-list">{item(basics, true)}</ul>}
            {pages.length > 0 && <>
              <p className="help-head" id={pagesHead}>{tr({ en: 'One tour per page', fr: 'Une visite par page' })}</p>
              <ul className="help-list" aria-labelledby={pagesHead}>{pages.map(tour => item(tour, false))}</ul>
            </>}
            <p className="help-foot">{tr({ en: 'Keys: arrows to move, Escape to leave.', fr: 'Touches : flèches pour avancer, Échap pour quitter.' })}</p>
          </>
        );
      }}
    </ChromeMenu>
  );
}
