import { test, expect } from '@playwright/test';

const initialDraft = {
  id: 'test-draft',
  title: 'Year 7 Science Plan',
  summary: 'Automatically parsed plan for review.',
  status: 'pending_review',
  review_notes: '',
  trimesters: [
    {
      id: 'tri-1',
      name: 'Trimester 1',
      start_date: '2024-01-08',
      end_date: '2024-03-22',
    },
    {
      id: 'tri-2',
      name: 'Trimester 2',
      start_date: '2024-04-08',
      end_date: '2024-06-28',
    },
  ],
  levels: [
    {
      id: 'lvl-7',
      name: 'Level 7',
      description: 'Core science skills.',
    },
    {
      id: 'lvl-8',
      name: 'Level 8',
      description: 'Extended investigations.',
    },
  ],
  topics: [
    {
      id: 'topic-1',
      name: 'Scientific Inquiry',
      trimester_id: 'tri-1',
      level_id: 'lvl-7',
      summary: 'Introduction to lab safety and experiments.',
    },
  ],
  created_at: '2024-01-01T00:00:00+00:00',
  updated_at: '2024-01-01T00:00:00+00:00',
  approved_at: null,
  history: [
    {
      timestamp: '2024-01-01T00:00:00+00:00',
      action: 'seed',
      payload: { message: 'Initial import' },
    },
  ],
};

test.describe('plan review workspace', () => {
  test('allows editing, approving, and requesting re-parse of a draft', async ({ page }) => {
    let patchBody: any | null = null;
    let approveCalled = false;
    let reparseCalled = false;

    await page.route('**/plans/test-draft', async (route) => {
      const method = route.request().method();
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(initialDraft),
        });
        return;
      }

      if (method === 'PATCH') {
        patchBody = JSON.parse(route.request().postData() ?? '{}');
        const updated = {
          ...initialDraft,
          ...patchBody,
          updated_at: new Date('2024-01-02T12:00:00+00:00').toISOString(),
          history: [
            ...initialDraft.history,
            {
              timestamp: new Date('2024-01-02T12:00:00+00:00').toISOString(),
              action: 'patch',
              payload: patchBody,
            },
          ],
        };
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(updated),
        });
        return;
      }

      await route.continue();
    });

    await page.route('**/plans/test-draft/approve', async (route) => {
      approveCalled = true;
      const base = { ...initialDraft, status: 'approved', approved_at: new Date('2024-01-03T09:00:00+00:00').toISOString() };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...base,
          history: [
            ...initialDraft.history,
            {
              timestamp: base.approved_at,
              action: 'approve',
              payload: { review_notes: '' },
            },
          ],
        }),
      });
    });

    await page.route('**/plans/test-draft/reparse', async (route) => {
      reparseCalled = true;
      const updatedAt = new Date('2024-01-04T09:30:00+00:00').toISOString();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...initialDraft,
          status: 'reparse_requested',
          updated_at: updatedAt,
          history: [
            ...initialDraft.history,
            {
              timestamp: updatedAt,
              action: 'reparse',
              payload: { review_notes: '' },
            },
          ],
        }),
      });
    });

    await page.goto('/frontend/pages/plan-review.html?draft_id=test-draft');

    await expect(page.getByRole('heading', { name: 'Plan Review' })).toBeVisible();
    await expect(page.locator('#trimester-name-0')).toHaveValue('Trimester 1');

    await page.locator('#trimester-name-0').fill('Term 1 Updated');
    await page.locator('#plan-notes').fill('Need updated assessment rubrics.');
    await page.getByRole('button', { name: 'Save changes' }).click();

    await expect(page.getByText('Draft saved successfully')).toBeVisible();
    expect(patchBody).not.toBeNull();
    expect(patchBody?.trimesters?.[0]?.name).toBe('Term 1 Updated');
    expect(patchBody?.review_notes).toBe('Need updated assessment rubrics.');

    await page.getByRole('button', { name: 'Approve' }).click();
    await expect(page.getByText('Draft approved successfully')).toBeVisible();
    expect(approveCalled).toBe(true);

    await page.getByRole('button', { name: 'Request Re-parse' }).click();
    await expect(page.getByText('Re-parse requested')).toBeVisible();
    expect(reparseCalled).toBe(true);
  });
});
