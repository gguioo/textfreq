@echo off
chcp 65001 >nul
where python >nul 2>nul
if errorlevel 1 (
  echo 请先安装 Python 并勾选 Add Python to PATH，然后重新双击本文件。
  pause & exit
)
pip install git+https://github.com/gguioo/textfreq.git >nul 2>nul
pythonw -m textfreq.desktop
if errorlevel 1 python -m textfreq.desktop
