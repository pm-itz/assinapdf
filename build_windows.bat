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

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
    echo.
    echo O aplicativo foi gerado em dist\AssinaPDF\AssinaPDF.exe.
    echo Para gerar o instalador, instale o Inno Setup 6 e execute este arquivo novamente.
    echo https://jrsoftware.org/isdl.php
    goto :success
)

echo [4/4] Gerando instalador...
"%ISCC%" installer.iss
if errorlevel 1 goto :error

echo.
echo Instalador criado em release\AssinaPDF-Setup.exe
goto :success

:error
echo.
echo Nao foi possivel concluir a compilacao. Veja as mensagens acima.
exit /b 1

:success
exit /b 0
