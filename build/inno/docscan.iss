; Inno Setup script para DocScan Studio — Windows
;
; Requisitos:
;   - Inno Setup 6.x instalado
;   - PyInstaller output en dist\docscan\
;
; Compilar:
;   iscc build\inno\docscan.iss
;
; Genera: Output\docscan-{version}-setup.exe

#define MyAppName "DocScan Studio"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Tecnomedia"
#define MyAppURL "https://github.com/ferreret/docscan"
#define MyAppExeName "DocScan Studio.exe"

[Setup]
AppId={{A7E3F4B2-9C1D-4E6A-8B5F-2D7C9E1A3F4B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\Output
OutputBaseFilename=docscan-{#MyAppVersion}-setup
SetupIconFile=..\..\resources\icons\docscan.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; No requiere admin — instala para el usuario
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Auto-close si se invoca con /SILENT /CLOSEAPPLICATIONS
CloseApplications=force
RestartApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "catalan"; MessagesFile: "compiler:Languages\Catalan.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenu"; Description: "Crear acceso en el menú Inicio"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Copiar todo el output de PyInstaller
Source: "..\..\dist\docscan\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpieza de ficheros generados en runtime
Type: filesandordirs; Name: "{app}\__pycache__"
