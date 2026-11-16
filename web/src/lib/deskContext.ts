/**
 * Which World investigation context the Decision Desk uses and shows (web/page-specs/decision-desk.md).
 * A shared link carries ?eventId, ?ticker, ?profileId and ?sourceRunId. Under the persona it names, that
 * context is used (ticker pre-fill, run originalText). Under another persona it is never used, but it is
 * still shown, flagged as foreign, so the reader can switch persona instead of losing it silently.
 */
import type { InvestigationContext } from './world';

export interface DeskContext {
  /** Context attached to a new decision run: the link's when it names this persona, else the restored run's. */
  context: InvestigationContext | null;
  /** Context shown in the Investigation context card. */
  shown: InvestigationContext | null;
  /** True when the shown context was selected for another persona (`contextProfile`). */
  foreign: boolean;
}

export function deskContext(
  urlContext: InvestigationContext | null, contextProfile: string | null, profileId: string,
  savedContext: InvestigationContext | null,
): DeskContext {
  const matches = !contextProfile || contextProfile === profileId;
  const context = (matches ? urlContext : null) ?? savedContext;
  if (context) return { context, shown: context, foreign: false };
  return { context: null, shown: urlContext, foreign: urlContext !== null };
}
