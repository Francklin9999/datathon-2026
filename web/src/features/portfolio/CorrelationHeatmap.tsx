'use client';
/**
 * Correlation matrix as a heatmap. Each cell is tinted on a diverging scale (cobalt −1, neutral 0,
 * orange +1) and keeps its value written in it, so the table stays the accessible reading and colour
 * is never the only signal. Hovering a cell highlights its row and column and says in words how the
 * two holdings move. The diagonal (a holding with itself) is muted.
 */
import { useState, type CSSProperties } from 'react';
import type { I18NText } from '../../contracts/types';
import { useApp } from '../../state/app';
import { useTheme } from '../../components/ui/ThemeProvider';
import { fmtNumber } from '../../lib/format';
import { corrColor, corrGradient, corrStrength, corrText, type CorrStrength } from '../../lib/ui/corr';

const STRENGTH: Record<CorrStrength, I18NText> = {
  opposite_strong: { en: 'almost always move in opposite directions', fr: 'évoluent presque toujours en sens inverse' },
  opposite: { en: 'often move in opposite directions', fr: 'évoluent souvent en sens inverse' },
  opposite_weak: { en: 'move slightly in opposite directions', fr: 'évoluent un peu en sens inverse' },
  independent: { en: 'move almost independently', fr: 'évoluent presque indépendamment' },
  together_weak: { en: 'move slightly together', fr: 'évoluent un peu ensemble' },
  together: { en: 'often move together', fr: 'évoluent souvent ensemble' },
  together_strong: { en: 'almost always move together', fr: 'évoluent presque toujours ensemble' },
};

export function CorrelationHeatmap({ tickers, matrix }: { tickers: readonly string[]; matrix: readonly (readonly number[])[] }) {
  const { tr, lang } = useApp();
  const { theme } = useTheme();
  const [hover, setHover] = useState<{ i: number; j: number } | null>(null);
  const hovered = hover ? matrix[hover.i]?.[hover.j] : undefined;
  const describe = (i: number, j: number, v: number) =>
    `${tickers[i]} ${tr({ en: 'and', fr: 'et' })} ${tickers[j]}${tr({ en: ':', fr: ' :' })} ${fmtNumber(v, lang, 2)}, ${tr(STRENGTH[corrStrength(v)])}`;

  return (
    <div className="corr">
      <div className="table-scroll corr-scroll" role="region" aria-label={tr({ en: 'Correlation matrix', fr: 'Matrice de corrélation' })} tabIndex={0}
        onPointerLeave={() => setHover(null)}>
        <table className="corr-table">
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">{tr({ en: 'Asset', fr: 'Actif' })}</span></th>
              {tickers.map((t, j) => <th key={t} scope="col" className="corr-col" data-hl={hover?.j === j ? 'true' : undefined}>{t}</th>)}
            </tr>
          </thead>
          <tbody>
            {tickers.map((t, i) => (
              <tr key={t}>
                <th scope="row" className="corr-row" data-hl={hover?.i === i ? 'true' : undefined}>{t}</th>
                {(matrix[i] ?? []).map((v, j) => {
                  const finite = Number.isFinite(v);
                  const self = i === j;
                  const bg = finite && !self ? corrColor(v, theme) : undefined;
                  const cross = hover !== null && (hover.i === i || hover.j === j);
                  return (
                    <td key={j} className="corr-cell"
                      data-self={self ? 'true' : undefined}
                      data-cross={cross && !(hover?.i === i && hover?.j === j) ? 'true' : undefined}
                      data-hover={hover?.i === i && hover?.j === j ? 'true' : undefined}
                      style={{ '--k': i + j, ...(bg ? { background: bg, color: corrText(bg, theme) } : {}) } as CSSProperties}
                      {...(finite && !self ? { title: describe(i, j, v) } : {})}
                      onPointerEnter={() => setHover({ i, j })}>
                      {finite ? fmtNumber(v, lang, 2) : '—'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="corr-foot">
        <p className="corr-read" aria-live="polite">
          {hover && hovered !== undefined && Number.isFinite(hovered) && hover.i !== hover.j
            ? describe(hover.i, hover.j, hovered)
            : tr({ en: 'Hover a cell to read it in words.', fr: 'Survolez une case pour la lire en mots.' })}
        </p>
        <div className="corr-legend" aria-hidden="true">
          <span className="corr-bar" style={{ background: corrGradient(theme) }} />
          <span className="corr-ticks">
            <span>−1 {tr({ en: 'opposite', fr: 'sens inverse' })}</span>
            <span>0 {tr({ en: 'independent', fr: 'indépendants' })}</span>
            <span>+1 {tr({ en: 'together', fr: 'ensemble' })}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
