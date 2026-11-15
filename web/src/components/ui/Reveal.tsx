/** Entrance wrapper: its panels fade and rise 8 px, delayed by `index` × 50 ms (styles/motion.css `.enter`). */
import type { CSSProperties, ReactNode } from 'react';

export function Reveal({ index = 0, className, children, as: Tag = 'div' }: {
  index?: number; className?: string; children: ReactNode; as?: 'div' | 'section' | 'header';
}) {
  return (
    <Tag className={`enter${className ? ` ${className}` : ''}`} style={{ '--i': index } as CSSProperties}>
      {children}
    </Tag>
  );
}
