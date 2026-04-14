@echo off
echo Gerando claude-tokens.exe...
python -m PyInstaller --onefile --windowed --name "claude-tokens" --clean widget.py
echo.
if exist "dist\claude-tokens.exe" (
    echo OK! Executavel em: dist\claude-tokens.exe
) else (
    echo ERRO ao gerar o executavel.
)
pause
