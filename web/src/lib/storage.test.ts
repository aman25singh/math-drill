import { describe, expect, it } from "vitest";
import {
  STORAGE_KEY,
  SessionDataError,
  appendSession,
  importSessions,
  loadSessions,
  normalizeSessions,
  parseSessions,
  saveSessions,
  serializeSessions,
  type SessionRecord,
  type StorageLike,
} from "./storage";

class FakeStorage implements StorageLike {
  value: string | null = null;
  failReads = false;
  failWrites = false;

  getItem(key: string): string | null {
    if (this.failReads) throw new Error("read failed");
    expect(key).toBe(STORAGE_KEY);
    return this.value;
  }

  setItem(key: string, value: string): void {
    if (this.failWrites) throw new Error("quota exceeded");
    expect(key).toBe(STORAGE_KEY);
    this.value = value;
  }
}

const answer = (overrides: Record<string, unknown> = {}) => ({
  timestamp: 1000,
  question: "2 + 3",
  operation: "add",
  operand_1: 2,
  operand_2: 3,
  correct_answer: 5,
  user_answer: 5,
  time_taken_sec: 1.25,
  correctness: true,
  ...overrides,
});

const session = (name = "practice"): SessionRecord => ({
  sessionName: name,
  duration: 60,
  insights: [
    {
      timestamp: 1000,
      question: "2 + 3",
      operation: "add",
      operand1: 2,
      operand2: 3,
      correctAnswer: 5,
      userAnswer: 5,
      timeTakenSec: 1.25,
      correctness: true,
    },
  ],
});

describe("session normalization", () => {
  it("normalizes Python field names and legacy question_type", () => {
    const [result] = normalizeSessions([
      {
        session_name: "practice",
        duration: 60,
        insights: [answer({ question_type: "add", operation: undefined })],
      },
    ]);
    expect(result.sessionName).toBe("practice");
    expect(result.insights[0]).toMatchObject({
      operation: "add",
      operand1: 2,
      operand2: 3,
      userAnswer: 5,
    });
  });

  it("keeps equal-name sessions as separate array entries", () => {
    const results = normalizeSessions([
      { session_name: "practice", duration: 30, insights: [] },
      { session_name: "practice", duration: 120, insights: [] },
    ]);
    expect(results).toHaveLength(2);
    expect(results.map((item) => item.duration)).toEqual([30, 120]);
    expect(results[0].id).not.toBe(results[1].id);
  });

  it.each([
    [null, ""],
    ["", ""],
  ])("treats missing or blank storage as empty", (value, _message) => {
    expect(parseSessions(value)).toEqual([]);
  });

  it.each([
    ["{}", "array"],
    ["not json", "valid JSON"],
    [JSON.stringify([{ session_name: "x", duration: 60, insights: "bad" }]), "insights"],
    [JSON.stringify([{ session_name: "x", duration: 60, insights: [answer({ operand_1: 1.5 })] }]), "safe whole number"],
  ])("rejects malformed data with a useful error", (value, message) => {
    expect(() => parseSessions(value)).toThrow(message);
  });
});

describe("storage persistence", () => {
  it("round-trips sessions using desktop-compatible field names", () => {
    const storage = new FakeStorage();
    saveSessions(storage, [session()]);
    expect(storage.value).toContain('"session_name":"practice"');
    expect(storage.value).toContain('"operand_1":2');
    expect(storage.value).not.toContain("question_type");
    expect(loadSessions(storage)[0]).toMatchObject({ sessionName: "practice", duration: 60 });
  });

  it("appends without deduplicating equal names", () => {
    const storage = new FakeStorage();
    saveSessions(storage, [session()]);
    const result = appendSession(storage, { ...session(), duration: 120 });
    expect(result).toHaveLength(2);
    expect(result.map((item) => item.sessionName)).toEqual(["practice", "practice"]);
  });

  it("preserves the existing serialized value when writing fails", () => {
    const storage = new FakeStorage();
    saveSessions(storage, [session()]);
    const original = storage.value;
    storage.failWrites = true;
    expect(() => appendSession(storage, session("new"))).toThrow(SessionDataError);
    expect(storage.value).toBe(original);
  });

  it("reports unavailable storage reads", () => {
    const storage = new FakeStorage();
    storage.failReads = true;
    expect(() => loadSessions(storage)).toThrow("could not be read");
  });

  it("does not serialize the browser-only identity", () => {
    expect(serializeSessions([{ ...session(), id: "private-id" }])).not.toContain("private-id");
  });

  it("validates every imported session before writing", () => {
    const storage = new FakeStorage();
    const imported = JSON.stringify([{ session_name: "imported", duration: 30, insights: [] }]);
    expect(importSessions(storage, imported)).toHaveLength(1);
    const before = storage.value;
    expect(() => importSessions(storage, "{invalid")).toThrow(SessionDataError);
    expect(storage.value).toBe(before);
  });
});
