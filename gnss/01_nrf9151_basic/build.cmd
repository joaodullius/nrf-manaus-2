@echo off
rem Codigo do curso (nrf-manaus-2). Compila o lab 1 (configuracao padrao do
rem prj.conf) e confere o .config com verifica_config.sh.
rem
rem Uso:  build.cmd [flash]
rem
rem O binario sai em build_9151\ dentro desta pasta (ignorado pelo git).
rem Com "flash", grava a DK depois de compilar.
setlocal
set NCS=C:\ncs\v3.4.0
set VER=v3.4.0
set APP=C:/work/nrf-manaus-2/gnss/01_nrf9151_basic
set AQUI=%~dp0

set OUT=%AQUI%build_9151
set OUT=%OUT:\=/%
pushd %NCS%
nrfutil sdk-manager toolchain launch --ncs-version %VER% -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d %OUT% %APP%
if errorlevel 1 ( popd & exit /b 1 )
if "%1"=="flash" nrfutil sdk-manager toolchain launch --ncs-version %VER% -- west flash -d %OUT%
popd
sh "%AQUI%verifica_config.sh" %OUT%
exit /b
