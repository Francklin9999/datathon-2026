'use client';
/** External links open safely; non-http(s) URLs render as plain text (no javascript: links). */
import type { ReactNode } from 'react';

export function safeHttpUrl(href: string | null | undefined): string | null {
  if (!href) return null;
  try {
    const url = new URL(href);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

export function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  const safe = safeHttpUrl(href);
  if (!safe) return <span className="break">{children}</span>;
  return (
    <a href={safe} target="_blank" rel="noopener noreferrer nofollow" className="break">
      {children}<span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}
