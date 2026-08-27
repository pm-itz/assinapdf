@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Gera o aplicativo Windows e, se o Inno Setup estiver instalado, o instalador.
set "PYTHON_CMD=py -3"
where py >nul 2>nul || set "PYTHON_CMD=python"

echo [1/4] Criando ambiente de compilacao...
%PYTHON_CMD% -m venv .venv-build
if errorlevel 1 goto :error

call .venv-build\Scripts\activate.bat
if errorlevel 1 goto :error

echo [2/4] Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error

echo [3/4] Gerando AssinaPDF.exe...
pyinstaller --noconfirm --clean --windowed --name AssinaPDF --icon "assets\imperatriz.ico" --add-data "assets;assets" app.py
if errorlevel 1 goto :error

rem Localiza o compilador do Inno Setup, inclusive quando instalado só para o usuário atual.
set "ISCC="
for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%I"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
    echo.
    echo O aplicativo foi gerado em dist\AssinaPDF\AssinaPDF.exe.
    echo Para gerar o instalador, instale o Inno Setup 6 e execute este arquivo novamente.
    echo https://jrsoftware.org/isdl.php
    goto :success
)

echo [4/4] Gerando instalador...
echo Usando Inno Setup: "%ISCC%"
"%ISCC%" installer.iss
if errorlevel 1 goto :error

set "DESKTOP_DIR="
for /f "delims=" %%D in ('powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"') do set "DESKTOP_DIR=%%D"
if not defined DESKTOP_DIR set "DESKTOP_DIR=%USERPROFILE%\Desktop"
copy /Y "release\AssinaPDF-Setup.exe" "%DESKTOP_DIR%\AssinaPDF-Setup.exe" >nul

echo.
echo Instalador criado em release\AssinaPDF-Setup.exe
echo Copia para instalacao criada em "%DESKTOP_DIR%\AssinaPDF-Setup.exe"
goto :success

:error
echo.
echo Nao foi possivel concluir a compilacao. Veja as mensagens acima.
exit /b 1

:success
exit /b 0
