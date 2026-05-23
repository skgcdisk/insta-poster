; Inno Setup スクリプト
; insta-poster インストーラー
;
; 使い方:
;   1. Inno Setup をインストール: https://jrsoftware.org/isdl.php
;   2. PyInstaller でビルド済みであること（dist\insta-poster\ が存在すること）
;   3. このファイルを Inno Setup Compiler で開いて「Build > Compile」

#define MyAppName "insta-poster"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "YOUR_NAME"
#define MyAppURL "https://github.com/YOUR_USERNAME/insta-poster"
#define MyAppExeName "insta-poster.exe"
#define MyAppSourceDir "dist\insta-poster"

[Setup]
; アプリ識別子（変更不要 - 更新インストールの一致に使われる）
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; インストーラー .exe の出力先
OutputDir=installer_output
OutputBaseFilename=insta-poster-setup-v{#MyAppVersion}
; 圧縮設定（lzma が最も高圧縮）
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; 管理者権限不要でインストール可能にする
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; GroupDescription: "追加タスク:"; Flags: unchecked

[Files]
; dist\insta-poster\ 以下のファイルをすべて含める
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} をアンインストール"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
