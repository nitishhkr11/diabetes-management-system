import { test, expect } from "@playwright/test";
import { resolve } from "node:path";

test("public landing page explains scope and navigates to education", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Understand the science/i })).toBeVisible();
  await expect(page.getByText(/not a diagnostic tool/i).first()).toBeVisible();
  await page.getByRole("link", { name: /Learn about diabetes/i }).click();
  await expect(page.getByRole("heading", { name: /Diabetes, explained with care/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Type 1 diabetes" })).toBeVisible();
});

test("concept illustration responds to educational state selection", async ({ page }) => {
  await page.goto("/simulation");
  await page.getByRole("button", { name: "Resistance" }).click();
  await expect(page.getByRole("heading", { name: "Cells respond less effectively" })).toBeVisible();
  await expect(page.getByText(/illustrative labels only/i)).toBeVisible();
});

test("theme choice persists through navigation", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.setItem("theme", "light"));
  await page.reload();
  await expect(page.getByRole("heading", { name: /Understand the science/i })).toBeVisible();
  await page.screenshot({ path: resolve(process.cwd(), "../docs/screenshots/website_home_light.png"), fullPage: true });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.screenshot({ path: resolve(process.cwd(), "../docs/screenshots/website_home_dark.png"), fullPage: true });
  await page.goto("/learn");
  await expect(page.locator("html")).toHaveClass(/dark/);
});

test("narrow layout does not overflow horizontally", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/learn");
  const sizes = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: document.documentElement.clientWidth }));
  expect(sizes.body).toBeLessThanOrEqual(sizes.viewport + 1);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
});

test("anonymous assessment uses only a marked synthetic demo", async ({ page }) => {
  await page.goto("/estimate");
  await expect(page.getByText(/Example values · not user data/i)).toBeVisible();
  await page.getByRole("button", { name: /Review model output/i }).click();
  await expect(page.getByText(/model score · not a personal clinical probability/i)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/not a personal medical probability/i)).toBeVisible();
});

test("report upload is offered only inside the authenticated workflow", async ({ page }) => {
  await page.goto("/estimate");
  await expect(page.getByRole("heading", { name: "Add values from a medical report" })).toBeVisible();
  await expect(page.getByText(/Sign in to upload a report/i)).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveCount(0);
});

test("model pages and estimator interactions do not trigger React suspension errors", async ({ page }) => {
  const runtimeErrors: string[] = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") runtimeErrors.push(message.text());
  });
  for (const route of ["/reliability", "/model-lab", "/estimate"]) {
    await page.goto(route);
    await expect(page.getByRole("main")).toBeVisible();
    if (route === "/reliability") await expect(page.getByRole("heading", { name: "Interactive release charts" })).toBeVisible({ timeout: 30_000 });
    if (route === "/estimate") {
      await page.getByRole("button", { name: /Review model output/i }).click();
      await expect(page.getByText(/Model estimate: (positive|negative) class under the selected benchmark threshold/i)).toBeVisible({ timeout: 60_000 });
      await expect(page.getByRole("heading", { name: "Laboratory report findings" })).toBeVisible();
    }
  }
  expect(runtimeErrors).toEqual([]);
});

