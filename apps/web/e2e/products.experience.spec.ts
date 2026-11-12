import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

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
