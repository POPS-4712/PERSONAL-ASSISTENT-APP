; ===========================================================================
;  Automation Center - instalador Windows (Inno Setup 6)
;  Produce: AutomationCenter-Setup.exe
;
;  Compilar:
;     ISCC.exe /DAppVersion=0.4.0 installer\windows\AutomationCenter.iss
;  (build\build-exe.ps1 lee VERSION y pasa /DAppVersion automáticamente.)
;
;  El .exe empaqueta TODO el repositorio (docker-compose + backend + frontend +
;  workflows + scripts) y, tras copiar los ficheros, ejecuta
;  installer\windows\scripts\bootstrap.ps1  (DETECTA -> WSL2 -> DOCKER ->
;  DESPLIEGA -> HEALTH CHECKS). No hay lógica de negocio en este .iss.
; ===========================================================================

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#define AppName "Automation Center"
#define AppPublisher "Automation Center"
#define RepoRoot "..\.."
#define ScriptsDir "{app}\installer\windows\scripts"
#define PwShell "{sys}\WindowsPowerShell\v1.0\powershell.exe"

[Setup]
AppId={{7F1C4E9A-3B2D-4A56-9E10-AC0DEC0DE001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Automation Center
DefaultGroupName=Automation Center
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir={#RepoRoot}\dist
OutputBaseFilename=AutomationCenter-Setup
SetupIconFile=assets\automation-center.ico
UninstallDisplayIcon={app}\installer\windows\assets\automation-center.ico
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; x86 / 32-bit NO soportado. Solo x64 y ARM64.
ArchitecturesAllowed=x64compatible arm64
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=no
MinVersion=10.0.19041
DisableDirPage=auto

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "runsetup"; Description: "Preparar el entorno y arrancar ahora (WSL2, Docker, servicios)"; GroupDescription: "Primer arranque:"
Name: "trayautostart"; Description: "Iniciar el icono de bandeja al iniciar sesión"; GroupDescription: "Extras:"
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Extras:"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion; \
  Excludes: "*\.git\*,\.git,\.git\*,\dist,\dist\*,\.env,*.log,\node_modules,\node_modules\*,*\node_modules\*,*\node_modules,*\.venv\*,*\.venv,*\__pycache__\*,*\.pytest_cache\*,\config\user_profile.json,\output\*\*.md"

[Icons]
Name: "{group}\Automation Center";        Filename: "{#PwShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#ScriptsDir}\control.ps1"" open"; IconFilename: "{app}\installer\windows\assets\automation-center.ico"; Comment: "Abrir el panel de Automation Center"
Name: "{group}\Iniciar";                  Filename: "{#PwShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#ScriptsDir}\control.ps1"" start"
Name: "{group}\Parar";                    Filename: "{#PwShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#ScriptsDir}\control.ps1"" stop"
Name: "{group}\Reiniciar";                Filename: "{#PwShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#ScriptsDir}\control.ps1"" restart"
Name: "{group}\Estado";                   Filename: "{#PwShell}"; Parameters: "-NoExit -NoProfile -ExecutionPolicy Bypass -File ""{#ScriptsDir}\control.ps1"" status"
Name: "{group}\Ver logs";                 Filename: "{#PwShell}"; Parameters: "-NoExit -NoProfile -ExecutionPolicy Bypass -File ""{#ScriptsDir}\control.ps1"" logs"
Name: "{group}\Copia de seguridad";       Filename: "{#PwShell}"; Parameters: "-NoExit -NoProfile -ExecutionPolicy Bypass -File ""{#ScriptsDir}\backup.ps1"""
Name: "{group}\Volver a ejecutar la instalación"; Filename: "{#PwShell}"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{#ScriptsDir}\bootstrap.ps1"""
Name: "{group}\{cm:UninstallProgram,Automation Center}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Automation Center";  Filename: "{#PwShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#ScriptsDir}\control.ps1"" open"; IconFilename: "{app}\installer\windows\assets\automation-center.ico"; Tasks: desktopicon
Name: "{userstartup}\Automation Center Tray"; Filename: "{#PwShell}"; Parameters: "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""{#ScriptsDir}\tray.ps1"""; Tasks: trayautostart

[Registry]
Root: HKCU; Subkey: "Software\Automation Center"; ValueType: string; ValueName: "Version";    ValueData: "{#AppVersion}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Automation Center"; ValueType: string; ValueName: "InstallDir"; ValueData: "{app}"

[Run]
Filename: "{#PwShell}"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{#ScriptsDir}\bootstrap.ps1"" {code:BootstrapArgs}"; \
  WorkingDir: "{app}"; Flags: runascurrentuser waituntilterminated; \
  StatusMsg: "Preparando el entorno (WSL2, Docker, servicios). Puede tardar varios minutos..."; \
  Tasks: runsetup; Check: not WizardSilent

[UninstallRun]
; Interactivo: pregunta (MessageBox) qué hacer con los datos.
Filename: "{#PwShell}"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\windows\scripts\uninstall.ps1"" -Mode Ask"; \
  RunOnceId: "AutomationCenterUninstall"; Flags: runascurrentuser waituntilterminated; \
  Check: not UninstallSilent
; Silencioso: conserva los datos (nunca borra en silencio).
Filename: "{#PwShell}"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\windows\scripts\uninstall.ps1"" -Mode KeepData -Silent"; \
  RunOnceId: "AutomationCenterUninstallSilent"; Flags: runascurrentuser waituntilterminated; \
  Check: UninstallSilent

[Code]
var
  GNeedRestart: Boolean;
  GPriorDir: String;

function BootstrapArgs(Param: String): String;
begin
  Result := '';
  if WizardSilent then
    Result := '-Unattended -SkipBrowser';
end;

// --- Detección de instalación previa (upgrade) --------------------------
function InitializeSetup(): Boolean;
begin
  Result := True;
  GNeedRestart := False;
  if RegQueryStringValue(HKCU, 'Software\Automation Center', 'InstallDir', GPriorDir) then
  begin
    if DirExists(GPriorDir) then
      Log('Instalación previa detectada en ' + GPriorDir);
  end;
end;

// --- Antes de sobrescribir ficheros: backup + parar (solo en upgrade) --
procedure CurStepChanged(CurStep: TSetupStep);
var
  RC: Integer;
  DockerScript: String;
begin
  if (CurStep = ssInstall) and (GPriorDir <> '') and DirExists(GPriorDir) then
  begin
    DockerScript := GPriorDir + '\installer\windows\scripts';
    if FileExists(DockerScript + '\backup.ps1') then
    begin
      Log('Upgrade: creando backup previo y parando servicios...');
      Exec(ExpandConstant('{#PwShell}'),
        '-NoProfile -ExecutionPolicy Bypass -File "' + DockerScript + '\backup.ps1" -Label pre-upgrade',
        '', SW_SHOW, ewWaitUntilTerminated, RC);
      Exec(ExpandConstant('{#PwShell}'),
        '-NoProfile -ExecutionPolicy Bypass -File "' + DockerScript + '\control.ps1" stop',
        '', SW_HIDE, ewWaitUntilTerminated, RC);
    end;
  end;

  if CurStep = ssPostInstall then
  begin
    if not WizardIsTaskSelected('runsetup') then exit;
    // bootstrap.ps1 lo ejecuta la sección [Run]; aquí solo capturamos su
    // resultado cuando corre en modo silencioso.
    if WizardSilent then
    begin
      Exec(ExpandConstant('{#PwShell}'),
        '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{#ScriptsDir}') + '\bootstrap.ps1" -Unattended -SkipBrowser',
        ExpandConstant('{app}'), SW_SHOW, ewWaitUntilTerminated, RC);
      if RC = 10 then GNeedRestart := True;
    end;
  end;
end;

// La sección [Run] no propaga el exit code; comprobamos RunOnce como señal
// de "reinicio pendiente" al terminar el asistente.
function NeedRestart(): Boolean;
var
  Dummy: String;
begin
  Result := GNeedRestart or
    RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\RunOnce', 'AutomationCenterSetupResume', Dummy);
end;
