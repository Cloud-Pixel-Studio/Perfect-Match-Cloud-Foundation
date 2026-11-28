import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

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
  await page.goto("/#employees-heading");
  await expect(nav.getByRole("link", { name: "Employee directory" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Employee directory" })).toHaveCount(0);
  await page.goto("/#company-storage-heading");
  await expect(nav.getByRole("link", { name: "Storage usage" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Storage usage" })).toHaveCount(0);
});

test("company storage shows document totals and clears responses from another company", async ({ page }, info) => {
  await useCompany(page, "owner");
  const foreignTenant = "10000000-0000-4000-8000-000000000002";
  let mismatched = false;
  let recordedBytes = 1_987_400;
  await page.route(`**/api/identity/company-storage/${tenant}`, route => route.fulfill({
    headers: { "X-Tenant-ID": tenant },
    json: {
      tenant_id: mismatched ? foreignTenant : tenant, recorded_bytes: recordedBytes, document_file_count: recordedBytes ? 3 : 0,
      allowance_bytes: null, available_bytes: null, usage_percent: null, usage_status: "unconfigured",
    },
  }));
  await page.goto("/#company-control-heading");
  await page.getByRole("button", { name: /Storage usage/ }).click();
  await expect(page).toHaveURL(/#company-storage-heading$/);
  const panel = page.getByRole("region", { name: "Storage usage" });
  await expect(panel.getByText("1,987,400 bytes")).toBeVisible();
  await expect(panel.getByText("1.99 MB", { exact: false })).toBeVisible();
  await expect(panel.getByText("Pending activation", { exact: false })).toBeVisible();
  await panel.screenshot({ path: info.outputPath("company-storage-desktop.png") });
  mismatched = true;
  await panel.getByRole("button", { name: "Refresh usage" }).click();
  await expect(panel.getByRole("alert")).toContainText("could not be loaded");
  await expect(panel.getByText("1,987,400 bytes")).toHaveCount(0);
  mismatched = false;
  recordedBytes = 36;
  await panel.getByRole("button", { name: "Refresh usage" }).click();
  await expect(panel.getByText("Less than 0.01 MB", { exact: false })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 760 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(321);
  const a11y = await new AxeBuilder({ page }).include(".cc-workspace").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(a11y.violations).toEqual([]);
  await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const darkA11y = await new AxeBuilder({ page }).include(".cc-workspace").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(darkA11y.violations).toEqual([]);
  await panel.screenshot({ path: info.outputPath("company-storage-mobile.png") });
});

test("company storage shows contracted capacity and warns when usage exceeds it", async ({ page }, info) => {
  await useCompany(page, "owner");
  let overLimit = false;
  await page.route(`**/api/identity/company-storage/${tenant}`, route => route.fulfill({
    headers: { "X-Tenant-ID": tenant },
    json: {
      tenant_id: tenant, document_file_count: 4, allowance_bytes: 10_000_000,
      recorded_bytes: overLimit ? 11_000_000 : 9_000_000, available_bytes: overLimit ? 0 : 1_000_000,
      usage_percent: overLimit ? 100 : 90, usage_status: overLimit ? "over_limit" : "warning",
    },
  }));
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/#company-storage-heading");
  const panel = page.getByRole("region", { name: "Storage usage" });
  const meter = panel.getByRole("meter", { name: "Percentage of company allowance used" });
  await expect(meter).toHaveAttribute("value", "90");
  await expect(panel.getByText("1 MB available")).toBeVisible();
  await expect(panel.getByText("You have reached 90% of your allowance.")).toBeVisible();
  await panel.screenshot({ path: info.outputPath("contracted-storage-desktop.png") });
  overLimit = true;
  await panel.getByRole("button", { name: "Refresh usage" }).click();
  await expect(meter).toHaveAttribute("value", "100");
  await expect(panel.getByText("Over capacity", { exact: true })).toBeVisible();
  await expect(panel.getByText("Recorded files use 1 MB more", { exact: false })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 760 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(321);
  const a11y = await new AxeBuilder({ page }).include(".cc-workspace").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(a11y.violations).toEqual([]);
  await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const darkA11y = await new AxeBuilder({ page }).include(".cc-workspace").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(darkA11y.violations).toEqual([]);
  await panel.screenshot({ path: info.outputPath("contracted-storage-mobile.png") });
});

test("company administration saves employee profiles and rejects an unexpected company response", async ({ page }, info) => {
  await useCompany(page, "owner");
  await page.setViewportSize({ width: 1280, height: 900 });
  const employeeId = "30000000-0000-4000-8000-000000000001";
  const unit = "40000000-0000-4000-8000-000000000001";
  let saved: { full_name: string; job_title: string; status: string; row_version: number; id: string; unit_id: string; tenant_id: string } | undefined;
  let mismatched = false;
  await page.route("**/api/identity/organization/units?*", route => route.fulfill({
    headers: { "X-Tenant-ID": tenant },
    json: [{ id: unit, tenant_id: tenant, status: "active", name: "Quality", code: "Q" }],
  }));
  await page.route("**/api/identity/employees/**", route => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = { "X-Tenant-ID": mismatched ? "different-company" : tenant };
    if (request.method() === "GET") {
      const items = saved && (saved.status === "active" || url.searchParams.get("include_archived") === "true") ? [saved] : [];
      return route.fulfill({ headers, json: { items, has_more: false } });
    }
    const payload = request.postDataJSON();
    if (request.method() === "POST" && url.pathname.endsWith(tenant)) {
      expect(payload).toEqual({ full_name: "Ana Montes", job_title: "Inspector", unit_id: unit });
      saved = { ...payload, id: employeeId, tenant_id: tenant, status: "active", row_version: 1 };
      return route.fulfill({ headers, json: saved, status: 201 });
    }
    if (!saved) throw new Error("Employee fixture was not saved");
    expect(payload.expected_version).toBe(saved.row_version);
    if (request.method() === "PATCH") {
      expect(payload.job_title).toBe("Lead inspector");
      saved = { ...saved, job_title: payload.job_title, row_version: saved.row_version + 1 };
    } else {
      saved = { ...saved, status: url.pathname.endsWith("/archive") ? "archived" : "active", row_version: saved.row_version + 1 };
    }
    return route.fulfill({ headers, json: saved });
  });
  await page.goto("/#company-control-heading");
  await page.getByRole("button", { name: /Employee directory/ }).click();
  await expect(page).toHaveURL(/#employees-heading$/);
  await page.getByRole("button", { name: "Add employee" }).click();
  const form = page.getByRole("form", { name: "New employee" });
  await form.getByLabel("Full name").fill("Ana Montes");
  await form.getByLabel("Job title").fill("Inspector");
  await form.getByLabel("Organization unit").selectOption(unit);
  await form.getByRole("button", { name: "Save profile" }).click();
  const profile = page.getByRole("region", { name: "Ana Montes" });
  await expect(profile.getByText("Inspector", { exact: true })).toBeVisible();
  await page.reload();
  await expect(profile).toBeVisible();
  await profile.getByRole("button", { name: "Edit profile" }).click();
  const editor = page.getByRole("form", { name: "Edit employee" });
  await editor.getByLabel("Job title").fill("Lead inspector");
  await editor.getByRole("button", { name: "Save profile" }).click();
  await expect(profile.getByText("Lead inspector")).toBeVisible();
  await profile.getByRole("button", { name: "Archive employee" }).click();
  await expect(profile).toHaveCount(0);
  await page.getByRole("checkbox", { name: "Include archived" }).check();
  await expect(profile.getByText("Archived", { exact: true })).toBeVisible();
  await profile.getByRole("button", { name: "Restore employee" }).click();
  await expect(profile.getByText("Active", { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("authenticated-employee-directory.png") });
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376);
  const a11y = await new AxeBuilder({ page }).include(".cc-workspace").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(a11y.violations).toEqual([]);
  await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
  const darkA11y = await new AxeBuilder({ page }).include(".cc-workspace").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(darkA11y.violations).toEqual([]);
  await profile.screenshot({ path: info.outputPath("authenticated-employee-mobile.png") });
  mismatched = true;
  await page.reload();
  await expect(page.getByRole("alert").getByText("The employee directory could not be loaded.")).toBeVisible();
  await expect(profile).toHaveCount(0);
  await page.route("**/api/identity/audit/events?*", route => route.fulfill({
    json: {
      items: [{
        id: employeeId, occurred_at: "2026-11-27T19:00:00Z", actor_display_name: "Synthetic account",
        actor_role: "owner", action: "employee.updated", resource_type: "employee_profile",
        resource_id: employeeId, request_id: unit, schema_version: 1, changed_fields: ["row_version"],
        old_values: { row_version: 1 }, new_values: { row_version: 2 }, metadata: { profile_fields: ["job_title"] },
      }],
      next_cursor: null,
    },
  }));
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("link", { name: "Audit trail", exact: true }).click();
  await page.locator(".audit-event summary").getByText("Employee · Updated", { exact: true }).click();
  await expect(page.getByText("Profile changes recorded for Job Title.", { exact: true })).toBeVisible();
});

test("the company profile uploads and displays a private employee portrait", async ({ page }, info) => {
  await useCompany(page, "owner");
  await page.setViewportSize({ width: 375, height: 812 });
  const employeeId = "30000000-0000-4000-8000-000000000001";
  const unit = "40000000-0000-4000-8000-000000000001";
  const portrait = await readFile(new URL("../public/brand/control-centers/portraits/elena-cruz.jpg", import.meta.url));
  const headers = { "X-Tenant-ID": tenant, "Cache-Control": "private, no-store" };
  let profile = {
    id: employeeId, tenant_id: tenant, unit_id: unit, full_name: "Elena Cruz", job_title: "Inspector",
    status: "active", row_version: 1, has_portrait: false,
  };
  await page.route("**/api/identity/organization/units?*", route => route.fulfill({
    headers, json: [{ id: unit, tenant_id: tenant, status: "active", name: "Quality", code: "Q" }],
  }));
  await page.route("**/api/identity/employees/**", route => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.endsWith("/photo")) return route.fulfill({ headers, json: { items: [profile], has_more: false } });
    expect(url.pathname).toBe(`/api/identity/employees/${tenant}/${employeeId}/photo`);
    if (request.method() === "GET") return route.fulfill({ headers, contentType: "image/jpeg", body: portrait });
    expect(url.searchParams.get("expected_version")).toBe(String(profile.row_version));
    if (request.method() === "PUT") {
      expect(request.headers()["content-type"]).toBe("image/jpeg");
      expect(request.postDataBuffer()).toEqual(portrait);
    }
    profile = { ...profile, has_portrait: request.method() === "PUT", row_version: profile.row_version + 1 };
    return route.fulfill({ headers, json: profile });
  });
  await page.goto("/#employees-heading");
  const panel = page.getByRole("region", { name: "Elena Cruz" });
  await panel.getByLabel("Choose profile photo").setInputFiles({ name: "employee.jpg", mimeType: "image/jpeg", buffer: portrait });
  await panel.getByRole("button", { name: "Save photo" }).click();
  const image = panel.getByRole("img", { name: "Portrait of Elena Cruz" });
  await expect(image).toBeVisible();
  await expect.poll(() => image.evaluate(node => (node as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  await page.reload();
  await expect(image).toBeVisible();
  const scan = () => new AxeBuilder({ page }).include(".cc-workspace").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect((await scan()).violations).toEqual([]);
  await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect((await scan()).violations).toEqual([]);
  await panel.screenshot({ path: info.outputPath("employee-private-portrait-mobile.png") });
  await panel.getByRole("button", { name: "Remove photo" }).click();
  await expect(image).toHaveCount(0);
  await expect(panel.getByLabel("Choose profile photo")).toBeVisible();
});

test("the explicitly enabled design preview supports employee, training, branding and operations review", async ({ page }, info) => {
  const response = await page.goto(preview);
  if (process.env.PMQMS_CONTROL_PREVIEW !== "1") {
    expect(response?.status()).toBe(404);
    return;
  }
  expect(response?.ok()).toBe(true);
  await page.setViewportSize({ width: 1280, height: 900 });
  const lucia = page.getByRole("region", { name: "Lucía Rivera" });
  const portrait = lucia.getByAltText("Photo of Lucía Rivera", { exact: true });
  await expect(portrait).toBeVisible();
  await expect.poll(() => portrait.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(512);
  await page.screenshot({ path: info.outputPath("employee-profile-desktop.png") });
  const viewPhoto = lucia.getByRole("button", { name: "View profile photo of Lucía Rivera" });
  await viewPhoto.press("Enter");
  const photoDialog = page.getByRole("dialog", { name: "Profile photo of Lucía Rivera" });
  await expect(photoDialog.getByAltText("Profile portrait of Lucía Rivera")).toBeVisible();
  const dialogA11y = await new AxeBuilder({ page }).include("dialog[open]").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(dialogA11y.violations).toEqual([]);
  await page.screenshot({ path: info.outputPath("employee-photo-viewer.png") });
  await page.keyboard.press("Escape");
  await expect(photoDialog).toBeHidden();
  await expect(viewPhoto).toBeFocused();
  await page.getByRole("button", { name: "Add employee" }).click();
  const employee = page.getByRole("form", { name: "Add employee" });
  await employee.getByLabel("Full name").fill("Ana Montes");
  await employee.getByLabel("Job title").fill("Quality technician");
  const saveEmployee = employee.getByRole("button", { name: "Save sample employee" });
  await saveEmployee.click();
  await expect(employee.getByRole("alert")).toHaveText("Add a profile photo before saving.");
  const profilePhoto = employee.getByLabel("Profile photo");
  await profilePhoto.setInputFiles({
    name: "broken.png", mimeType: "image/png", buffer: Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
  });
  await expect(employee.getByRole("alert")).toHaveText("This image could not be opened.");
  await profilePhoto.setInputFiles("public/brand/control-centers/portraits/elena-cruz.jpg");
  await expect(employee.getByRole("img", { name: "Employee photo preview" })).toBeVisible();
  await saveEmployee.click();
  const record = page.getByRole("region", { name: "Ana Montes" });
  await expect(record.getByAltText("Photo of Ana Montes")).toBeVisible();
  await record.getByRole("button", { name: "Edit profile" }).click();
  const editor = page.getByRole("form", { name: "Edit employee" });
  const editedPhoto = editor.getByAltText("Photo of Ana Montes");
  const originalPhoto = await editedPhoto.getAttribute("src");
  await editor.getByLabel("Profile photo").setInputFiles("public/brand/control-centers/portraits/marcos-pena.jpg");
  await expect(editedPhoto).not.toHaveAttribute("src", originalPhoto!);
  const replacementPhoto = await editedPhoto.getAttribute("src");
  await editor.getByRole("button", { name: "Save sample employee" }).click();
  await expect(record.getByAltText("Photo of Ana Montes")).toHaveAttribute("src", replacementPhoto!);

  await page.getByRole("button", { name: "New course" }).click();
  const course = page.getByRole("form", { name: "New course" });
  await course.getByLabel("Course title").fill("Sampling inspection");
  await course.getByRole("button", { name: "Save sample course" }).click();
  const assign = record.getByRole("form", { name: "Assign training" });
  await assign.getByLabel("Course").selectOption({ label: "Sampling inspection" });
  await assign.getByLabel("Due date").fill("2026-12-08");
  await assign.getByRole("button", { name: "Assign course" }).click();
  await record.getByRole("button", { name: "Record completion for Sampling inspection" }).click();
  const assigned = record.getByRole("region", { name: "Assigned training" });
  await expect(assigned.getByText("Completed", { exact: true })).toBeVisible();
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
  await expect(assigned.getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "People & training" })).toBeVisible();
  const a11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(a11y.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(376);
  await page.getByRole("checkbox", { name: "Use dark theme" }).press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: /Lucía Rivera.*Quality coordinator/ }).click();
  await expect(portrait).toBeVisible();
  const darkA11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(darkA11y.violations).toEqual([]);
  await lucia.screenshot({ path: info.outputPath("employee-profile-mobile.png") });
  await page.setViewportSize({ width: 320, height: 720 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(321);
});
