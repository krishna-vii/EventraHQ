# Eventra frontend — editorial rebuild, 5 November 2026

Status: implementation and build verification complete; visual/interaction acceptance pending browser access. This is not a claim of production readiness.

## Direction

An editorial performance journal: obsidian, warm ivory, restrained brass, Cormorant Garamond headlines and Manrope interface typography. Fonts are locally hosted WOFF2 files (101,432 bytes total) with OFL licenses. Performance imagery remains local and retains the existing photography credits and illustrative disclosures.

The logo uses explicit dark and ivory vector assets. No CSS color inversion is used: inverting a previously cached teal mark could produce pink. The favicon, installed icons and lockup share the monochrome identity.

## Implementation

- `editorial-home.tsx`: new asymmetric landing composition, performance disciplines, actual catalogue results, event journey, city discovery, assistant and artist entry points. Search still submits the existing GET parameters.
- `identity.css`: shared typography, tokens, navigation, buttons, forms, listings, profile, event brief, access screens, role-based workspace, calendar, messages, bookings, account/settings, moderation, errors and footer. Mobile compositions at 1150/900/800/767/600/380 pixels; reduced-motion fallback.
- `fonts.css` and `public/fonts`: self-hosted typefaces; no Google request at runtime.
- `marketplace.tsx`: landing presentation extracted, active navigation and light/dark branding. Existing session, API, shortlist, filters, event submission, assistant and account logic retained.
- `layout.tsx`, `auth/confirm/page.tsx`, brand assets: shared identity, theme and confirmation-screen presentation.
- `tests/browser/workspace.spec.ts`: updated the homepage heading assertion; existing interaction coverage retained.

Backend code, Supabase schema/configuration/policies, contracts and `.env` are outside this change. No remote operations, migrations, account creation, payments, commits or pushes performed. Earlier uncommitted recovery edits remain intact.

## Verification

- ESLint: passed.
- TypeScript: passed.
- Production build: passed after Windows permission blocked an initial generated directory.
- HTTP checks: 200 for `/`, `/artists`, `/saved`, `/plan`, `/login`, `/join`, `/account`, `/about`, `/auth/confirm`, the new ivory SVG and local serif WOFF2.
- Existing browser tests were updated but not executed during this rebuild. Browser access reports “Local browser use is disabled in Work settings.” The user intends to enable it; the tool remains disabled at the last attempt.
- HTTP success does not verify visual layout, client-side interactions or authenticated workflows.

## Acceptance still needed

Inspect desktop, laptop, tablet and mobile renderings; check overflow, typography, image crops, navigation/dialog keyboard behavior and console errors. Exercise catalogue search, guest shortlist persistence, draft persistence, login/registration states and existing role-specific workspace journeys. Run the existing frontend browser suite against its configured isolated fixtures after browser access is restored. Do not run fixture expectations against the connected 120-record catalogue. No backend tests need repeating solely for presentation changes.

Existing external email/payment acceptance remains documented in the recovery report; no setup was changed by this frontend task.

## Run

From the repository root:

```powershell
npm run dev
```

Open `http://127.0.0.1:3000/`. For checks: `npm run lint`, `npm run typecheck`, `npm run build`. Dependencies and the recovered local environment are already present in this workspace.
