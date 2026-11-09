import { test, expect, type Page } from '@playwright/test';

const year = new Date().getFullYear();
const fixtureDate = (value: string) => value.replace('2027', String(year));
// Browser-only test doubles. These records are never inserted into a real account.
const events = [
  { id: 'test-event-1', title: 'TEST — Rooftop reception', city: 'Mumbai', event_type: 'Wedding', starts_at: '2027-05-09T12:30:00Z', ends_at: '2027-05-09T16:30:00Z', budget_paise: 5000000, guest_count: 60, notes: 'Test brief: acoustic music and a warm evening.' },
  { id: 'test-event-2', title: 'TEST — Team gathering', city: 'Pune', event_type: 'Corporate event', starts_at: '2027-06-10T12:30:00Z', ends_at: '2027-06-10T16:30:00Z', budget_paise: 3000000, guest_count: 40, notes: '' },
  { id: 'test-event-3', title: 'TEST — Previous occasion', city: 'Mumbai', event_type: 'Private party', starts_at: '2027-04-01T12:30:00Z', ends_at: '2027-04-01T16:30:00Z', budget_paise: 2000000, guest_count: 20, notes: '' },
].map(event => ({ ...event, starts_at: fixtureDate(event.starts_at), ends_at: fixtureDate(event.ends_at) }));

test.use({ timezoneId: 'Asia/Kolkata' });
test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date(fixtureDate('2027-05-08T06:30:00Z')));
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
});

async function account(page: Page, empty = false) {
  await page.route('**/api/v1/session', route => route.fulfill({ json: { user: { id: 'test-user' }, configured: true, roles: ['organizer'] } }));
  await page.route('**/api/v1/me', route => route.fulfill({ json: { profile: { id: 'test-user', display_name: 'Test organiser', phone: '' }, roles: ['organizer'] } }));
  await page.route('**/api/v1/events', route => route.fulfill({ json: { items: empty ? [] : events } }));
  await page.route('**/api/v1/inquiries', route => route.fulfill({ json: { items: empty ? [] : [{ id: 'test-inquiry', event_title: events[0].title, artist_name: 'TEST artist' }] } }));
  await page.route('**/api/v1/bookings', route => route.fulfill({ json: { items: empty ? [] : [
    { id: 'test-booking', status: 'confirmed', event_title: events[0].title, artist_name: 'TEST artist', total_paise: 5000000, starts_at: events[0].starts_at, ends_at: events[0].ends_at },
    { id: 'test-expired-hold', status: 'pending_payment', expires_at: fixtureDate('2027-05-07T06:30:00Z') },
  ] } }));
  await page.route('**/api/v1/notifications', route => route.fulfill({ json: { items: empty ? [] : [{ id: 'test-notification', title: 'TEST — A quote is ready to review', created_at: fixtureDate('2027-05-08T06:00:00Z'), read_at: null }] } }));
}

test('workspace shows saved records and preserves event/calendar navigation', async ({ page }, info) => {
  await account(page);
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto('/account');
  await expect(page.getByRole('heading', { name: /Welcome back, Test/ })).toBeVisible();
  await expect(page.locator('.workspace-metric').filter({ hasText: 'Upcoming events' }).locator('strong')).toHaveText('2');
  await expect(page.locator('.workspace-metric').filter({ hasText: 'Confirmed bookings' }).locator('strong')).toHaveText('1');
  await expect(page.locator('.payment-reminder')).toHaveCount(0);
  await page.screenshot({ path: `test-results/${info.project.name}-workspace-design.png`, fullPage: true });
  await page.getByRole('navigation', { name: 'Account sections' }).getByRole('button', { name: 'Your events', exact: true }).click();
  await expect(page.locator('.event-card')).toHaveCount(2);
  await expect(page.locator('.event-card').first().getByRole('link')).toHaveAttribute('href', '/artists?city=Mumbai&event_type=Wedding');
  await page.screenshot({ path: `test-results/${info.project.name}-events-design.png`, fullPage: true });
  await page.getByRole('button', { name: 'Past', exact: true }).click();
  await expect(page.locator('.event-card h3')).toHaveText(events[2].title);
  await page.getByLabel('Search your events').fill('missing occasion');
  await expect(page.getByRole('heading', { name: 'No events in this view.' })).toBeVisible();
  await page.getByRole('button', { name: 'Show all events' }).click();
  await expect(page.locator('.event-card')).toHaveCount(3);
  await page.getByRole('navigation', { name: 'Account sections' }).getByRole('button', { name: 'Calendar', exact: true }).click();
  await page.getByRole('button', { name: `9 May ${year}, 1 events`, exact: true }).click();
  await expect(page.locator('.calendar-agenda')).toContainText(events[0].title);
  await page.screenshot({ path: `test-results/${info.project.name}-calendar-design.png`, fullPage: true });
  await page.getByRole('button', { name: 'Next month' }).click();
  await expect(page.locator('.calendar-heading')).toContainText(`June ${year}`);
  await page.goBack();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Your events');
  expect(errors).toEqual([]);
});

