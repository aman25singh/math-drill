import type { AnswerRecord, SessionRecord } from "./storage";

export const BOOLEAN_FEATURES = [
  "is_carry_addition",
  "is_borrow_subtraction",
  "is_round_operand_1",
  "is_round_operand_2",
  ...Array.from({ length: 9 }, (_, i) => `has_${i + 1}`),
] as const;
export const NUMERIC_FEATURES = [
  "num_digits_op1",
  "num_digits_op2",
  "operand_diff",
  "max_operand",
] as const;
export const FEATURE_LABELS: Record<string, string> = {
  is_carry_addition: "addition with a carry",
  is_borrow_subtraction: "subtraction with a borrow",
  is_round_operand_1: "first operand is a multiple of 10",
  is_round_operand_2: "second operand is a multiple of 10",
  num_digits_op1: "digits in first operand",
  num_digits_op2: "digits in second operand",
  operand_diff: "gap between operands",
  max_operand: "larger operand",
};
for (let digit = 1; digit <= 9; digit += 1)
  FEATURE_LABELS[`has_${digit}`] = `an operand containing ${digit}`;

export class NoDataError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NoDataError";
  }
}
export interface FeatureRow extends AnswerRecord {
  sessionName: string;
  duration: number;
  index: number;
  sessionIndex: number;
  [key: string]: unknown;
}
export interface DigitDifficulty {
  digit: number;
  avgTime: number;
  errorRate: number;
  n: number;
}
export interface FeatureComparison {
  feature: string;
  label: string;
  group: string;
  avgTime: number;
  baselineTime: number;
  delta: number;
  accuracy: number;
  n: number;
  baselineN: number;
  description: string;
}

