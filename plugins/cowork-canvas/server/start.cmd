@echo off
setlocal
rem Starts the canvas MCP server of the cowork-canvas plugin on the .NET 10
rem runtime that is already on the machine (the pyRevit installer brings it).
rem Nothing is downloaded or installed. stdout carries the MCP protocol, so
rem every message from this file goes to stderr.
set "HERE=%~dp0"
set "DOTNET="
for %%X in (dotnet.exe) do set "DOTNET=%%~$PATH:X"
if defined DOTNET goto found
set "DOTNET=%ProgramFiles%\dotnet\dotnet.exe"
if exist "%DOTNET%" goto found
echo cowork-canvas: dotnet.exe was not found on PATH or in "%ProgramFiles%\dotnet". The server needs the .NET 10 runtime, which the pyRevit installer brings. Run the pyRevit Utility, then restart Claude. 1>&2
exit /b 1
:found
if exist "%HERE%bin\CanvasMcp.dll" goto run
echo cowork-canvas: "%HERE%bin\CanvasMcp.dll" is missing. The plugin folder is incomplete; update or reinstall the plugin. 1>&2
exit /b 1
:run
set "DOTNET_NOLOGO=1"
"%DOTNET%" "%HERE%bin\CanvasMcp.dll"
