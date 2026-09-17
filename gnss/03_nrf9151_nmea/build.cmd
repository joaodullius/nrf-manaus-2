@echo off
rem Codigo do curso (nrf-manaus-2). Compila o lab 3 (NMEA limpo) a partir do
rem fonte do lab 1 (gnss/01_nrf9151_basic) e confere o .config com verifica_nmea.sh.
rem
rem Uso:  build.cmd [flash]
rem
rem O binario sai em build\ dentro desta pasta (ignorado pelo git).
rem Com "flash", grava a DK depois de compilar.
setlocal
set NCS=C:\ncs\v3.4.0
set VER=v3.4.0
set APP=C:/work/nrf-manaus-2/gnss/01_nrf9151_basic
set AQUI=%~dp0
set OPTS=-D01_nrf9151_basic_CONFIG_GNSS_SAMPLE_NMEA_ONLY=y -D01_nrf9151_basic_CONFIG_LOG=n -D01_nrf9151_basic_CONFIG_AT_HOST_LIBRARY=n

set OUT=%AQUI%build
set OUT=%OUT:\=/%
pushd %NCS%
nrfutil sdk-manager toolchain launch --ncs-version %VER% -- west build -p -b nrf9151dk/nrf9151/ns --sysbuild -d %OUT% %APP% -- %OPTS%
if errorlevel 1 ( popd & exit /b 1 )
if "%1"=="flash" nrfutil sdk-manager toolchain launch --ncs-version %VER% -- west flash -d %OUT%
popd
sh "%AQUI%verifica_nmea.sh" %OUT%
exit /b
