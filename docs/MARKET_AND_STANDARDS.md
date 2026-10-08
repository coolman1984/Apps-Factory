# Commercial engineering standards • checked 2026-10-08

This is a **risk-scoped engineering baseline**, NOT an assertion of audit certification, universal legal compliance or the complete requirements of every country/industry. Implementation/evidence must be recorded per product. Official primary sources linked below; review for changes before launch.

## 1. Engineering/security anchors
| Source | Current status / relevance | Factory controls / evidence |
|---|---|---|
| [OWASP ASVS v5](https://owasp.org/projects/asvs) | Stable v5.0.0 | ASVS baseline mapping; authn/authz, input/output, logs, error handling, encryption; attack tests per exposed surface |
| [OWASP API Top 10](https://api-security.owasp.org/editions/2023/en/0x11-t10/) | 2023 published guidance | Object-, field-, function-level authorization; anti-automation and rate limits |
| [NIST SSDF SP 800-218 v1.1](https://csrc.nist.gov/pubs/sp/800/218/final) | Final, Feb 2022; [v1.2 is draft](https://csrc.nist.gov/projects/ssdf/publications) as checked | Secure SDLC, code review, provenance, vulnerability response, change control |
| [OWASP SAMM](https://owaspsamm.org/model/) | Maturity improvement model | Governance, design, implementation, verification, operations |
| [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) | Current cheat sheet | Adaptive salted password hashing (Argon2id preferred, or vetted alternatives) and password lifecycle |
| [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) | W3C Recommendation (12 Dec 2024 update) | Target AA on web UI: labels, focus, contrast, keyboard, errors, accessible dialogs |
| [OWASP SCVS](https://scvs.owasp.org/scvs/using-scvs/) | Supply-chain verification standard | Dependency/source inventory, SBOM, component analysis, provenance |
| [GitHub supply chain guidance](https://docs.github.com/en/code-security/concepts/supply-chain-security/supply-chain-security) | Operational practice | Pin deps, controlled releases and provenance, vulnerability patch policy |
| [CISA Secure by Design Pledge](https://www.cisa.gov/sites/default/files/2024-05/CISA%20Secure%20by%20Design%20Pledge_508c.pdf) | Product design guidance (not certification) | No shared default passwords in sold software; secure setup experience |
| [OWASP Agentic AI Top 10](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/) | Published Dec 2025 | Prompt injection, privilege misuse, agent tool scope/approvals, output verification where AI acts |

### Priority controls for every saleable business app
**P0/never waive:** secure provisioning, per-action server authorization, tenant isolation if multi-tenant, money/idempotency if financial, data persistence/correction/audit, restorability, secret protection, safe deployment, consent-based vendor support, honest licensing states, no public real data.
**P1/required for agreed launch scope:** usability AR/EN where marketed, WCAG AA target for web surfaces, onboarding, status/help, observability, support/incident process, signed/traceable releases and dependency scanning.
**Conditional:** MFA for high-risk/public exposed owners, hosted tenancy, offline signature licensing, SSO, mobile camera, AI tool governance, HIPAA/PCI/education/medical/finance requirements, localization/tax adapters, dedicated penetration tests.

## 2. Localization and market routing
**Egypt:** Egyptian Arabic content help for SME staff, correct RTL and Arabic numbers/date/currency/time formatting, offline/LAN offerings where appropriate; legal review for [Egypt Law 151/2020 and Executive Regulations 816/2025](https://www.pdpc.gov.eg/) including data roles, notices, consent/legitimate basis, rights, retention and cross-border transfers. **Never assume** local-only deployment automatically exempts privacy duties.

**Saudi Arabia:** Arabic-first product and official forms, localized SAR/VAT support if applicable, contractual hosting/transfer preferences; legal review against [SDAIA PDPL implementing regulation](https://sdaia.gov.sa/en/SDAIA/about/Documents/ImplementingRegulation.pdf) and [cross-border transfer rules](https://dgp.sdaia.gov.sa/wps/portal/pdp/knowledgecenter/details/RegulationonPersonalDataTransferOutsidetheKingdom). Government or regulated buyers may require sector-specific security standards.

**UAE:** Arabic+English where targeted, AED/VAT features only if relevant, regional hosting decisions and rights/consent; review [Federal Decree-Law 45/2021](https://u.ae/ar/about-the-uae/digital-uae/data/data-protection-laws) and relevant free-zone or sector regime. UAE law is not automatically interchangeable with Saudi/Egypt law.

**European Union:** If targeting EU customers or monitoring people in EU, evaluate [EU GDPR territorial scope](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/application-gdpr_en); subject rights, legal basis, data transfer, retention, data processor terms and breach process. Do not claim EU compliance from a checkbox.

**United States/rest of world:** No single "US privacy law" or one global tax/invoice format; identify actual state, sector, data type, customer size, payment method and hosting. PCI DSS only when payment-card data is in scope: prefer hosted payment pages/tokenization to minimize it.

## 3. Sellability features: all products vs conditional
| Product capability | Core expectation | Only if required |
|---|---|---|
| Market study & pricing | Customer/persona, direct competition, dated feature/price evidence, willingness-to-pay interviews | Geographic expansion |
| Administration | User roles, org profile, secure setup/recovery, audit, export/backup | Multi-site, complex approval chains |
| Billing and licensing | Explicit plan, entitlement and renewal/grace/cancel rules for paid software | Billing gateway for SaaS; signed offline activation for desktop |
| Data/financial integrity | Durable write, retry safety, backup+restore, reports consistent with source | Immutable finance ledger, tax integrations |
| UX | Coherent components, onboarding, AR/EN when marketed, understandable errors, responsive web | Specialized 3D/canvas or advanced analytics |
| Support and operations | Opt-in support, diagnostics, documentation and patch channel | SLA 24/7, enterprise SSO |
| Security and privacy | Least-privilege, secure storage, transport appropriate to mode, privacy policy and inventory | High-risk/regulatory assessments |
| Distribution | Exact version/artifact, safe upgrade, field install test | Automatic updater, app-store approval |
| Integrations | Export/CSV where valuable; stable data contract | ERP, messaging, AI, billing/e-invoicing APIs |

## 4. No fake universal market conclusions
Market research requires **at least 5 direct/adjacent competitors where available**, evidence links, region and price date, feature tier, target buyer, customer complaints from attributable reviews, 5 real-customer questions and estimated monthly support costs. If research cannot verify pricing/competitors, say UNKNOWN. Existing repo capabilities do not establish demand.

## 5. Regulatory gates
Compliance profile lives in the product manifest: jurisdictions, regulated data, data residency, data controller/processor mapping, legal-review owner, sources checked/date and explicit applicability. No final legal/tax/security compliance label may be set without competent human sign-off.
