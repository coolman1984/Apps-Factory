# GitHub radar 📡 — well-known projects we rely on or learn from

**Adopt** = used now. **Trial** = next product should try it. **Learn** = study the pattern, don't depend on it.
Licences must stay permissive (MIT / Apache-2.0 / BSD / OFL) for anything shipped inside a product.

| Project | Ring | Why |
|---|---|---|
| [microsoft/playwright](https://github.com/microsoft/playwright) | Adopt | Browser tests, UI Lab, CDP throttling (Apache-2.0) |
| [dequelabs/axe-core](https://github.com/dequelabs/axe-core) | Adopt | Accessibility rules in UI Lab (MPL-2.0, test-time only) |
| [GoogleChrome/web-vitals](https://github.com/GoogleChrome/web-vitals) | Learn | Definitions of LCP / CLS / INP we measure |
| [GoogleChrome/lighthouse](https://github.com/GoogleChrome/lighthouse) | Trial | Second opinion on a release candidate |
| [fontsource/fontsource](https://github.com/fontsource/fontsource) + Google Fonts (Readex Pro, Alexandria) | Adopt | Self-hosted OFL fonts |
| View Transitions API ([w3c/csswg-drafts](https://github.com/w3c/csswg-drafts)) | Adopt | Page swaps without a framework |
| [pyca/cryptography](https://github.com/pyca/cryptography) | Adopt | Signing in Licence Studio only (products verify with stdlib) |
| [Nuitka/Nuitka](https://github.com/Nuitka/Nuitka) + [jrsoftware/issrc](https://github.com/jrsoftware/issrc) (Inno Setup) | Adopt (Hessa) | Compiled Windows build + installer |
| [modelcontextprotocol/specification](https://github.com/modelcontextprotocol/specification) | Adopt | MCP for agents (Licence Studio, WinSight) |
| [odoo/odoo](https://github.com/odoo/odoo) `point_of_sale` | Learn | Offline POS session, cash control, returns |
| [frappe/erpnext](https://github.com/frappe/erpnext) | Learn | Serial/batch stock, instalment-like payment schedules |
| [inventree/InvenTree](https://github.com/inventree/InvenTree) | Learn | Stock locations, stocktake |
| [electric-sql/electric](https://github.com/electric-sql/electric), [rocicorp/mono](https://github.com/rocicorp/mono) | Learn | Sync patterns for `cloud_sync` tier |
| [litestream](https://github.com/benbjohnson/litestream) | Trial | Continuous SQLite backup to cloud tier |
| [pmndrs/motion](https://github.com/motiondivision/motion) | Learn | Spring motion ideas (we keep our own tiny kit) |
| [Shopify/polaris](https://github.com/Shopify/polaris), [carbon-design-system/carbon](https://github.com/carbon-design-system/carbon) | Learn | Design-system documentation quality |
