# Windows installer template (verified in Al-Store)

Copy these files into a product, then change the marked names. Verified on a real Windows runner by Al-Store's workflow
`windows installer` (build → start the program folder → silent install → start the installed program → uninstall keeps the data).

| File | Goes to | Change |
|---|---|---|
| `build_windows.py` | `tools/` | `EXE`, `SHIPPED`, the Nuitka `--include-data-*` lines for your static files |
| `installer.iss` | `installer/store.iss` (rename) | `MyAppName`, **two** `AppId` GUIDs (`commercial` vs `ci-test` via `/DAppChannel=`), folder names, practice shortcut |
| `windows.yml` | `.github/workflows/` | exe/folder names in the smoke steps |
| `smoke_exe.py` | `tools/` | the asset list that must be served |
| `make_icon.py` | `tools/` | draw your own icon |

Rules that cost a day to learn (see docs/knowledge/LESSONS.md):
1. The program must never die because a console cannot print Arabic or does not exist (`say()` in Al-Store's `server/app.py`).
2. Resolve `web/` and key files next to the compiled program (`FROZEN` / `ROOT` in `server/version.py`), not relative to `__file__`'s parent.
3. Data lives in `%ProgramData%\<Product>`, never in Program Files; the installer never touches it; uninstall keeps it.
4. The smoke test prints the program's own output when it fails — without that the first red run is unreadable.
5. Firewall rule for the private/domain network only.
6. CI builds must use a **different** Inno `AppId` and install folder than commercial (`AF_INSTALLER_CHANNEL=ci-test` in `build_windows.py`, or `/DAppChannel=ci-test` on ISCC) so test installers never upgrade a real customer's copy in place.
7. A smoke test that only checks pages can miss a sold build whose licence can be switched off. `smoke_exe.py` already starts the program on a brand-new data folder. Pass `--license-path /your/licence/status` (and `--license-state trial` when that is the fresh state), or set `AF_SMOKE_LICENSE_PATH` and `AF_SMOKE_LICENSE_STATE`. The check stays off until the product names its own route.
