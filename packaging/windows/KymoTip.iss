#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

#define MyAppName "KymoTip"
#define MyAppExeName "KymoTip.exe"

[Setup]
AppId=KymoTip.KymoTip_GUI
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=KymoTip
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\installer
OutputBaseFilename=KymoTip-{#MyAppVersion}-Setup
SetupIconFile=..\icons\kymotip-shortcut.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; GroupDescription: "追加アイコン:"; Flags: unchecked

[Files]
Source: "..\..\dist\KymoTip\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\envs\sam2\*"; DestDir: "{app}\sam2env"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\icons\kymotip-shortcut.ico"; DestDir: "{app}\assets"; DestName: "kymotip-shortcut.ico"; Flags: ignoreversion
Source: "..\..\.claude\*"; DestDir: "{app}\.claude"; Excludes: "settings.local.json"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\kymotip-shortcut.ico"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\kymotip-shortcut.ico"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName}を起動する"; Flags: nowait postinstall skipifsilent
