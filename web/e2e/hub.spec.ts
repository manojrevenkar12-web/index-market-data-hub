import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

async function deskDay(page: Page): Promise<string> {
  const days: string[] = await (await page.request.get("/api/days")).json();
  for (const d of days) {
    const desk = await (await page.request.get(`/api/desk?date=${d}`)).json();
    if (desk.items.some((i: { looked_up: boolean }) => i.looked_up)) return d;
  }
  throw new Error("no desk lookups in the loaded quarter");
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
});

async function noViolations(page: Page) {
  await page.waitForLoadState("networkidle");
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
}

test("the board lists every index and opens one with its constituents", async ({ page }) => {
  await page.goto("/");
  const board = page.getByRole("navigation", { name: "Indices" });
  await expect(board.getByRole("button")).toHaveCount(4);
  await board.getByRole("button", { name: /UK Select 20/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("UK Select 20");
  await expect(page.locator("tbody tr")).toHaveCount(20);
  await expect(page.locator("tbody tr").first().getByRole("list")).toHaveAttribute("aria-label", /Northwind/);
  await noViolations(page);
});

test("the desk shows what was looked up before the close", async ({ page }) => {
  const day = await deskDay(page);
  await page.goto(`/#/GDIV40/desk/${day}`);
  await expect(page.getByRole("heading", { level: 2 })).toContainText("looked up before the close");
  await expect(page.getByText("Looked up").first()).toBeVisible();
  await noViolations(page);
});

test("designs are compared on the same files, the hub included", async ({ page }) => {
  await page.goto("/#/GTL30/designs");
  const table = page.getByRole("region", { name: /Development market/ });
  await expect(table.getByRole("rowheader", { name: "Hub", exact: true })).toBeVisible();
  await expect(table.getByRole("rowheader", { name: "One vendor" })).toBeVisible();
  await noViolations(page);
});

test("choosing a trade date moves the whole view", async ({ page }) => {
  await page.goto("/#/UKS20/close");
  const select = page.getByLabel("Trade date");
  const days: string[] = await (await page.request.get("/api/days")).json();
  await select.selectOption(days[10] ?? "");
  await expect(page).toHaveURL(new RegExp(`${days[10]}$`));
  await expect(page.getByText(/close of .*2026/)).toBeVisible();
});

test("tabs follow the arrow keys", async ({ page }) => {
  await page.goto("/#/UKS20/close");
  await page.getByRole("tab", { name: "Close" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /Desk/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tab", { name: /Desk/ })).toBeFocused();
});

test("a failed load explains itself and retries", async ({ page }) => {
  let fail = true;
  await page.route("**/api/board", (route) =>
    fail ? route.fulfill({ status: 500, body: JSON.stringify({ detail: "database is down" }) }) : route.continue(),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Could not load the indices");
  await expect(page.getByRole("alert")).toContainText("database is down");
  fail = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("navigation", { name: "Indices" })).toBeVisible();
});

test("an empty store says what to do and loading shows a placeholder", async ({ page }) => {
  await page.route("**/api/board", async (route) => {
    await new Promise((r) => setTimeout(r, 400));
    await route.fulfill({ status: 200, body: JSON.stringify({ date: null, days: [], indices: [] }) });
  });
  await page.goto("/");
  await expect(page.getByRole("status", { name: "Loading the indices" })).toBeVisible();
  await expect(page.getByText("No closes published yet")).toBeVisible();
});
