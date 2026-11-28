import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("product tour supports keyboard selection and real captures", async ({ page }) => {
  await page.goto("/products", { waitUntil: "networkidle" });
  const documents = page.getByRole("tab", { name: "Document control" });
  await documents.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Risks & opportunities" })).toBeFocused();
  await expect(page.getByRole("tabpanel")).toHaveAccessibleName("Risks & opportunities");
  await expect(page.getByRole("tabpanel").getByRole("img")).toHaveJSProperty("naturalWidth", 1192);
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Corrective actions" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel")).toContainText("DEMO-CAPA-001");
  await expect(page.getByRole("link", { name: "Open the full capture" })).toHaveAttribute("href", "/brand/product/capa.png");
  await page.keyboard.press("Home");
  await expect(documents).toBeFocused();
  await expect(documents).toHaveAttribute("aria-selected", "true");
});

test("demo enquiry validates seats and produces a reviewable email and local brief", async ({ page }) => {
  await page.goto("/products#demo", { waitUntil: "networkidle" });
  const email = page.getByRole("link", { name: "Prepare demo email", exact: true });
  const downloadButton = page.getByRole("button", { name: "Download brief" });
  await page.getByRole("spinbutton", { name: "Team seats" }).fill("0");
  await expect(email).toHaveAttribute("aria-disabled", "true");
  await expect(email).not.toHaveAttribute("href");
  await expect(downloadButton).toBeDisabled();
  await expect(page.locator(".market-enquiry-form").getByRole("alert")).toContainText("1 to 10,000");
  await page.getByRole("spinbutton", { name: "Team seats" }).fill("42");
  await page.getByRole("textbox", { name: "Company" }).fill("Example & Partners");
  await page.getByRole("combobox", { name: "Main priority" }).selectOption("documents");
  await page.getByRole("checkbox", { name: "ISO 9001 In preparation", exact: true }).check();
  await expect(downloadButton).toBeEnabled();
  const mailto = new URL((await email.getAttribute("href"))!);
  expect(mailto.protocol).toBe("mailto:");
  expect(mailto.pathname).toBe("Demo@invperfectmatch.com");
  expect([...mailto.searchParams.keys()]).toEqual(["subject", "body"]);
  const body = mailto.searchParams.get("body")!;
  expect(body).toContain("Company: Example & Partners");
  expect(body).toContain("Team seats: 42");
  expect(body).toContain("Main priority: Documents");
  expect(body).toContain("ISO 9001 (In preparation)");
  const pending = page.waitForEvent("download");
  await downloadButton.click();
  const download = await pending;
  expect(download.suggestedFilename()).toBe("perfect-match-qms-demo-brief.txt");
  expect(await download.failure()).toBeNull();
  expect(await readFile((await download.path())!, "utf8")).toBe(body);
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByRole("textbox", { name: "Company" })).toHaveValue("");
  await expect(page.getByRole("spinbutton", { name: "Team seats" })).toHaveValue("25");
});

test("compact product navigation and FAQ work at 320 pixels", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/products", { waitUntil: "networkidle" });
  await page.getByRole("navigation", { name: "Product navigation" }).getByRole("link", { name: "Security", exact: true }).click();
  await expect(page).toHaveURL(/#security$/);
  await expect(page.getByRole("heading", { name: "Your quality data. Clear boundaries." })).toBeInViewport();
  const question = page.locator("summary").filter({ hasText: "Is a seat the same as approval authority?" });
  await question.focus();
  await page.keyboard.press("Enter");
  await expect(question.locator("..")).toHaveAttribute("open", "");
  await expect(question.locator("..")).toContainText("Seats describe team capacity");
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});

