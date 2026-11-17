import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { authenticateWithKeycloak } from "./support/auth";

const password = process.env.KEYCLOAK_USER_A_PASSWORD;

const visualActions = {
  scope: "mine",
  generated_at: "2026-11-10T12:00:00Z",
  summary: { total: 2, overdue: 1, due_soon: 0, unassigned: 0, by_source: { capa: 2 } },
  items: [
    {
      id: "10000000-0000-4000-8000-000000000011",
      source: "capa",
      source_id: "10000000-0000-4000-8000-000000000021",
      unit_id: "10000000-0000-4000-8000-000000000031",
      title: "Assign receiving inspection owner",
      context: "DEMO-CAPA-002 · Receiving control follow-up",
      state: "open",
      urgency: "overdue",
      due_date: "2026-11-06",
      overdue: true,
      assigned_to_user_id: "10000000-0000-4000-8000-000000000041",
      assignee_name: "Quality specialist",
      target_workspace: "capa",
      target_record_id: "10000000-0000-4000-8000-000000000021",
      target_subrecord_id: null,
      target_process_id: "10000000-0000-4000-8000-000000000051",
      updated_at: "2026-11-10T12:00:00Z",
    },
    {
      id: "10000000-0000-4000-8000-000000000012",
      source: "capa",
      source_id: "10000000-0000-4000-8000-000000000022",
      unit_id: "10000000-0000-4000-8000-000000000031",
      title: "Update receiving inspection checklist",
      context: "DEMO-CAPA-001 · Supplier documentation validation",
      state: "open",
      urgency: "normal",
      due_date: "2026-11-22",
      overdue: false,
      assigned_to_user_id: "10000000-0000-4000-8000-000000000041",
      assignee_name: "Quality specialist",
      target_workspace: "capa",
      target_record_id: "10000000-0000-4000-8000-000000000022",
      target_subrecord_id: null,
      target_process_id: "10000000-0000-4000-8000-000000000051",
      updated_at: "2026-11-10T12:00:00Z",
    },
  ],
};

async function stabilizeOverviewActions(page: Page) {
  // Keep this existing visual baseline on its original collaborator persona.
  // Audit planning has separate authorized-persona navigation and UI coverage.
  await page.route("**/api/identity/qms-access/active-capabilities", async (route) => {
    const response = await route.fetch();
    if (!response.ok()) return route.fulfill({ response });
    const access = await response.json() as { capabilities: string[] };
    return route.fulfill({ response, json: { ...access, capabilities: access.capabilities.filter((capability) => !capability.startsWith("audits.")) } });
  });
  await page.route("**/api/identity/action-center?scope=mine&limit=5", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(visualActions) });
  });
}

async function authenticate(page: Page) {
  await authenticateWithKeycloak(page, {
    username: "pmc-user-a",
    password: String(password),
  });
  const organization = page.getByRole("combobox", { name: "Current organization" });
  if (await organization.isVisible()) {
    const values = await organization.locator("option:not([disabled])").evaluateAll((options) =>
      options.map((option) => (option as HTMLOptionElement).value).filter(Boolean),
    );
    if (values[0]) {
      await organization.selectOption(values[0]);
      await page.waitForLoadState("networkidle");
    }
  }
  await expect(page.getByRole("heading", { name: "Work with clarity." })).toBeVisible();
}

for (const viewport of [
  { name: "mobile", width: 375, height: 812 },
  { name: "desktop", width: 1280, height: 900 },
] as const) {
  test(`authenticated workspace ${viewport.name}`, async ({ page }) => {
    test.skip(!password, "Local development credential was not provided");
    await page.setViewportSize(viewport);
    await stabilizeOverviewActions(page);
    await authenticate(page);
    await page.evaluate(() => document.fonts.ready);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await expect(page).toHaveScreenshot(`workspace-${viewport.name}.png`, {
      fullPage: true,
    });
  });
}

test("action center opens the exact authorized record", async ({ page }) => {
  test.skip(!password, "Local development credential was not provided");
  await page.setViewportSize({ width: 1280, height: 900 });
  await authenticate(page);
  const action = page.locator(".action-item").first();
  await expect(action).toBeVisible();
  await action.getByRole("button", { name: /^Open / }).click();
  await expect(page).toHaveURL(/pm_record=[0-9a-f-]+/i);
  await expect(page.locator(".action-target-record").first()).toBeVisible();
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
});

test("an unavailable deep link returns to the authorized overview", async ({ page }) => {
  test.skip(!password, "Local development credential was not provided");
  await authenticate(page);
  await page.goto("/?pm_record=10000000-0000-4000-8000-000000000001&pm_source=capa#audit-heading", { waitUntil: "networkidle" });
  await expect(page).toHaveURL(/\/#overview-heading$/);
  await expect(page.getByRole("heading", { name: "Work with clarity." })).toBeVisible();
  await expect(page.getByRole("link", { name: "Audit trail" })).toHaveCount(0);
});
