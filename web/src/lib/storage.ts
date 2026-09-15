/** Browser persistence for the desktop-compatible session contract. */

import { OPERATIONS, type Operation } from "./core";

export const STORAGE_KEY = "math-drill.sessions";

export interface AnswerRecord {
  timestamp: number;
  question: string;
  operation: Operation;
  operand1: number;
  operand2: number;
  correctAnswer: number;
  userAnswer: number | null;
  timeTakenSec: number;
  correctness: boolean;
  [key: string]: unknown;
}

export interface SessionRecord {
  sessionName: string;
  duration: number;
  insights: AnswerRecord[];
  /** Browser-only identity. Never included in exported JSON. */
  readonly id?: string;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export class SessionDataError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SessionDataError";
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function requireFiniteNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new SessionDataError(`${label} must be a finite number.`);
  }
  return value;
}

function requireSafeInteger(value: unknown, label: string): number {
  const number = requireFiniteNumber(value, label);
  if (!Number.isSafeInteger(number)) {
    throw new SessionDataError(`${label} must be a safe whole number.`);
  }
  return number;
}

function normalizeAnswer(raw: unknown, sessionIndex: number, answerIndex: number): AnswerRecord {
  const label = `Session ${sessionIndex + 1}, answer ${answerIndex + 1}`;
  if (!isRecord(raw)) throw new SessionDataError(`${label} must be an object.`);

  const operationValue = raw.operation ?? raw.question_type;
  if (!OPERATIONS.includes(operationValue as Operation)) {
    throw new SessionDataError(`${label} has an invalid operation.`);
  }
  if (typeof raw.question !== "string") {
    throw new SessionDataError(`${label}.question must be a string.`);
  }

  const userAnswer = raw.user_answer;
  if (userAnswer !== undefined && userAnswer !== null) {
    requireFiniteNumber(userAnswer, `${label}.user_answer`);
  }
  if (raw.correctness !== true && raw.correctness !== false) {
    throw new SessionDataError(`${label}.correctness must be boolean.`);
  }

  const {
    question_type: _legacyOperation,
    operation: _operation,
    operand_1: _operand1,
    operand_2: _operand2,
    correct_answer: _correctAnswer,
    user_answer: _userAnswer,
    time_taken_sec: _timeTakenSec,
    ...extras
  } = raw;

  return {
    ...extras,
    timestamp: requireFiniteNumber(raw.timestamp, `${label}.timestamp`),
    question: raw.question,
    operation: operationValue as Operation,
    operand1: requireSafeInteger(raw.operand_1, `${label}.operand_1`),
    operand2: requireSafeInteger(raw.operand_2, `${label}.operand_2`),
    correctAnswer: requireSafeInteger(raw.correct_answer, `${label}.correct_answer`),
    userAnswer: userAnswer === undefined ? null : (userAnswer as number | null),
    timeTakenSec: requireFiniteNumber(raw.time_taken_sec, `${label}.time_taken_sec`),
    correctness: raw.correctness,
  };
}

function toStoredAnswer(record: AnswerRecord): Record<string, unknown> {
  const { id: _id, operand1, operand2, correctAnswer, userAnswer, timeTakenSec, ...rest } = record;
  return {
    ...rest,
    operand_1: operand1,
    operand_2: operand2,
    correct_answer: correctAnswer,
    user_answer: userAnswer,
    time_taken_sec: timeTakenSec,
  };
}

export function normalizeSessions(payload: unknown): SessionRecord[] {
  if (!Array.isArray(payload)) {
    throw new SessionDataError("Session storage must contain an array of sessions.");
  }

  return payload.map((rawSession, sessionIndex) => {
    const label = `Session ${sessionIndex + 1}`;
    if (!isRecord(rawSession)) throw new SessionDataError(`${label} must be an object.`);
    if (typeof rawSession.session_name !== "string") {
      throw new SessionDataError(`${label}.session_name must be a string.`);
    }
    const duration = requireSafeInteger(rawSession.duration, `${label}.duration`);
    if (duration < 0) throw new SessionDataError(`${label}.duration cannot be negative.`);
    if (!Array.isArray(rawSession.insights)) {
      throw new SessionDataError(`${label}.insights must be an array.`);
    }

    return {
      sessionName: rawSession.session_name,
      duration,
      insights: rawSession.insights.map((answer, answerIndex) =>
        normalizeAnswer(answer, sessionIndex, answerIndex),
      ),
      id: `${sessionIndex}:${rawSession.session_name}`,
    };
  });
}

export function parseSessions(text: string | null): SessionRecord[] {
  if (text === null || text.trim() === "") return [];
  let payload: unknown;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new SessionDataError("Session storage is not valid JSON.");
  }
  return normalizeSessions(payload);
}

export function loadSessions(storage: StorageLike): SessionRecord[] {
  try {
    return parseSessions(storage.getItem(STORAGE_KEY));
  } catch (error) {
    if (error instanceof SessionDataError) throw error;
    throw new SessionDataError("Session storage could not be read.");
  }
}

export function serializeSessions(sessions: readonly SessionRecord[]): string {
  return JSON.stringify(
    sessions.map(({ sessionName, duration, insights }) => ({
      session_name: sessionName,
      duration,
      insights: insights.map(toStoredAnswer),
    })),
  );
}

export function saveSessions(storage: StorageLike, sessions: readonly SessionRecord[]): void {
  const serialized = serializeSessions(sessions);
  try {
    storage.setItem(STORAGE_KEY, serialized);
  } catch {
    throw new SessionDataError(
      "Session storage could not be written. Your existing history was left unchanged.",
    );
  }
}

export function appendSession(storage: StorageLike, session: SessionRecord): SessionRecord[] {
  const sessions = loadSessions(storage);
  const next = [...sessions, { ...session, id: `${sessions.length}:${session.sessionName}` }];
  saveSessions(storage, next);
  return next;
}

export function browserStorage(): StorageLike {
  try {
    if (typeof globalThis.localStorage === "undefined") throw new Error("localStorage unavailable");
    return globalThis.localStorage;
  } catch {
    throw new SessionDataError("Browser storage is unavailable in this context.");
  }
}

export function loadBrowserSessions(): SessionRecord[] {
  return loadSessions(browserStorage());
}

export function appendBrowserSession(session: SessionRecord): SessionRecord[] {
  return appendSession(browserStorage(), session);
}
