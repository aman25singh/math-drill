import { describe, expect, it } from "vitest";
import { createDrillConfig, type RandomSource } from "./core";
import { DrillController } from "./drill";
import type { SessionRecord } from "./storage";

class FakeClock { value = 0; now = () => this.value; }
const random: RandomSource = { choice: <T>(items: readonly T[]) => items[0], randint: (low) => low };
const config = () => createDrillConfig({ sessionName: "test", duration: 10, operations: ["add"], addRange1: [2, 2], addRange2: [3, 3] });

describe("DrillController", () => {
  it("ignores blanks and records one answered question", () => {
    const clock = new FakeClock(); const saved: SessionRecord[] = [];
    const drill = new DrillController(config(), { clock, random, timestampNow: () => 123, save: (s) => saved.push(s) });
    drill.start(); drill.armQuestion();
    expect(drill.submit(" ")).toBe("ignored");
    clock.value = 1200; expect(drill.submit("5")).toBe("accepted");
    expect(drill.state.score).toBe(1); expect(drill.state.records[0].timeTakenSec).toBe(1.2);
    drill.finish(); expect(saved).toHaveLength(1); expect(saved[0].insights).toHaveLength(1);
  });

  it("rejects exact expiry, duplicate submits, and saves only once", () => {
    const clock = new FakeClock(); let saves = 0;
    const drill = new DrillController(config(), { clock, random, save: () => { saves += 1; } });
    drill.start(); drill.armQuestion(); clock.value = 10_000;
    expect(drill.submit("5")).toBe("expired");
    expect(drill.submit("5")).toBe("expired"); drill.finish(); expect(saves).toBe(1);
  });

  it("does not start response timing until the question is armed", () => {
    const clock = new FakeClock(); const drill = new DrillController(config(), { clock, random });
    drill.start(); clock.value = 5000; expect(drill.submit("5")).toBe("ignored");
    drill.armQuestion(); clock.value = 5500; expect(drill.submit("5")).toBe("accepted");
    expect(drill.state.records[0].timeTakenSec).toBe(0.5);
  });

  it("keeps results when persistence fails", () => {
    const clock = new FakeClock(); const drill = new DrillController(config(), { clock, random, save: () => { throw new Error("storage full"); } });
    drill.start(); drill.armQuestion(); drill.submit("5"); drill.finish();
    expect(drill.state.status).toBe("finished"); expect(drill.state.records).toHaveLength(1); expect(drill.state.saveError).toBe("storage full");
  });
});
