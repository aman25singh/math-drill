import { describe, expect, it } from "vitest";
import {
  computeInsightFlags,
  digitDifficulty,
  flattenSessions,
  sessionSummary,
  responseTimeSeries,
  NoDataError,
} from "./features";
import type { SessionRecord } from "./storage";

const sessions: SessionRecord[] = [
  {
    sessionName: "practice",
    duration: 60,
    insights: [
      {
        timestamp: 1,
        question: "19 + 2",
        operation: "add",
        operand1: 19,
        operand2: 2,
        correctAnswer: 21,
        userAnswer: 21,
        timeTakenSec: 2,
        correctness: true,
      },
      {
        timestamp: 2,
        question: "30 - 12",
        operation: "sub",
        operand1: 30,
        operand2: 12,
        correctAnswer: 18,
        userAnswer: 10,
        timeTakenSec: 4,
        correctness: false,
      },
    ],
  },
];

describe("feature parity", () => {
  it("flattens sessions and derives the desktop flags", () => {
    const rows = computeInsightFlags(flattenSessions(sessions));
    expect(rows[0].is_carry_addition).toBe(true);
    expect(rows[1].is_borrow_subtraction).toBe(true);
    expect(rows[0].has_9).toBe(true);
    expect(rows[1].is_round_operand_1).toBe(true);
    expect(rows[1].operand_diff).toBe(18);
  });
  it("matches headline metric definitions", () => {
    const rows = computeInsightFlags(flattenSessions(sessions));
    expect(digitDifficulty(rows, 1).find((r) => r.digit === 9)).toMatchObject({
      avgTime: 2,
      n: 1,
    });
    expect(sessionSummary(rows)).toMatchObject({
      total: 2,
      correct: 1,
      accuracy: 0.5,
      totalDurationSec: 60,
      questionsPerMin: 2,
    });
    expect(responseTimeSeries(rows)[1].rolling).toBe(3);
  });
  it("reports empty data explicitly", () => {
    expect(() => digitDifficulty([])).toThrow(NoDataError);
    expect(() => sessionSummary([])).toThrow("No session data");
  });
});
