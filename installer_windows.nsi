; Playlist Helper Windows Installer
; NSIS script — compiles with makensis under Wine

Unicode True
RequestExecutionLevel admin

Name "Playlist Helper"
OutFile "dist/PlaylistHelper_Setup.exe"
InstallDir "$PROGRAMFILES64\PlaylistHelper"
InstallDirRegKey HKLM "Software\PlaylistHelper" "InstallDir"

!include "MUI2.nsh"
!include "FileFunc.nsh"

; Modern UI
!define MUI_ABORTWARNING
!define MUI_ICON "resources\icon.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    
    ; Main executable (PyInstaller onefile .exe)
    File "dist\PlaylistHelper.exe"
    
    ; FFmpeg for audio processing
    File "resources\ffmpeg.exe"
    
    ; Sample test files (one per format — covers all 5 supported types)
    SetOutPath "$INSTDIR\tests\original"
    File "resources\test_samples\02 - Under Your Spell.flac"
    File "resources\test_samples\08 Weight of the World _ English Ver.m4a"
    File "resources\test_samples\Ado - 0.mp3"
    File "resources\test_samples\test_tone.wav"
    File "resources\test_samples\test_tone.opus"
    
    ; Test framework
    SetOutPath "$INSTDIR\tests"
    File "tests\test_all.py"
    File "tests\cover_test.png"
    
    ; Copy source files for test imports
    SetOutPath "$INSTDIR"
    File /r "src\*.py"
    
    ; Copy main.py
    File "main.py"
    
    ; Copy requirements
    File "requirements.txt"
    
    ; Create Start Menu shortcut
    CreateDirectory "$SMPROGRAMS\Playlist Helper"
    CreateShortCut "$SMPROGRAMS\Playlist Helper\Playlist Helper.lnk" "$INSTDIR\PlaylistHelper.exe" "" "$INSTDIR\PlaylistHelper.exe" 0
    CreateShortCut "$SMPROGRAMS\Playlist Helper\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0
    
    ; Create Desktop shortcut
    CreateShortCut "$DESKTOP\Playlist Helper.lnk" "$INSTDIR\PlaylistHelper.exe" "" "$INSTDIR\PlaylistHelper.exe" 0
    
    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    ; Registry for uninstall
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlaylistHelper" \
        "DisplayName" "Playlist Helper"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlaylistHelper" \
        "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlaylistHelper" \
        "DisplayIcon" "$INSTDIR\PlaylistHelper.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlaylistHelper" \
        "Publisher" "PlaylistHelper"
    
    ; Run tests post-install via system Python on installed test files
    ; The PyInstaller exe does not bundle tests/, so run Python directly.
    ; If Python is not on PATH, skip gracefully with a user-visible message.
    nsExec::ExecToStack '"cmd" /c "cd /d $INSTDIR && python tests\test_all.py --limit-per-format 1"'
    Pop $0
    StrCmp $0 0 +3
    StrCmp $0 "" 0 +2
    MessageBox MB_ICONINFORMATION "Post-install verification:$\ntests\test_all.py --limit-per-format 1 exited with code $0.$\n$\n(This is expected if Python is not on PATH on this system.)"
SectionEnd

Section "Uninstall"
    ; Remove files
    Delete "$INSTDIR\PlaylistHelper.exe"
    Delete "$INSTDIR\ffmpeg.exe"
    Delete "$INSTDIR\main.py"
    Delete "$INSTDIR\requirements.txt"
    Delete "$INSTDIR\uninstall.exe"
    RMDir /r "$INSTDIR\src"
    RMDir /r "$INSTDIR\tests"
    
    ; Remove shortcuts
    Delete "$SMPROGRAMS\Playlist Helper\Playlist Helper.lnk"
    Delete "$SMPROGRAMS\Playlist Helper\Uninstall.lnk"
    RMDir "$SMPROGRAMS\Playlist Helper"
    Delete "$DESKTOP\Playlist Helper.lnk"
    
    ; Remove registry keys
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlaylistHelper"
    DeleteRegKey HKLM "Software\PlaylistHelper"
    
    RMDir "$INSTDIR"
SectionEnd
