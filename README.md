# Minecraft 智能翻译工具（Translation Core）

## 项目简介

本项目是一个面向 Minecraft 聊天场景的翻译工具，支持：

- 多翻译引擎（Baidu / Google）
- 手动翻译 + 智能翻译
- 历史记录、结果导出
- 悬浮窗翻译联动
- 中英文 UI 切换（部分版本）

如果你只想开源“翻译核心”，可以只发布 `translator/`、`ui/main_window.py` 中与翻译相关的模块和接口。

---

## 功能亮点

- 实时翻译：输入文本后快速输出译文
- 智能语言识别：自动判断来源语言
- 引擎切换：按需选择 Baidu 或 Google
- 缓存机制：减少重复请求
- 历史追踪：保存每次翻译记录

---

## 目录说明（建议开源结构）

```text
.
├─ main.py
├─ translator/                  # 翻译引擎与扩展
├─ ui/
│  └─ main_window.py            # UI + 翻译调用主流程
├─ core/                        # 热键、日志、通用能力
├─ license/                     # 授权/在线校验（如不公开可移除）
└─ README.md
```

---

## 快速开始

### 1. 环境要求

- Python 3.10+（建议 3.11/3.12）
- Windows 10/11

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

如果你暂时没有 `requirements.txt`，至少安装：

```bash
pip install pyqt6 requests
```

### 3. 运行

```bash
python main.py
```

---

## 翻译接口配置

在配置文件中填写对应密钥后可启用 Baidu 翻译；Google 通常可直接调用公开接口（受网络环境影响）。

- Baidu 申请地址：`https://api.fanyi.baidu.com/`
- 配置项示例：
  - `baidu_app_id`
  - `baidu_secret_key`
  - `translation_engine` (`baidu` / `google`)

---

## 打包（PyInstaller）

```bash
pyinstaller -y --clean MC_Translator_onedir.spec
```

输出目录通常为：

- `dist/MC_Translator/`

---

## 发布到 GitHub 前必须检查

1. 删除或替换硬编码密钥（API Key、服务器密钥）
2. 清理本地配置与日志文件（含用户路径）
3. 确认不上传私有授权逻辑（若不打算公开）
4. 补充许可证文件（推荐 `MIT` 或 `Apache-2.0`）

---

## 常见问题（FAQ）

### Q1: 为什么 Google 翻译有时失败？

可能是网络环境或接口限制导致，建议：

- 切换到 Baidu 引擎
- 增加重试与超时处理
- 检查代理/防火墙

### Q2: 为什么显示有英文未翻译？

- 该文本可能被规则过滤（如名字、命令）
- 缓存命中旧结果
- 自动检测语言误判

---

## 贡献

欢迎提交 Issue / PR：

- Bug 修复
- 翻译质量改进
- 新引擎适配
- UI/交互优化

---

## 免责声明

本项目仅供学习与技术研究，请遵守目标平台与翻译服务提供商的使用条款。
