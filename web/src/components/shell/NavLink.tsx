'use client';
/**
 * One page link of the rail and the phone menu. The label is in the DOM once (.nav-text) and always
 * visible: a caption under the icon in the compact rail, beside it when the rail is expanded.
 */
import Link from 'next/link';
import type { CSSProperties, MouseEvent, ReactNode, Ref } from 'react';
import { useApp } from '../../state/app';
import type { NavEntry } from '../../lib/ui/nav';

export function NavLink({ item, href, active, pill, index, icon, onClick, title, ariaLabel, linkRef }: {
  item: NavEntry;
  /** Defaults to the entry's own address (World adds `?country=`). */
  href?: string;
  active: boolean;
  pill: boolean;
  index: number;
  icon: ReactNode;
  onClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
  title?: string;
  ariaLabel?: string;
  linkRef?: Ref<HTMLAnchorElement>;
}) {
  const { tr } = useApp();
  return (
    <Link href={href ?? item.href} className="nav-link" aria-current={active ? 'page' : undefined} data-tour={item.tour}
      style={{ '--n': index } as CSSProperties} data-pill-target={pill && active ? 'true' : undefined}
      {...(onClick ? { onClick } : {})} {...(title ? { title } : {})} {...(ariaLabel ? { 'aria-label': ariaLabel } : {})}
      {...(linkRef ? { ref: linkRef } : {})}>
      {icon}
      <span className="nav-text">{tr(item.label)}</span>
    </Link>
  );
}
