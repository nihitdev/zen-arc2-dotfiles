# Zen Arc 2.0 dotfiles

A snapshot of [nihitdev](https://github.com/nihitdev)'s working Zen Browser customization: Arc 2.0 styling, a fireplace new-tab background, and the active Zen Mods appearance.

Repository: **https://github.com/nihitdev/zen-arc2-dotfiles**

> Publication preparation: Apple SF Pro / SF Symbols font redistribution remains unresolved. The fonts are included in this local preparation at the owner's explicit request. See [security and licensing review](SECURITY-AND-LICENSING.md) before distributing this repository.

## Screenshots

_Screenshot placeholder: add a screenshot of the sidebar and fireplace new tab with personal tabs, bookmarks, workspace names, and account details hidden._

## Features

- The existing Arc-style sidebar, tab groups, URL bar, workspace buttons, animations, borders, and picture-in-picture styling.
- Original `CONFIG.css` values and animated `fireplace.gif` new-tab background, with the logo/search hidden.
- A snapshot of all 11 active Zen Mods, including floating history/status bar and the customized Ctrl+Tab panel.
- Local fonts and icons, preserving filename case and directory structure.
- Linux and Windows installers with profile discovery, interactive selection, overwrite confirmation, integrity checks, and backups.

This is a preserved personal configuration, not a replacement with the latest upstream theme. Only external asset URLs in `modules/Chrome/icons.css` were converted to relative URLs; the local font files and pinned upstream icons supply those assets. [packaging-changes.json](packaging-changes.json) records each substitution. Other copied files are unchanged. Remote font versions may have differed from the local copies; visual equivalence has not been browser-tested.

## Requirements

- Zen Browser installed and launched at least once, with an existing profile.
- Linux: Bash and Python **3.9+**. Windows: Windows PowerShell **5.1+** or PowerShell 7.
- Write access to your own profile. No root, `sudo`, or administrator terminal is required.
- Close **all Zen windows and background processes** before installation.

The installers preserve existing `user.js` contents and append three explicit theme settings: stylesheet loading, transparent browser content, and the source setup's single-toolbar preference (`false`). They do not copy `prefs.js`, sessions, workspaces, bookmarks, account data, extensions, or window placement.

## Linux installation

```bash
git clone https://github.com/nihitdev/zen-arc2-dotfiles.git
cd zen-arc2-dotfiles
./install.sh
```

Select a profile if prompted, confirm Zen is closed, and review any overwrite prompt. Restart Zen after success.

Discovery checks `$XDG_CONFIG_HOME/zen`, `~/.config/zen`, `~/.zen`, and common Flatpak profile locations. For a portable or unusual installation, use the **Root Directory** shown in `about:profiles`:

```bash
./install.sh --profile "/path with spaces/to/your profile"
# Or point discovery to another profile registry:
./install.sh --profiles-ini "/path with spaces/profiles.ini"
```

## Windows installation

In a regular PowerShell terminal:

```powershell
git clone https://github.com/nihitdev/zen-arc2-dotfiles.git
Set-Location .\zen-arc2-dotfiles
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

`-ExecutionPolicy Bypass` applies only to that PowerShell process. Review the script first; organization policies may still prevent execution. In PowerShell 7, use `pwsh` instead of `powershell.exe`.

Discovery reads `%APPDATA%\zen\profiles.ini` and `%APPDATA%\Zen Browser\profiles.ini`. Select your profile and approve any customization-file overwrites. Restart Zen after installation. For a portable installation:

```powershell
.\install.ps1 -ProfilePath "D:\Zen Portable\Profiles\My profile"
# Or:
.\install.ps1 -ProfilesIni "D:\Zen Portable\profiles.ini"
```

## What gets installed

- `chrome/`: the complete manifest-listed payload, including both original font directories, icons, fireplace GIF, and `zen-themes.css`.
- `user.js`: existing bytes are retained and the theme preference block is appended. A repeat installation is a no-op if the files and final preference block already match.

Only files listed in `manifest.json` plus `user.js` are written. Existing unrelated files are retained. Symlinks/junctions beneath the profile are rejected. Updated files are backed up to a fresh `.zen-arc2-backup-<id>` directory inside the selected profile before writing begins. A failed write may leave a partial installation; the error and backup path allow recovery.

The bundled `zen-themes.css` is a static snapshot of the source setup. Zen can regenerate it when managing Mods in Settings; that can replace these styles. Do not edit it through the Mods manager if you want to retain this snapshot. Existing extensions and their toolbar positions are not installed or moved by these scripts.

## Troubleshooting and restoring

- **No profiles found:** launch Zen once, then retry or use an explicit profile path. Choose the profile's Root Directory, not its cache/Local Directory.
- **No visible styling:** check the selected profile, restart Zen fully, and verify `toolkit.legacyUserProfileCustomizations.stylesheets = true` in `about:config`.
- **Profile locked:** close Zen fully. The installer never removes lock files. A stale Linux `lock` link also causes a safe refusal; verify no Zen process is using the profile before investigating it.
- **Checksum mismatch:** restore the checkout's files or intentionally regenerate `manifest.json` after reviewing your edits; the installer rejects missing/changed payloads.
- **Different colors, fonts, or transparency:** Zen versions, operating-system rendering, compositor effects, workspace colors, extension settings, and native toolbar layout affect appearance. Those personal browser settings are not a portable CSS theme. The new-tab and Arc CSS are preserved, but pixel-identical rendering across platforms is not guaranteed.
- **Restore:** close Zen, copy the affected files from the printed backup directory to their original relative paths, then restart. To uninstall newly added files, remove only paths listed in `manifest.json`; never delete the entire profile or `chrome` directory. Restore `user.js` from backup or remove its marked theme block. Preferences already loaded into `prefs.js` may need resetting in `about:config`.

## Validation

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
bash -n install.sh
shellcheck install.sh  # optional development tool
```

Linux validation uses disposable mock profiles, including paths with spaces, relative/absolute profile discovery, overwrite cancellation, backups, repeat installation, profile locks, and symlink rejection. PowerShell is not installed on the preparation machine, so its parser and Windows runtime behavior have not been tested. No live profile was modified during validation.

## Credits and licensing

- [Arc 2.0](https://github.com/YashjitPal/Arc-2.0), by **YashjitPal / Equinox**. Its README explicitly permits redistribution with credit; a pinned record is in [licenses/Arc-2.0-PERMISSION.md](licenses/Arc-2.0-PERMISSION.md).
- [Nebula](https://github.com/JustADumbPrsn/Zen-Nebula), by **JustADumbPrsn**, and the contributors credited by Arc 2.0, including neurokitti, TheBigWazz, GuiMar10, Tanay-Kar, greeeen-dev, lunar-os, sameerasw, rrthrr, and Comp-Tech-Guy.
- [Arc_Zen_Theme](https://github.com/neurokitti/Arc_Zen_Theme), by **neurokitti / Studio Movie Girl**, for the local sidebar and archive icons.
- [Zen Mods](https://github.com/zen-browser/theme-store): Lumio4u, lindongbin, Felkazz, TheCatRiX, psu, AmirhBeigi, ahmaadaziz, qtchaos, ch4og, Dinno-DEV, and Anoms12, with attribution retained in the snapshot.
- Nunito and SUSE project authors for their OFL fonts; Apple Inc. for SF Pro and SF Symbols (proprietary).
- Fireplace GIF and personal configuration: **nihitdev**.

See [LICENSE](LICENSE) for component-specific terms and [licenses/](licenses/) for notices. The packaging license does not relicense upstream code or proprietary fonts. This is an independent dotfiles repository, not an official Arc or Zen Browser release.
