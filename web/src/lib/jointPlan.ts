/** Shared external cash flows for POST /profiles/{id}/joint-plan, parsed from `DATE SIGNED_AMOUNT [description]` lines. */
export type JointCashflow = { date: string; amount: number; origin: 'user'; description?: string };

/** CashFlowInput.description max_length in backend/aplomb/quant/joint_plan_api.py. */
export const CASHFLOW_DESCRIPTION_MAX = 1000;

/**
 * One flow per non-blank line. The optional free text after the amount is sent as `description`, which
 * the backend compares with same-day requirement names to flag a possibly double-counted withdrawal.
 * Returns null when any line lacks an ISO date or a finite amount, or its description is too long.
 */
export function parseJointCashflows(text: string): JointCashflow[] | null {
  const flows: JointCashflow[] = [];
  for (const line of text.split('\n').map(s => s.trim()).filter(Boolean)) {
    const [date, amount, ...rest] = line.split(/\s+/);
    if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date) || amount === undefined || amount === '' || !Number.isFinite(Number(amount))) return null;
    const description = rest.join(' ');
    if (description.length > CASHFLOW_DESCRIPTION_MAX) return null;
    flows.push(description ? { date, amount: Number(amount), origin: 'user', description } : { date, amount: Number(amount), origin: 'user' });
  }
  return flows;
}
