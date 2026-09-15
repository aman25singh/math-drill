import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

const key = "math-drill.sessions";
const fixture = [
  {
    session_name: '<img src=x onerror="window.injected=true">',
    duration: 60,
    insights: [
      {
        timestamp: 2,
        question: "2 + 3",
        operation: "add",
        operand_1: 2,
        operand_2: 3,
        correct_answer: 5,
        user_answer: 5,
        time_taken_sec: 2,
        correctness: true,
      },
    ],
  },
  {
    session_name: '<img src=x onerror="window.injected=true">',
    duration: 30,
    insights: [],
  },
  {
    session_name: "zeros",
    duration: 0,
    insights: [
      {
        timestamp: 1,
        question: "0 + 0",
        question_type: "add",
        operand_1: 0,
        operand_2: 0,
        correct_answer: 0,
        user_answer: 0,
        time_taken_sec: 1,
        correctness: true,
      },
    ],
  },
];

async function start(page: Page) {
  await page.locator("#duration").selectOption("30");
  await page.getByRole("button", { name: "Start drill", exact: true }).click();
  await expect(page.locator("#answer")).toBeEnabled();
}

test("keyboard drill, held Enter, expiry, persistence and restart", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.clock.install();
  await page.goto("/");
  await expect(page.locator("#analytics-empty")).toContainText(
    "Complete a drill",
  );
  await page.screenshot({
    path: test.info().outputPath("setup.png"),
    fullPage: true,
  });
  await start(page);
  await expect(page.locator("#answer")).toBeFocused();
  await page.screenshot({
    path: test.info().outputPath("drill.png"),
    fullPage: true,
  });
  await page.keyboard.press("Enter");
  await expect(page.locator("#drill-status")).toHaveText(
    "Type an answer first.",
  );
  const question = await page.locator("#question").innerText();
  const [a, op, b] = question.split(" ");
  const correct =
    op === "+"
      ? Number(a) + Number(b)
      : op === "-"
        ? Number(a) - Number(b)
        : op === "×"
          ? Number(a) * Number(b)
          : Number(a) / Number(b);
  await page.locator("#answer").fill(String(correct));
  await page.keyboard.down("Enter");
  await expect(page.locator("#score")).toHaveText("1");
  await expect(page.locator("#answer")).toBeEnabled();
  await page.locator("#answer").fill("123");
  await page.keyboard.down("Enter"); // OS key-repeat: must not consume this question.
  await page.keyboard.up("Enter");
  await expect(page.locator("#answer")).toHaveValue("123");
  await page.clock.fastForward(31000);
  await expect(page.locator("#results")).toBeVisible();
  await expect(page.locator("#results-summary")).toHaveText(
    "1 of 1 correct (100%).",
  );
  const history = await page.evaluate(
    (k) => JSON.parse(localStorage.getItem(k)!),
    key,
  );
  expect(history).toHaveLength(1);
  expect(history[0].insights).toHaveLength(1);
  await page.reload();
  await expect(page.locator("#summary-metrics")).toContainText("100.0%");
  await expect(page.locator("#sample-note")).toContainText("Fewer than 20");
  await start(page);
  await page.clock.fastForward(31000);
  await page.getByRole("button", { name: "Start another drill" }).click();
  await expect(page.locator("#session-name")).toBeFocused();
  expect(
    await page.evaluate(
      (k) => JSON.parse(localStorage.getItem(k)!).length,
      key,
    ),
  ).toBe(2);
  expect(errors).toEqual([]);
});

test("imports, separates repeated names, handles empty/zero data and exports backup", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByText("Import a backup or old desktop history", { exact: true })
    .click();
  await page.locator("#import-file").setInputFiles({
    name: "synthetic.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(fixture)),
  });
  await expect(page.locator("#import-status")).toHaveText("Added 3 sessions.");
  await expect(page.locator("#analytics-session option")).toHaveCount(4);
  await expect(page.locator("#analytics img")).toHaveCount(0);
  await expect(page.locator("#summary-metrics")).toContainText("100.0%");
  await expect(page.locator("#operation-view")).toContainText("1.50 s");
  await expect(page.locator("#sequence-view tbody tr")).toHaveCount(2);
  await page.locator("#analytics-session").selectOption("1");
  await expect(page.locator("#analytics-empty")).toContainText(
    "No answered questions",
  );
  await page.locator("#analytics-session").selectOption("2");
  await expect(page.locator("#digit-view")).toContainText("No operands");
  await expect(page.locator("#summary-metrics")).toContainText("Unavailable");
  await page.locator("#analytics-session").selectOption("");
  await page.screenshot({
    path: test.info().outputPath("analytics.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const before = await page.evaluate((k) => localStorage.getItem(k), key);
  await page.locator("#import-file").setInputFiles({
    name: "bad.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify([...fixture, { invalid: true }])),
  });
  await expect(page.locator("#import-status")).toContainText("Import failed");
  expect(await page.evaluate((k) => localStorage.getItem(k), key)).toBe(before);
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export all history as JSON" })
    .click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("session_insights.json");
  const exported = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(exported).toHaveLength(3);
  expect(exported[2].insights[0].operation).toBe("add");
  expect(JSON.stringify(exported)).not.toContain("question_type");
  await page.locator("#import-file").setInputFiles({
    name: "repeat.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(exported)),
  });
  await expect(page.locator("#import-status")).toHaveText("Added 3 sessions.");
  await expect(page.locator("#analytics-session option")).toHaveCount(7);
});

test("leaving a drill discards it and returning cannot revive callbacks", async ({
  page,
}) => {
  await page.clock.install();
  await page.goto("/");
  await start(page);
  await page.goto("about:blank");
  await page.goBack();
  await expect(page.locator("#setup")).toBeVisible();
  await page.clock.fastForward(31000);
  expect(await page.evaluate((k) => localStorage.getItem(k), key)).toBeNull();
});

test("storage failures keep a downloadable result", async ({ page }) => {
  await page.clock.install();
  await page.addInitScript(() => {
    Storage.prototype.setItem = () => {
      throw new DOMException("Storage full", "QuotaExceededError");
    };
  });
  await page.goto("/");
  await start(page);
  await page.locator("#answer").fill("not a number");
  await page.keyboard.press("Enter");
  await page.clock.fastForward(31000);
  await expect(page.locator("#save-status")).toContainText("not saved");
  const event = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download unsaved session" }).click();
  const data = JSON.parse(
    await readFile((await (await event).path())!, "utf8"),
  );
  expect(data[0].insights[0]).toMatchObject({
    user_answer: null,
    correctness: false,
  });
});
