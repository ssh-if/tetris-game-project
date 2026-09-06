@echo off
chcp 65001 >nul
REM 俄罗斯方块核心逻辑单元测试一键运行
cd /d "%~dp0"

echo ========================================
echo  俄罗斯方块 - 单元测试
echo ========================================
echo.

where pytest >nul 2>nul
if errorlevel 1 (
    echo [!] 未检测到 pytest，正在安装...
    pip install pytest pytest-cov
)

echo [1/2] 运行单元测试并生成覆盖率...
pytest test_tetris_core.py --cov=../01-游戏源码 --cov-report=term-missing
echo.
echo [2/2] 测试完成。
pause
