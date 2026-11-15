/**
 * Theme preference (UI preference only, web/SPEC.md §2). The resolved mode is written to
 * `html[data-theme]`; the boot script runs before first paint so the page never flashes the wrong theme.
 */
export type ThemeMode = 'light' | 'dark';
export type ThemePref = ThemeMode | 'system';

/** Key passed to readPref/writePref, i.e. localStorage `aplomb.pref.theme`. */
export const THEME_PREF_KEY = 'theme';

export function isThemePref(value: unknown): value is ThemePref {
  return value === 'light' || value === 'dark' || value === 'system';
}

/** Explicit light/dark wins; `system`, missing or corrupt values follow the operating system. */
export function resolveTheme(pref: string | null, systemDark: boolean): ThemeMode {
  if (pref === 'light' || pref === 'dark') return pref;
  return systemDark ? 'dark' : 'light';
}

/** Inline, dependency-free twin of resolveTheme for <head>. Storage may throw (private mode). */
export const THEME_BOOT_SCRIPT = `(function(){var p=null;try{p=window.localStorage.getItem('aplomb.pref.theme');}catch(e){}
var d=p==='dark'||(p!=='light'&&window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches);
var r=document.documentElement;r.setAttribute('data-theme',d?'dark':'light');r.style.colorScheme=d?'dark':'light';})();`;

/** Mode to write to <html>, or null while the stored preference is still unread (the boot script owns it). */
export function themeToApply(pref: ThemePref | null, systemDark: boolean): ThemeMode | null {
  return pref === null ? null : resolveTheme(pref, systemDark);
}

/** Browser UI colour (meta theme-color) for a resolved theme; matches --bg in styles/tokens.css. */
export function themeColorFor(theme: ThemeMode): string {
  return theme === 'dark' ? '#050E17' : '#E3E9EE';
}

/**
 * Pages opened in a background tab (or a hidden preview) would freeze entrance animations at their
 * start frame. While hidden, html[data-motion="off"] disables them; when the tab becomes visible the
 * attribute is removed in the same task, so the entrance plays once, as the person first sees it.
 */
export const MOTION_BOOT_SCRIPT = `(function(){var r=document.documentElement;function s(){if(document.visibilityState==='hidden'){r.setAttribute('data-motion','off');}}
s();document.addEventListener('visibilitychange',function(){if(document.visibilityState==='visible'){r.removeAttribute('data-motion');}else{s();}});})();`;
