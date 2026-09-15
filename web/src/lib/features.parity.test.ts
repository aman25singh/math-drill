import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import * as metrics from "./features";
import { parseSessions, type SessionRecord } from "./storage";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const python = process.env.MATHDRILL_PYTHON ?? (process.platform === "win32" ? `${root}.venv/Scripts/python.exe` : "python3");
const script = `
import json, sys, math
from mathdrill import features as f
def clean(value):
    if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list): return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value): return None
    return value
def attempt(fn):
    try: return fn()
    except f.NoDataError: return {'noData': True}
results = []
for case in json.load(sys.stdin):
    def evaluate():
        df = f.compute_insight_flags(f.filter_session(f.to_dataframe(case['sessions']), case.get('filter')))
        return {
            'flags': df[list(f.BOOLEAN_FEATURES) + list(f.NUMERIC_FEATURES)].to_dict('records'),
            'digits': attempt(lambda: f.digit_difficulty(df, case['minimum']).reset_index().to_dict('records')),
            'comparison': attempt(lambda: f.feature_comparison(df, case['minimum']).to_dict('records')),
            'buckets': f.accuracy_by_time_bucket(df).to_dict(),
            'errors': f.error_counts_by_operation(df).to_dict(),
            'summary': f.session_summary(df),
            'sequence': f.response_time_series(df)[['timestamp', 'question_number', 'rolling']].to_dict('records'),
        }
    results.append(attempt(evaluate))
print(json.dumps(clean(results), allow_nan=False))
`;

function session(values: number[], duration = 60, name = "repeat") {
  return { session_name: name, duration, insights: values.map((value, i) => ({
    timestamp: (values.length - i) % 7, question: `fixture ${i}`, operation: ["add", "sub", "mul", "div"][i % 4],
    operand_1: value, operand_2: i % 2 ? 19 : 10, correct_answer: 1, user_answer: i % 3 ? 1 : null,
    time_taken_sec: [-1, 0, 2, 2.001, 4, 4.001, 6, 6.001, 10][i % 9], correctness: i % 3 !== 0,
  })) };
}
const cases = [
  { sessions: [session(Array.from({ length: 80 }, (_, i) => i * 7 - 30)), session([1], 30), session([2], 0)], minimum: 5 },
  { sessions: [session([...Array(39).fill(1), 100])], minimum: 1 }, // collapsed quantiles -> equal width
  { sessions: [session(Array(20).fill(0))], minimum: 5 },
  { sessions: [session([1], 0)], minimum: 5 },
  { sessions: [session([1], 60), session([2, 3], 120), session([], 30)], minimum: 1 },
  { sessions: [session([1, 2, 3]), session([9], 30, "other")], filter: "other", minimum: 1 },
  { sessions: [session([1])], filter: "absent", minimum: 1 },
  { sessions: [], minimum: 5 },
  { sessions: [session([1, 2, 3])], minimum: 100 },
  ...Array.from({ length: 20 }, (_, seed) => ({
    sessions: [session(Array.from({ length: 21 + seed }, (_, i) => ((i * 137 + seed * 31) % 1000) - 100))],
    minimum: seed % 2 ? 1 : 5,
  })),
];
const snake = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(snake);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, v]) => [key.replace(/[A-Z]/g, c => `_${c.toLowerCase()}`), snake(v)]));
  return typeof value === "number" && !Number.isFinite(value) ? null : value;
};
function attempt(fn: () => unknown): unknown {
  try { return fn(); } catch (error) { if (error instanceof metrics.NoDataError) return { noData: true }; throw error; }
}
function evaluate(sessions: SessionRecord[], minimum: number, filter?: string) {
  return attempt(() => {
    const rows = metrics.computeInsightFlags(metrics.filterSession(metrics.flattenSessions(sessions), filter));
    return {
      flags: rows.map(row => Object.fromEntries([...metrics.BOOLEAN_FEATURES, ...metrics.NUMERIC_FEATURES].map(key => [key, row[key]]))),
      digits: attempt(() => snake(metrics.digitDifficulty(rows, minimum))),
      comparison: attempt(() => snake(metrics.featureComparison(rows, minimum))),
      buckets: snake(metrics.accuracyByTimeBucket(rows)), errors: metrics.errorCountsByOperation(rows),
      summary: snake(metrics.sessionSummary(rows)),
      sequence: metrics.responseTimeSeries(rows).map(row => ({ timestamp: row.timestamp, question_number: row.questionNumber, rolling: row.rolling })),
    };
  });
}
function compare(actual: unknown, expected: unknown): void {
  if (typeof expected === "number") { expect(actual).toBeTypeOf("number"); expect(actual).toBeCloseTo(expected, 10); }
  else if (Array.isArray(expected)) { expect(Array.isArray(actual)).toBe(true); expect(actual).toHaveLength(expected.length); expected.forEach((v, i) => compare((actual as unknown[])[i], v)); }
  else if (expected && typeof expected === "object") {
    expect(Object.keys(actual as object).sort()).toEqual(Object.keys(expected).sort());
    Object.entries(expected).forEach(([k, v]) => compare((actual as Record<string, unknown>)[k], v));
  } else expect(actual).toEqual(expected);
}

describe("live Python metric parity", () => {
  it("matches flags, bins, baselines, thresholds, summaries, filters, boundaries and stable ordering", () => {
    const expected = JSON.parse(execFileSync(python, ["-c", script], { cwd: root, input: JSON.stringify(cases), encoding: "utf8" }));
    cases.forEach((fixture, i) => compare(evaluate(parseSessions(JSON.stringify(fixture.sessions)), fixture.minimum, fixture.filter), expected[i]));
  }, 30_000);
});
