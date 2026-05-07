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
# 1. 下载 mihomo 二进制: https://github.com/MetaCubeX/mihomo/releases
#    选择: linux-amd64 的 .gz 文件
#    放到本目录下命名为 mihomo.gz 或 /tmp/mihomo.gz

# 2. 安装
sudo bash install.sh

# 3. 添加订阅
# 编辑 /rw/config/clash/config.yaml — 在 'proxies:' 下添加节点

# 4. 重启
sudo systemctl restart mihomo

# 5. 测试
bash scripts/test.sh

# 6. dom0 设置 AppVM 使用此 NetVM
qvm-prefs <appvm名称> netvm <此netvm名称>
```

## 架构

```
AppVM (任意) → NetVM (sys-clash)
    ↓ 所有流量到达 vif* 接口
mihomo TUN (auto-redirect 自动处理 nftables)
    ├→ 国内域名/IP → 直连 eth0 出去
    └→ 国外 → 代理节点 → 上游 NetVM → 互联网
```

## 文件结构

```
├── install.sh              # 安装脚本
├── uninstall.sh            # 卸载脚本
├── config/
│   └── config.yaml         # mihomo 配置模板
├── scripts/
│   └── test.sh             # 连通性测试
└── clashctl/               # TUI 管理工具（计划中）
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
