'use client';
/** The "?" button of the top bar: replay the basic tour or open a tutorial per use case. */
import { Check, CircleHelp, PlayCircle } from 'lucide-react';
import { useApp } from '../../state/app';
import { ChromeMenu } from '../../components/shell/TopBar';
import { useTours } from './TourProvider';

export function HelpMenu() {
  const { tr } = useApp();
  const { tours, progress, start } = useTours();
  return (
    <ChromeMenu label={tr({ en: 'Help and tutorials', fr: 'Aide et tutoriels' })} tour="help" wide
      icon={<CircleHelp aria-hidden="true" size={18} strokeWidth={1.75} />}>
      {close => (
        <>
          <p className="help-head">{tr({ en: 'Tutorials', fr: 'Tutoriels' })}</p>
          <ul className="help-list">
            {tours.map((tour, i) => {
              const done = progress.done.includes(tour.id);
              return (
                <li key={tour.id}>
                  <button type="button" className={`help-item${i === 0 ? ' help-item-main' : ''}`} onClick={() => { close(); start(tour.id); }}>
                    <span className="help-icon" aria-hidden="true">{done ? <Check size={16} strokeWidth={2} /> : <PlayCircle size={16} strokeWidth={1.75} />}</span>
                    <span className="help-text">
                      <span className="help-title">{tr(tour.title)}</span>
                      <span className="help-sub">{tr(tour.summary)}{done ? ` ${tr({ en: '(done)', fr: '(fait)' })}` : ''}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="help-foot">{tr({ en: 'Keys: arrows to move, Escape to leave.', fr: 'Touches : flèches pour avancer, Échap pour quitter.' })}</p>
        </>
      )}
    </ChromeMenu>
  );
}
