[Setup]
AppName=Activity Logger
AppVersion=1.0
DefaultDirName={autopf}\Activity Logger
DefaultGroupName=Activity Logger
UninstallDisplayIcon={app}\activity_logger.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputBaseFilename=ActivityLogger-Setup
SetupIconFile=assets\activity_logger.ico
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Start Activity Logger when Windows starts up"; GroupDescription: "Startup Options"; Flags: checkedonce

[Files]
Source: "dist\windows\activity_logger.exe"; DestDir: "{app}"; Flags: ignoreversion
; assets folder ti copy korar jonno nicher line ti deya hoyeche
Source: "assets\*"; DestDir: "{app}\assets"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Activity Logger"; Filename: "{app}\activity_logger.exe"
Name: "{autodesktop}\Activity Logger"; Filename: "{app}\activity_logger.exe"; Tasks: desktopicon

; Auto-start er jonno Registry te entry add kora hocche
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ActivityLogger"; ValueData: """{app}\activity_logger.exe"""; Tasks: startup

[Run]
Filename: "{app}\activity_logger.exe"; Description: "{cm:LaunchProgram,Activity Logger}"; Flags: nowait postinstall skipifsilent
