import { expect, type Page } from "@playwright/test";

type AuthenticationOptions = {
  username: string;
  password: string;
  destination?: string;
  organization?: string;
};

const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";
const webURL = new URL(process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000");

export async function authenticateWithKeycloak(
  page: Page,
  { username, password, destination = "/", organization }: AuthenticationOptions,
) {
  await page.goto(`${apiURL}/auth/login`, { waitUntil: "domcontentloaded" });
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);

  await Promise.all([
    page.waitForURL(
      (url) => url.origin === webURL.origin && url.pathname === webURL.pathname,
      { waitUntil: "domcontentloaded", timeout: 20_000 },
    ),
    page.locator("#kc-login").click(),
  ]);

  await expect
    .poll(
      async () => {
        const response = await page.request.get(`${apiURL}/auth/me`);
        return response.status();
      },
      {
        message: "OIDC callback must create the application session before the workspace loads",
        timeout: 20_000,
      },
    )
    .toBe(200);

  if (organization) {
    const selector = page.getByRole("combobox", { name: "Current organization", exact: true });
    await expect(selector).toBeVisible();
    const option = selector.locator("option").filter({ hasText: organization });
    await expect(option).toHaveCount(1);
    const value = await option.getAttribute("value");
    if (!value) throw new Error("Synthetic organization is unavailable");
    if (await selector.inputValue() !== value) await selector.selectOption(value);
  }

  await expect(page.getByRole("heading", { name: "Work with clarity." })).toBeVisible({
    timeout: 20_000,
  });

  if (destination !== "/") {
    await page.goto(destination, { waitUntil: "networkidle" });
  }
}
