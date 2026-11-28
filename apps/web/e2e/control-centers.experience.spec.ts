import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const preview = "/design-studio/control-centers";
const tenant = "10000000-0000-4000-8000-000000000001";
const user = "20000000-0000-4000-8000-000000000001";

async function useCompany(page: Page, role: "owner" | "member") {
  await page.route("**/api/identity/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/identity", "");
    const ok = (json: unknown) => route.fulfill({ json, headers: { "X-Tenant-ID": tenant } });
    if (path === "/auth/me") return ok({
      id: user, display_name: "Synthetic account", email: "account@example.invalid", current_tenant_id: tenant,
    });
    if (path === "/auth/tenants") return ok([{ id: tenant, name: "Synthetic company", slug: "synthetic", role }]);
    if (path === "/qms-access/active-capabilities") return ok({ capabilities: [] });
    if (path.startsWith("/organization/")) return ok([]);
    if (path === "/action-center") return ok({
      scope: "mine", generated_at: "2026-11-27T12:00:00Z",
      summary: { total: 0, overdue: 0, due_soon: 0, unassigned: 0, by_source: {} }, items: [],
    });
    return route.fulfill({ status: 404, json: {} });
  });
}

test("company owners can open existing administration screens and inspect their own account", async ({ page }) => {
  await useCompany(page, "owner");
  await page.goto("/#company-control-heading");
  await expect(page.getByRole("heading", { name: "Company control" })).toBeVisible();
  await page.getByRole("button", { name: /Organization structure/ }).click();
  await expect(page).toHaveURL(/#organization-workspace-heading$/);
  await page.getByRole("link", { name: "My profile", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My profile", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Account details" }).getByText("account@example.invalid")).toBeVisible();
  await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("link", { name: "Company control", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "Use dark theme" })).toBeChecked();
});

test("a collaborator can see their profile and a direct hash does not open company control", async ({ page }) => {
  await useCompany(page, "member");
  await page.goto("/#company-control-heading");
  const nav = page.getByRole("navigation", { name: "QMS modules" });
  await expect(nav.getByRole("link", { name: "Company control", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Company control" })).toHaveCount(0);
  await nav.getByRole("link", { name: "My profile", exact: true }).click();
  await expect(page.getByRole("region", { name: "Account details" }).getByText("member", { exact: true })).toBeVisible();
});

test("the explicitly enabled design preview supports employee, training, branding and operations review", async ({ page }, info) => {
  const response = await page.goto(preview);
  if (process.env.PMQMS_CONTROL_PREVIEW !== "1") {
    expect(response?.status()).toBe(404);
    return;
  }
  expect(response?.ok()).toBe(true);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({ path: info.outputPath("people-preview.png"), fullPage: true });
  await page.getByRole("button", { name: "Add employee" }).click();
  const employee = page.getByRole("form", { name: "Add employee" });
  await employee.getByLabel("Full name").fill("Ana Montes");
  await employee.getByLabel("Job title").fill("Quality technician");
  await employee.getByLabel("Employee photo").setInputFiles("public/brand/raster/favicon-64.png");
  await expect(employee.getByRole("img", { name: "Employee photo preview" })).toBeVisible();
  await employee.getByRole("button", { name: "Save sample employee" }).click();
  const record = page.getByRole("region", { name: "Ana Montes" });
  await expect(record.getByRole("img", { name: "Photo of Ana Montes" })).toBeVisible();

  await page.getByRole("button", { name: "New course" }).click();
  const course = page.getByRole("form", { name: "New course" });
  await course.getByLabel("Course title").fill("Sampling inspection");
  await course.getByRole("button", { name: "Save sample course" }).click();
  const assign = record.getByRole("form", { name: "Assign training" });
  await assign.getByLabel("Course").selectOption({ label: "Sampling inspection" });
  await assign.getByLabel("Due date").fill("2026-12-08");
  await assign.getByRole("button", { name: "Assign course" }).click();
  await record.getByRole("button", { name: "Record completion for Sampling inspection" }).click();
  await expect(record.getByText("Completed", { exact: true })).toBeVisible();
  await record.getByRole("button", { name: "Archive employee" }).click();
  await expect(record.getByText("Archived", { exact: true })).toBeVisible();
  await record.getByRole("button", { name: "Restore employee" }).click();
  await expect(record.getByText("Active", { exact: true })).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Control center previews" });
  await nav.getByRole("button", { name: "Company settings" }).click();
  await page.getByLabel("Company display name").fill("Synthetic quality team");
  await page.getByLabel("Accent palette").selectOption("blue");
  await page.getByLabel("Company logo").setInputFiles("public/brand/raster/favicon-64.png");
  const branding = page.getByRole("region", { name: "Company appearance preview" });
  await expect(branding.getByRole("heading", { name: "Synthetic quality team" })).toBeVisible();
  await expect(branding.getByRole("img", { name: "Company logo preview" })).toBeVisible();
  await expect(branding).toHaveAttribute("data-accent", "blue");
  await page.screenshot({ path: info.outputPath("company-settings-preview.png"), fullPage: true });

  await nav.getByRole("button", { name: "Platform operations" }).click();
  await expect(page.getByRole("heading", { name: "Platform operations", exact: true })).toBeVisible();
  await page.getByLabel("Company status").selectOption("Suspended");
  const subscription = page.getByRole("region", { name: "Company subscription preview" });
  await expect(subscription.getByRole("heading", { name: "Pacific Materials" })).toBeVisible();
  await expect(subscription.getByText("2 / 3")).toBeVisible();
  await page.getByLabel("Company status").selectOption("All");
  await page.screenshot({ path: info.outputPath("platform-operations-preview.png"), fullPage: true });

  await page.setViewportSize({ width: 375, height: 812 });
  await nav.getByRole("button", { name: "People & training" }).click();
  await expect(record.getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "People & training" })).toBeVisible();
  const a11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(a11y.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376);
  await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const darkA11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(darkA11y.violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("people-mobile-dark.png"), fullPage: true });
});