function requireRows(rows: readonly FeatureRow[]): void {
  if (!rows.length)
    throw new NoDataError("No session data found. Play a session first.");
}
export function flattenSessions(
  sessions: readonly SessionRecord[],
): FeatureRow[] {
  return sessions.flatMap((session, sessionIndex) =>
    session.insights.map((answer, index) => ({
      ...answer,
      sessionName: session.sessionName,
      duration: session.duration,
      index: index + 1,
      sessionIndex,
    })),
  );
}
export function filterSession(
  rows: readonly FeatureRow[],
  sessionName?: string,
): FeatureRow[] {
  requireRows(rows);
  if (!sessionName) return [...rows];
  const filtered = rows.filter((row) => row.sessionName === sessionName);
  if (!filtered.length)
    throw new NoDataError(`No data found for session '${sessionName}'.`);
  return filtered;
}
export function computeInsightFlags(rows: readonly FeatureRow[]): FeatureRow[] {
  requireRows(rows);
  return rows.map((row) => {
    const a = Math.abs(row.operand1).toString(),
      b = Math.abs(row.operand2).toString();
    return {
      ...row,
      is_carry_addition:
        row.operation === "add" &&
        (((row.operand1 % 10) + 10) % 10) + (((row.operand2 % 10) + 10) % 10) >=
          10,
      is_borrow_subtraction:
        row.operation === "sub" &&
        ((row.operand1 % 10) + 10) % 10 < ((row.operand2 % 10) + 10) % 10,
      is_round_operand_1: ((row.operand1 % 10) + 10) % 10 === 0,
      is_round_operand_2: ((row.operand2 % 10) + 10) % 10 === 0,
      ...Object.fromEntries(
        Array.from({ length: 9 }, (_, i) => [
          `has_${i + 1}`,
          a.includes(String(i + 1)) || b.includes(String(i + 1)),
        ]),
      ),
      num_digits_op1: a.length,
      num_digits_op2: b.length,
      operand_diff: Math.abs(row.operand1 - row.operand2),
      max_operand: Math.max(row.operand1, row.operand2),
    };
  });
}
export function digitDifficulty(
  rows: readonly FeatureRow[],
  minSamples = 1,
): DigitDifficulty[] {
  requireRows(rows);
  const flagged = rows.some((r) => "has_1" in r)
    ? [...rows]
    : computeInsightFlags(rows);
  const result: DigitDifficulty[] = [];
  for (let digit = 1; digit <= 9; digit += 1) {
    const subset = flagged.filter((r) => r[`has_${digit}`] === true);
    if (subset.length >= minSamples)
      result.push({
        digit,
        avgTime:
          subset.reduce((sum, r) => sum + r.timeTakenSec, 0) / subset.length,
        errorRate:
          1 - subset.filter((r) => r.correctness).length / subset.length,
        n: subset.length,
      });
  }
  if (!result.length)
    throw new NoDataError("Not enough data to compare digits yet.");
  return result.sort(
    (a, b) => Number(b.avgTime.toFixed(10)) - Number(a.avgTime.toFixed(10)),
  );
}
export function accuracyByTimeBucket(
  rows: readonly FeatureRow[],
): Record<string, number> {
  requireRows(rows);
  const labels = ["<2s", "2-4s", "4-6s", "6s+"];
  const grouped = Object.fromEntries(
    labels.map((label) => [label, [] as FeatureRow[]]),
  );
  rows.forEach((row) => {
    const t = row.timeTakenSec;
    if (t < 0 || Number.isNaN(t)) return;
    grouped[t <= 2 ? "<2s" : t <= 4 ? "2-4s" : t <= 6 ? "4-6s" : "6s+"].push(
      row,
    );
  });
  return Object.fromEntries(
    labels.map((label) => [
      label,
      grouped[label].length
        ? grouped[label].filter((r) => r.correctness).length /
          grouped[label].length
        : NaN,
    ]),
  );
}
export function errorCountsByOperation(
  rows: readonly FeatureRow[],
): Partial<Record<string, number>> {
  requireRows(rows);
  return rows.reduce(
    (counts, row) => {
      if (!row.correctness)
        counts[row.operation] = (counts[row.operation] ?? 0) + 1;
      return counts;
    },
    {} as Partial<Record<string, number>>,
  );
}
export function sessionSummary(rows: readonly FeatureRow[]) {
  requireRows(rows);
  const groups = new Map<number, FeatureRow[]>();
  rows.forEach((row) =>
    groups.set(row.sessionIndex, [
      ...(groups.get(row.sessionIndex) ?? []),
      row,
    ]),
  );
  const sessions = [...groups.values()];
  const total = rows.length,
    correct = rows.filter((r) => r.correctness).length;
  const rates = sessions
    .filter((group) => group[0].duration > 0)
    .map((group) => (group.length * 60) / group[0].duration);
  return {
    sessionName:
      sessions.length === 1
        ? rows[0].sessionName
        : `${sessions.length} sessions`,
    sessions: sessions.length,
    total,
    correct,
    incorrect: total - correct,
    accuracy: correct / total,
    avgTimeSec: rows.reduce((s, r) => s + r.timeTakenSec, 0) / total,
    totalDurationSec: sessions.reduce((s, group) => s + group[0].duration, 0),
    questionsPerMin: rates.reduce((s, n) => s + n, 0) / rates.length,
  };
}
export function responseTimeSeries(rows: readonly FeatureRow[], window = 5) {
  requireRows(rows);
  if (!Number.isInteger(window) || window < 1)
    throw new RangeError("window must be a positive integer");
  const ordered = [...rows].sort((a, b) => a.timestamp - b.timestamp);
  return ordered.map((row, index) => ({
    ...row,
    questionNumber: index + 1,
    rolling:
      ordered
        .slice(Math.max(0, index - window + 1), index + 1)
        .reduce((s, item) => s + item.timeTakenSec, 0) /
      Math.min(window, index + 1),
  }));
}

