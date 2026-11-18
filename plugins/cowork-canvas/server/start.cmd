@echo off
setlocal
rem Starts the canvas MCP server of the cowork-canvas plugin on the .NET 10
rem runtime that is already on the machine (the pyRevit installer brings it).
rem Nothing is downloaded or installed. stdout carries the MCP protocol, so
rem every message from this file goes to stderr.
rem
rem The server does NOT run from this folder. Windows will not let a folder be
rem replaced while a program runs from it, so a server running here would stop
rem the plugin from ever updating. The built files in bin\ are copied once per
rem build to %LOCALAPPDATA%\cowork-canvas\run\<build id> and run from there.
set "HERE=%~dp0"
set "DOTNET="
for %%X in (dotnet.exe) do set "DOTNET=%%~$PATH:X"
if defined DOTNET goto havedotnet
set "DOTNET=%ProgramFiles%\dotnet\dotnet.exe"
if exist "%DOTNET%" goto havedotnet
echo cowork-canvas: dotnet.exe was not found on PATH or in "%ProgramFiles%\dotnet". The server needs the .NET 10 runtime, which the pyRevit installer brings. Run the pyRevit Utility, then restart Claude. 1>&2
exit /b 1
:havedotnet
if exist "%HERE%bin\CanvasMcp.dll" goto havebin
echo cowork-canvas: "%HERE%bin\CanvasMcp.dll" is missing. The plugin folder is incomplete; update or reinstall the plugin. 1>&2
exit /b 1
:havebin
set "DOTNET_NOLOGO=1"
set "COWORK_CANVAS_PLUGIN_DIR=%HERE%"
set "RUN=%HERE%bin"
set "BUILD_ID="
if exist "%HERE%bin.id" set /p BUILD_ID=<"%HERE%bin.id"
if not defined BUILD_ID goto inplace
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
if not defined COWORK_CANVAS_RUN set "COWORK_CANVAS_RUN=%LOCALAPPDATA%\cowork-canvas\run"
set "RUN=%COWORK_CANVAS_RUN%\%BUILD_ID%"
if exist "%RUN%\CanvasMcp.dll" goto retire
rem Copy to a temporary name, then rename: the build folder appears complete or not at all,
rem even when two server processes start at the same moment.
set "STAGING=%COWORK_CANVAS_RUN%\tmp-%BUILD_ID%-%RANDOM%%RANDOM%"
robocopy "%HERE%bin" "%STAGING%" /E /NFL /NDL /NJH /NJS /NP /R:1 /W:1 1>nul 2>nul
if errorlevel 8 goto inplace
ren "%STAGING%" "%BUILD_ID%" 1>nul 2>nul
rem The rename fails when another server process finished its copy first; that copy is used.
if exist "%STAGING%" rd /s /q "%STAGING%" 1>nul 2>nul
if not exist "%RUN%\CanvasMcp.dll" goto inplace
:retire
rem Remove the copies of other builds. A folder is renamed first: the rename fails while a
rem running server still uses it, so a build in use is never touched.
for /d %%D in ("%COWORK_CANVAS_RUN%\*") do call :retireone "%%~nxD"
for /d %%D in ("%COWORK_CANVAS_RUN%\old-*") do rd /s /q "%%D" 1>nul 2>nul
cd /d "%COWORK_CANVAS_RUN%" 1>nul 2>nul
goto run
:retireone
set "N=%~1"
if /i "%N%"=="%BUILD_ID%" exit /b 0
if /i "%N:~0,4%"=="old-" exit /b 0
if /i "%N:~0,16%"=="tmp-%BUILD_ID%" exit /b 0
ren "%COWORK_CANVAS_RUN%\%N%" "old-%N%-%RANDOM%" 1>nul 2>nul
exit /b 0
:inplace
echo cowork-canvas: could not prepare a copy of the server outside the plugin folder; running from "%HERE%bin". The plugin cannot update while this server runs. 1>&2
set "RUN=%HERE%bin"
:run
rem One line on purpose: cmd reads it whole before running it, so nothing is read from this
rem file after the server exits, even if an update has replaced the file in the meantime.
rem %* passes on the mode the plugin's .mcp.json asks for (--host).
"%DOTNET%" "%RUN%\CanvasMcp.dll" %* & exit
