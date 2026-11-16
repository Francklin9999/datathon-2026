/** Pure Decision Desk logic: request building, staleness and race gating (web/page-specs/decision-desk.md). */
import type {
  CheckRequest, DecisionRequest, Funding, FundingMode, I18NText, Lang, ProposedMove, RuleOverride, WindowSpec,
} from '../contracts/types';
import type { ApiRequestError } from '../api/errors';
import { bilingualReason } from './failure';
import { isCashTicker, isSupportedTicker, normalizeTicker, unsupportedTickerMessage } from './universe';

export interface MoveForm {
  ticker: string;
  sizePct: number;
  fundingMode: FundingMode;
  fromTickers: string[];
}

function fundingOf(form: MoveForm): Funding {
  return form.fundingMode === 'from_holdings'
    ? { mode: 'from_holdings', fromTickers: [...form.fromTickers] }
    : { mode: form.fundingMode };
}

export function roundSize(size: number): number {
  return Math.round(size * 10) / 10;
}

/** Size 0 (or no ticker) previews the baseline with move=null, never an invalid zero-size move. */
export function moveOf(form: MoveForm): ProposedMove | null {
  const ticker = form.ticker.trim().toUpperCase();
  if (!ticker || !(form.sizePct > 0)) return null;
  return { ticker, sizePct: roundSize(form.sizePct), funding: fundingOf(form) };
}

export function buildCheckRequest(
  profileId: string, form: MoveForm, window: WindowSpec, ruleOverrides: RuleOverride[] = [],
): CheckRequest {
  const move = moveOf(form);
  const request: CheckRequest = { profileId, move, window };
  if (ruleOverrides.length) request.ruleOverrides = ruleOverrides;
  if (move?.funding.mode === 'auto') request.compareFunding = true;
  return request;
}

export interface MoveFormIssue { field: keyof MoveForm; message: { en: string; fr: string } }

/** The supported universe, given only once its read has completed (useAssetUniverse().ready). */
export interface MoveUniverse {
  assets: readonly { ticker: string }[];
  total: number;
  dataVersion: string;
  /** Feature `on_demand_tickers`: an unlisted ticker may still be fetched, so it is not blocked here. */
  onDemand: boolean;
}

/** Optional context: the profile's holdings (funding feasibility) and the supported universe. */
export interface MoveFormContext {
  positions?: readonly { ticker: string; weightPct: number }[] | undefined;
  universe?: MoveUniverse | null | undefined;
}

/**
 * The ticker typed in the form when it is neither listed in the universe, nor a cash pseudo-asset,
 * nor already held; null otherwise, and always null without a loaded universe.
 */
export function unlistedMoveTicker(form: Pick<MoveForm, 'ticker'>, ctx: MoveFormContext): string | null {
  const universe = ctx.universe;
  const ticker = normalizeTicker(form.ticker);
  if (!universe || universe.assets.length === 0 || !ticker || isCashTicker(ticker)) return null;
  if ((ctx.positions ?? []).some(p => normalizeTicker(p.ticker) === ticker)) return null;
  return isSupportedTicker(universe.assets, ticker) ? null : ticker;
}

/** Tolerance in fractions. Looser than the server's 1e-12 so the client never blocks a size it accepts. */
const FUNDING_EPS = 1e-9;

const points = (value: number, lang: 'en' | 'fr') => (lang === 'fr' ? value.toFixed(1).replace('.', ',') : value.toFixed(1));

/**
 * Funding feasibility, mirroring backend quant/funding.py `apply_move`: from_cash needs the cash
 * pseudo-assets (other than the target) to cover the size; from_holdings needs the named holdings
 * to cover it. Other modes are resolved or checked by the server only.
 */
