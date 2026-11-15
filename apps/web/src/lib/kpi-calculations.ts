/**
 * Pure presentation-safe KPI math. Caller MUST supply counts already scoped and
 * authorized by the server; this module performs no authorization or fetching.
 */
export type KpiRatio = Readonly<{
  numerator: number;
  denominator: number;
  percentage: number | null;
}>;

function validCount(value: number): boolean {
  return Number.isSafeInteger(value) && value >= 0;
}

/**
 * Returns null for empty denominators, never a misleading 0% or 100%.
 * Throws for impossible counts rather than silently displaying a false KPI.
 */
export function calculateKpiRatio(numerator: number, denominator: number): KpiRatio {
  if (!validCount(numerator) || !validCount(denominator) || numerator > denominator) {
    throw new RangeError("KPI counts must be nonnegative safe integers with numerator <= denominator");
  }
  return {
    numerator,
    denominator,
    percentage: denominator === 0 ? null : Math.round((numerator / denominator) * 1000) / 10,
  };
}

/**
 * Returns null if any observation is absent; missing months must never be
 * silently represented as zero activity.
 */
export function completeMonthlySeries(
  months: readonly string[],
  observations: Readonly<Record<string, number>>,
): readonly { month: string; count: number }[] | null {
  if (new Set(months).size !== months.length) throw new RangeError("Duplicate month keys");
  const result: { month: string; count: number }[] = [];
  for (const month of months) {
    if (!Object.prototype.hasOwnProperty.call(observations, month)) return null;
    const count = observations[month];
    if (!validCount(count)) throw new RangeError("Invalid monthly count");
    result.push({ month, count });
  }
  return result;
}
