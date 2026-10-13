#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$ProfilePath,
    [string]$ProfilesIni
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-SafeTarget([string]$Root, [string]$Relative) {
    $current = $Root
    $parts = $Relative.Split('/')
    foreach ($part in $parts) {
        $current = Join-Path $current $part
        # Get-Item also detects reparse points, including directory junctions.
        $item = Get-Item -LiteralPath $current -Force -ErrorAction SilentlyContinue
        if ($null -ne $item) {
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing a symlink or junction: $current"
            }
            if ($part -ne $parts[-1] -and -not $item.PSIsContainer) {
                throw "Parent is not a directory: $current"
            }
        }
    }
    if (Test-Path -LiteralPath $current -PathType Container) { throw "Destination is a directory: $current" }
    return $current
}

function Read-Profiles([string]$Ini) {
    if (-not (Test-Path -LiteralPath $Ini -PathType Leaf)) { return }
    $sections = @{}
    $section = ''
    foreach ($line in [IO.File]::ReadAllLines($Ini)) {
        if ($line -match '^\s*\[([^\]]+)\]\s*$') {
            $section = $Matches[1]
            $sections[$section] = @{}
        } elseif ($section -and $line -match '^\s*([^=;#]+?)\s*=(.*)$') {
            $sections[$section][$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }
    foreach ($key in ($sections.Keys | Sort-Object)) {
        $entry = $sections[$key]
        if ($key -notmatch '^Profile' -or -not $entry.ContainsKey('Path')) { continue }
        $path = $entry['Path'].Replace('/', [IO.Path]::DirectorySeparatorChar)
        if ($entry['IsRelative'] -ne '0') { $path = Join-Path (Split-Path -Parent $Ini) $path }
        if (Test-Path -LiteralPath $path -PathType Container) {
            [PSCustomObject]@{ Path = [IO.Path]::GetFullPath($path); Name = $entry['Name'] }
        }
    }
}

try {
    $root = $PSScriptRoot
    $manifest = Get-Content -LiteralPath (Join-Path $root 'manifest.json') -Raw | ConvertFrom-Json
    $files = New-Object 'System.Collections.Generic.List[object]'
    $seen = @{}
    foreach ($entry in $manifest.files) {
        $relative = [string]$entry.path
        if ($relative -notmatch '^chrome/.+' -or $relative -match '(^|/)\.\.?(/|$)|[\\:]|//|/$' -or $seen.ContainsKey($relative)) {
            throw "Unsafe or duplicate manifest path: $relative"
        }
        $seen[$relative] = $true
        $source = Get-SafeTarget $root $relative
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing payload: $relative" }
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
            throw "Changed payload: $relative. Run scripts/validate.py."
        }
        $files.Add([PSCustomObject]@{ Path = $relative; Bytes = [IO.File]::ReadAllBytes($source) })
    }
    foreach ($required in @('chrome/userChrome.css', 'chrome/userContent.css', 'chrome/CONFIG.css')) {
        if (-not $seen.ContainsKey($required)) { throw 'Incomplete manifest.' }
    }
    if ($ProfilePath) {
        if (-not (Test-Path -LiteralPath $ProfilePath -PathType Container)) { throw "Profile not found: $ProfilePath" }
        $profile = (Resolve-Path -LiteralPath $ProfilePath).ProviderPath
    } else {
        if ($ProfilesIni) {
            $iniFiles = @([IO.Path]::GetFullPath($ProfilesIni))
        } else {
            if (-not $env:APPDATA) { throw 'APPDATA is unavailable. Use -ProfilePath PATH.' }
            $iniFiles = @((Join-Path $env:APPDATA 'zen/profiles.ini'), (Join-Path $env:APPDATA 'Zen Browser/profiles.ini'))
        }
        $profiles = @($iniFiles | ForEach-Object { Read-Profiles $_ } | Sort-Object -Property Path -Unique)
        if ($profiles.Count -eq 0) { throw 'No Zen profiles found. Launch Zen once or use -ProfilePath PATH.' }
        for ($i = 0; $i -lt $profiles.Count; $i++) { Write-Host "$($i + 1). $($profiles[$i].Name)`n   $($profiles[$i].Path)" }
        $choice = 1
        if ($profiles.Count -gt 1) {
            $answer = Read-Host 'Select profile number'
            if (-not [int]::TryParse($answer, [ref]$choice)) { throw 'Invalid profile selection.' }
        }
        if ($choice -lt 1 -or $choice -gt $profiles.Count) { throw 'Invalid profile selection.' }
        $profile = $profiles[$choice - 1].Path
    }
    Write-Host "Target: $profile"
    # Reject live Windows profile locks; an unlocked leftover parent.lock is harmless.
    $lockPath = Join-Path $profile 'parent.lock'
    if (Test-Path -LiteralPath $lockPath) {
        try { $lockStream = [IO.File]::Open($lockPath, 'Open', 'ReadWrite', 'None'); $lockStream.Dispose() }
        catch { throw 'The profile is locked. Close Zen completely and retry.' }
    }
    if ((Read-Host 'Close Zen completely before installing. Is Zen closed? [y/N]') -notmatch '^(y|yes)$') {
        Write-Host 'Cancelled; no files were changed.'; exit 0
    }
    $prefsPath = Get-SafeTarget $profile 'user.js'
    [byte[]]$oldPrefs = @()
    if (Test-Path -LiteralPath $prefsPath) { $oldPrefs = [IO.File]::ReadAllBytes($prefsPath) }
    if ((Get-FileHash -LiteralPath (Join-Path $root 'theme-prefs.js') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.preferences_sha256) {
        throw 'Theme preference checksum mismatch.'
    }
    $prefs = [IO.File]::ReadAllText((Join-Path $root 'theme-prefs.js'))
    if (-not $prefs.EndsWith("`n")) { throw 'Invalid theme-prefs.js.' }
    [byte[]]$block = [Text.Encoding]::UTF8.GetBytes("`n// BEGIN zen-arc2-dotfiles`n" + $prefs + "// END zen-arc2-dotfiles`n")
    $hasBlock = $oldPrefs.Length -ge $block.Length
    if ($hasBlock) {
        for ($i = 0; $i -lt $block.Length; $i++) {
            if ($oldPrefs[$oldPrefs.Length - $block.Length + $i] -ne $block[$i]) { $hasBlock = $false; break }
        }
    }
    [byte[]]$newPrefs = $oldPrefs
    if (-not $hasBlock) { $newPrefs = $oldPrefs + $block }
    $files.Add([PSCustomObject]@{ Path = 'user.js'; Bytes = $newPrefs })
    $changed = New-Object 'System.Collections.Generic.List[object]'
    $overwritten = New-Object 'System.Collections.Generic.List[string]'
    foreach ($file in $files) {
        $destination = Get-SafeTarget $profile $file.Path
        if (Test-Path -LiteralPath $destination -PathType Leaf) {
            $existing = [IO.File]::ReadAllBytes($destination)
            if ([Convert]::ToBase64String($existing) -eq [Convert]::ToBase64String($file.Bytes)) { continue }
            $overwritten.Add($file.Path)
        }
        $changed.Add($file)
    }
    if ($changed.Count -eq 0) { Write-Host 'Success: the complete theme is already installed; no changes needed.'; exit 0 }
    if ($overwritten.Count -gt 0) {
        Write-Host "Existing files to update (backups will be saved):`n$($overwritten -join "`n")"
        if ((Read-Host 'Overwrite these customization files? [y/N]') -notmatch '^(y|yes)$') {
            Write-Host 'Cancelled; no files were changed.'; exit 0
        }
        $backup = Join-Path $profile ('.zen-arc2-backup-' + [Guid]::NewGuid().ToString('N'))
        [IO.Directory]::CreateDirectory($backup) | Out-Null
        foreach ($relative in $overwritten) {
            $backupFile = Join-Path $backup $relative
            [IO.Directory]::CreateDirectory((Split-Path -Parent $backupFile)) | Out-Null
            [IO.File]::Copy((Join-Path $profile $relative), $backupFile, $false)
        }
        Write-Host "Backup: $backup"
    }
    foreach ($file in $changed) {
        $destination = Get-SafeTarget $profile $file.Path
        [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
        $temporary = Join-Path (Split-Path -Parent $destination) ('.zen-arc2-' + [Guid]::NewGuid().ToString('N'))
        try {
            [IO.File]::WriteAllBytes($temporary, $file.Bytes)
            if ([IO.File]::Exists($destination)) {
                [IO.File]::Replace($temporary, $destination, $null)
            } else {
                [IO.File]::Move($temporary, $destination)
            }
        } finally {
            if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        }
    }
    Write-Host "Success: installed $($changed.Count) files into $profile. Restart Zen."
    Write-Host 'Existing user.js content was preserved; theme preferences were appended.'
} catch {
    Write-Error "Installation failed: $($_.Exception.Message). If a backup was created, restore the files from the printed backup directory." -ErrorAction Continue
    exit 1
}