function fundingIssue(form: MoveForm, positions: readonly { ticker: string; weightPct: number }[]): MoveFormIssue | null {
  if (!(form.sizePct > 0)) return null;
  const size = roundSize(form.sizePct) / 100;
  const target = normalizeTicker(form.ticker);
  if (form.fundingMode === 'from_cash') {
    const cash = positions
      .filter(p => isCashTicker(p.ticker) && normalizeTicker(p.ticker) !== target && p.weightPct > 0)
      .reduce((sum, p) => sum + p.weightPct / 100, 0);
    if (cash + FUNDING_EPS >= size) return null;
    if (cash <= 0) {
      return {
        field: 'fundingMode',
        message: {
          en: 'This portfolio holds no cash, so the move cannot be funded from cash. Choose another funding mode.',
          fr: 'Ce portefeuille ne contient aucune liquidité : le mouvement ne peut donc pas être financé par l’encaisse. Choisissez un autre mode de financement.',
        },
      };
    }
    return {
      field: 'fundingMode',
      message: {
        en: `Cash holdings total ${points(cash * 100, 'en')} points, less than the ${points(size * 100, 'en')} points this move needs. Choose another funding mode or a smaller size.`,
        fr: `Les liquidités totalisent ${points(cash * 100, 'fr')} points, moins que les ${points(size * 100, 'fr')} points requis par ce mouvement. Choisissez un autre mode de financement ou une taille plus petite.`,
      },
    };
  }
  if (form.fundingMode === 'from_holdings' && form.fromTickers.length > 0) {
    const named = new Set(form.fromTickers.map(normalizeTicker));
    const available = positions
      .filter(p => named.has(normalizeTicker(p.ticker)) && p.weightPct > 0)
      .reduce((sum, p) => sum + p.weightPct / 100, 0);
    if (available + FUNDING_EPS >= size) return null;
    return {
      field: 'fromTickers',
      message: {
        en: `The selected holdings total ${points(available * 100, 'en')} points, less than the ${points(size * 100, 'en')} points this move needs. Select more holdings or reduce the size.`,
        fr: `Les positions choisies totalisent ${points(available * 100, 'fr')} points, moins que les ${points(size * 100, 'fr')} points requis par ce mouvement. Choisissez d’autres positions ou réduisez la taille.`,
      },
    };
  }
  return null;
}

/**
 * Client-side checks mirroring api.md 4.2 validation; the server remains authoritative. With `ctx`,
 * also funding feasibility (positions) and, when on-demand fetching is off, an unsupported ticker.
 */
export function validateMoveForm(form: MoveForm, currentWeightPct: number | null, ctx: MoveFormContext = {}): MoveFormIssue[] {
  const issues: MoveFormIssue[] = [];
  if (!form.ticker.trim()) {
    issues.push({ field: 'ticker', message: { en: 'Choose an asset.', fr: 'Choisissez un actif.' } });
  } else if (ctx.universe && !ctx.universe.onDemand) {
    const unlisted = unlistedMoveTicker(form, ctx);
    if (unlisted) {
      issues.push({ field: 'ticker', message: unsupportedTickerMessage(unlisted, ctx.universe.total, ctx.universe.dataVersion) });
    }
  }
  if (!(form.sizePct > 0)) {
    issues.push({ field: 'sizePct', message: { en: 'Size must be greater than 0 points.', fr: 'La taille doit être supérieure à 0 point.' } });
  } else if (form.fundingMode !== 'new_money' && currentWeightPct !== null && form.sizePct > 100 - currentWeightPct) {
    const max = (100 - currentWeightPct).toFixed(1);
    issues.push({
      field: 'sizePct',
      message: {
        en: `Size cannot exceed ${max} points unless funded with new money.`,
        fr: `La taille ne peut dépasser ${max.replace('.', ',')} points sauf avec un nouvel apport.`,
      },
    });
  }
  if (form.fundingMode === 'from_holdings' && form.fromTickers.length === 0) {
    issues.push({ field: 'fromTickers', message: { en: 'Name at least one holding to fund the move.', fr: 'Nommez au moins une position pour financer le mouvement.' } });
  }
  // Only once the size itself is valid, so one problem is reported at a time.
  if (ctx.positions && !issues.some(i => i.field === 'sizePct')) {
    const funding = fundingIssue(form, ctx.positions);
    if (funding) issues.push(funding);
  }
  return issues;
}

