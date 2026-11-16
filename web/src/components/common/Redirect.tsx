'use client';
/**
 * A page that moved: the static export has no server redirects, so the old address replaces itself
 * with the new one on the client and shows a plain link meanwhile (and when scripts are slow).
 */
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import type { I18NText } from '../../contracts/types';
import { useApp } from '../../state/app';

export function Redirect({ to, label }: { to: string; label: I18NText }) {
  const router = useRouter();
  const { tr } = useApp();
  useEffect(() => {
    // Keep a query or hash the old address carried (for instance ?ticker=).
    router.replace(`${to}${window.location.search}${window.location.hash}`);
  }, [router, to]);
  return (
    <p className="redirect-note" role="status">
      {tr({ en: 'This page moved to', fr: 'Cette page a été déplacée vers' })} <Link href={to}>{tr(label)}</Link>.
    </p>
  );
}
