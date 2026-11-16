/**
 * Pages that moved. The static export has no server redirects, so each old route renders a client
 * Redirect (components/common/Redirect.tsx) for old bookmarks, and in-app links that arrive as data
 * (for instance an API navigation target) are rewritten with `currentHref` before they are shown.
 */

/** Old route → its new address: Markets' asset analytics live in Decide, Risk in Portfolio's Risk tab. */
export const MOVED_ROUTES = {
  '/markets/': '/decision-desk/',
  '/risk-intelligence/': '/portfolio/?tab=risk',
} as const;

/**
 * Where a moved page sends its visitor: the new address, plus the query and hash the old address
 * carried (for instance ?ticker=), merged into the new address's own query rather than appended
 * after it. A parameter the new address sets itself (such as ?tab=risk) keeps the new value.
 */
export function redirectTarget(to: string, search: string, hash: string): string {
  const hashAt = to.indexOf('#');
  const ownHash = hashAt >= 0 ? to.slice(hashAt) : '';
  const beforeHash = hashAt >= 0 ? to.slice(0, hashAt) : to;
  const queryAt = beforeHash.indexOf('?');
  const path = queryAt >= 0 ? beforeHash.slice(0, queryAt) : beforeHash;
  const params = new URLSearchParams(queryAt >= 0 ? beforeHash.slice(queryAt + 1) : '');
  for (const [key, value] of new URLSearchParams(search)) {
    if (!params.has(key)) params.append(key, value);
  }
  const query = params.toString();
  return `${path}${query ? `?${query}` : ''}${hash && hash !== '#' ? hash : ownHash}`;
}

/** An in-app link with a moved page replaced by its new address (its query and hash kept). */
export function currentHref(href: string): string {
  const match = /^([^?#]*)(\?[^#]*)?(#.*)?$/.exec(href);
  if (!match) return href;
  const path = match[1] ?? '';
  const key = path.endsWith('/') ? path : `${path}/`;
  const to = (MOVED_ROUTES as Readonly<Record<string, string>>)[key];
  return to ? redirectTarget(to, match[2] ?? '', match[3] ?? '') : href;
}
