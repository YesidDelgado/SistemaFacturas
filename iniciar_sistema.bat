@echo off
setlocal
title Sistema de Facturacion
color 0B

rem ==================================================
rem 1. UBICACION DEL PROYECTO
rem ==================================================

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PYTHON=%ROOT%.venv\Scripts\python.exe"
set "PYTHON_LAUNCHER="
set "PYTHON_ARGS="

echo.
echo ==========================================
echo       SISTEMA DE FACTURACION
echo ==========================================
echo.

rem ==================================================
rem 2. VERIFICAR ARCHIVOS NECESARIOS
rem ==================================================

if not exist "%ROOT%backend\requirements.txt" (
    echo ERROR: No se encuentra backend\requirements.txt.
    pause
    exit /b 1
)

rem ==================================================
rem 3. BUSCAR PYTHON EN WINDOWS
rem ==================================================

echo [1/4] Verificando instalacion de Python...

where python >nul 2>&1

if not errorlevel 1 (
    set "PYTHON_LAUNCHER=python"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_LAUNCHER=py"
        set "PYTHON_ARGS=-3"
    )
)

if not defined PYTHON_LAUNCHER (
    echo.
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo Instala Python 3 y habilita la opcion Add Python to PATH.
    echo Despues vuelve a ejecutar este archivo.
    pause
    exit /b 1
)

rem ==================================================
rem 4. CREAR EL ENTORNO VIRTUAL SI NO EXISTE
rem ==================================================

if not exist "%PYTHON%" (
    echo.
    echo No se encuentra el entorno virtual.
    echo Creando automaticamente la carpeta .venv...
    echo.

    %PYTHON_LAUNCHER% %PYTHON_ARGS% -m venv "%ROOT%.venv"

    if errorlevel 1 (
        echo.
        echo ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

if not exist "%PYTHON%" (
    echo.
    echo ERROR: No se pudo localizar el Python del entorno virtual.
    pause
    exit /b 1
)

echo Entorno virtual disponible.

rem ==================================================
rem 5. VERIFICAR E INSTALAR DEPENDENCIAS
rem ==================================================

echo.
echo [2/4] Verificando e instalando dependencias...

"%PYTHON%" -m pip --version >nul 2>&1

if errorlevel 1 (
    echo Preparando pip...
    "%PYTHON%" -m ensurepip --upgrade

    if errorlevel 1 (
        echo ERROR: No se pudo preparar pip.
        pause
        exit /b 1
    )
)

echo Instalando o verificando dependencias del proyecto...
echo.

"%PYTHON%" -m pip install --disable-pip-version-check -r "%ROOT%backend\requirements.txt"

if errorlevel 1 (
    echo.
    echo ERROR: No se pudieron instalar las dependencias.
    echo Verifica tu conexion a internet y requirements.txt.
    pause
    exit /b 1
)

rem ==================================================
rem 6. VERIFICAR CONFIGURACION DE GEMINI
rem ==================================================

echo.
echo [3/4] Verificando configuracion de Gemini...

if not exist "%ROOT%.env" (
    echo.
    echo AVISO: No se encuentra el archivo .env en la raiz.
    echo La integracion con Gemini y las credenciales
    echo configuradas mediante variables de entorno
    echo podrian no funcionar.
    echo.
) else (
    "%PYTHON%" -c "from pathlib import Path; from dotenv import load_dotenv; import os; load_dotenv(Path.cwd() / '.env'); print('Archivo .env encontrado.'); print('GEMINI_API_KEY configurada.' if os.getenv('GEMINI_API_KEY') else 'GEMINI_API_KEY NO configurada.')"
)

rem ==================================================
rem 7. INICIAR LA API
rem ==================================================

echo.
echo [4/4] Iniciando la API...

cd /d "%ROOT%backend"

echo.
echo ==========================================
echo API: http://127.0.0.1:8000
echo Documentacion: http://127.0.0.1:8000/docs
echo Para detener la API, presiona CTRL+C.
echo ==========================================
echo.

"%PYTHON%" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

echo.
echo La API se ha detenido.
pause
