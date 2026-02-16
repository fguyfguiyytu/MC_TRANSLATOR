# 服务端部署说明 / Server Deployment Guide

> 本节适用于完整工程（含 `server/` 目录）的部署场景。  
> This section applies to the full edition that includes `server/`.

## 1) 环境准备 / Environment Setup

```bash
cd server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2) 关键环境变量 / Key Environment Variables

| 变量 / Variable | 默认值 / Default | 说明 / Description |
|---|---|---|
| `MC_API_SECRET` | `change-me` | 客户端请求签名密钥 / API HMAC secret |
| `MC_ADMIN_USER` | `admin` | 管理后台用户名 / admin username |
| `MC_ADMIN_PASS` | `admin` | 管理后台密码（务必修改）/ admin password |
| `MC_SESSION_DAYS` | `7` | 会话有效期（天）/ session TTL days |
| `MC_TS_WINDOW` | `60` | 时间戳窗口（秒）/ timestamp window |
| `MC_GITHUB_REPO` | `fguyfguiyytu/MC_TRANSLATOR` | 更新检测仓库 / update source repo |

> ⚠️ **CN**: 生产环境必须修改默认密码与密钥。  
> ⚠️ **EN**: Change all default secrets/passwords before production.

## 3) 启动方式 / Startup

```bash
uvicorn server.app:app --host 127.0.0.1 --port 8000
```

### systemd 示例 / systemd sample

```ini
[Unit]
Description=MC License Server
After=network.target

[Service]
WorkingDirectory=/www/wwwroot/your-site
ExecStart=/www/wwwroot/your-site/venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 8000
Restart=always
User=www
Group=www

[Install]
WantedBy=multi-user.target
```

## 4) 宝塔/Nginx 反向代理 / BaoTa Nginx Reverse Proxy

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

## 5) 故障排查 / Troubleshooting

```bash
systemctl status mc_license.service -n 200 --no-pager
journalctl -u mc_license.service -n 200 --no-pager
ss -lntp | grep 8000
nginx -t
```

- 502 常见根因：后端未监听、Nginx 证书路径失效、反代端口不一致。
- Python 3.8 兼容性：避免 `str | None`，使用 `Optional[str]`。

## 6) 管理后台与安全建议 / Admin & Security

- 建议按角色分级：viewer / operator / owner。
- 定期轮换密钥：`MC_API_SECRET`。
- 记录异常日志并限制管理入口来源 IP。
