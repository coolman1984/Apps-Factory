# Design QA gate

Use this checklist as product-specific test instructions. **Static checks are insufficient.**

## Visual
- [ ] Primary user task immediately obvious; no equal-weight rainbow KPI/card grid
- [ ] Intended visual identity consistently carried across routes, forms and reports
- [ ] Typography hierarchy, readable contrast, color is semantic, no accidental overflow/clipping
- [ ] Check desktop 1440×900, tablet 768×1024 and phone 390×844; 320px + 200% zoom as stress cases
- [ ] Light/dark surfaces, selected/hover/focus/disabled/error states
- [ ] Arabic right-to-left and English left-to-right: numbers, dates, prices, table/actions, icons
- [ ] Reference screenshot compared with actual rendered screenshot after build, and changes accepted

## Function
- [ ] Buttons and links perform real actions; no fake interaction
- [ ] Form submission validation/save/error/retry; stale data and double click
- [ ] Search/sort/filter/export accurate; loading/empty/permission denied/offline
- [ ] Keyboard navigation and focus visible; Escape/drawer/dialog behavior
- [ ] Correct real API authorization; UI hidden actions cannot bypass server

## Access and technical
- [ ] WCAG 2.2 AA automated scan **and** manual keyboard review; issues documented
- [ ] No external CDNs for offline build; fonts/assets bundled and licensed
- [ ] Only one chosen UI kit; no competing global CSS reset/theme libraries
- [ ] No customer data/credentials in screenshots; synthetic examples labeled
- [ ] No React dependency introduced into a plain HTML app without separate decision
- [ ] Third-party licence notices and component provenance retained

## Reports
- Status for each line PASS / FAIL / UNVERIFIED, with screenshot/test evidence.
- Browser unavailable => screenshot verification UNVERIFIED, never PASS.
- Accessibility scanner green ≠ full WCAG compliance; record manual results.
