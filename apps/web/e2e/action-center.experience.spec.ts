import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const companyA = "10000000-0000-4000-8000-000000000001";
const companyB = "10000000-0000-4000-8000-000000000002";
const actor = "20000000-0000-4000-8000-000000000007";

function actions(company: string, scope = "mine") {
  return {
    scope, generated_at: "2026-11-17T12:00:00Z",
    summary: { total: 1, overdue: 0, due_soon: 0, unassigned: 1, by_source: { capa: 1 } },
    items: [{ id: `capa:${company}`, source: "capa", source_id: company, unit_id: null, title: company === companyA ? "DEMO A inspection follow-up" : "DEMO B document review", context: "Synthetic UI regression fixture", state: "open", urgency: "normal", due_date: null, overdue: false, assigned_to_user_id: null, assignee_name: null, target_workspace: "capa", target_record_id: company, target_subrecord_id: null, target_process_id: null, updated_at: "2026-11-17T12:00:00Z" }],
  };
}

async function fixture(page: Page) {
  const state = { company: companyA, status: 200, invalid: false, login: false, holdNext: false, held: false, release: () => {} };
  await page.route("**/api/identity/**", async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: { id: actor, display_name: "Synthetic reviewer", email: null, current_tenant_id: state.company } });
    if (path.endsWith("/auth/tenants")) return route.fulfill({ json: [{ id: companyA, name: "DEMO Company A", slug: "demo-a", role: "owner" }, { id: companyB, name: "DEMO Company B", slug: "demo-b", role: "owner" }] });
    if (path.endsWith("/qms-access/active-capabilities")) return route.fulfill({ json: { capabilities: [] } });
    if (path.endsWith("/auth/tenant") && request.method() === "POST") { state.company = request.postDataJSON().tenant_id; return route.fulfill({ json: {} }); }
    if (path.endsWith("/auth/login")) { state.login = true; state.status = 200; return route.fulfill({ status: 302, headers: { location: "/#overview-heading" } }); }
    if (path.endsWith("/action-center")) {
      const payload = actions(state.company, url.searchParams.get("scope") ?? "mine");
      if (state.holdNext) { state.holdNext = false; state.held = true; await new Promise<void>(resolve => { state.release = resolve; }); }
      return route.fulfill({ status: state.status, json: state.invalid ? { items: null } : payload });
    }
    return route.fulfill({ status: 404, json: { detail: "Synthetic fixture endpoint unavailable" } });
  });
  return state;
}

for (const compact of [true, false]) {
  const location = compact ? "/#overview-heading" : "/#action-center-heading";
  const panelSelector = compact ? "section[aria-labelledby='overview-actions-heading']" : "section[aria-labelledby='action-center-heading']";
  for (const [status, message] of [[401, "Your session has expired"], [403, "You no longer have access"], [500, "temporarily unavailable"]] as const) {
    test(`action queue ${compact ? "overview" : "full"} clears old tasks on ${status}`, async ({ page }, info) => {
      const state = await fixture(page);
      await page.goto(location);
      const panel = page.locator(panelSelector);
      await expect(panel.getByText("DEMO A inspection follow-up", { exact: true })).toBeVisible();
      state.status = status;
      await panel.getByRole("button", { name: "Refresh action center" }).click();
      await expect(panel.getByRole("alert")).toContainText(message);
      await expect(panel.getByText("DEMO A inspection follow-up", { exact: true })).toHaveCount(0);
      await expect(panel.getByLabel("Action summary")).toHaveCount(0);
      if (status === 401) {
        await expect(panel.getByRole("link", { name: "Sign in again" })).toHaveAttribute("href", "/api/identity/auth/login");
        await expect(panel.getByRole("button", { name: "Refresh action center" })).toBeDisabled();
        const accessibility = await new AxeBuilder({ page }).include(panelSelector).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        expect(accessibility.violations).toEqual([]);
        await info.attach("expired-session", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
        await panel.getByRole("link", { name: "Sign in again" }).click();
        await expect.poll(() => state.login).toBe(true);
        await expect(page.getByText("DEMO A inspection follow-up", { exact: true })).toBeVisible();
      } else {
        state.status = 200;
        await panel.getByRole("button", { name: "Refresh action center" }).click();
        await expect(panel.getByText("DEMO A inspection follow-up", { exact: true })).toBeVisible();
      }
    });
  }

  test(`action queue ${compact ? "overview" : "full"} rejects a malformed success without stale tasks`, async ({ page }) => {
    const state = await fixture(page);
    await page.goto(location);
    const panel = page.locator(panelSelector);
    await expect(panel.getByText("DEMO A inspection follow-up", { exact: true })).toBeVisible();
    state.invalid = true;
    await panel.getByRole("button", { name: "Refresh action center" }).click();
    await expect(panel.getByRole("alert")).toContainText("temporarily unavailable");
    await expect(panel.getByText("DEMO A inspection follow-up", { exact: true })).toHaveCount(0);
  });

  test(`action queue ${compact ? "overview" : "full"} ignores a delayed previous-company response`, async ({ page }) => {
    const state = await fixture(page);
    await page.goto(location);
    const panel = page.locator(panelSelector);
    await expect(panel.getByText("DEMO A inspection follow-up", { exact: true })).toBeVisible();
    state.holdNext = true;
    await panel.getByRole("button", { name: "Refresh action center" }).click();
    await expect.poll(() => state.held).toBe(true);
    await expect(panel.getByText("DEMO A inspection follow-up", { exact: true })).toHaveCount(0);
    await page.getByRole("combobox", { name: "Current organization", exact: true }).selectOption(companyB);
    await expect(panel.getByText("DEMO B document review", { exact: true })).toBeVisible();
    const previousResponse = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/action-center"));
    state.release();
    const previous = await previousResponse;
    await previous.finished();
    expect((await previous.json()).items[0].title).toBe("DEMO A inspection follow-up");
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(panel.getByText("DEMO A inspection follow-up", { exact: true })).toHaveCount(0);
    await expect(panel.getByText("DEMO B document review", { exact: true })).toBeVisible();
  });
}
