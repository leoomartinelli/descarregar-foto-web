; Instalador do Windows (Inno Setup 6). Compilado pelo GitHub Actions:
;   iscc /DVersao=1.2.3 packaging\windows\instalador.iss
; Instala em "Arquivos de Programas", cria o icone na Area de Trabalho e no Menu Iniciar e libera o programa
; no Firewall do Windows (rede local Lider/Auxiliar e painel no celular). Instalar uma versao nova por cima
; atualiza sem perder nada: os dados ficam em %USERPROFILE%\Descarregador de Fotos.

#ifndef Versao
  #error Informe a versao: iscc /DVersao=X.Y.Z
#endif
#define Nome "Descarregador de Fotos"
#define Exe "DescarregadorDeFotos.exe"
#define Raiz AddBackslash(SourcePath) + "..\.."

[Setup]
; AppId fixo: o Windows reconhece cada nova versao como atualizacao do mesmo programa
AppId={{2090D9E4-BFD6-43DB-A058-6744F3C8F51E}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
VersionInfoVersion={#Versao}
AppPublisher=Sistemas Educacionais Crescer
AppPublisherURL=https://github.com/leoomartinelli/descarregar-foto-web
AppUpdatesURL=https://github.com/leoomartinelli/descarregar-foto-web/releases
DefaultDirName={autopf}\{#Nome}
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile={#Raiz}\housinho.ico
UninstallDisplayIcon={app}\{#Exe}
OutputDir={#Raiz}\saida
OutputBaseFilename=DescarregadorDeFotos-{#Versao}-windows-instalador
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=no

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "{#Raiz}\dist\DescarregadorDeFotos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; arquivos da versao anterior que nao existem mais na nova
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Exe}"
Name: "{autoprograms}\{#Nome}"; Filename: "{app}\{#Exe}"
Name: "{autoprograms}\Pasta de dados do {#Nome}"; Filename: "{%USERPROFILE}\Descarregador de Fotos"

[Run]
; libera a porta do servidor (50007/TCP) e a descoberta do lider (50008/UDP) em qualquer tipo de rede:
; a rede da igreja costuma ser marcada como "Publica" pelo Windows
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#Nome}"""; Flags: runhidden; StatusMsg: "Configurando o Firewall..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#Nome}"" dir=in action=allow program=""{app}\{#Exe}"" enable=yes profile=any"; Flags: runhidden
Filename: "{app}\{#Exe}"; Description: "Abrir o {#Nome} agora"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#Nome}"""; Flags: runhidden; RunOnceId: "Firewall"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#Exe}"; Flags: runhidden; RunOnceId: "Fechar"

[Code]
// fecha o programa aberto (sem janela, roda em segundo plano) antes de substituir os arquivos
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#Exe}', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;
