# Publication review

Prepared on 2026-10-13. Public creation and push require the owner's final confirmation.

## Scope and preservation

The source is the active Zen release profile's `chrome` directory. The original
profile was read only; installer testing used temporary mock profiles.

The payload includes `userChrome.css`, `userContent.css`, `CONFIG.css`, the 12
imported Chrome modules, both existing font directories, `fireplace.gif`, two
pinned upstream SVG icons, and the active `zen-themes.css` snapshot. The 11 Mods
and their authors remain credited inside that snapshot.

All copied source files were byte-compared against the profile. The only allowed
changes are the eight URL substitutions recorded in `packaging-changes.json`:
six font sources and two SVG source URLs (one SVG appears twice). These make
assets local; CSS selectors, values, order, and configuration remain intact.
Local font versions have not been compared against the historical remote font
responses, so pixel-identical appearance is not claimed.

Unused content/PDF modules, old Nebula metadata, sample fx-autoconfig CSS,
JavaScript loader files, and inactive theme-management files are not dependencies
of the imported Arc styles and are omitted. Native workspace colors, extensions,
toolbar placement, and operating-system compositor configuration are not exported.

## Security review

- No history, cookies, passwords, tokens, sessions, browser databases, or profile
  JSON files were copied or staged.
- `prefs.js` is not included. `theme-prefs.js` contains just three explicitly
  selected, primitive theme preferences; it contains no account or site data.
- Theme assets were enumerated explicitly. Manifest checksums cover the 31
  payload files and the generated preference file.
- Every active CSS import and local asset reference resolves. No active CSS
  dependency needs an HTTP request. Browser-provided `chrome:`, `resource:`,
  `about:` and embedded `data:` URLs are intentionally retained.
- The GIF was visually inspected: pixel-art scenery, no visible browser data;
  no GIF comment metadata was present.
- The staged allowlist and focused private-path/token scan passed. This is not
  a guarantee that an arbitrary future file contains no secret.
- Both installers request overwrite confirmation, preserve unrelated files,
  and create backups before writing changed existing files. They do not elevate
  privileges or download/execute remote code. SHA-256 detects changed/missing
  payload files, but is not a signature authenticating the repository author.

## Licensing review

- **Arc 2.0:** YashjitPal / Equinox explicitly permits forking, modification and
  redistribution with attribution in the upstream README. A commit-pinned copy
  of that statement is in `licenses/Arc-2.0-PERMISSION.md`.
- **Nebula lineage:** credited to JustADumbPrsn; upstream GPL-3.0 text is included,
  and the distributed CSS source is available directly in this repository.
- **Arc_Zen_Theme icons and Zen Mods:** upstream MIT notices are included.
- **Nunito and SUSE:** SIL OFL notices are included.
- **Fireplace GIF:** the owner confirmed ownership and requested inclusion.
  That does not grant downstream users a separate reuse license.
- **Apple SF Pro / SF Symbols: unresolved redistribution permission.** The
  owner explicitly requested inclusion after being told about the restrictions.
  Their binaries are present in this local commit, in both original font
  directories. The embedded SF Pro notice restricts use and does not authorize
  this public cross-platform redistribution. The owner request is not an Apple
  license. These fonts must not be described as MIT/OFL/GPL. Public publication
  of this exact commit would include them despite that unresolved issue.

The root `LICENSE` licenses only original packaging under MIT and lists the
separate component terms. It does not claim ownership of upstream work or confer
rights that the upstream authors have not granted.

## Validation results

- Linux mock-profile integration tests: **13 passed**.
- Bash syntax (`bash -n`) and ShellCheck: **passed**.
- Git whitespace check: original CSS and upstream license files contain trailing
  whitespace, retained to preserve their bytes. New packaging files pass.
- Manifest and CSS dependency audit: **31 payload files, 20 local references,
  all passed**.
- Source byte comparison: **passed**, allowing only documented URL substitutions.
- PowerShell parser validation: **not run**, neither `pwsh` nor `powershell` is
  installed on the preparation machine.
- Windows runtime and live-browser visual validation: **not run**.

No public repository was created and no push was performed during preparation.
The GitHub CLI is authenticated as the intended owner; the requested repository
was not found at the initial check. Its existence and remote history must be
rechecked immediately before publishing. A future publication must not force-push.
