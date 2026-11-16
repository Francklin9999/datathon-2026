'use client';
/**
 * Plan health's "Closest to their limit" lines: whole sentences that wrap, as many as fit the widget's
 * height. A sentence that does not fit is left out entirely (never cut mid-figure) and a button opens
 * the card's Details sheet, which lists every one with its figures.
 */
import { useLayoutEffect, useRef, useState } from 'react';
import type { RuleCheck } from '../../contracts/types';
import { useApp } from '../../state/app';
import { useCardDetails } from '../../components/common/Page';
import { useElementSize } from '../../components/ui/useElementSize';
import { fitRowsWithMore } from '../../lib/ui/layout';

/** The "Closest to their limit" title with its margin (dashboard.css .health-rest-title). */
const TITLE_PX = 28;
/** The "more in Details" row (dashboard.css .more-row, .more-btn). */
const MORE_PX = 36;

export function ClosestToLimit({ checks }: { checks: readonly RuleCheck[] }) {
  const { tr } = useApp();
  const openDetails = useCardDetails();
  const { ref, size } = useElementSize<HTMLDivElement>();
  const rows = useRef<(HTMLLIElement | null)[]>([]);
  const [heights, setHeights] = useState<number[] | null>(null);
  const texts = checks.map(check => tr(check.detail));
  const textKey = texts.join('\u0000');

  // Rows not shown stay laid out at the list's width (dashboard.css li[data-unfit]), so each row's
  // wrapped height is known whether it is shown or not; a resize or a late font re-measures.
  useLayoutEffect(() => {
    const measure = () => {
      const next = texts.map((_, i) => rows.current[i]?.offsetHeight ?? 0);
      setHeights(prev => (prev && prev.length === next.length && prev.every((h, i) => h === next[i]) ? prev : next));
    };
    measure();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(measure);
    for (const el of rows.current.slice(0, texts.length)) if (el) observer.observe(el);
    return () => observer.disconnect();
    // texts is derived from textKey; re-measure only when the sentences change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textKey]);

  const fit = size && heights && heights.length === checks.length
    ? fitRowsWithMore(size.h - TITLE_PX, heights, MORE_PX)
    : { shown: 0, more: false };
  const more = fit.more && openDetails !== null;
  const hidden = checks.length - fit.shown;
  return (
    <div ref={ref} className="health-rest">
      {checks.length > 0 && (
        <>
          {(fit.shown > 0 || more) && <h3 className="eyebrow health-rest-title">{tr({ en: 'Closest to their limit', fr: 'Les plus proches de leur limite' })}</h3>}
          <ul className="limit-lines">
            {checks.map((check, i) => (
              <li key={check.ruleId} ref={el => { rows.current[i] = el; }} title={texts[i]}
                {...(i >= fit.shown ? { 'data-unfit': 'true' } : {})}>
                {texts[i]}
              </li>
            ))}
          </ul>
          {more && (
            <div className="more-row">
              <button type="button" className="more-btn" aria-haspopup="dialog" onClick={event => openDetails?.(event.currentTarget)}>
                {fit.shown > 0
                  ? tr({ en: `${hidden} more in Details`, fr: `${hidden} de plus dans Détails` })
                  : tr({ en: 'See them in Details', fr: 'Les voir dans Détails' })}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
