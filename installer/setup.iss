; ============================================================
;  Инсталлятор Support Bot Panel
;  Создан: Inno Setup 6
;  Скачать: https://jrsoftware.org/isinfo.php
;
;  Сборка:
;    installer\build_installer.bat
; ============================================================

[Setup]
AppName=Support Bot Panel
AppVersion=1.0
AppPublisher=SupportBot Team
DefaultDirName={autopf}\SupportBotPanel
DefaultGroupName=Support Bot Panel
OutputDir=installer
OutputBaseFilename=SupportBotPanel_Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\SupportBotPanel.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Support Bot Panel"; Filename: "{app}\SupportBotPanel.exe"
Name: "{group}\Удаление Support Bot Panel"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Support Bot Panel"; Filename: "{app}\SupportBotPanel.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SupportBotPanel.exe"; Description: "Запустить панель"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
