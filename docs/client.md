# 客户端使用说明 / Client Guide

## 1) 运行环境与依赖 / Runtime & Dependencies

**CN**
- Python: 推荐 3.10-3.12（3.14 也可运行，但部分第三方依赖兼容性需自测）。
- GUI: `PyQt6==6.8.1`, `PyQt6-Qt6==6.8.2`, `PyQt6-sip==13.10.0`

**EN**
- Python: 3.10-3.12 recommended (3.14 works in many cases; verify dependency compatibility).
- GUI deps: `PyQt6==6.8.1`, `PyQt6-Qt6==6.8.2`, `PyQt6-sip==13.10.0`

## 2) 启动与基本使用 / Startup & Basic Usage

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
python -m pip install PyQt6==6.8.1 PyQt6-Qt6==6.8.2 PyQt6-sip==13.10.0
python main.py
```

**CN**
- 主入口：`main.py`
- UI 主逻辑：`ui/main_window.py`
- 翻译核心：`minecraft_translator_complete_enhanced.py`

**EN**
- Entry point: `main.py`
- Main UI: `ui/main_window.py`
- Translation core: `minecraft_translator_complete_enhanced.py`

## 3) 授权与同步 / License & Sync

**CN**
- 常见流程：激活 -> 周期验证 -> 消耗（时长/金币）-> 同步状态。
- 机器码通常由 `license/machine_id.py` 提供。
- 网络接口封装位于 `license/online.py`。

**EN**
- Typical flow: activate -> verify -> consume (time/credits) -> sync state.
- Machine code is usually provided by `license/machine_id.py`.
- Network API wrapper is in `license/online.py`.

## 4) 更新检测逻辑 / Update Check Logic

**CN**
- 客户端读取 GitHub `latest release`，比较 `APP_RELEASE_TAG` 与远端 `tag_name`。
- 更新入口通常位于“帮助 -> 检查更新”。

**EN**
- Client reads GitHub `latest release` and compares local `APP_RELEASE_TAG` with remote `tag_name`.
- Update action is typically in `Help -> Check Updates`.

## 5) 常见问题 / FAQ

- 启动报错 `MainApp().reun`: 将 `reun()` 修正为 `run()`。
- 中文乱码：确保文档与 JSON 统一 UTF-8，发布说明建议用 `--notes-file`。
- 同步 401/Session expired：重新激活并检查服务端 `MC_API_SECRET` 一致性。
