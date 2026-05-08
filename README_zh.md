# Qubes Clash Gateway

**[English](README.md)** | [中文](README_zh.md)

Qubes OS 透明代理网关，基于 [mihomo](https://github.com/MetaCubeX/mihomo)。AppVM 零配置 — 所有流量（TCP/UDP，全端口）自动走代理。

## 为什么？

Qubes OS 隔离了 VM，但没解决代理问题。每个 AppVM 单独跑代理客户端太麻烦。本项目把 Qubes NetVM 变成透明代理网关 — 任何使用它作为 NetVM 的 AppVM 自动走代理，AppVM 端零配置。

**相比 sing-box TUN 方案**（上一个项目 `qubes-singroute-gateway`）：

| 特性 | sing-box | mihomo |
|------|----------|--------|
| nftables 自动配置 | ❌ 手动 | ✅ `auto-redirect` |
| DNS 劫持 | ❌ 需要外部转发器 | ✅ 内置 `dns-hijack` |
| Fake-IP DNS | ❌ 不支持 | ✅ 内置 |
| 网关文档 | ❌ 无 | ✅ "在路由器上按预期工作" |
| 路由稳定性 | ❌ 多个边界情况 | ✅ Clash 久经考验 |

## 快速开始

```bash
# 1. 克隆到 NetVM
git clone https://github.com/iasds/qubes-clash-gateway.git
cd qubes-clash-gateway

# 2. 一键安装（自动配置 nftables、clashctl、systemd）
sudo bash setup.sh

# 3. 添加订阅
clashctl /sub add <订阅链接>

# 4. 选择模式
clashctl /mode rule     # 规则分流（推荐）
clashctl /mode global   # 全局代理
clashctl /mode direct   # 直连

# 5. dom0 设置 AppVM 使用此 NetVM
qvm-prefs <appvm名称> netvm <此netvm名称>
```

## 架构

```
AppVM → vif* 接口 → nftables (DNS 劫持 :53→:1053) → mihomo TUN
                                                 ├→ 国内域名/IP → 直连 eth0
                                                 └→ 国外 → 代理节点 → 上游 → 互联网
```

## 文件结构

```
├── setup.sh              # 一键安装（推荐）
├── install.sh            # 基础安装（无 nftables）
├── uninstall.sh          # 卸载
├── config/
│   └── config.yaml       # mihomo 配置模板
├── scripts/
│   └── test.sh           # 连通性测试
└── clashctl/
    ├── __main__.py       # CLI 入口
    ├── api.py            # mihomo REST API 客户端
    ├── config.py         # 常量、路径、预设
    ├── data.py           # JSON/YAML 文件读写
    ├── i18n.py           # 中英文翻译
    ├── monitor.py        # 健康监控守护进程
    ├── nodes.py          # 节点解析、测速、GeoIP
    ├── parser.py         # 订阅解析 (vmess/vless/ss/ssr/trojan/hy2/tuic/wg)
    ├── proxy.py          # 模式切换、DNS 配置、服务控制
    ├── ui.py             # 终端 UI
    ├── web.py            # Web UI 服务
    └── web_templates/
        └── index.html    # Web UI（暗色 SPA）
```

## 持久化

Qubes AppVM 重启后 `/etc/` 会丢失。本项目通过以下方式处理持久化：

- **`/rw/config/clash/`** — 配置文件（持久）
- **`/rw/config/rc.local`** — 启动脚本，启动 mihomo 并激活 vif 接口
- **`/usr/local/bin/mihomo`** — 二进制文件（AppVM 中持久）

## 配置

编辑 `/rw/config/clash/config.yaml`：

### 添加订阅

```yaml
proxy-groups:
  - name: auto
    type: url-test
    proxies:
      - 节点1
      - 节点2
    url: https://www.gstatic.com/generate_204
    interval: 300
```

### DNS 模式

- **`fake-ip`**（推荐）：返回假 IP（198.18.x.x），防止 DNS 污染
- **`redir-host`**：返回真实 IP，兼容性更好

## 卸载

```bash
sudo bash uninstall.sh
```

## 许可

MIT
