# 打包与发布说明 / Packaging & Release Guide

## 1) 客户端 onefile 安全构建 / Secure Onefile Build

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_secure.ps1 `
  -PythonExe "C:\Users\Administrator\AppData\Local\Python\bin\python.exe" `
  -SkipInstall -SkipPyArmor -OneFile

Copy-Item .\dist_secure\MC_Translator_Secure.exe .\dist_secure\MC_Translator.exe -Force
```

## 2) 完整性签名构建 / Integrity Manifest Build

```powershell
python tools\build_integrity.py
```

若缺少依赖：

```powershell
python -m pip install -r requirements-security.txt
```

## 3) 发布到 GitHub Release / Publish to GitHub Release

```powershell
# 生成 UTF-8 发布说明
@'
import json, pathlib
v = json.loads(pathlib.Path("server/static/version.json").read_text(encoding="utf-8"))
pathlib.Path("release_notes.md").write_text((v.get("notes") or "").strip() + "\n", encoding="utf-8")
'@ | python -

# 创建发布
gh release create v2026.02.15-client.1 ".\dist_secure\MC_Translator.exe#MC_Translator.exe" `
  -R fguyfguiyytu/MC_TRANSLATOR `
  -t "v2026.02.15-client.1" `
  --notes-file .\release_notes.md
```

## 4) 发布后校验 / Post-release Checks

```powershell
gh release view v2026.02.15-client.1 -R fguyfguiyytu/MC_TRANSLATOR --json tagName,assets,body
```

校验项：
- 资产名为 `MC_Translator.exe`
- Release body 无乱码
- 客户端能检测到最新 tag

## 5) 回滚与热修复 / Rollback & Hotfix

- 热修复建议：`vYYYY.MM.DD-client.N`（递增 N）
- 若标签已存在，使用：

```powershell
gh release upload v2026.02.15-client.1 .\dist_secure\MC_Translator.exe#MC_Translator.exe -R fguyfguiyytu/MC_TRANSLATOR --clobber
```

## 6) 安全流水线 / Security Pipeline

```powershell
python tools\check_requirements_pinned.py requirements-client.txt requirements-security.txt server/requirements.txt
python -m pip install -r requirements-security.txt
python -m pip_audit -r requirements-client.txt --strict
python -m pip_audit -r server/requirements.txt --strict
```
