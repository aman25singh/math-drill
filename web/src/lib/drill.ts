import { generateQuestion, type DrillConfig, type Question, type RandomSource } from "./core";
import type { AnswerRecord, SessionRecord } from "./storage";

export interface Clock { now(): number; }

export interface DrillState {
  status: "idle" | "running" | "finished";
  config: DrillConfig;
  currentQuestion: Question | null;
  records: AnswerRecord[];
  score: number;
  startedAt: number | null;
  deadline: number | null;
  currentQuestionStartedAt: number | null;
  saveError: string | null;
}

export interface DrillControllerOptions {
  clock?: Clock;
  timestampNow?: () => number;
  random?: RandomSource;
  save?: (session: SessionRecord) => void;
}

const browserClock: Clock = { now: () => performance.now() };

export class DrillController {
  readonly state: DrillState;
  private readonly clock: Clock;
  private readonly timestampNow: () => number;
  private readonly random?: RandomSource;
  private readonly save?: (session: SessionRecord) => void;
  private saved = false;

  constructor(config: DrillConfig, options: DrillControllerOptions = {}) {
    this.clock = options.clock ?? browserClock;
    this.timestampNow = options.timestampNow ?? (() => Date.now() / 1000);
    this.random = options.random;
    this.save = options.save;
    this.state = {
      status: "idle", config, currentQuestion: null, records: [], score: 0,
      startedAt: null, deadline: null, currentQuestionStartedAt: null, saveError: null,
    };
  }

  start(): DrillState {
    const now = this.clock.now();
    this.saved = false;
    this.state.status = "running";
    this.state.records = [];
    this.state.score = 0;
    this.state.startedAt = now;
    this.state.deadline = now + this.state.config.duration * 1000;
    this.state.currentQuestion = generateQuestion(this.state.config, this.random);
    this.state.currentQuestionStartedAt = null;
    this.state.saveError = null;
    return this.state;
  }

  armQuestion(): boolean {
    if (this.state.status !== "running" || !this.state.currentQuestion || this.state.currentQuestionStartedAt !== null) return false;
    if (this.clock.now() >= this.state.deadline!) { this.finish(); return false; }
    this.state.currentQuestionStartedAt = this.clock.now();
    return true;
  }

  tick(): DrillState {
    if (this.state.status === "running" && this.clock.now() >= this.state.deadline!) this.finish();
    return this.state;
  }

  submit(raw: string): "ignored" | "accepted" | "expired" {
    if (this.state.status !== "running") return "expired";
    const now = this.clock.now();
    if (now >= this.state.deadline!) { this.finish(); return "expired"; }
    if (!raw.trim() || !this.state.currentQuestion || this.state.currentQuestionStartedAt === null) return "ignored";
    const parsed = Number(raw.trim());
    const userAnswer = Number.isFinite(parsed) ? parsed : null;
    const question = this.state.currentQuestion;
    const record: AnswerRecord = {
      timestamp: this.timestampNow(), question: question.text, operation: question.operation,
      operand1: question.operand1, operand2: question.operand2, correctAnswer: question.answer,
      userAnswer, timeTakenSec: Math.max(0, (now - this.state.currentQuestionStartedAt) / 1000),
      correctness: userAnswer !== null && userAnswer === question.answer,
    };
    this.state.records.push(record);
    if (record.correctness) this.state.score += 1;
    this.state.currentQuestion = generateQuestion(this.state.config, this.random);
    this.state.currentQuestionStartedAt = null;
    if (now >= this.state.deadline!) this.finish();
    return "accepted";
  }

  finish(): DrillState {
    if (this.state.status === "finished") return this.state;
    this.state.status = "finished";
    this.state.currentQuestionStartedAt = null;
    if (!this.saved) {
      this.saved = true;
      if (this.save) {
        try { this.save({ sessionName: this.state.config.sessionName, duration: this.state.config.duration, insights: [...this.state.records] }); }
        catch (error) { this.state.saveError = error instanceof Error ? error.message : "Session could not be saved."; }
      }
    }
    return this.state;
  }
}
