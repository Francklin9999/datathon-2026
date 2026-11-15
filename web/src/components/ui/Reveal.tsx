/** Entrance wrapper: a short fade + 8 px rise, delayed by `index` × 50 ms (styles/motion.css). */
import type { CSSProperties, ReactNode } from 'react';

export function Reveal({ index = 0, className, children, as: Tag = 'div' }: {
  index?: number; className?: string; children: ReactNode; as?: 'div' | 'section' | 'header';
}) {
  return (
    <Tag className={`reveal${className ? ` ${className}` : ''}`} style={{ '--i': index } as CSSProperties}>
      {children}
    </Tag>
  );
}