test("plans explain the company allowance and carry it into the downloadable brief", async ({ page }) => {
  await page.goto("/products");
  await page.getByRole("navigation", { name: "Product navigation" }).getByRole("link", { name: "Plans & storage" }).click();
  await expect(page).toHaveURL(/\/products\/plans$/);
  await expect(page.getByRole("heading", { name: "Plans & included storage" })).toBeVisible();
  const capacity = page.getByRole("region", { name: "Proposed capacity per company" });
  await expect(capacity.getByRole("listitem")).toHaveCount(4);
  for (const amount of ["5,000 MB", "25,000 MB", "100,000 MB", "250,000 MB"]) {
    await expect(capacity.getByText(amount, { exact: true })).toBeVisible();
  }
  const terms = page.getByRole("region", { name: "How the allowance works" });
  for (const statement of ["retained revisions", "Managed backups", "80% and 90%", "No automatic overage charges"]) {
    await expect(terms).toContainText(statement);
  }
  await capacity.getByRole("link", { name: "Discuss Basic" }).click();
  await expect(page).toHaveURL(/\?plan=basic#demo$/);
  const plan = page.getByRole("combobox", { name: "Plan of interest" });
  await expect(plan).toHaveValue("basic");
  await expect(page.getByRole("spinbutton", { name: "Team seats" })).toHaveValue("3");
  await plan.selectOption("professional");
  const email = page.getByRole("link", { name: "Prepare demo email" });
  const body = new URL((await email.getAttribute("href"))!).searchParams.get("body")!;
  expect(body).toContain("100,000 MB per company");
  expect(body).toContain("Final capacity, seats, ISO editions and price");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download brief" }).click();
  expect(await readFile((await (await downloaded).path())!, "utf8")).toBe(body);
  await page.goto("/products?plan=unlimited#demo");
  await expect(plan).toHaveCount(0);
});

test("plan disclosure is accessible in both themes at a narrow viewport", async ({ page }, info) => {
  await page.setViewportSize({ width: 320, height: 760 });
  await page.goto("/products/plans");
  await expect(page.getByRole("heading", { name: "Plans & included storage" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("spinbutton", { name: "Estimated retained files (MB)" }).fill("25000");
  await page.getByRole("button", { name: "Compare my needs" }).press("Enter");
  await expect(page.getByRole("heading", { name: "Team fits your storage estimate" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  for (const dark of [false, true]) {
    if (dark) {
      await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    }
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
    expect(result.violations).toEqual([]);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath("company-plans-mobile-dark.png"), fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath("company-plans-desktop.png"), fullPage: true });
  await page.getByRole("region", { name: "Find a plan for your company" }).screenshot({ path: info.outputPath("company-plan-estimate.png") });
});

test("plan guide explains seat and storage gaps and preserves the estimate in the brief", async ({ page }) => {
  await page.goto("/products/plans", { waitUntil: "networkidle" });
  const guide = page.getByRole("region", { name: "Find a plan for your company" });
  await guide.getByRole("spinbutton", { name: "People who need access" }).fill("6");
  const storage = guide.getByRole("spinbutton", { name: "Estimated retained files (MB)" });
  const compare = guide.getByRole("button", { name: "Compare my needs" });
  await storage.fill("5000");
  await compare.press("Enter");
  await expect(guide.getByRole("heading", { name: "Basic fits your storage estimate" })).toBeVisible();
  await expect(guide).toContainText("3 additional seats");
  await storage.fill("250001");
  await expect(guide.getByRole("link", { name: "Continue to demo brief" })).toHaveCount(0);
  await compare.press("Enter");
  await expect(guide.getByRole("heading", { name: "You need a custom storage quote" })).toBeVisible();
  await guide.getByRole("link", { name: "Continue to demo brief" }).click();
  await expect(page.getByRole("combobox", { name: "Plan of interest" })).toHaveValue("enterprise");
  await expect(page.getByRole("spinbutton", { name: "Team seats" })).toHaveValue("6");
  await expect(page.getByRole("spinbutton", { name: "Estimated storage (MB)" })).toHaveValue("250001");
  const href = (await page.getByRole("link", { name: "Prepare demo email" }).getAttribute("href"))!;
  const brief = new URL(href).searchParams.get("body");
  expect(brief).toContain("Estimated retained storage: 250,001 MB per company.");
  expect(brief).toContain("Additional storage to quote: 1 MB.");
  expect(brief).toContain("one-time implementation costs separately");
});