test('failed records show unknown counts and recover without invented events', async ({ page }) => {
  await account(page, true);
  let healthy = false;
  await page.route('**/api/v1/events', route => route.fulfill(healthy ? { json: { items: [] } } : { status: 503, json: { detail: 'Test event service unavailable.' } }));
  await page.goto('/account');
  await expect(page.locator('.workspace-metric').first().locator('strong')).toHaveText('—');
  await expect(page.locator('main').getByRole('alert')).toContainText('Test event service unavailable.');
  healthy = true;
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.locator('.workspace-metric').first().locator('strong')).toHaveText('0');
  await expect(page.getByRole('heading', { name: 'Your next story starts here.' })).toBeVisible();
  await expect(page.locator('.upcoming-event')).toHaveCount(0);
});

test('guest welcome has useful entry points and does not request private records', async ({ page }, info) => {
  const privateRequests: string[] = [];
  page.on('request', request => { if (/\/api\/v1\/(events|me|inquiries|bookings|notifications)$/.test(request.url())) privateRequests.push(request.url()); });
  await page.route('**/api/v1/session', route => route.fulfill({ json: { user: null, configured: true } }));
  await page.goto('/account');
  await expect(page.getByRole('link', { name: 'Log in or create an account' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Start an event brief' })).toHaveAttribute('href', '/plan');
  await expect(page.locator('.workspace-metric')).toHaveCount(0);
  expect(privateRequests).toEqual([]);
  await page.screenshot({ path: `test-results/${info.project.name}-workspace-guest.png`, fullPage: true });
});

async function fillBrief(page: Page) {
  await page.getByLabel('Event name', { exact: true }).fill('TEST — Rooftop celebration');
  await page.getByLabel('Starts (your local time)').fill(fixtureDate('2027-05-20T18:00'));
  await page.getByLabel('Ends (your local time)').fill(fixtureDate('2027-05-20T22:00'));
  await page.getByLabel('Artist budget (INR)', { exact: true }).fill('50000');
  await page.getByLabel('The occasion and the vibe').fill('Acoustic music for a warm evening with our closest friends.');
}

test('planning summary reflects the brief and rejects reversed dates', async ({ page }, info) => {
  await page.route('**/api/v1/session', route => route.fulfill({ json: { user: null, configured: true } }));
  await page.goto('/plan');
  await fillBrief(page);
  await expect(page.getByRole('complementary', { name: 'Your event summary' })).toContainText('TEST — Rooftop celebration');
  await expect(page.locator('.summary-budget strong')).toContainText('50,000');
  await page.screenshot({ path: `test-results/${info.project.name}-plan-design.png`, fullPage: true });
  await page.getByLabel('Ends (your local time)').fill(fixtureDate('2027-05-20T16:00'));
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(page.locator('main').getByRole('alert')).toContainText('Choose an end time after your event starts.');
  expect(await page.evaluate(() => localStorage.getItem('eventrahq.event-draft.v2'))).toBeNull();
  await page.getByLabel('Ends (your local time)').fill(fixtureDate('2027-05-20T22:00'));
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Draft saved' })).toBeVisible();
});

test('inquiry retry reuses the saved event and successful saves cannot duplicate', async ({ page }) => {
  await account(page, true);
  let eventWrites = 0; let inquiryWrites = 0;
  await page.route('**/api/v1/events', async route => {
    expect(route.request().method()).toBe('POST'); eventWrites++;
    expect(route.request().postDataJSON()).toMatchObject({ title: 'TEST — Rooftop celebration', budget_paise: 5000000, guest_count: 50 });
    await route.fulfill({ json: { id: 'saved-test-event' } });
  });
  await page.route('**/api/v1/inquiries', async route => {
    inquiryWrites++;
    expect(route.request().postDataJSON()).toMatchObject({ event_id: 'saved-test-event', artist_id: 'test-artist' });
    await route.fulfill(inquiryWrites === 1 ? { status: 503, json: { detail: 'Test inquiry connection failed.' } } : { json: { id: 'saved-test-inquiry' } });
  });
  await page.goto('/plan?artist=test-artist');
  await fillBrief(page);
  await page.getByRole('button', { name: 'Save & send inquiry' }).click();
  await expect(page.locator('main').getByRole('alert')).toContainText('Your event is saved. The inquiry was not sent');
  await expect(page.getByLabel('Event name', { exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Retry inquiry' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Event saved and inquiry sent.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Event saved', exact: true })).toBeDisabled();
  expect(eventWrites).toBe(1); expect(inquiryWrites).toBe(2);
});

test('workspace and planning stay within narrow and wide viewports', async ({ page }) => {
  await account(page, true);
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ['/account', '/account?tab=events', '/account?tab=calendar', '/plan']) {
      await page.goto(path);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.locator('.workspace-loading')).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${path} at ${width}px`).toBeTruthy();
    }
  }
  await page.goto('/account');
  await page.getByRole('navigation', { name: 'Account sections' }).getByRole('button', { name: 'Calendar', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Calendar');
});
