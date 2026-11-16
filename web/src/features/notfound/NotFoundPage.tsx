'use client';
/**
 * 404: a page in the app shell (title, one sentence, the way back) with the main pages in the active
 * language. The list is the rail's own (same entries, same feature-flag filter).
 */
import Link from 'next/link';
import { useEffect } from 'react';
import { useApp } from '../../state/app';
import { Card, PageHeader } from '../../components/common/Page';
import { navIcon, useNavEntries } from '../../components/shell/NavRail';

export function NotFoundPage() {
  const { tr } = useApp();
  const entries = useNavEntries(true);
  const title = tr({ en: 'Page not found', fr: 'Page introuvable' });
  const listLabel = tr({ en: 'Main pages', fr: 'Pages principales' });
  // The static export serves this page for every unknown address; the title follows the language.
  useEffect(() => { document.title = `${title} · Aplomb`; }, [title]);
  return (
    <>
      <PageHeader title={title} actions={<Link href="/" className="btn">{tr({ en: 'Back to Home', fr: 'Retour à l’accueil' })}</Link>}>
        <p className="page-sub">{tr({ en: 'There is no page at this address. Choose a page below.', fr: 'Aucune page ne correspond à cette adresse. Choisissez une page ci-dessous.' })}</p>
      </PageHeader>
      <Card title={listLabel}>
        <nav aria-label={listLabel}>
          <ul className="notfound-links">
            {entries.map(entry => {
              const Icon = navIcon(entry.href);
              return (
                <li key={entry.href}>
                  <Link href={entry.href} className="notfound-link">
                    <Icon aria-hidden="true" size={18} strokeWidth={1.75} />
                    <span>{tr(entry.label)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </Card>
    </>
  );
}
