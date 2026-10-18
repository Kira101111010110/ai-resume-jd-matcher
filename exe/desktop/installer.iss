; ============================================
; Inno Setup Script สำหรับ Resume AI
; build: ใช้ build.ps1 (ส่งเลขเวอร์ชันจาก version.py มาให้)
;   หรือ compile เอง: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=2.0.0 installer.iss
; ต้อง build exe ก่อน (dist\ResumeAI\) — ไฟล์นี้ต้องบันทึกเป็น UTF-8 with BOM (มีข้อความไทย)
; ============================================

#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif
#define MyAppName "Resume AI"
#define MyAppExeName "ResumeAI.exe"
#define ManualName "คู่มือการใช้งาน.html"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher=Rajamangala University of Technology Lanna — Computer Engineering
; AppId เดิมของ v1.0 — ติดตั้งทับเวอร์ชันเก่าได้เลย ไม่ต้องถอนก่อน
AppId={{A1B2C3D4-E5F6-47A8-9B0C-1D2E3F4A5B6C}}
; ไม่ต้องใช้สิทธิ์ admin: ติดตั้งลงโฟลเดอร์ของผู้ใช้ (เครื่องในมหาวิทยาลัยมักไม่ให้สิทธิ์ admin)
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\ResumeAI
DisableDirPage=yes
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
OutputDir=Output
OutputBaseFilename=ResumeAI_Setup_v{#MyAppVersion}
; โมเดล + torch ใหญ่ — บีบอัดแรงสุดเพื่อให้ไฟล์ติดตั้งไม่เกิน 2 GB (ขีดจำกัดต่อไฟล์ของ GitHub Releases)
; ถ้าวันหนึ่งเกิน: เปิด DiskSpanning=yes + DiskSliceSize=2000000000 → ได้ไฟล์ .bin แยก ต้องแจกคู่กับ .exe
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
; โปรแกรมเปิดค้างอยู่ระหว่างติดตั้ง/ถอน → ให้ตัวติดตั้งถามปิดให้ (ชื่อเดียวกับ mutex ใน launcher.py)
AppMutex=Local\ResumeAI_API_single_instance
CloseApplications=yes
WizardStyle=modern
ShowLanguageDialog=no
LanguageDetectionMethod=none

[Languages]
Name: "thai"; MessagesFile: "compiler:Languages\Thai.isl"

[CustomMessages]
thai.LaunchNow=เปิด Resume AI เลย
thai.Manual=คู่มือการใช้งาน
thai.Uninstall=ถอนการติดตั้ง Resume AI
thai.AskDeleteSettings=ต้องการลบการตั้งค่าของ Resume AI ด้วยหรือไม่?%n%n(API key, โมเดลที่เลือก และไฟล์ log ใน %1)%n%nเลือก "ไม่" ถ้าจะติดตั้งใหม่ภายหลังและอยากใช้ key เดิม

[InstallDelete]
; ลบไฟล์ของเวอร์ชันเก่าก่อนติดตั้ง (v1 ใช้ชื่อ exe อื่น และ _internal มีแพ็กเกจที่เลิกใช้แล้ว)
Type: files; Name: "{app}\ResumeAI_API.exe"
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; build แบบ onedir: คัดลอกทั้งโฟลเดอร์ (exe + _internal ที่มีโมเดล/หน้าเว็บ/Tesseract)
Source: "dist\ResumeAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; คู่มือแยกไว้นอก _internal ให้เปิดจาก Start Menu ได้แม้โปรแกรมไม่ได้เปิดอยู่
Source: "static\manual.html"; DestDir: "{app}"; DestName: "{#ManualName}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName}\{cm:Manual}"; Filename: "{app}\{#ManualName}"
Name: "{autoprograms}\{#MyAppName}\{cm:Uninstall}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchNow}"; Flags: nowait postinstall skipifsilent

[Code]
// ตอนถอนการติดตั้ง: ถามว่าจะลบ %APPDATA%\ResumeAI (key, config.json, logs) ด้วยไหม
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SettingsDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    SettingsDir := ExpandConstant('{userappdata}\ResumeAI');
    if DirExists(SettingsDir) and not UninstallSilent then
      if MsgBox(FmtMessage(CustomMessage('AskDeleteSettings'), [SettingsDir]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(SettingsDir, True, True, True);
  end;
end;
