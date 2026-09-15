import { describe, expect, it } from "vitest";
import {
  ConfigError,
  createDrillConfig,
  generateQuestion,
  type Operation,
  type RandomSource,
} from "./core";

class SequenceRandom implements RandomSource {
  private readonly values: number[];
  constructor(values: number[]) {
    this.values = [...values];
  }
  choice<T>(items: readonly T[]): T {
    const index = this.values.shift();
    if (index === undefined) throw new Error("Random sequence exhausted");
    return items[index % items.length];
  }
  randint(low: number, high: number): number {
    const value = this.values.shift();
    if (value === undefined) throw new Error("Random sequence exhausted");
    return low + (value % (high - low + 1));
  }
}

const config = (operation: Operation, overrides = {}) =>
  createDrillConfig({
    sessionName: "test",
    duration: 60,
    operations: [operation],
    ...overrides,
  });

describe("createDrillConfig", () => {
  it("deduplicates operations while preserving order", () => {
    expect(
      createDrillConfig({
        sessionName: "  test  name ",
        duration: 60,
        operations: ["mul", "add", "mul"],
      }),
    ).toMatchObject({
      sessionName: "test name",
      operations: ["mul", "add"],
    });
  });

  it.each([
    [[], "at least one operation"],
    [["log"], "Unknown operation"],
  ])("rejects invalid operations", (operations, message) => {
    expect(() =>
      createDrillConfig({ sessionName: "test", duration: 60, operations }),
    ).toThrow(message);
  });

  it.each([
    [[100, 2], "greater than its maximum"],
    [[-1, 10], "cannot be negative"],
    [[1.5, 2], "safe whole number"],
  ])("rejects invalid ranges", (range, message) => {
    expect(() =>
      createDrillConfig({
        sessionName: "test",
        duration: 60,
        operations: ["add"],
        addRange1: range as [number, number],
      }),
    ).toThrow(message);
  });

  it("rejects zero duration and unusable division ranges", () => {
    expect(() =>
      createDrillConfig({
        sessionName: "test",
        duration: 0,
        operations: ["add"],
      }),
    ).toThrow("positive");
    expect(() =>
      createDrillConfig({
        sessionName: "test",
        duration: 60,
        operations: ["div"],
        mulRange2: [0, 0],
      }),
    ).toThrow("divisor");
  });
});

describe("generateQuestion", () => {
  it.each([
    ["add", (a: number, b: number) => a + b],
    ["sub", (a: number, b: number) => a - b],
    ["mul", (a: number, b: number) => a * b],
    ["div", (a: number, b: number) => a / b],
  ] as const)(
    "generates mathematically correct %s questions",
    (operation, expected) => {
      const question = generateQuestion(
        config(operation),
        new SequenceRandom([0, 2, 3, 0, 1]),
      );
      expect(question.answer).toBe(
        expected(question.operand1, question.operand2),
      );
      expect(question.operation).toBe(operation);
    },
  );

  it("keeps division exact and respects divisor/quotient ranges", () => {
    const question = generateQuestion(
      config("div", { mulRange1: [3, 6], mulRange2: [10, 20] }),
      new SequenceRandom([0, 1, 2]),
    );
    expect(question.operand2).toBeGreaterThanOrEqual(10);
    expect(question.operand2).toBeLessThanOrEqual(20);
    expect(question.answer).toBeGreaterThanOrEqual(3);
    expect(question.answer).toBeLessThanOrEqual(6);
    expect(question.operand1 % question.operand2).toBe(0);
  });

  it("uses addition ranges for subtraction and can forbid negative answers", () => {
    const question = generateQuestion(
      config("sub", {
        addRange1: [1, 3],
        addRange2: [90, 99],
        allowNegativeAnswers: false,
      }),
      new SequenceRandom([0, 0, 0, 0]),
    );
    expect(question.operand1).toBeGreaterThanOrEqual(question.operand2);
    expect(question.answer).toBeGreaterThanOrEqual(0);
  });
});

describe("safe arithmetic failures", () => {
  it("rejects products that cannot be represented safely", () => {
    expect(() =>
      config("mul", {
        mulRange1: [Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER],
        mulRange2: [2, 2],
      }),
    ).toThrow(ConfigError);
  });
  it("rejects addition overflow and excessive timers before a drill starts", () => {
    expect(() =>
      config("add", {
        addRange1: [Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER],
      }),
    ).toThrow("Addition ranges");
    expect(() => config("add", { duration: Number.MAX_SAFE_INTEGER })).toThrow(
      "timer precision",
    );
  });
});
