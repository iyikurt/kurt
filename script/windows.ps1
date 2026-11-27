<#
    The Makefile's Windows half: what `mkdir -p`, `ln -s` and the
    libsqlite3-dev package do on Linux and macOS.

      build    bin\ exists, and sqlite3.lib and sqlite3.dll are in a directory
               on iyi's IYI_LIBRARY_PATH. When they are not, SQLite's own x64
               DLL is downloaded from sqlite.org, checked against the sha256
               below, and its import library made with MSVC's lib.exe. They
               go into the first directory on that path (iyi's own lib\iyi by
               default), where every iyi build finds them: bin\kurt.exe, and
               the applications `kurt new` writes. A build copies sqlite3.dll
               beside the executable.
      install  bin\ on the user's PATH. Not a copy of kurt.exe: kurt finds
               this checkout through the executable's own path, and Windows
               finds sqlite3.dll beside it. A symlink would do neither.

    Run by make as `powershell -NoProfile -ExecutionPolicy Bypass -File
    script/windows.ps1 <step> <iyi>`, from cmd.exe or a POSIX shell alike.
    Windows PowerShell 5.1 and PowerShell 7; no administrator, the PATH it
    edits is HKCU's.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [ValidateSet('build', 'install')] [string] $Step,
    [string] $Iyi = 'iyi'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Bin = Join-Path (Split-Path -Parent $PSScriptRoot) 'bin'

# sqlite.org/download.html, "Precompiled Binaries for Windows". The zip holds
# sqlite3.dll and the sqlite3.def an import library is made from.
$SqliteZip = 'sqlite-dll-win-x64-3540100.zip'
$SqliteUrl = "https://sqlite.org/2026/$SqliteZip"
$SqliteSha256 = 'f436f53ad8f965af43f3817b42c99c0689e6787f6b7ace208fe38dab7ffc4971'

function Say([string] $Line) { Write-Host $Line }

function Die([string] $Line) {
    [Console]::Error.WriteLine("script/windows.ps1: $Line")
    exit 1
}

# lib.exe from the Visual C++ build tools iyi links with, found the way iyi's
# installer finds them; a developer prompt's PATH otherwise.
function Find-LibExe {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere -PathType Leaf) {
        $found = @(& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find 'VC\Tools\MSVC\**\bin\Hostx64\x64\lib.exe' 2>$null)
        if ($found) { return ($found | Sort-Object | Select-Object -Last 1) }
    }
    $command = Get-Command lib.exe -CommandType Application -ErrorAction SilentlyContinue
    if ($command) { return @($command)[0].Source }
    Die ("no lib.exe: install the Visual Studio Build Tools with the workload " +
         "'Desktop development with C++' (https://aka.ms/vs/17/release/vs_BuildTools.exe), which iyi links with too")
}

function Install-Sqlite {
    $paths = & $Iyi env IYI_LIBRARY_PATH
    if ($LASTEXITCODE -ne 0) { Die "``$Iyi env IYI_LIBRARY_PATH`` failed" }
    $dirs = @("$paths" -split ';' | Where-Object { $_.Trim() } | ForEach-Object { [IO.Path]::GetFullPath($_.Trim()) })
    if (-not $dirs) { Die "iyi names no IYI_LIBRARY_PATH to put sqlite3.lib in" }

    foreach ($dir in $dirs) {
        if ((Test-Path -LiteralPath (Join-Path $dir 'sqlite3.lib') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $dir 'sqlite3.dll') -PathType Leaf)) { return }
    }

    $lib = Find-LibExe
    $destination = $dirs[0]
    $temp = Join-Path ([IO.Path]::GetTempPath()) ('kurt-sqlite-' + [IO.Path]::GetRandomFileName())
    New-Item -ItemType Directory -Path $temp | Out-Null
    try {
        Say "sqlite3.lib is on no IYI_LIBRARY_PATH; fetching $SqliteUrl"
        # sqlite.org refuses anything below TLS 1.2, which Windows PowerShell
        # 5.1 on an un-updated machine does not offer by default.
        try {
            [Net.ServicePointManager]::SecurityProtocol =
                [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        } catch {}
        $zip = Join-Path $temp $SqliteZip
        try {
            Invoke-WebRequest -Uri $SqliteUrl -OutFile $zip -UseBasicParsing
        } catch {
            Die "download failed: ${SqliteUrl}: $($_.Exception.Message)"
        }
        $actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $SqliteSha256) { Die "${SqliteZip}: expected sha256 $SqliteSha256, got $actual" }

        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($zip, $temp)

        $def = Join-Path $temp 'sqlite3.def'
        $output = & $lib /nologo "/def:$def" "/out:$(Join-Path $temp 'sqlite3.lib')" /machine:x64 2>&1
        if ($LASTEXITCODE -ne 0) { Die "$lib failed: $($output -join ' ')" }

        New-Item -ItemType Directory -Path $destination -Force | Out-Null
        foreach ($name in @('sqlite3.lib', 'sqlite3.dll')) {
            Copy-Item -LiteralPath (Join-Path $temp $name) -Destination $destination -Force
        }
        Say "sqlite3.lib, sqlite3.dll -> $destination"
    } finally {
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# The user's PATH, in the registry rather than through
# [Environment]::SetEnvironmentVariable, which writes the value back as a
# plain string and so freezes every `%USERPROFILE%\...` entry in it. Read
# unexpanded and written back as the kind it was; iyi's install.ps1 does the
# same for iyi's bin.
function Add-ToPath([string] $Dir) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true)
    if (-not $key) { $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey('Environment') }
    try {
        $current = [string] $key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $kind = if ($current) { $key.GetValueKind('Path') } else { [Microsoft.Win32.RegistryValueKind]::ExpandString }
        $entries = @($current -split ';' | Where-Object { $_ } | ForEach-Object { $_.Trim().TrimEnd('\') })
        if ($entries -contains $Dir.TrimEnd('\')) { return $false }
        $key.SetValue('Path', (@($current.TrimEnd(';'), $Dir) | Where-Object { $_ }) -join ';', $kind)
    } finally {
        $key.Dispose()
    }

    # Explorer hands every program it starts the environment it cached; this
    # tells it to reread, so a new terminal sees the change before sign-out.
    try {
        if (-not ('Kurt.Native' -as [type])) {
            Add-Type -Namespace Kurt -Name Native -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll", SetLastError = true, CharSet = System.Runtime.InteropServices.CharSet.Auto)]
public static extern System.IntPtr SendMessageTimeout(System.IntPtr hWnd, uint msg, System.UIntPtr wParam, string lParam, uint flags, uint timeout, out System.UIntPtr result);
'@
        }
        $answer = [UIntPtr]::Zero
        # HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG, 5 s.
        [void] [Kurt.Native]::SendMessageTimeout([IntPtr] 0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref] $answer)
    } catch {}
    return $true
}

switch ($Step) {
    'build' {
        New-Item -ItemType Directory -Path $Bin -Force | Out-Null
        Install-Sqlite
    }
    'install' {
        $kurt = Join-Path $Bin 'kurt.exe'
        if (-not (Test-Path -LiteralPath $kurt -PathType Leaf)) { Die "$kurt is not built" }
        if (Add-ToPath $Bin) {
            Say "added $Bin to your PATH; open a new terminal to use kurt"
        } else {
            Say "kurt -> $kurt (already on your PATH)"
        }
    }
}
