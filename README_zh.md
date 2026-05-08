# Qubes Clash Gateway

Qubes OS 透明代理网关，基于 [mihomo](https://github.com/MetaCubeX/mihomo)。将 NetVM 变成代理网关 — AppVM 零配置自动走代理。

## 功能

- TCP/UDP 全端口透明代理
- DNS fake-ip 防污染（198.18.x.x）
- GeoIP 规则分流（国内直连，国外代理）
- 订阅解析（Clash YAML、vmess/vless/ss/ssr/trojan/hy2/tuic/wireguard）
- 终端控制器 `clashctl` + Web UI

## 安装

```bash
# 1. SSH 到 NetVM
ssh user@<netvm-ip>

# 2. 克隆项目
git clone https://github.com/iasds/qubes-clash-gateway.git
cd qubes-clash-gateway

# 3. 一键安装（mihomo + nftables + clashctl + systemd）
sudo bash setup.sh

# 4. 添加订阅
clashctl /sub add <订阅链接>

# 5. 选择模式
clashctl /mode rule      # 规则分流（推荐）

# 6. dom0 设置 AppVM 使用此 NetVM
qvm-prefs <appvm名称> netvm <此netvm名称>
```

安装完成后 AppVM 即可上网，无需额外配置。

## 使用

### 常用命令

```bash
clashctl /status              # 查看状态、流量、节点数
clashctl /mode rule           # 规则分流（国内直连，国外代理）
clashctl /mode global         # 全局代理
clashctl /mode direct         # 直连
clashctl /sub add <url>       # 添加订阅
clashctl /sub update          # 更新所有订阅
clashctl /sub list            # 列出订阅
clashctl /node                # 列出所有节点
clashctl /node <节点名>       # 选择节点
clashctl /test                # 全部节点测速
clashctl /test <节点名>       # 单节点测速
clashctl /dns fake-ip         # 切换 DNS 模式
clashctl /restart             # 重启 mihomo
clashctl /web                 # 启动 Web UI（默认端口 9091）
```

别名：`/s`=`/status`，`/m`=`/mode`，`/n`=`/node`，`/t`=`/test`

### Web UI

```bash
clashctl /web                 # 启动，自动生成 token
clashctl /web --secret <密码> # 指定 token
```

浏览器打开 `http://<netvm-ip>:9091`，输入 token 即可管理。

### 测试连通性

```bash
# 在 NetVM 上测试
bash scripts/test.sh

# 在 AppVM 上测试
curl -s https://api.ipify.org          # 出口 IP（应为代理服务器 IP）
curl -s https://www.baidu.com          # 国内直连
curl -s https://www.google.com         # 国外代理
```

## 架构

```
AppVM → vif* 接口 → nftables 劫持 → mihomo
                                  ├→ DNS :53 → :1053 (fake-ip)
                                  ├→ TCP  → :7892 (redir-port)
                                  └→ UDP  → :7893 (tproxy-port)

mihomo 分流：
  ├→ 国内域名/IP → 直连
  └→ 国外 → 代理节点 → 互联网
```

## 持久化

Qubes AppVM 重启后 `/etc/` 会丢失，以下路径持久保存：

| 路径 | 内容 |
|------|------|
| `/rw/config/clash/` | 配置文件、规则集、订阅数据 |
| `/rw/config/rc.local` | 启动脚本（mihomo + nftables） |
| `/usr/local/bin/mihomo` | mihomo 二进制 |
| `/etc/systemd/system/mihomo.service` | systemd 服务 |

## 配置文件

主配置：`/rw/config/clash/config.yaml`

### 添加代理节点

```yaml
proxies:
  - name: 节点1
    type: ss
    server: example.com
    port: 443
    cipher: aes-256-gcm
    password: your-password
```

或直接用命令：`clashctl /sub add <订阅链接>`

### 分流规则

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
- 停止并删除 mihomo systemd 服务
- 删除 `/usr/local/bin/mihomo`
- 删除 `/etc/sudoers.d/clashctl`
- 清理 `/rw/config/rc.local` 中的启动配置
- 删除 nftables 规则

配置文件 `/rw/config/clash/` 保留，手动删除：

```bash
sudo rm -rf /rw/config/clash
```

dom0 需手动将 AppVM 的 netvm 改回原值：

```bash
qvm-prefs <appvm名称> netvm <原netvm名称>
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
    ├── data.py                # 文件读写
    ├── i18n.py                # 国际化
    ├── monitor.py             # 健康监控
    ├── nodes.py               # 节点解析和测速
    ├── parser.py              # 订阅 URI 解析
    ├── proxy.py               # 模式切换和服务控制
    ├── ui.py                  # 终端 UI
    ├── web.py                 # Web UI 服务
    └── web_templates/
        └── index.html         # Web UI 前端
```

## 许可

MIT
