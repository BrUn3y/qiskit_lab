import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";

const manifest = JSON.parse(await readFile(
  fileURLToPath(new URL("../../../artifacts/report-smoke/fixtures/manifest.json", import.meta.url)), "utf8",
));

async function guard(context, page) {
  const external = [];
  const errors = [];
  await context.route(/^(https?|wss?):/, async route => {
    external.push(route.request().url());
    await route.abort("blockedbyclient");
  });
  page.on("pageerror", error => errors.push(error.message));
  return async () => {
    expect(external, "Reports must not request remote resources").toEqual([]);
    expect(errors, "Report JavaScript must run without errors").toEqual([]);
  };
}

async function download(page, name) {
  const ready = page.waitForEvent("download");
  await page.getByRole("link", { name, exact: false }).click();
  const result = await ready;
  expect(await result.failure()).toBeNull();
  return { filename: result.suggestedFilename(), bytes: await readFile(await result.path(), "utf8") };
}

test("charts and isolated controls work offline", async ({ context, page }) => {
  const check = await guard(context, page);
  await page.goto(pathToFileURL(manifest.interactive).href);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(manifest.data.title);
  await expect(page).toHaveTitle(`${manifest.data.title} | Qiskit Lab`);
  const first = page.locator(".publication").nth(0);
  const second = page.locator(".publication").nth(1);
  await expect(first.getByRole("img", { name: /measurement distribution/i })).toBeVisible();
  await expect(first.locator("svg rect.bar")).toHaveCount(16);
  await expect(first.locator("tbody tr")).toHaveCount(50);
  await expect(first.locator(".page-info")).toHaveText("64 states · Page 1 of 2");
  await expect(first.getByRole("button", { name: "Previous" })).toBeDisabled();
  await first.getByRole("button", { name: "Next" }).click();
  await expect(first.locator("tbody tr")).toHaveCount(14);
  await expect(first.locator(".page-info")).toHaveText("64 states · Page 2 of 2");
  await expect(first.getByRole("button", { name: "Next" })).toBeDisabled();
  await expect(second.locator("tbody tr")).toHaveCount(2);
  await first.getByLabel("Filter bitstrings").fill("111111");
  await expect(first.locator("tbody tr")).toHaveCount(1);
  await expect(first.locator("tbody")).toContainText("0.0481%");
  await expect(first.locator(".page-info")).toHaveText("1 states · Page 1 of 1");
  expect(Number(await first.locator("svg rect.bar").getAttribute("width"))).toBeCloseTo(530 / 2080, 10);
  await first.getByLabel("Chart value").selectOption("counts");
  await expect(first.locator("svg .axis-label")).toContainText("Counts");
  await expect(first.locator("svg rect.bar")).toHaveAttribute("width", "530");
  await expect(second.locator("svg .axis-label")).toContainText("Probability");
  await first.getByLabel("Filter bitstrings").fill("unobserved");
  await expect(first.locator("tbody")).toHaveText("No matching observed states.");
  await expect(first.locator("svg rect.bar")).toHaveCount(0);
  await first.getByLabel("Filter bitstrings").fill("");
  await expect(first.locator("tbody tr")).toHaveCount(50);
  await first.getByLabel("Chart value").selectOption("probability");
  await check();
});

test("complete downloads, source disclosures and embedded images work offline", async ({ context, page }, info) => {
  const check = await guard(context, page);
  await page.goto(pathToFileURL(manifest.interactive).href);
  const json = await download(page, "Download result JSON");
  expect(json.filename).toBe(`${manifest.data.report_filename.slice(0, -5)}-results.json`);
  expect(JSON.parse(json.bytes)).toEqual(manifest.data);
  const python = await download(page, "Download circuit.py");
  expect(python.filename).toBe("circuit.py");
  expect(python.bytes).toBe(manifest.source);
  expect((await download(page, "Download circuit.qasm")).bytes).toBe(manifest.qasm);
  const source = page.locator("#circuit-py");
  await expect(source.locator(".code-preview")).toBeVisible();
  await source.locator("summary").click();
  await expect(source.locator(".source-code")).toBeVisible();
  await expect(source.locator(".source-code")).toHaveText(manifest.source.trimEnd());
  await source.locator("summary").click();
  await page.getByText("Scientific dashboard", { exact: true }).click();
  const image = page.getByRole("img", { name: "Circuit and scientific results dashboard" });
  await expect(image).toBeVisible();
  expect(await image.evaluate(node => node.complete && node.naturalWidth === 2400)).toBe(true);
  expect(await page.locator(".publication").first().locator("svg")
    .evaluate(node => node.getBoundingClientRect().width)).toBeGreaterThan(200);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: info.outputPath("report.png"), fullPage: true });
  await check();
});

test("static charts, source disclosure and downloads work without JavaScript", async ({ browser }, info) => {
  const context = await browser.newContext({
    javaScriptEnabled: false, viewport: info.project.use.viewport, serviceWorkers: "block",
  });
  try {
    const page = await context.newPage();
    const check = await guard(context, page);
    await page.goto(pathToFileURL(manifest.interactive).href);
    const first = page.locator(".publication").first();
    await expect(first.getByRole("img", { name: "Measurement probabilities, publication 1" })).toBeVisible();
    await expect(first.locator("svg rect.bar")).toHaveCount(16);
    await expect(first.locator("tbody tr")).toHaveCount(50);
    await expect(first.getByLabel("Chart value")).toBeHidden();
    await expect(first.locator("noscript p")).toBeVisible();
    await expect(first.locator("noscript p")).toContainText("Showing the first 50 states");
    await page.locator("#circuit-py summary").click();
    await expect(page.locator("#circuit-py .source-code")).toBeVisible();
    expect(JSON.parse((await download(page, "Download result JSON")).bytes)).toEqual(manifest.data);
    await check();
  } finally {
    await context.close();
  }
});

test("failed and cancelled jobs never display invented charts or counts", async ({ context, page }) => {
  const check = await guard(context, page);
  for (const status of ["ERROR", "CANCELLED"]) {
    await page.goto(pathToFileURL(manifest[status]).href);
    await expect(page.getByRole("heading", { name: "No measurement results" })).toBeVisible();
    await expect(page.locator(".publication")).toHaveCount(0);
    await expect(page.locator("svg.distribution")).toHaveCount(0);
    const result = JSON.parse((await download(page, "Download result JSON")).bytes);
    expect(result.status).toBe(status);
    expect(result).not.toHaveProperty("counts");
  }
  await check();
});
