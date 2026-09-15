import { ConfigError, createDrillConfig } from "../lib/core";
import { DrillController } from "../lib/drill";
import {
  appendBrowserSession,
  importBrowserSessions,
  loadBrowserSessions,
  parseSessions,
  serializeSessions,
} from "../lib/storage";
import { renderAnalytics } from "./analytics";

const get = (id: string) => document.getElementById(id)!;
const input = (id: string) => get(id) as HTMLInputElement;
const setup = get("setup"),
  drill = get("drill"),
  results = get("results");
const answer = input("answer"),
  submit = get("submit-answer") as HTMLButtonElement;
let controller: DrillController | null = null;
let interval: number | undefined;
let frame: number | undefined;
let resultShown = false;

function cleanup() {
  window.clearInterval(interval);
  if (frame !== undefined) cancelAnimationFrame(frame);
  interval = frame = undefined;
}

function show(section: HTMLElement) {
  setup.hidden = section !== setup;
  drill.hidden = section !== drill;
  results.hidden = section !== results;
  get("analytics").hidden = section === drill;
  get("history-tools").hidden = section === drill;
}

function setReady(ready: boolean) {
  answer.disabled = submit.disabled = !ready;
  (get("negate-answer") as HTMLButtonElement).disabled = !ready;
}

function finishView() {
  if (!controller || resultShown) return;
  resultShown = true;
  cleanup();
  setReady(false);
  const state = controller.state;
  const total = state.records.length;
  get("results-summary").textContent =
    `${state.score} of ${total} correct (${total ? Math.round((state.score / total) * 100) : 0}%).`;
  get("save-status").textContent = state.saveError
    ? `This session was not saved. ${state.saveError} Download it below before starting again.`
    : "Session saved in this browser.";
  get("download-session").hidden = !state.saveError;
  show(results);
  renderAnalytics();
  get("results-title").focus();
}

function tick() {
  if (!controller) return;
  controller.tick();
  const remaining = Math.max(
    0,
    Math.ceil(((controller.state.deadline ?? 0) - performance.now()) / 1000),
  );
  get("timer").textContent =
    `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`;
  if (controller.state.status === "finished") finishView();
}

function presentQuestion() {
  if (!controller || controller.state.status !== "running") return;
  setReady(false);
  answer.value = "";
  get("question").textContent = controller.state.currentQuestion!.text;
  get("score").textContent = String(controller.state.score);
  // Two frames define the boundary after the new question has had a paint opportunity.
  // A hidden tab cannot arm an unseen question; its session deadline still runs.
  frame = requestAnimationFrame(() => {
    frame = requestAnimationFrame(() => {
      frame = undefined;
      if (controller?.armQuestion()) {
        setReady(true);
        answer.focus();
      }
      tick();
    });
  });
}

get("setup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (controller?.state.status === "running") return;
  get("setup-error").textContent = "";
  try {
    const range = (name: string): [number, number] => [
      Number(input(`${name}-min`).value),
      Number(input(`${name}-max`).value),
    ];
    const config = createDrillConfig({
      sessionName: input("session-name").value,
      duration: Number((get("duration") as HTMLSelectElement).value),
      operations: [
        ...document.querySelectorAll<HTMLInputElement>(
          'input[name="operation"]:checked',
        ),
      ].map((element) => element.value),
      addRange1: range("add1"),
      addRange2: range("add2"),
      mulRange1: range("mul1"),
      mulRange2: range("mul2"),
      allowNegativeAnswers: input("allow-negative").checked,
    });
    cleanup();
    controller = new DrillController(config, { save: appendBrowserSession });
    controller.start();
    resultShown = false;
    get("drill-status").textContent = "";
    show(drill);
    tick();
    presentQuestion();
    interval = window.setInterval(tick, 100);
  } catch (cause) {
    get("setup-error").textContent =
      cause instanceof ConfigError
        ? cause.message
        : "The drill could not start. Check your settings.";
  }
});

get("answer-form").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.repeat || event.isComposing))
    event.preventDefault();
});
get("answer-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!controller) return;
  const outcome = controller.submit(answer.value);
  if (outcome === "ignored") {
    if (!answer.value.trim())
      get("drill-status").textContent = "Type an answer first.";
    return;
  }
  get("drill-status").textContent = "";
  tick();
  if (outcome === "accepted" && controller.state.status === "running")
    presentQuestion();
});
get("negate-answer").addEventListener("click", () => {
  answer.value = answer.value.startsWith("-")
    ? answer.value.slice(1)
    : `-${answer.value}`;
  answer.focus();
});
get("restart").addEventListener("click", () => {
  cleanup();
  controller = null;
  show(setup);
  input("session-name").focus();
});

function download(text: string, filename: string) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

get("download-session").addEventListener("click", () => {
  if (!controller) return;
  download(
    serializeSessions([
      {
        sessionName: controller.state.config.sessionName,
        duration: controller.state.config.duration,
        insights: controller.state.records,
      },
    ]),
    "unsaved-session.json",
  );
});

get("import-file").addEventListener("change", async (event) => {
  const picker = event.currentTarget as HTMLInputElement,
    file = picker.files?.[0];
  if (!file) return;
  const status = get("import-status");
  picker.disabled = true;
  try {
    const text = await file.text();
    const count = parseSessions(text).length;
    importBrowserSessions(text);
    status.textContent = `Added ${count} session${count === 1 ? "" : "s"}.`;
    renderAnalytics();
  } catch (cause) {
    status.textContent = `Import failed: ${cause instanceof Error ? cause.message : "File could not be read."} Existing history was not changed.`;
  } finally {
    picker.value = "";
    picker.disabled = false;
  }
});
get("export-history").addEventListener("click", () => {
  try {
    download(serializeSessions(loadBrowserSessions()), "session_insights.json");
    get("import-status").textContent = "History export requested.";
  } catch (cause) {
    get("import-status").textContent =
      cause instanceof Error ? cause.message : "Export failed.";
  }
});
get("analytics-session").addEventListener("change", renderAnalytics);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) tick();
});
window.addEventListener("storage", () => {
  if (controller?.state.status !== "running") renderAnalytics();
});
window.addEventListener("pagehide", () => {
  cleanup();
  controller?.cancel();
  controller = null;
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    show(setup);
    setReady(false);
    renderAnalytics();
  }
});
renderAnalytics();
