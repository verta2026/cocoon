# 8 块钱给 cocoon 上域名

> 一年 8 块，手机随时随地打开 `chat.xxx.top` 就能和你的 AI 聊天。

## 你需要什么

- 一台 VPS（任何云服务商，能跑 cocoon 的那台）
- 一张能付 8 块钱的卡

## 第一步：买域名（Spaceship）

1. 打开 [spaceship.com](https://www.spaceship.com/)
2. 搜你想要的名字，选最便宜的后缀（`.top`、`.xyz`、`.site` 通常几块钱一年）
3. 注册账号，付款

> 不用买 SSL、隐私保护之类的附加服务——Cloudflare 全免费给你。

## 第二步：接入 Cloudflare（免费 SSL + CDN）

Cloudflare 免费计划就够用。它给你：自动 HTTPS、全球 CDN 加速、隐藏你的 VPS 真实 IP。

1. 注册 [cloudflare.com](https://www.cloudflare.com/)（免费）
2. 点 **Add a site**，输入你刚买的域名
3. 选 **Free** 计划
4. Cloudflare 会给你两个 nameserver 地址，类似：
   ```
   anna.ns.cloudflare.com
   bob.ns.cloudflare.com
   ```
5. 回到 Spaceship → 你的域名 → **Nameservers** → 改成 Cloudflare 给的这两个
6. 等几分钟到几小时生效（通常很快）

## 第三步：DNS 指向你的 VPS

在 Cloudflare 的 DNS 设置里：

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `chat` | `你的VPS IP` | Proxied (橙色云) |

- `Name` 填 `chat`（这样访问地址就是 `chat.你的域名.top`）
- `Content` 填你 VPS 的公网 IP
- **Proxy status 一定要开**（橙色云图标）——这样 Cloudflare 帮你加 HTTPS，还能隐藏真实 IP

## 第四步：VPS 上配反向代理

cocoon 跑在 `localhost:8080`，你需要一个反向代理把 80/443 端口的流量转过去。

### 方案 A：Caddy（推荐，最简单）

```bash
# 安装 Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

写配置文件 `/etc/caddy/Caddyfile`：

```
chat.你的域名.top {
    reverse_proxy localhost:8080
}
```

启动：

```bash
sudo systemctl restart caddy
```

完事。Caddy 自动处理 SSL 证书。

### 方案 B：nginx

```bash
sudo apt install nginx
```

写配置 `/etc/nginx/sites-available/cocoon`：

```nginx
server {
    listen 80;
    server_name chat.你的域名.top;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

启用并重启：

```bash
sudo ln -s /etc/nginx/sites-available/cocoon /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

> 因为 Cloudflare 代理了流量并提供 HTTPS，nginx 这边只需要监听 80 端口。浏览器看到的是 HTTPS（Cloudflare → 你的 VPS 这段也可以加密，去 Cloudflare SSL/TLS 设置里选 **Full**）。

## 第五步：打开浏览器

`https://chat.你的域名.top/chat`

输入你的 cocoon token，开始聊天。

手机上加到主屏幕，就像一个 app。

## Cloudflare SSL 设置

去 Cloudflare 控制台 → **SSL/TLS**：

- 用 Caddy：选 **Full (strict)**（Caddy 有真证书）
- 用 nginx（没配证书）：选 **Full**（不要选 Flexible，会有重定向循环）

## 省钱小贴士

- `.top` 域名首年通常 1-8 元，续费可能涨到 20-30 元
- 如果只是自己用，续费前看看有没有其他便宜后缀，换一个就行
- Cloudflare 的所有功能（DNS、CDN、SSL、隐藏 IP）**永久免费**

## 完整花费

| 项目 | 费用 |
|------|------|
| 域名（.top 一年） | ~8 元 |
| Cloudflare | 免费 |
| Caddy / nginx | 免费 |
| SSL 证书 | 免费（Cloudflare 提供） |
| **总计** | **~8 元/年** |
