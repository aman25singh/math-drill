import { describe, expect, it } from "vitest";
import * as metrics from "./features";
import { parseSessions, type SessionRecord } from "./storage";
import fixtures from "./fixtures/metrics.json";

const snake = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(snake);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value).map(([key, v]) => [
        key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`),
        snake(v),
      ]),
    );
  return typeof value === "number" && !Number.isFinite(value) ? null : value;
};
function attempt(fn: () => unknown): unknown {
  try {
    return fn();
  } catch (error) {
    if (error instanceof metrics.NoDataError) return { noData: true };
    throw error;
  }
}
function evaluate(sessions: SessionRecord[], minimum: number, filter?: string) {
  return attempt(() => {
    const rows = metrics.computeInsightFlags(
      metrics.filterSession(metrics.flattenSessions(sessions), filter),
    );
    return {
      flags: rows.map((row) =>
        Object.fromEntries(
          [...metrics.BOOLEAN_FEATURES, ...metrics.NUMERIC_FEATURES].map(
            (key) => [key, row[key]],
          ),
        ),
      ),
      digits: attempt(() => snake(metrics.digitDifficulty(rows, minimum))),
      comparison: attempt(() =>
        snake(metrics.featureComparison(rows, minimum)),
      ),
      buckets: snake(metrics.accuracyByTimeBucket(rows)),
      errors: metrics.errorCountsByOperation(rows),
      summary: snake(metrics.sessionSummary(rows)),
      sequence: metrics.responseTimeSeries(rows).map((row) => ({
        timestamp: row.timestamp,
        question_number: row.questionNumber,
        rolling: row.rolling,
      })),
    };
  });
}
function compare(actual: unknown, expected: unknown): void {
  if (typeof expected === "number") {
    expect(actual).toBeTypeOf("number");
    expect(actual).toBeCloseTo(expected, 10);
  } else if (Array.isArray(expected)) {
    expect(Array.isArray(actual)).toBe(true);
    expect(actual).toHaveLength(expected.length);
    expected.forEach((v, i) => compare((actual as unknown[])[i], v));
  } else if (expected && typeof expected === "object") {
    expect(Object.keys(actual as object).sort()).toEqual(
      Object.keys(expected).sort(),
    );
    Object.entries(expected).forEach(([k, v]) =>
      compare((actual as Record<string, unknown>)[k], v),
    );
  } else expect(actual).toEqual(expected);
}

describe("verified metric fixtures", () => {
  it.each(
    fixtures.cases.map((fixture, i) => ({
      fixture,
      expected: fixtures.expected[i],
      index: i + 1,
    })),
  )("matches verified scenario $index", ({ fixture, expected }) => {
    compare(
      evaluate(
        parseSessions(JSON.stringify(fixture.sessions)),
        fixture.minimum,
        "filter" in fixture ? fixture.filter : undefined,
      ),
      expected,
    );
  });
});
