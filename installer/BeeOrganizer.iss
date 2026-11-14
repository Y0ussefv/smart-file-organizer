; BeeOrganizer – Windows installer (Inno Setup 6)
; Build:  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer\BeeOrganizer.iss
;         (CI passes /DAppVersion=x.y.z)
; Output: dist\BeeOrganizer-Setup.exe

#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif
#define AppName "BeeOrganizer"
#define AppPublisher "RNJ"
#define AppURL "https://github.com/Y0ussefv/smart-file-organizer"
#define AppExe "BeeOrganizer.exe"

[Setup]
AppId={{C0486E98-E87F-4353-B0D5-A6651F4A12DC}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
; Per-user install: no admin rights, no UAC prompt
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=..\dist
OutputBaseFilename=BeeOrganizer-Setup
SetupIconFile=..\src\app\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
english.StartupTask=Start BeeOrganizer when Windows starts (rename new downloads automatically)
french.StartupTask=Lancer BeeOrganizer au démarrage de Windows (renommer automatiquement les nouveaux téléchargements)
english.LaunchApp=Launch BeeOrganizer now
french.LaunchApp=Lancer BeeOrganizer maintenant

[Tasks]
Name: "startup"; Description: "{cm:StartupTask}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Automatically gives every download an exact name"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Start with Windows in background mode (shows in Task Manager > Startup apps)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"" --watch"; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopBeeOrganizer"

[UninstallDelete]
; Remove the start-up entry even if it was turned on later from the tray menu
Type: files; Name: "{app}\*.log"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}');
end;
