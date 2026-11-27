import { test, expect } from "@playwright/test";
import { resolve } from "node:path";

test("homepage explains Indian diabetes screening and navigates to both pathways", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Understand Your Diabetes Risk/i })).toBeVisible();
  await expect(page.getByText(/Not a clinical diagnosis/i).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Check Your Risk/i }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Understand My Test Results/i })).toBeVisible();

  await page.getByRole("link", { name: /Understand Diabetes/i }).first().click();
  await expect(page.getByRole("heading", { name: /Diabetes, explained with care/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Type 1 diabetes" })).toBeVisible();
});

test("Pathway A: visitor completes MDRF-IDRS screening wizard and sees score & category", async ({ page }) => {
  await page.goto("/screening?mode=idrs");
  await expect(page.getByRole("heading", { name: /MDRF Indian Diabetes Risk Score/i })).toBeVisible();

  await page.getByLabel("Age (years)").fill("42");
  await page.getByLabel("Sex (for waist threshold)").selectOption("female");
  await page.getByLabel("Waist Circumference", { exact: true }).fill("85");
  await page.getByRole("button", { name: /Next: Activity & Family/i }).click();

  await page.getByLabel("Physical Activity Level").selectOption("moderate");
  await page.getByLabel("Family History of Diabetes (Parents)").selectOption("one_parent");
  await page.getByRole("button", { name: /Review Inputs/i }).click();

  await page.getByRole("button", { name: /Calculate MDRF-IDRS/i }).click();
  const resultRegion = page.getByRole("region", { name: /MDRF-IDRS screening result/i });
  await expect(resultRegion).toBeVisible({ timeout: 15_000 });
  await expect(resultRegion).toContainText("50");
  await expect(resultRegion).toContainText(/Moderate risk/i);
  await expect(resultRegion).toContainText(/not a diabetes diagnosis/i);
});

test("Pathway B: visitor interprets lab values with clinical confirmation & pregnancy safeguards", async ({ page }) => {
  await page.goto("/screening?mode=lab");
  await expect(page.getByRole("heading", { name: /Interpret Blood-Test Results/i })).toBeVisible();

  await page.getByRole("button", { name: /Next: Enter Lab Values/i }).click();
  await page.getByLabel("HbA1c (%)").fill("6.8");
  await page.getByRole("button", { name: /Interpret Test Results/i }).click();

  const labRegion = page.getByRole("region", { name: /Laboratory interpretation result/i });
  await expect(labRegion).toBeVisible({ timeout: 15_000 });
  await expect(labRegion).toContainText(/Diabetes range/i);
  await expect(labRegion).toContainText(/confirmation/i);

  // Test pregnancy safeguard
  await page.getByRole("button", { name: /Back/i }).click();
  await page.getByLabel(/Currently pregnant/i).check();
  await page.getByRole("button", { name: /View Pregnancy Guidance/i }).click();
  await expect(labRegion).toContainText(/Pregnancy/i);
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
  await expect(page.getByRole("heading", { name: /Understand Your Diabetes Risk/i })).toBeVisible();
  await page.screenshot({ path: resolve(process.cwd(), "../docs/screenshots/website_home_light.png"), fullPage: true });
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.screenshot({ path: resolve(process.cwd(), "../docs/screenshots/website_home_dark.png"), fullPage: true });
  await page.goto("/learn");
  await expect(page.locator("html")).toHaveClass(/dark/);
});

test("narrow mobile layout does not overflow horizontally", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of ["/", "/screening", "/learn", "/about"]) {
    await page.goto(route);
    const sizes = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: document.documentElement.clientWidth }));
    expect(sizes.body).toBeLessThanOrEqual(sizes.viewport + 1);
  }
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
});

test("authentication gates retain a safe return route for sign in", async ({ page }) => {
  await page.goto("/history");
  await expect(page).toHaveURL(/\/auth\/login\?next=%2Fhistory/);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/auth\/login\?next=%2Fdashboard/);
});
