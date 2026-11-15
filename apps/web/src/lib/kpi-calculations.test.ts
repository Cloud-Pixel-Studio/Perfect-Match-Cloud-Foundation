import { describe, expect, it } from "vitest";
import { calculateKpiRatio, completeMonthlySeries } from "./kpi-calculations";

describe("KPI calculation contracts", () => {
  it("calculates exact 0 and 100 percent when there are observations", () => {
    expect(calculateKpiRatio(0, 10)).toEqual({ numerator: 0, denominator: 10, percentage: 0 });
    expect(calculateKpiRatio(10, 10).percentage).toBe(100);
  });

  it("does not invent a rate for an empty population", () => {
    expect(calculateKpiRatio(0, 0).percentage).toBeNull();
  });

  it("rounds to one decimal place", () => {
    expect(calculateKpiRatio(2, 3).percentage).toBe(66.7);
  });

  it.each([[1, 0], [-1, 3], [1.5, 2], [Infinity, 2], [1, NaN], [Number.MAX_SAFE_INTEGER + 1, 3]])(
    "rejects invalid count pair %s/%s",
    (numerator, denominator) => {
      expect(() => calculateKpiRatio(numerator, denominator)).toThrow(RangeError);
    },
  );

  it("preserves explicit zero activity while distinguishing missing observations", () => {
    expect(completeMonthlySeries(["2026-09", "2026-10"], { "2026-09": 0, "2026-10": 4 }))
      .toEqual([{ month: "2026-09", count: 0 }, { month: "2026-10", count: 4 }]);
    expect(completeMonthlySeries(["2026-09", "2026-10"], { "2026-09": 0 })).toBeNull();
  });

  it("rejects malformed, non-calendar and unordered monthly periods", () => {
    for (const month of ["2026-00", "2026-13", "2026-1", "2026/01", "2026-01-extra"]) {
      expect(() => completeMonthlySeries([month], { [month]: 1 })).toThrow(RangeError);
    }
    expect(() => completeMonthlySeries(["2026-10", "2026-09"], { "2026-10": 1, "2026-09": 2 }))
      .toThrow(RangeError);
    expect(completeMonthlySeries([], {})).toEqual([]);
  });

  it("rejects duplicate periods and malformed counts", () => {
    expect(() => completeMonthlySeries(["2026-09", "2026-09"], { "2026-09": 1 })).toThrow(RangeError);
    expect(() => completeMonthlySeries(["2026-09"], { "2026-09": -2 })).toThrow(RangeError);
  });
});
