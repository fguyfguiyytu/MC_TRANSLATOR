# Minecraft Smart Translator / Minecraft 智能翻译工具

> **CN**: 本仓库当前公开翻译核心源码，并提供完整的客户端/服务端/发布使用说明。  
> **EN**: This repository currently exposes translation-core source code and includes complete bilingual guides for client, server, and release workflow.

## 1) 项目简介 / Project Overview

**CN**
- 主要能力：聊天文本翻译、Google/Baidu 翻译调用、历史记录与基础 UI 入口。
- 开源范围：当前仓库以翻译核心为主；服务端授权与打包流程说明已在文档中给出。

**EN**
- Main capabilities: chat translation flow, Google/Baidu integrations, history, and UI entry logic.
- Open-source scope: this repo focuses on translation core; server licensing and release steps are documented.

## 2) 架构概览 / Architecture

```text
Client (PyQt6)
  |- ui/main_window.py
  |- minecraft_translator_complete_enhanced.py
  \- translation calls (Google/Baidu)

Server (FastAPI, full edition)
  |- /api/activate /api/verify /api/consume /api/ping
  |- /api/version /download /redeem
  \- Nginx reverse proxy + systemd

Distribution
  |- PyInstaller onefile
  |- GitHub Release asset: MC_Translator.exe
  \- Client update checks against latest release tag
```

## 3) 快速开始 / Quick Start

### 客户端（源码）/ Client (source)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
python -m pip install PyQt6==6.8.1 PyQt6-Qt6==6.8.2 PyQt6-sip==13.10.0
python main.py
```

### 服务端（完整工程）/ Server (full project)

```bash
cd server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn server.app:app --host 127.0.0.1 --port 8000
```

## 4) 文档导航 / Documentation Index

- [docs/client.md](docs/client.md) — 客户端安装、激活、同步、更新 / client setup and usage
- [docs/server.md](docs/server.md) — FastAPI + 宝塔/Nginx + systemd 部署 / server deployment
- [docs/release.md](docs/release.md) — 打包、完整性校验、GitHub Release / packaging & release
- [docs/troubleshooting.md](docs/troubleshooting.md) — 常见问题排查 / troubleshooting
- [README_build.md](README_build.md) — 构建入口说明 / build entry doc

## 5) 版本与更新机制 / Version & Update Mechanism

**CN**
- 客户端通过 GitHub Releases `latest` 获取 `tag_name` 与下载地址。
- 服务端 `/api/version` 与 `/download` 可向前端和兑换页展示同一版本信息。

**EN**
- The client queries GitHub Releases `latest` for `tag_name` and download URL.
- Server `/api/version` and `/download` can expose the same version metadata for redeem page and clients.

## 6) 安全说明 / Security Notes

**CN**
- 请勿在仓库中提交真实 API 密钥、私钥或管理员密码。
- 完整性校验与依赖审计流程见 [docs/release.md](docs/release.md)。

**EN**
- Never commit real API keys, private keys, or admin credentials.
- See [docs/release.md](docs/release.md) for integrity verification and dependency audit.

## License

请按你的项目授权策略使用本代码和文档。  
Use according to your project licensing policy.
