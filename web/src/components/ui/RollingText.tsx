/**
 * Odometer-style figure: digits rise into place, staggered, when the text first renders or
 * changes (re-keyed). Screen readers get the plain text once; the animated glyphs are hidden.
 * The final state is the base style; only @keyframes hold the start state (styles/motion.css).
 */
import type { CSSProperties } from 'react';
import { rollSegments } from '../../lib/ui/roll';

export function RollingText({ text }: { text: string }) {
  let digitIndex = 0;
  return (
    <span className="roll">
      <span className="sr-only">{text}</span>
      <span className="roll-glyphs" aria-hidden="true" key={text}>
        {rollSegments(text).map((seg, i) => {
          if (!seg.digit) return <span key={i} className="roll-static">{seg.ch}</span>;
          const style = { '--d': digitIndex++ } as CSSProperties;
          return <span key={i} className="roll-cell"><span className="roll-digit" style={style}>{seg.ch}</span></span>;
        })}
      </span>
    </span>
  );
}
