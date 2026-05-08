# Qubes Clash Gateway

[English](README.md) | 中文

Qubes OS 透明代理网关，基于 [mihomo](https://github.com/MetaCubeX/mihomo)。将 NetVM 变成代理网关 — AppVM 零配置即可使用代理。

## 功能特性

- TCP/UDP 全流量透明代理
- DNS fake-ip 防污染 (198.18.x.x)
- GeoIP 规则路由（国内直连，国外代理）
- 订阅解析器（Clash YAML、vmess/vless/ss/ssr/trojan/hy2/tuic/wireguard）
- 终端控制器 `clashctl` + Web UI

## 安装

```bash
# 1. SSH 连接到 NetVM
ssh user@<netvm-ip>

# 2. 克隆项目
git clone https://github.com/iasds/qubes-clash-gateway.git
cd qubes-clash-gateway

# 3. 一键安装（mihomo + nftables + clashctl + systemd）
sudo bash setup.sh

# 4. 添加订阅
clashctl /sub add <订阅链接>

# 5. 选择模式
clashctl /mode rule      # 规则路由（推荐）

# 6. 在 dom0 中将 AppVM 设置为使用此 NetVM
qvm-prefs <appvm名称> netvm <此netvm名称>
```

安装完成后，AppVM 即可直接上网。

## 使用方法

### 常用命令

```bash
clashctl /status              # 查看状态、流量、节点数
clashctl /mode rule           # 规则路由
clashctl /mode global         # 全局代理
clashctl /mode direct         # 直连
clashctl /sub add <url>       # 添加订阅
clashctl /sub update          # 更新所有订阅
clashctl /sub list            # 列出订阅
clashctl /node                # 列出所有节点
clashctl /node <name>         # 选择节点
clashctl /test                # 全部测速
clashctl /test <name>         # 单节点测速
clashctl /dns fake-ip         # 切换 DNS 模式
clashctl /restart             # 重启 mihomo
clashctl /web                 # 启动 Web UI（默认端口 9091）
```

别名：`/s`=`/status`、`/m`=`/mode`、`/n`=`/node`、`/t`=`/test`

### Web UI

```bash
clashctl /web                 # 自动生成 token 启动
clashctl /web --secret <密码> # 自定义 token 启动
```

在浏览器中打开 `http://<netvm-ip>:9091`，输入 token 即可管理。

### 测试连通性

```bash
# 在 NetVM 上
bash scripts/test.sh

# 在 AppVM 上
curl -s https://api.ipify.org          # 出口 IP（应为代理服务器 IP）
curl -s https://www.baidu.com          # 国内直连
curl -s https://www.google.com         # 国外代理
```

## 架构

```
AppVM → vif* 接口 → nftables 重定向 → mihomo
                                      ├→ DNS :53 → :1053 (fake-ip)
                                      ├→ TCP  → :7892 (redir-port)
                                      └→ UDP  → :7893 (tproxy-port)

mihomo 路由规则：
  ├→ 国内域名/IP → 直连
  └→ 国外 → 代理节点 → 互联网
```

## 持久化

Qubes AppVM 重启后 `/etc/` 会丢失。以下路径持久化：

| 路径 | 内容 |
|------|------|
| `/rw/config/clash/` | 配置文件、规则、订阅数据 |
| `/rw/config/rc.local` | 启动脚本（mihomo + nftables） |
| `/usr/local/bin/mihomo` | mihomo 二进制文件 |
| `/etc/systemd/system/mihomo.service` | systemd 服务 |

## 配置

主配置文件：`/rw/config/clash/config.yaml`

### 添加代理节点

```yaml
proxies:
  - name: node1
    type: ss
    server: example.com
    port: 443
    cipher: aes-256-gcm
    password: your-password
```

或使用命令：`clashctl /sub add <订阅链接>`

### 路由规则

```yaml
rules:
  - GEOSITE,cn,DIRECT       # 国内域名直连
  - GEOIP,CN,DIRECT         # 国内 IP 直连
  - MATCH,auto               # 其余走代理
```

## 卸载

```bash
# 在 NetVM 上执行
sudo bash uninstall.sh
```

卸载会：
- 停止并移除 mihomo systemd 服务
- 移除 `/usr/local/bin/mihomo`
- 移除 `/etc/sudoers.d/clashctl`
- 清理 `/rw/config/rc.local` 中的启动配置
- 移除 nftables 规则

`/rw/config/clash/` 中的配置文件会保留，手动删除：

```bash
sudo rm -rf /rw/config/clash
```

在 dom0 中将 AppVM 的 netvm 改回：

```bash
qvm-prefs <appvm名称> netvm <原netvm>
```

## 文件结构

```
├── setup.sh                  # 一键安装
├── install.sh                # 基础安装（仅 mihomo）
├── uninstall.sh              # 卸载
├── config/
│   ├── config.yaml           # mihomo 配置模板
│   ├── nftables-proxy.sh     # nftables 透明代理规则
│   └── sudoers-clashctl      # sudoers 免密配置
├── scripts/
│   └── test.sh               # 连通性测试
└── clashctl/
    ├── __main__.py            # CLI 入口
    ├── api.py                 # mihomo REST API
    ├── config.py              # 常量和预设
    ├── data.py                # 文件 I/O
    ├── i18n.py                # 国际化
    ├── monitor.py             # 健康监控
    ├── nodes.py               # 节点解析和测速
    ├── parser.py              # 订阅 URI 解析器
    ├── proxy.py               # 模式切换和服务控制
    ├── ui.py                  # 终端 UI
    ├── web.py                 # Web UI 服务
    └── web_templates/
        └── index.html         # Web UI 前端
```

## 许可证

MIT
