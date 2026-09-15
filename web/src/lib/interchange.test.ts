import { describe, expect, it } from "vitest";
import {
  importSessions,
  loadSessions,
  parseSessions,
  serializeSessions,
  type StorageLike,
} from "./storage";
import { flattenSessions, sessionSummary } from "./features";

const fixture = [
  {
    session_name: "same <label>",
    duration: 60,
    insights: [
      {
        timestamp: 1,
        question: "2 + 3",
        operation: "add",
        operand_1: 2,
        operand_2: 3,
        correct_answer: 5,
        user_answer: 5,
        time_taken_sec: 2,
        correctness: true,
      },
      {
        timestamp: 2,
        question: "2 - 3",
        question_type: "sub",
        operand_1: 2,
        operand_2: 3,
        correct_answer: -1,
        user_answer: null,
        time_taken_sec: 4,
        correctness: false,
      },
      {
        timestamp: 3,
        question: "2 * 3",
        operation: "mul",
        operand_1: 2,
        operand_2: 3,
        correct_answer: 6,
        user_answer: 6,
        time_taken_sec: 6,
        correctness: true,
      },
      {
        timestamp: 4,
        question: "6 / 3",
        operation: "div",
        operand_1: 6,
        operand_2: 3,
        correct_answer: 2,
        user_answer: 2,
        time_taken_sec: 8,
        correctness: true,
      },
    ],
  },
  { session_name: "same <label>", duration: 30, insights: [] },
];

function memory() {
  let value: string | null = null;
  const storage: StorageLike = {
    getItem: () => value,
    setItem: (_key, next) => {
      value = next;
    },
  };
  return storage;
}

describe("desktop interchange", () => {
  it("appends repeated imports and preserves equal names, empty sessions and all operations", () => {
    const storage = memory();
    importSessions(storage, JSON.stringify(fixture));
    importSessions(storage, JSON.stringify(fixture));
    const loaded = loadSessions(storage);
    expect(loaded).toHaveLength(4);
    expect(loaded[1].insights).toEqual([]);
    expect(new Set(loaded.map((s) => s.id)).size).toBe(4);
    expect(loaded[0].insights.map((r) => r.operation)).toEqual([
      "add",
      "sub",
      "mul",
      "div",
    ]);
    expect(sessionSummary(flattenSessions(loaded))).toMatchObject({
      total: 8,
      correct: 6,
      questionsPerMin: 4,
    });
  });

  it("preserves history when a later imported session is invalid or storage fails", () => {
    const storage = memory();
    importSessions(storage, JSON.stringify(fixture));
    const before = serializeSessions(loadSessions(storage));
    for (const text of [
      " ",
      "{",
      JSON.stringify([...fixture, { session_name: "bad" }]),
    ]) {
      expect(() => importSessions(storage, text)).toThrow();
      expect(serializeSessions(loadSessions(storage))).toBe(before);
    }
    storage.setItem = () => {
      throw new Error("quota");
    };
    expect(() => importSessions(storage, JSON.stringify(fixture))).toThrow(
      "could not be written",
    );
    expect(serializeSessions(loadSessions(storage))).toBe(before);
  });

  it("round-trips the verified legacy migration fixture without browser metadata", () => {
    const exported = serializeSessions(parseSessions(JSON.stringify(fixture)));
    const records = JSON.parse(exported);
    expect(records).toEqual(
      fixture.map((session) => ({
        ...session,
        insights: session.insights.map(({ question_type, ...answer }) => ({
          ...answer,
          operation: answer.operation ?? question_type,
        })),
      })),
    );
    expect(
      sessionSummary(flattenSessions(parseSessions(exported))),
    ).toMatchObject({
      total: 4,
      correct: 3,
      accuracy: 0.75,
      avgTimeSec: 5,
      questionsPerMin: 4,
    });
  });
});
