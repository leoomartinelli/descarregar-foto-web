; Instalador do Windows (Inno Setup 6). Compilado pelo GitHub Actions:
;   iscc /DVersao=1.2.3 packaging\windows\instalador.iss
; Instala na pasta do usuario (%LOCALAPPDATA%\Programs), cria o icone na Area de Trabalho e no Menu Iniciar e
; libera o programa no Firewall do Windows (rede local Lider/Auxiliar e painel no celular).
; Sem precisar de administrador para instalar, o programa se ATUALIZA SOZINHO (app/atualizador.py roda este
; instalador em silencio com /REABRIR=1). So a regra do firewall pede administrador, uma unica vez: o caminho do
; programa nao muda entre versoes. Os dados ficam em %USERPROFILE%\Descarregador de Fotos.

#ifndef Versao
  #error Informe a versao: iscc /DVersao=X.Y.Z
#endif
#define Nome "Descarregador de Fotos"
#define Exe "DescarregadorDeFotos.exe"
; uma regra por usuario do Windows: cada um instala na propria pasta
#define Regra "Descarregador de Fotos - {username}"
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
PrivilegesRequired=lowest
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
; libera a porta do servidor (50007/TCP) e a descoberta do lider (50008/UDP) em qualquer tipo de rede (a da
; igreja costuma ser "Publica"). Pede administrador so se a regra ainda nao existe: nas atualizacoes nao pergunta.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#Regra}"" dir=in action=allow program=""{app}\{#Exe}"" enable=yes profile=any"; Flags: shellexec runhidden waituntilterminated; Verb: runas; Check: PrecisaFirewall; StatusMsg: "Liberando o programa no Firewall..."
Filename: "{app}\{#Exe}"; Description: "Abrir o {#Nome} agora"; Flags: nowait postinstall skipifsilent
; atualizacao automatica (silenciosa): reabre o programa sem abrir outra aba no navegador
Filename: "{app}\{#Exe}"; Parameters: "--sem-navegador"; Flags: nowait; Check: Reabrir

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#Exe}"; Flags: runhidden; RunOnceId: "Fechar"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#Regra}"""; Flags: shellexec runhidden waituntilterminated; Verb: runas; RunOnceId: "Firewall"

[Code]
// a regra do firewall ja existe para este caminho? (netsh responde 0 quando acha a regra)
function PrecisaFirewall: Boolean;
var
  Codigo: Integer;
begin
  Result := not (Exec(ExpandConstant('{sys}\netsh.exe'),
    'advfirewall firewall show rule name="' + ExpandConstant('{#Regra}') + '"', '', SW_HIDE, ewWaitUntilTerminated, Codigo)
    and (Codigo = 0));
end;

function Reabrir: Boolean;
begin
  Result := ExpandConstant('{param:REABRIR|0}') = '1';
end;

// fecha o programa aberto (sem janela, roda em segundo plano) antes de substituir os arquivos
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#Exe}', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;
