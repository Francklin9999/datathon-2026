'use client';
/**
 * Route skeleton for pages owned by another track (T13 creates route skeletons; T15 owns these
 * bodies, docs/04-TRACKS.md). Disabled flags show an unavailable state for bookmarked routes (WEB-07).
 */
import type { I18NText } from '../../contracts/types';
import { useApp } from '../../state/app';
import { PageHeader } from './Page';
import { Unavailable } from './States';

export function OwnedElsewhere({ title, flag, owner, spec }: { title: I18NText; flag?: string; owner: string; spec: string }) {
  const { tr, feature, meta } = useApp();
  const disabled = Boolean(flag && meta && !feature(flag));
  return (
    <>
      <PageHeader title={tr(title)} />
      {disabled ? (
        <Unavailable title={tr({ en: 'This page is turned off in this deployment.', fr: 'Cette page est désactivée dans ce déploiement.' })} />
      ) : (
        <Unavailable title={tr({ en: 'This page is not built yet.', fr: 'Cette page n’est pas encore construite.' })}>
          {tr({ en: `Owned by ${owner}; see ${spec}. No data is shown here.`, fr: `Relève de ${owner} ; voir ${spec}. Aucune donnée n’est affichée ici.` })}
        </Unavailable>
      )}
    </>
  );
}
