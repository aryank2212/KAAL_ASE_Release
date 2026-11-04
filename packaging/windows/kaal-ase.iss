; Build:  iscc /DVersion=2.2.0 packaging\windows\kaal-ase.iss   (after PyInstaller has produced dist\kaal-ase)
#ifndef Version
  #define Version "0.0.0"
#endif
[Setup]
AppId={{B7E3C1A2-5D44-4C1B-9A6E-3F2E8D6A1C77}
AppName=KAAL ASE
AppVersion={#Version}
AppPublisher=RedClove
AppPublisherURL=https://redclove.space
DefaultDirName={autopf}\KAAL ASE
DefaultGroupName=KAAL ASE
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist\installer
OutputBaseFilename=KAAL-ASE-{#Version}-setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=KAAL ASE
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "..\..\dist\kaal-ase\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{group}\KAAL ASE Console"; Filename: "{app}\kaal-ase.exe"
Name: "{group}\Uninstall KAAL ASE"; Filename: "{uninstallexe}"
Name: "{autodesktop}\KAAL ASE Console"; Filename: "{app}\kaal-ase.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\kaal-ase.exe"; Description: "Start KAAL ASE now"; Flags: nowait postinstall skipifsilent
