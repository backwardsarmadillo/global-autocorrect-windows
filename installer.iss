; Inno Setup script for Global Autocorrect.
; Per-user install (no admin / no UAC): everything goes under the user's
; LocalAppData, autostart is an HKCU Run key, and a proper uninstaller is
; registered in Add/Remove Programs.

#define MyAppName "Global Autocorrect"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "backwardsarmadillo"
#define MyAppURL "https://github.com/backwardsarmadillo/global-autocorrect-windows"
#define MyAppExeName "GlobalAutocorrect.exe"

[Setup]
AppId={{A7E3F1C9-2B6D-4E8A-9F1C-3D5B7A9C0E12}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Global Autocorrect
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_out
OutputBaseFilename=GlobalAutocorrectSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "GlobalAutocorrect.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "frequency_dictionary_en_82_765.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "frequency_bigramdictionary_en_243_342.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "global_autocorrect_config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
; Launch at sign-in.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "GlobalAutocorrect"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Start Global Autocorrect now"; Flags: nowait runhidden postinstall

[Code]
// Stop any running copy before installing over it, so the exe isn't locked.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/im {#MyAppExeName} /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

// And stop it before uninstalling, otherwise file removal fails.
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('taskkill.exe', '/im {#MyAppExeName} /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
