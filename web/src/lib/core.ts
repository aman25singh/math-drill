/** GUI-free question generation and configuration for the browser drill.
 *
 * The rules in this module intentionally mirror mathdrill/core.py. Keeping
 * this code free of Astro and browser APIs makes it usable from tests and
 * future client islands without changing the persisted session contract.
 */

export const OPERATIONS = ["add", "sub", "mul", "div"] as const;
export type Operation = (typeof OPERATIONS)[number];

export type OperandRange = readonly [number, number];

export interface DrillConfigInput {
  sessionName: string;
  duration: number;
  operations: readonly string[];
  addRange1?: OperandRange;
  addRange2?: OperandRange;
  mulRange1?: OperandRange;
  mulRange2?: OperandRange;
  allowNegativeAnswers?: boolean;
}

export interface DrillConfig {
  readonly sessionName: string;
  readonly duration: number;
  readonly operations: readonly Operation[];
  readonly addRange1: OperandRange;
  readonly addRange2: OperandRange;
  readonly mulRange1: OperandRange;
  readonly mulRange2: OperandRange;
  readonly allowNegativeAnswers: boolean;
}

export interface Question {
  readonly text: string;
  readonly answer: number;
  readonly operation: Operation;
  readonly operand1: number;
  readonly operand2: number;
}

export interface RandomSource {
  choice<T>(items: readonly T[]): T;
  randint(low: number, high: number): number;
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;

function validateInteger(value: number, label: string): number {
  if (!Number.isSafeInteger(value)) {
    throw new ConfigError(`${label} must be a safe whole number.`);
  }
  return value;
}

function validateRange(name: string, value: OperandRange | undefined, fallback: OperandRange): OperandRange {
  const range = value ?? fallback;
  if (!Array.isArray(range) || range.length !== 2) {
    throw new ConfigError(`${name} must be a [minimum, maximum] pair.`);
  }
  const low = validateInteger(range[0], `${name} minimum`);
  const high = validateInteger(range[1], `${name} maximum`);
  if (low > high) {
    throw new ConfigError(`${name} minimum (${low}) is greater than its maximum (${high}).`);
  }
  if (low < 0) {
    throw new ConfigError(`${name} cannot be negative (got ${low}).`);
  }
  return [low, high];
}

export function cleanSessionName(raw: string): string {
  return raw.replace(/[\u0000-\u001f\u007f]/g, "").trim().replace(/\s+/g, " ").slice(0, 120);
}

export function createDrillConfig(input: DrillConfigInput): DrillConfig {
  const operations: Operation[] = [];
  for (const operation of input.operations) {
    if (!OPERATIONS.includes(operation as Operation)) {
      throw new ConfigError(`Unknown operation: ${operation}.`);
    }
    if (!operations.includes(operation as Operation)) operations.push(operation as Operation);
  }
  if (operations.length === 0) throw new ConfigError("Select at least one operation.");
  if (!Number.isSafeInteger(input.duration) || input.duration <= 0) {
    throw new ConfigError("Duration must be a positive safe whole number of seconds.");
  }

  const config: DrillConfig = {
    sessionName: cleanSessionName(input.sessionName),
    duration: input.duration,
    operations,
    addRange1: validateRange("addRange1", input.addRange1, [2, 100]),
    addRange2: validateRange("addRange2", input.addRange2, [2, 100]),
    mulRange1: validateRange("mulRange1", input.mulRange1, [2, 12]),
    mulRange2: validateRange("mulRange2", input.mulRange2, [2, 100]),
    allowNegativeAnswers: input.allowNegativeAnswers ?? true,
  };

  if (config.operations.includes("div")) {
    if (config.mulRange2[1] < 1) {
      throw new ConfigError("Division needs a divisor of at least 1; widen mulRange2.");
    }
    if (config.mulRange1[1] < 1) {
      throw new ConfigError("Division needs a quotient of at least 1; widen mulRange1.");
    }
  }
  return config;
}

class MathRandomSource implements RandomSource {
  choice<T>(items: readonly T[]): T {
    return items[Math.floor(Math.random() * items.length)];
  }

  randint(low: number, high: number): number {
    return Math.floor(Math.random() * (high - low + 1)) + low;
  }
}

const defaultRandom = new MathRandomSource();

function positiveRandomInt(random: RandomSource, low: number, high: number): number {
  return random.randint(high < 1 ? low : Math.max(low, 1), high);
}

export function generateQuestion(config: DrillConfig, random: RandomSource = defaultRandom): Question {
  const operation = random.choice(config.operations);

  if (operation === "add") {
    let operand1 = random.randint(config.addRange1[0], config.addRange1[1]);
    let operand2 = random.randint(config.addRange2[0], config.addRange2[1]);
    if (random.choice([true, false])) [operand1, operand2] = [operand2, operand1];
    return { text: `${operand1} + ${operand2}`, answer: operand1 + operand2, operation, operand1, operand2 };
  }

  if (operation === "sub") {
    let operand1 = random.randint(config.addRange1[0], config.addRange1[1]);
    let operand2 = random.randint(config.addRange2[0], config.addRange2[1]);
    if (random.choice([true, false])) [operand1, operand2] = [operand2, operand1];
    if (!config.allowNegativeAnswers && operand2 > operand1) [operand1, operand2] = [operand2, operand1];
    return { text: `${operand1} - ${operand2}`, answer: operand1 - operand2, operation, operand1, operand2 };
  }

  if (operation === "div") {
    const operand2 = positiveRandomInt(random, config.mulRange2[0], config.mulRange2[1]);
    const quotient = positiveRandomInt(random, config.mulRange1[0], config.mulRange1[1]);
    const operand1 = operand2 * quotient;
    if (!Number.isSafeInteger(operand1)) throw new ConfigError("Division operands exceed safe integer precision.");
    return { text: `${operand1} ÷ ${operand2}`, answer: quotient, operation, operand1, operand2 };
  }

  let operand1 = random.randint(config.mulRange1[0], config.mulRange1[1]);
  let operand2 = random.randint(config.mulRange2[0], config.mulRange2[1]);
  if (random.choice([true, false])) [operand1, operand2] = [operand2, operand1];
  if (!Number.isSafeInteger(operand1 * operand2)) {
    throw new ConfigError("Multiplication operands exceed safe integer precision.");
  }
  return { text: `${operand1} × ${operand2}`, answer: operand1 * operand2, operation, operand1, operand2 };
}

export { MAX_SAFE_INTEGER };
