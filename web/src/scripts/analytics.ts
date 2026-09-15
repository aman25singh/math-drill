import { OPERATIONS } from "../lib/core";
import {
  computeInsightFlags,
  digitDifficulty,
  flattenSessions,
  NoDataError,
  responseTimeSeries,
  sessionSummary,
} from "../lib/features";
import { loadBrowserSessions } from "../lib/storage";

const labels = {
  add: "Addition",
  sub: "Subtraction",
  mul: "Multiplication",
  div: "Division",
};
const seconds = (value: number) =>
  Number.isFinite(value) ? `${value.toFixed(2)} s` : "Unavailable";

function table(target: HTMLElement, headings: string[], rows: string[][]) {
  const element = document.createElement("table");
  const head = element.createTHead().insertRow();
  headings.forEach((text) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = text;
    head.append(cell);
  });
  const body = element.createTBody();
  rows.forEach((row) => {
    const tr = body.insertRow();
    row.forEach((text) => {
      tr.insertCell().textContent = text;
    });
  });
  target.replaceChildren(element);
}

export function renderAnalytics() {
  const get = (id: string) => document.getElementById(id)!;
  const selector = get("analytics-session") as HTMLSelectElement;
  const empty = get("analytics-empty"),
    content = get("analytics-content"),
    error = get("analytics-error");
  error.textContent = "";
  content.hidden = true;
  empty.hidden = true;
  try {
    const sessions = loadBrowserSessions();
    const selection = selector.value;
    selector.replaceChildren(new Option("All sessions", ""));
    sessions.forEach((session, index) => {
      selector.add(
        new Option(
          `#${index + 1}: ${session.sessionName || "Unnamed"} (${session.duration}s, ${session.insights.length} answers)`,
          String(index),
        ),
      );
    });
    selector.value =
      selection !== "" && Number(selection) < sessions.length ? selection : "";
    const all = flattenSessions(sessions);
    const rows =
      selector.value === ""
        ? all
        : all.filter((row) => row.sessionIndex === Number(selector.value));
    if (!rows.length) {
      empty.textContent = sessions.length
        ? "No answered questions in this selection yet."
        : "Complete a drill or import history to see your insights.";
      empty.hidden = false;
      return;
    }
    content.hidden = false;
    const flagged = computeInsightFlags(rows),
      summary = sessionSummary(rows);
    const metrics = [
      [String(summary.total), "Answered"],
      [String(summary.correct), "Correct"],
      [`${(summary.accuracy * 100).toFixed(1)}%`, "Accuracy"],
      [seconds(summary.avgTimeSec), "Average response"],
      [
        Number.isFinite(summary.questionsPerMin)
          ? summary.questionsPerMin.toFixed(2)
          : "Unavailable",
        "Questions / minute",
      ],
      [String(summary.sessions), "Sessions with answers"],
    ];
    const cards = metrics.map(([value, label]) => {
      const card = document.createElement("div"),
        number = document.createElement("strong"),
        caption = document.createElement("span");
      number.textContent = value;
      caption.textContent = label;
      card.append(number, caption);
      return card;
    });
    get("summary-metrics").replaceChildren(...cards);
    get("sample-note").textContent =
      rows.length < 20
        ? "Fewer than 20 answers: these averages are early observations, not established weaknesses. Keep practising."
        : "Digit groups can overlap. Compare time together with error rate and sample count; groups under 5 answers are marked as small samples.";
    try {
      table(
        get("digit-view"),
        ["Digit", "Average time", "Error rate", "Answers"],
        digitDifficulty(flagged).map((d) => [
          String(d.digit),
          seconds(d.avgTime),
          `${(d.errorRate * 100).toFixed(1)}%`,
          `${d.n}${d.n < 5 ? " (small sample)" : ""}`,
        ]),
      );
    } catch (cause) {
      if (!(cause instanceof NoDataError)) throw cause;
      get("digit-view").textContent =
        "No operands containing digits 1–9 in this selection.";
    }
    table(
      get("operation-view"),
      ["Operation", "Average time", "Answers"],
      OPERATIONS.flatMap((operation) => {
        const group = rows.filter((row) => row.operation === operation);
        return group.length
          ? [
              [
                labels[operation],
                seconds(
                  group.reduce((sum, row) => sum + row.timeTakenSec, 0) /
                    group.length,
                ),
                String(group.length),
              ],
            ]
          : [];
      }),
    );
    table(
      get("sequence-view"),
      ["Answer", "Question", "Time", "5-answer average", "Result"],
      responseTimeSeries(rows).map((row) => [
        String(row.questionNumber),
        row.question,
        seconds(row.timeTakenSec),
        seconds(row.rolling),
        row.correctness ? "Correct" : "Incorrect",
      ]),
    );
  } catch (cause) {
    content.hidden = true;
    error.textContent =
      cause instanceof Error ? cause.message : "History could not be loaded.";
  }
}