/** Right-closed pandas qcut bins, dropping duplicate edges and falling back to cut. */
function numericGroups(rows: readonly FeatureRow[], feature: string) {
  const values = rows.map((row) => Number(row[feature]));
  const sorted = [...values].sort((a, b) => a - b);
  const count = Math.min(4, new Set(values).size);
  if (count < 2) return [];
  const quantile = (q: number) => {
    const position = (sorted.length - 1) * q;
    const low = Math.floor(position),
      fraction = position - low;
    return (
      sorted[low] + ((sorted[low + 1] ?? sorted[low]) - sorted[low]) * fraction
    );
  };
  let edges = [
    ...new Set(
      Array.from({ length: count + 1 }, (_, i) => quantile(i / count)),
    ),
  ];
  const assign = (bounds: number[]) =>
    bounds
      .slice(1)
      .map((high, i) =>
        rows.filter(
          (_, j) =>
            values[j] <= high &&
            (i === 0 ? values[j] >= bounds[0] : values[j] > bounds[i]),
        ),
      );
  let groups = assign(edges);
  let quantiles = true;
  if (groups.filter((group) => group.length).length < 2) {
    quantiles = false;
    const low = sorted[0],
      high = sorted[sorted.length - 1],
      width = high - low;
    edges = Array.from(
      { length: count + 1 },
      (_, i) => low + (width * i) / count,
    );
    edges[0] -= width * 0.001;
    groups = assign(edges);
  }
  if (groups.filter((group) => group.length).length < 2) return [];
  // pandas starts at precision 3 and increases until rounded edges are distinct.
  const round = (value: number, precision: number) => {
    const digits =
      value !== 0 && Math.abs(value) < 1
        ? -Math.floor(Math.log10(Math.abs(value))) - 1 + precision
        : precision;
    return Number(value.toFixed(Math.max(0, Math.min(100, digits))));
  };
  let precision = 3;
  while (
    precision < 20 &&
    new Set(edges.map((v) => round(v, precision))).size !== edges.length
  )
    precision++;
  const display = edges.map((v) => round(v, precision));
  if (quantiles) display[0] -= 10 ** -precision;
  const label = (v: number) => (Number.isInteger(v) ? v.toFixed(1) : String(v));
  return groups.map((group, i) => ({
    group,
    label: `(${label(display[i])}, ${label(display[i + 1])}]`,
  }));
}

export function featureComparison(
  rows: readonly FeatureRow[],
  minSamples = 5,
): FeatureComparison[] {
  requireRows(rows);
  const mean = (group: readonly FeatureRow[]) =>
    group.reduce((sum, row) => sum + row.timeTakenSec, 0) / group.length;
  const result: FeatureComparison[] = [];
  const add = (
    feature: string,
    group: string,
    subset: FeatureRow[],
    baseline: readonly FeatureRow[],
  ) => {
    const avgTime = mean(subset),
      baselineTime = mean(baseline),
      label = FEATURE_LABELS[feature];
    result.push({
      feature,
      label,
      group,
      avgTime,
      baselineTime,
      delta: avgTime - baselineTime,
      accuracy: subset.filter((row) => row.correctness).length / subset.length,
      n: subset.length,
      baselineN: baseline.length,
      description: group === "true" ? label : `${label} ${group}`,
    });
  };
  for (const feature of BOOLEAN_FEATURES) {
    if (!(feature in rows[0])) continue;
    const yes = rows.filter((row) => Boolean(row[feature]));
    const no = rows.filter((row) => !row[feature]);
    if (yes.length >= minSamples && no.length >= minSamples)
      add(feature, "true", yes, no);
  }
  for (const feature of NUMERIC_FEATURES) {
    if (!(feature in rows[0])) continue;
    for (const bin of numericGroups(rows, feature)) {
      if (bin.group.length >= minSamples)
        add(feature, bin.label, bin.group, rows);
    }
  }
  if (!result.length)
    throw new NoDataError(
      `Not enough data yet to compare features. Each group needs at least ${minSamples} questions.`,
    );
  return result.sort(
    (a, b) => Number(b.delta.toFixed(10)) - Number(a.delta.toFixed(10)),
  );
}
