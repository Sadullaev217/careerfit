import { expect, test } from '@playwright/test';

test('the landing page explains the product and links to sign-in @phone', async ({ page }) => {
  await page.goto('/en');
  await expect(
    page.getByRole('heading', { name: 'See where you stand for the job you want' }),
  ).toBeVisible();
  await page.getByRole('link', { name: 'Check my resume' }).first().click();
  await expect(page).toHaveURL(/\/en\/login/);
});

for (const [path, heading] of [
  ['/en/privacy', 'Privacy Policy'],
  ['/en/terms', 'Terms of Service'],
  ['/en/how-scoring-works', 'How the score works'],
  ['/ru/privacy', 'Политика конфиденциальности'],
] as const) {
  test(`${path} renders`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
  });
}

test('pages behind sign-in send people to the login page', async ({ page }) => {
  await page.goto('/en/documents');
  await expect(page).toHaveURL(/\/en\/login/);
  await expect(page.getByRole('heading', { name: 'Log in to CareerFit' })).toBeVisible();
});
