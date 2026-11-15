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
  return theme === 'dark' ? '#0B0D12' : '#ECEFF5';
}

/**
 * Pages opened in a background tab (or a hidden preview) would freeze entrance animations at their
 * start frame. While hidden, html[data-motion="off"] disables them; when the tab becomes visible the
 * attribute is removed in the same task, so the entrance plays once, as the person first sees it.
 */
export const MOTION_BOOT_SCRIPT = `(function(){var r=document.documentElement;function s(){if(document.visibilityState==='hidden'){r.setAttribute('data-motion','off');}}
s();document.addEventListener('visibilitychange',function(){if(document.visibilityState==='visible'){r.removeAttribute('data-motion');}else{s();}});})();`;

/**
 * Animation preference: `auto` follows the system "reduce motion" setting, `on` keeps the load
 * animations (counting figures, drawing charts, the rail) even when the system asks to reduce them,
 * `off` removes them. `on` is the default (product decision, 2026-11-15); a person who reduces motion
 * picks Auto or Off in Settings. Applied before paint as html[data-anim] (absent for `auto`).
 */
export type AnimPref = 'auto' | 'on' | 'off';
export const ANIM_PREF_KEY = 'anim';
export const DEFAULT_ANIM: AnimPref = 'on';

export function isAnimPref(value: unknown): value is AnimPref {
  return value === 'auto' || value === 'on' || value === 'off';
}

export const ANIM_BOOT_SCRIPT = `(function(){var a=null;try{a=window.localStorage.getItem('aplomb.pref.anim');}catch(e){}if(a!=='auto'&&a!=='off'){a='on';}if(a!=='auto'){document.documentElement.setAttribute('data-anim',a);}})();`;

/** Whether load animations should play now (preference, system setting, hidden page). */
export function animationsAllowed(pref: string | undefined, systemReduce: boolean, pageHidden: boolean): boolean {
  if (pageHidden || pref === 'off') return false;
  if (pref === 'on') return true;
  return !systemReduce;
}

/** Navigation rail preference: collapsed (floating icon rail, the default) or expanded (icons with labels). */
export type SidebarState = 'expanded' | 'collapsed';
export const SIDEBAR_PREF_KEY = 'sidebar';

export function isSidebarState(value: unknown): value is SidebarState {
  return value === 'expanded' || value === 'collapsed';
}

/** Applies the stored rail state to <html> before first paint, so an expanded rail never flashes closed. */
export const SIDEBAR_BOOT_SCRIPT = `(function(){try{var s=window.localStorage.getItem('aplomb.pref.sidebar');if(s==='expanded'){document.documentElement.setAttribute('data-sidebar','expanded');}}catch(e){}})();`;
