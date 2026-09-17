@echo off
rem Codigo do curso (nrf-manaus-2). Compila uma variante do lab 2 a partir do
rem fonte do lab 1 (gnss/01_nrf9151_basic) e confere o .config com verifica_variantes.sh.
rem
rem Uso:  build.cmd sem ^| minima ^| nuvem ^| periodico  [flash]
rem
rem O binario sai em build_<variante>\ dentro desta pasta (ignorado pelo git).
rem Com "flash" no fim, grava a DK depois de compilar.
setlocal
set NCS=C:\ncs\v3.4.0
set VER=v3.4.0
set APP=C:/work/nrf-manaus-2/gnss/01_nrf9151_basic
set AQUI=%~dp0
set V=%1
if "%V%"=="" goto uso

set P=-D01_nrf9151_basic_CONFIG_GNSS_SAMPLE
set TTFF=%P%_MODE_CONTINUOUS=n %P%_MODE_TTFF_TEST=y %P%_MODE_TTFF_TEST_COLD_START=y
if "%V%"=="sem"       set OPTS=%TTFF%
if "%V%"=="minima"    set OPTS=%TTFF% %P%_ASSISTANCE_NONE=n %P%_ASSISTANCE_MINIMAL=y
if "%V%"=="nuvem"     set OPTS=%TTFF% %P%_ASSISTANCE_NONE=n %P%_ASSISTANCE_NRF_CLOUD=y
if "%V%"=="periodico" set OPTS=%P%_MODE_CONTINUOUS=n %P%_MODE_PERIODIC=y %P%_LTE_ON_DEMAND=y %P%_ASSISTANCE_NONE=n %P%_ASSISTANCE_MINIMAL=y
if not defined OPTS goto uso

set OUT=%AQUI%build_%V%
set OUT=%OUT:\=/%
pushd %NCS%
nrfutil sdk-manager toolchain launch --ncs-version %VER% -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d %OUT% %APP% -- %OPTS%
if errorlevel 1 ( popd & exit /b 1 )
if "%2"=="flash" nrfutil sdk-manager toolchain launch --ncs-version %VER% -- west flash -d %OUT%
popd
sh "%AQUI%verifica_variantes.sh" %OUT% %V%
exit /b

:uso
echo Uso: build.cmd sem ^| minima ^| nuvem ^| periodico  [flash]
exit /b 2
