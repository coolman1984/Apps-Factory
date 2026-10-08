# Repository map 🗺️ (checked 2026-10-08)

What each repository of the owner is, what it is good for, and what the factory can reuse. Facts come from each README read in
this session; rows marked **not inspected** were only listed, never opened. Private repositories are listed by name only.

## Products built with the factory rules
| Repository | What it is | Stack | Reuse in the factory |
|---|---|---|---|
| `Apps-Factory` | The factory: constitution, controls, schema, Control Center, af-license, **Licence Studio**, **af-ui**, **UI Lab**, knowledge | Python, JS | — |
| `Store` | **Al-Store (الستور)** — household & appliance shop: counter, serials, instalments, owner's eye | Python stdlib + ES modules | First consumer of af-ui, UI Lab, licence codes |
| `Teachers` | **Hessa (حِصّة)** — tutoring centres; office mesh sync, the Watch, parent gateway | Python stdlib + JS + Cloudflare Worker | Source of mesh, watch, advisor, help standards (docs/HESSA_FACTORY_ALIGNMENT.md) |
| `Yousef-Transportation` | **Trip Orders** — transport office trips/drivers/km; the engine Hessa forked | Python stdlib + JS | Original engine and design family |
| `Doctors` | **Eyada** — clinics, offline per PC, encrypted sharing, patient mailbox, signed-licence modules | — | Same architecture family (not inspected in depth) |
| `Mr.Ayman-HR` | **BAMS** — break-area management, one installer, one-PC or many-PC | Python | Installer + multi-PC pattern |
| `Accounting-sys` | **Mizan** — double-entry accounting, LAN, AR/EN | Node 22 + TypeScript + SQLite | Accounting contracts for factories (GMES link) |
| `GMES` | Lightweight MES for small factories (kernel + Mizan link) | TypeScript | Ecosystem contracts, ×1000 quantities, outbox/acks |
| `complete-company` | One package of four apps (Mizan, GMES, HR, 3D planner) | — | Multi-app packaging |
| `HR-System` | People/attendance source of truth for the ecosystem | — | Identity of people |
| `3D-Modeling` | **Atrium** space planner (3D, desktop installer, Electron-style window) | TypeScript, pnpm | Installer without admin rights, data in %APPDATA% |
| `Seramic-Rondi` | Ceramic & porcelain factory system (plan) | — | Factory domain research |
| `Delivery-Manager` | Multi-tenant delivery platform for one governorate | — | Tenancy (cloud_only) reference |
| `Self-Business-App` | Business OS for 1–4 person businesses (research done) | — | Next product candidate |
| `Business-Template`, `Perfect-Project-Template` | Business engines/recipes; offline Excel automation engine | Python | Integrate, don't rebuild (README) |

## Automation and agents
| Repository | What it is | Reuse |
|---|---|---|
| `opening-nerp-tcode` | Samsung **G-MES automation through Chrome DevTools Protocol** (Nexacro): sign-in with DPAPI credential, open screens, run Inquiry, export Excel; 100+ phases of history | CDP know-how, "prove every action" discipline, PROJECT_EXPERIENCE.md field guide |
| `win-agent-desktop` | **wad** — Windows desktop automation for agents through the accessibility tree, proves every action | Agent tooling for Windows apps |
| `Computer-use`, `Python-RPA` | SmartOps: repeat a report download in Chrome and prove the file; PySide6 workflow recorder | RPA patterns |
| `Performance` | **WinSight** — Windows check-up toolkit with 34 tools, reversible fixes and an **MCP server** for agents | Support diagnostics; MCP pattern |
| `Office-Automation`, `Excel-Data-Extractor`, `Webassembly-Webapp`, `automate-excel-reports` | Excel → verified SQLite → AI context; trustworthy extraction CLI; BOM dashboard | Data import for products |
| `Search-Jobs`, `Economic` | Personal business-development agent; EGX investment office ("software calculates, AI challenges") | Agent product patterns |

## Visual and marketing
| Repository | What it is | Reuse |
|---|---|---|
| `Animation` | **Code-driven film studio**: HTML/CSS/JS scenes rendered frame by frame, motion kits (`lib/uimorph.js`, `kinetics.js`), music/voice, quality playbook | Motion grammar of af-ui; **promo films for every product** (capture real screens with `lib/app-capture.mjs`) |
| `promo-video-generator` (fork) | Deterministic web-page → MP4 with motion blur and synthesised soundtrack | Launch films |
| `shaders` (fork) | 200+ WebGPU effects as components (gradients, glass, metal, light, transitions) | Marketing pages only; never on working screens (PERF-02) |
| `The-Slide-Show`, `presentation`, `Personal-Web`, `Course` | Decks, training course, personal site | Sales material |

## Forks of agent platforms (study, don't ship)
`opencode`, `OpenHands`, `continue`, `composio`, `agent-zero`, `Fabric`, `memU`, `langfuse`, `delegate-skills`, `harness-engineering`,
`deepseek-harness`, `Agent-Reach`, `TradingAgents`, `whisper`, `free-for-dev` — not inspected in this session.

## Everything else
Private or not inspected: `Control`, `Production-Plan-Reporting-Codex`, `my-ideas-book`, `Course`, `Programming-`, `work_dashboard`,
`City-Zero`, `Hermes-Agent-Skills`, `Best-Hermes-Skills`, `Files_-_OCR`, `AI`, `Openclaw`, `ActivityApp-Releases`, and the private repositories.
