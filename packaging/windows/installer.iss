; ===================================================================
;  Inno Setup script for PhotoOrganizer AI
;
;  Prerequisite: run build_exe.bat first so that
;      dist\PhotoOrganizerAI\PhotoOrganizerAI.exe
;  exists.
;
;  Then compile this script with Inno Setup 6:
;      "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\installer.iss
;  (or open it in the Inno Setup Compiler and press Build).
;
;  Output: dist\installer\PhotoOrganizerAI-Setup.exe
; ===================================================================

#define MyAppName "PhotoOrganizer AI"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Andreas Wilde"
#define MyAppURL "https://github.com/andreaswilde76-web/photo-organizer-ai"
#define MyAppExeName "PhotoOrganizerAI.exe"
; Path is relative to this .iss file (packaging\windows).
#define BuildDir "..\..\dist\PhotoOrganizerAI"

[Setup]
AppId={{7B3D9C2E-4A1F-4C6B-9E2A-8D5F1C0A7E33}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\PhotoOrganizerAI
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=PhotoOrganizerAI-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
; Uncomment once packaging\windows\app.ico exists:
; SetupIconFile=app.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BuildDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