test("calibration, confusion matrix, ROC, and SHAP tooltips show saved values", async ({ page, request }) => {
  const response = await request.get("http://127.0.0.1:8000/api/v1/evaluation/chart-data");
  expect(response.ok()).toBeTruthy();
  const source = await response.json();
  expect(source.available).toBe(true);
  await page.goto("/reliability");
  await expect(page.getByTestId("calibration-chart")).toBeVisible();

  const calibrationBin = source.calibration_bins[source.calibration_bins.length - 1];
  await page.getByTestId("calibration-chart").locator("svg circle").last().hover();
  await expect(page.getByRole("status").filter({ hasText: "Mean predicted score" })).toContainText(calibrationBin.mean_predicted.toFixed(6));
  await expect(page.getByRole("status").filter({ hasText: "Mean predicted score" })).toContainText(String(calibrationBin.count));

  const matrixCell = page.getByRole("button", { name: /Actual Negative; predicted Negative/ });
  await matrixCell.focus();
  await expect(page.getByRole("tooltip").filter({ hasText: `count ${source.confusion_matrix.actual_negative.predicted_negative}` })).toBeVisible();

  const rocSvg = page.getByTestId("roc-chart").getByRole("application");
  await rocSvg.focus();
  await page.keyboard.press("ArrowRight");
  const rocTooltip = page.getByRole("status").filter({ hasText: "False-positive rate" });
  await expect(rocTooltip).toContainText(source.roc_points[0].false_positive_rate.toFixed(6));
  const rocBox = await rocSvg.boundingBox();
  if (!rocBox) throw new Error("ROC chart has no visible drawing area.");
  await page.mouse.move(rocBox.x + rocBox.width * 0.55, rocBox.y + rocBox.height * 0.5);
  await expect(rocTooltip).toBeVisible();
  const hoverText = await rocTooltip.textContent() ?? "";
  const hoveredRocPoint = source.roc_points.find((point: { false_positive_rate: number; true_positive_rate: number; threshold: number | null }) =>
    hoverText.includes(point.false_positive_rate.toFixed(6)) && hoverText.includes(point.true_positive_rate.toFixed(6)) &&
    (point.threshold === null ? hoverText.includes("above maximum score") : hoverText.includes(point.threshold.toFixed(6))));
  if (!hoveredRocPoint) throw new Error("ROC tooltip does not contain values from the active release.");

  const shapRow = source.shap_importance[0];
  await page.getByTestId("shap-chart").locator(".recharts-rectangle").first().hover();
  await expect(page.getByRole("status").filter({ hasText: "Mean absolute SHAP" })).toContainText(shapRow.feature);
  await expect(page.getByRole("status").filter({ hasText: "Mean absolute SHAP" })).toContainText(shapRow.mean_abs_shap.toFixed(6));

  await page.getByRole("button", { name: /Switch to dark theme/i }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.getByTestId("calibration-chart")).toBeVisible();
  await matrixCell.hover();
  await expect(page.getByRole("tooltip").filter({ hasText: `count ${source.confusion_matrix.actual_negative.predicted_negative}` })).toBeVisible();
  const darkCalibrationTooltip = page.getByRole("status").filter({ hasText: "Mean predicted score" });
  await page.getByTestId("calibration-chart").locator("svg circle").last().hover();
  await expect(darkCalibrationTooltip).toContainText(calibrationBin.mean_predicted.toFixed(6));
  const darkRocSvg = page.getByTestId("roc-chart").getByRole("application");
  await darkRocSvg.scrollIntoViewIfNeeded();
  const darkRocBox = await darkRocSvg.boundingBox();
  if (!darkRocBox) throw new Error("Dark-theme ROC chart has no visible drawing area.");
  await page.mouse.move(darkRocBox.x + darkRocBox.width * 0.55, darkRocBox.y + darkRocBox.height * 0.5);
  await expect(rocTooltip).toBeVisible();
  const darkRocText = await rocTooltip.textContent() ?? "";
  const darkRocPoint = source.roc_points.find((point: { false_positive_rate: number; true_positive_rate: number; threshold: number | null }) =>
    darkRocText.includes(point.false_positive_rate.toFixed(6)) && darkRocText.includes(point.true_positive_rate.toFixed(6)) &&
    (point.threshold === null ? darkRocText.includes("above maximum score") : darkRocText.includes(point.threshold.toFixed(6))));
  if (!darkRocPoint) throw new Error("Dark-theme ROC tooltip does not contain values from the active release.");
  const darkShapTooltip = page.getByRole("status").filter({ hasText: "Mean absolute SHAP" });
  await page.getByTestId("shap-chart").locator(".recharts-rectangle").first().hover();
  await expect(darkShapTooltip).toContainText(shapRow.feature);
  await expect(darkShapTooltip).toContainText(shapRow.mean_abs_shap.toFixed(6));
  await page.setViewportSize({ width: 390, height: 844 });
  const sizes = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: document.documentElement.clientWidth }));
  expect(sizes.body).toBeLessThanOrEqual(sizes.viewport + 1);
});

test("interactive chart fallback, themes, and mobile layout remain usable", async ({ page }) => {
  await page.route("**/api/dms/api/v1/evaluation/chart-data", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ available: false, reason: "Interactive chart data do not match this release." }),
  }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/reliability");
  await expect(page.getByText("Interactive chart data do not match this release.")).toBeVisible();
  await page.getByRole("button", { name: /Switch to dark theme/i }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  const width = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: document.documentElement.clientWidth }));
  expect(width.body).toBeLessThanOrEqual(width.viewport + 1);
});

test("authentication gates retain a safe return route for sign in", async ({ page }) => {
  await page.goto("/history");
  await expect(page).toHaveURL(/\/auth\/login\?next=%2Fhistory/);
  await page.goto("/estimate");
  await expect(page.getByRole("link", { name: /Sign in to continue/i })).toHaveAttribute("href", "/auth/login?next=%2Festimate");
});
