; ClefTune installer for Windows 10/11 (Inno Setup 6.1+).
; Built by packaging/build.py:  iscc /DAppVersion=.. /DCoreDir=.. /DWindowDir=.. /DIconFile=.. installer.iss
; Self-contained: bundles its own Python runtime, libraries and JavaScript engine.
; Run it again later to switch between "own window" and "web browser" or to update.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "ClefTune"
#define AppExe "ClefTune.exe"
#define WebView2Key "Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

[Setup]
AppId={{8AB81424-C1D0-44A9-AC6B-FAED46002959}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=ClefTune (unofficial)
AppComments=Unofficial YouTube Music client
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
CloseApplications=force
RestartApplications=no
UsePreviousAppDir=yes
OutputBaseFilename=ClefTune-{#AppVersion}-windows-x64-setup

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[InstallDelete]
; clean the previous version so no stale files remain; the window add-on is re-added only if chosen
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\window"
Type: files; Name: "{app}\install.json"

[Files]
Source: "{#CoreDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#WindowDir}\*"; DestDir: "{app}\window"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: WantWindow

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Comment: "Unofficial YouTube Music client"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  ModePage: TInputOptionWizardPage;
  DownloadPage: TDownloadWizardPage;
  NeedWebView2: Boolean;

function WantWindow: Boolean;
begin
  Result := ModePage.SelectedValueIndex = 0;
end;

function UiMode: String;
begin
  if WantWindow then Result := 'window' else Result := 'browser';
end;

function WebView2Installed: Boolean;
var
  Version: String;
begin
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\{#WebView2Key}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM, 'SOFTWARE\{#WebView2Key}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\{#WebView2Key}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

procedure InitializeWizard;
begin
  ModePage := CreateInputOptionPage(wpSelectDir,
    'How should ClefTune open?',
    'You can change this later in Settings, or by running this setup again.',
    'Choose where the music player appears:', True, False);
  ModePage.Add('In its own window (recommended)');
  ModePage.Add('In my web browser (smaller install; audio plays in a browser tab)');
  if GetPreviousData('UiMode', 'window') = 'browser' then
    ModePage.SelectedValueIndex := 1
  else
    ModePage.SelectedValueIndex := 0;
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), 'Downloading Microsoft Edge WebView2 (needed for the window)…', nil);
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'UiMode', UiMode);
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo,
  MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := MemoDirInfo + NewLine + NewLine + 'Opens in:' + NewLine + Space;
  if WantWindow then Result := Result + 'its own window' else Result := Result + 'your web browser';
  if MemoTasksInfo <> '' then Result := Result + NewLine + NewLine + MemoTasksInfo;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  NeedWebView2 := False;
  if (CurPageID = wpReady) and WantWindow and not WebView2Installed then
  begin
    DownloadPage.Clear;
    DownloadPage.Add('https://go.microsoft.com/fwlink/p/?LinkId=2124703', 'MicrosoftEdgeWebview2Setup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        NeedWebView2 := True;
      except
        if SuppressibleMsgBox('WebView2 could not be downloaded (' + GetExceptionMessage + ').' + #13#10 +
          'ClefTune will open in your web browser until WebView2 is installed. Continue?',
          mbConfirmation, MB_YESNO, IDYES) <> IDYES then
          Result := False;
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
  Window: String;
begin
  if CurStep = ssPostInstall then
  begin
    if NeedWebView2 then
      Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code);
    if WantWindow then Window := 'true' else Window := 'false';
    { the app applies this choice once per setup run (stamp), then the in-app setting takes over }
    SaveStringToFile(ExpandConstant('{app}\install.json'),
      '{"version": "{#AppVersion}", "ui_mode": "' + UiMode + '", "window": ' + Window +
      ', "stamp": ' + GetDateTimeString('yyyymmddhhnnss', #0, #0) + '}', False);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    if MsgBox('Also delete your library, playlists and settings?' + #13#10 +
              '(Downloaded music in Music\ClefTune is always kept.)', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\ClefTune'), True, True, True);
end;
