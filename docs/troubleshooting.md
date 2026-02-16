# 常见问题排查 / Troubleshooting Matrix

## 客户端 / Client

| 问题 / Symptom | 可能原因 / Cause | 处理 / Fix |
|---|---|---|
| `MainApp` has no attribute `reun` | 拼写错误 | 将 `reun()` 改为 `run()` |
| `integrity_failed:hash:main.py` | onefile 提取后 `main.py` 哈希不稳定 | 冻结环境跳过 `main.py` 哈希校验 |
| `No module named PyQt6` | 缺少 GUI 依赖 | 安装 `requirements-client.txt` |
| 更新说明乱码 | 发布文案编码被控制台污染 | 使用 `--notes-file`（UTF-8） |

## 服务端 / Server

| 问题 / Symptom | 可能原因 / Cause | 处理 / Fix |
|---|---|---|
| 502 Bad Gateway | 后端未运行或 Nginx 配置错误 | 查 `systemctl status` + `nginx -t` |
| `TypeError: 'type' object is not subscriptable` | Python 3.8 不支持 `dict[str, Any]` | 改为 `Dict[str, Any]` |
| `unsupported operand type(s) for |` | Python 3.8 不支持 `str | None` | 改为 `Optional[str]` |
| `HTTP 401 Session expired` | 会话过期或密钥不一致 | 重新激活并校验 `MC_API_SECRET` |

## 发布 / Release

| 问题 / Symptom | 处理 / Fix |
|---|---|
| `gh release create` 失败但半成功 | 先 `gh release view <tag>`，存在则改 `gh release upload --clobber` |
| 资产下载错文件 | 确认资产名统一为 `MC_Translator.exe` |