/** Fields a server refusal can point at (details.fields). */
export type RefusedField = 'ticker' | 'sizePct' | 'fundingMode' | 'fromTickers';

export interface PreviewRefusal {
  field: RefusedField | null;
  /** The server's bilingual details.reason, when it sent one. */
  reason: I18NText | null;
}

function fieldOfPath(path: string): RefusedField | null {
  if (/fromTickers/i.test(path)) return 'fromTickers';
  if (/funding/i.test(path)) return 'fundingMode';
  if (/sizePct/i.test(path)) return 'sizePct';
  if (/ticker/i.test(path)) return 'ticker';
  return null;
}

/**
 * Whether the instant check's error means the same request would be refused by "Analyze" (POST
 * /runs runs the same preparation): only an input refusal (validation_error) or an unknown item
 * (not_found). Transient failures (network, rate limit, unavailable, insufficient data) never gate.
 */
export function previewRefusal(error: Pick<ApiRequestError, 'code' | 'message' | 'details'> | null): PreviewRefusal | null {
  if (!error || (error.code !== 'validation_error' && error.code !== 'not_found')) return null;
  const reason = bilingualReason(error.details?.reason);
  const rawFields = error.details?.fields;
  const fields: readonly unknown[] = Array.isArray(rawFields) ? rawFields : [];
  let field: RefusedField | null = null;
  for (const entry of fields) {
    const path = typeof entry === 'string' ? entry
      : entry && typeof entry === 'object' && typeof (entry as { path?: unknown }).path === 'string' ? (entry as { path: string }).path : '';
    field = fieldOfPath(path);
    if (field) break;
  }
  if (!field && error.code === 'not_found' && /ticker/i.test(error.message)) field = 'ticker';
  return { field, reason };
}

function canonicalFunding(funding: Funding): string {
  return `${funding.mode}:${[...(funding.fromTickers ?? [])].sort().join(',')}`;
}

/**
 * Whether a signed brief was written for the request currently on screen. A run stores the
 * resolved funding (never "auto"), so an "auto" form matches any resolved funding.
 */
export function sameDecisionRequest(a: DecisionRequest, b: DecisionRequest): boolean {
  if (a.type === 'move' && b.type === 'move') {
    return a.move.ticker === b.move.ticker && Math.abs(a.move.sizePct - b.move.sizePct) < 1e-9
      && (a.move.funding.mode === 'auto' || b.move.funding.mode === 'auto'
        || canonicalFunding(a.move.funding) === canonicalFunding(b.move.funding));
  }
  return JSON.stringify(a) === JSON.stringify(b);
}

export function describeRequest(request: DecisionRequest, lang: Lang): string {
  if (request.type === 'move') {
    const size = lang === 'fr' ? String(request.move.sizePct).replace('.', ',') : String(request.move.sizePct);
    return lang === 'fr' ? `+${size} points de ${request.move.ticker}` : `+${size} points of ${request.move.ticker}`;
  }
  const parts = [...request.goal.themes, ...request.goal.assetClasses, ...request.goal.tickers];
  return lang === 'fr' ? `Objectif : ${parts.join(', ')}` : `Goal: ${parts.join(', ')}`;
}

/**
 * Monotonic request gate: only the most recently issued token may apply its response
 * (WEB-04 / AT-20: an old response cannot overwrite the latest).
 */
export function createLatestGate() {
  let current = 0;
  return {
    issue(): number { current += 1; return current; },
    isLatest(token: number): boolean { return token === current; },
    invalidate(): void { current += 1; },
  };
}
