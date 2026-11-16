'use client';
/**
 * One look for every short caveat or hint inside a card: a quiet note with an icon, in place of the
 * many one-off paragraphs. `ProxyNote` is the single wording of the listing-country / quotation-
 * currency caveat that several pages repeated.
 */
import { Info, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { useApp } from '../../state/app';

export function Note({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'caution' }) {
  const Icon = tone === 'caution' ? TriangleAlert : Info;
  return (
    <p className={`note note-${tone}`}>
      <Icon aria-hidden="true" size={15} strokeWidth={1.75} className="note-icon" />
      <span>{children}</span>
    </p>
  );
}

export function ProxyNote() {
  const { tr } = useApp();
  return (
    <Note>
      {tr({
        en: 'Country and currency use the listing exchange and quotation currency: a proxy, not where revenue is earned.',
        fr: 'Pays et devise viennent de la bourse de cotation et de la devise de cotation : une approximation, pas l’origine des revenus.',
      })}
    </Note>
  );
}
