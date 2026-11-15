'use client';
/**
 * Segmented control as a native-feeling radio group: one tab stop, arrows move and select, and one
 * highlight glides under the chosen segment. The highlight is positioned in group coordinates
 * (useSlidingPill), so page scroll or a sticky parent can never make it jump; it only glides for
 * changes the person makes (restored preferences place it instantly). Reduced motion: no glide.
 */
import { useRef, useState, type KeyboardEvent } from 'react';
import { nextSegmentIndex, segmentAccessibleName } from '../../lib/ui/segmented';
import { pillStyle, useSlidingPill } from './useSlidingPill';

export interface SegmentOption<T extends string> { value: T; label: string; title?: string }

export function SegmentedControl<T extends string>({ label, value, options, onChange, size = 'md' }: {
  label: string;
  value: T;
  options: readonly SegmentOption<T>[];
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const selected = Math.max(0, options.findIndex(o => o.value === value));
  const { ref, box } = useSlidingPill<HTMLDivElement>(`${value}|${options.map(o => o.label).join('|')}`);
  const [armed, setArmed] = useState(false);
  const arm = () => { if (!armed) setArmed(true); };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const next = nextSegmentIndex(selected, event.key, options.length);
    const option = next === null ? undefined : options[next];
    if (next === null || !option) return;
    event.preventDefault();
    onChange(option.value);
    refs.current[next]?.focus();
  };

  return (
    <div ref={ref} role="radiogroup" aria-label={label} className={`segmented segmented-${size}`} onKeyDown={onKeyDown}
      onPointerEnter={arm} onFocus={arm}>
      <span className="segment-pill" aria-hidden="true" data-animate={armed ? 'true' : undefined} style={pillStyle(box)} />
      {options.map((option, i) => {
        const checked = i === selected;
        const name = segmentAccessibleName(option.label, option.title);
        return (
          <button key={option.value} ref={el => { refs.current[i] = el; }} type="button" role="radio"
            aria-checked={checked} tabIndex={checked ? 0 : -1} className="segment"
            data-pill-target={checked ? 'true' : undefined}
            {...(option.title ? { title: option.title } : {})}
            {...(name ? { 'aria-label': name } : {})}
            onClick={() => onChange(option.value)}>
            <span className="segment-label">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
