; Inno Setup script (https://jrsoftware.org/isinfo.php). Build with:  iscc packaging\windows\VibeSimulation.iss /DAppVersion=1.2.0
; Needs dist\VibeSimulation\ to exist first (python packaging\build.py).
#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif

[Setup]
AppId={{F57FEF97-E13A-4097-83E1-8C67940B236F}
AppName=VibeSimulation
AppVersion={#AppVersion}
AppPublisher=VibeSimulation
DefaultDirName={autopf}\VibeSimulation
DefaultGroupName=VibeSimulation
UninstallDisplayIcon={app}\VibeSimulation.exe
SetupIconFile=..\icon.ico
OutputDir=..\..\dist
OutputBaseFilename=VibeSimulation-{#AppVersion}-windows-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; Signing (optional): iscc ... "/Ssigntool=signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f cert.pfx /p PASSWORD $f"
; and uncomment:
; SignTool=signtool
; SignedUninstaller=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "assoc"; Description: "Open Logisim .circ and Verilog .v files with VibeSimulation"; GroupDescription: "File types:"; Flags: unchecked

[Files]
Source: "..\..\dist\VibeSimulation\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\VibeSimulation"; Filename: "{app}\VibeSimulation.exe"
Name: "{group}\Uninstall VibeSimulation"; Filename: "{uninstallexe}"
Name: "{autodesktop}\VibeSimulation"; Filename: "{app}\VibeSimulation.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.circ\OpenWithProgids"; ValueType: string; ValueName: "VibeSimulation.circ"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\VibeSimulation.circ"; ValueType: string; ValueData: "Logisim circuit"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\VibeSimulation.circ\shell\open\command"; ValueType: string; ValueData: """{app}\VibeSimulation.exe"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\VibeSimulation.exe"; Description: "Start VibeSimulation"; Flags: nowait postinstall skipifsilent
