/** Pure Decision Desk logic: request building, staleness and race gating (web/page-specs/decision-desk.md). */
import type {
  CheckRequest, DecisionRequest, Funding, FundingMode, Lang, ProposedMove, RuleOverride, WindowSpec,
} from '../contracts/types';

export interface MoveForm {
  ticker: string;
  sizePct: number;
  fundingMode: FundingMode;
  fromTickers: string[];
}

export function fundingOf(form: MoveForm): Funding {
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

/** Client-side checks mirroring api.md 4.2 validation; the server remains authoritative. */
export function validateMoveForm(form: MoveForm, currentWeightPct: number | null): MoveFormIssue[] {
  const issues: MoveFormIssue[] = [];
  if (!form.ticker.trim()) {
    issues.push({ field: 'ticker', message: { en: 'Choose an asset.', fr: 'Choisissez un actif.' } });
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
  return issues;
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
