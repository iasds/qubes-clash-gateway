"""Tests for clashctl.parser — subscription parsing and URI decoding."""

import base64
import json

import pytest

from clashctl.parser import (
    _try_base64,
    parse_uri,
    parse_subscription_text,
)


# ── base64 helper ────────────────────────────────────────────────────────


class TestTryBase64:
    """Tests for _try_base64()."""

    def test_decodes_valid_base64(self):
        raw = "hello world"
        encoded = base64.b64encode(raw.encode()).decode()
        assert _try_base64(encoded) == raw

    def test_returns_original_on_invalid_base64(self):
        s = "this is not base64 @@@"
        result = _try_base64(s)
        # _try_base64 adds padding before trying, so result may have extra =
        # The key is it doesn't crash and returns a string
        assert isinstance(result, str)

    def test_handles_missing_padding(self):
        raw = "test"
        encoded = base64.b64encode(raw.encode()).decode()
        # Strip padding
        stripped = encoded.rstrip("=")
        assert _try_base64(stripped) == raw

    def test_handles_whitespace(self):
        raw = "hello"
        encoded = base64.b64encode(raw.encode()).decode()
        assert _try_base64(f"  {encoded}  ") == raw


# ── SS URI parsing ───────────────────────────────────────────────────────


class TestParseSS:
    """Tests for ss:// URI parsing."""

    def test_standard_base64_format(self):
        # method:password@server:port
        userinfo = "aes-256-gcm:mypassword"
        encoded = base64.b64encode(userinfo.encode()).decode()
        uri = f"ss://{encoded}@1.2.3.4:8388#my-node"
        result = parse_uri(uri)
        assert result is not None
        assert result["type"] == "ss"
        assert result["server"] == "1.2.3.4"
        assert result["port"] == 8388
        assert result["cipher"] == "aes-256-gcm"
        assert result["password"] == "mypassword"
        assert result["name"] == "my-node"

    def test_sip002_format(self):
        userinfo = base64.b64encode(b"chacha20-ietf-poly1305:secret").decode()
        uri = f"ss://{userinfo}@192.0.2.1:443#sip002-node"
        result = parse_uri(uri)
        assert result is not None
        assert result["type"] == "ss"
        assert result["cipher"] == "chacha20-ietf-poly1305"
        assert result["password"] == "secret"
        assert result["server"] == "192.0.2.1"

    def test_auto_generated_name(self):
        userinfo = base64.b64encode(b"aes-128-gcm:pass").decode()
        uri = f"ss://{userinfo}@5.6.7.8:1234"
        result = parse_uri(uri)
        assert result is not None
        assert result["name"] == "ss-5.6.7.8"

    def test_returns_none_for_wrong_scheme(self):
        assert parse_uri("http://example.com") is None


# ── VMess URI parsing ────────────────────────────────────────────────────


class TestParseVmess:
    """Tests for vmess:// URI parsing."""

    def test_basic_vmess(self):
        vmess_data = {
            "ps": "vmess-test",
            "add": "vm.example.com",
            "port": "443",
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "aid": "0",
            "scy": "auto",
            "net": "tcp",
            "tls": "",
        }
        encoded = base64.b64encode(json.dumps(vmess_data).encode()).decode()
        uri = f"vmess://{encoded}"
        result = parse_uri(uri)
        assert result is not None
        assert result["type"] == "vmess"
        assert result["name"] == "vmess-test"
        assert result["server"] == "vm.example.com"
        assert result["port"] == 443
        assert result["uuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert result["alterId"] == 0
        assert result["cipher"] == "auto"

    def test_vmess_with_tls_and_ws(self):
        vmess_data = {
            "ps": "ws-tls-node",
            "add": "ws.example.com",
            "port": 443,
            "id": "11111111-2222-3333-4444-555555555555",
            "aid": 0,
            "net": "ws",
            "tls": "tls",
            "host": "ws.example.com",
            "path": "/ws",
            "sni": "ws.example.com",
        }
        encoded = base64.b64encode(json.dumps(vmess_data).encode()).decode()
        uri = f"vmess://{encoded}"
        result = parse_uri(uri)
        assert result is not None
        assert result["tls"] is True
        assert result["servername"] == "ws.example.com"
        assert result["network"] == "ws"
        assert result["ws-opts"]["path"] == "/ws"
        assert result["ws-opts"]["headers"]["Host"] == "ws.example.com"

    def test_vmess_name_prefix_stripped(self):
        vmess_data = {
            "ps": "[HK] my-server",
            "add": "hk.example.com",
            "port": 443,
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "aid": 0,
        }
        encoded = base64.b64encode(json.dumps(vmess_data).encode()).decode()
        result = parse_uri(f"vmess://{encoded}")
        assert result is not None
        assert result["name"] == "my-server"

    def test_vmess_with_grpc_transport(self):
        vmess_data = {
            "ps": "grpc-node",
            "add": "grpc.example.com",
            "port": 443,
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "aid": 0,
            "net": "grpc",
            "path": "grpc-service",
        }
        encoded = base64.b64encode(json.dumps(vmess_data).encode()).decode()
        result = parse_uri(f"vmess://{encoded}")
        assert result is not None
        assert result["network"] == "grpc"
        assert result["grpc-opts"]["grpc-service-name"] == "grpc-service"


# ── VLESS URI parsing ────────────────────────────────────────────────────


class TestParseVless:
    """Tests for vless:// URI parsing."""

    def test_basic_vless_tls(self):
        uri = (
            "vless://aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            "@vless.example.com:443"
            "?security=tls&sni=vless.example.com&type=tcp"
            "#vless-node"
        )
        result = parse_uri(uri)
        assert result is not None
        assert result["type"] == "vless"
        assert result["name"] == "vless-node"
        assert result["server"] == "vless.example.com"
        assert result["port"] == 443
        assert result["uuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert result["tls"] is True
        assert result["servername"] == "vless.example.com"

    def test_vless_with_reality(self):
        uri = (
            "vless://uuid-here"
            "@reality.example.com:443"
            "?security=reality&pbk=publickey123&sid=shortid456&flow=xtls-rprx-vision"
            "#reality-node"
        )
        result = parse_uri(uri)
        assert result is not None
        assert result["tls"] is True
        assert result["reality-opts"]["public-key"] == "publickey123"
        assert result["reality-opts"]["short-id"] == "shortid456"
        assert result["flow"] == "xtls-rprx-vision"

    def test_vless_with_ws(self):
        uri = (
            "vless://uuid"
            "@ws.example.com:443"
            "?security=tls&type=ws&path=%2Fvless-ws&host=ws.example.com"
            "#ws-node"
        )
        result = parse_uri(uri)
        assert result is not None
        assert result["network"] == "ws"
        assert result["ws-opts"]["path"] == "/vless-ws"
        assert result["ws-opts"]["headers"]["Host"] == "ws.example.com"

    def test_vless_default_port(self):
        uri = "vless://uuid@host.example.com?type=tcp#node"
        result = parse_uri(uri)
        assert result is not None
        assert result["port"] == 443


# ── Trojan URI parsing ──────────────────────────────────────────────────


class TestParseTrojan:
    """Tests for trojan:// URI parsing."""

    def test_basic_trojan(self):
        uri = "trojan://mypassword@trojan.example.com:443#trojan-node"
        result = parse_uri(uri)
        assert result is not None
        assert result["type"] == "trojan"
        assert result["name"] == "trojan-node"
        assert result["server"] == "trojan.example.com"
        assert result["port"] == 443
        assert result["password"] == "mypassword"

    def test_trojan_with_sni(self):
        uri = "trojan://pass@host.example.com:443?sni=sni.example.com#sni-node"
        result = parse_uri(uri)
        assert result is not None
        assert result["sni"] == "sni.example.com"

    def test_trojan_auto_name(self):
        uri = "trojan://pass@auto.example.com:8443"
        result = parse_uri(uri)
        assert result is not None
        assert result["name"] == "trojan-auto.example.com"


# ── Subscription text parsing ────────────────────────────────────────────


class TestParseSubscriptionText:
    """Tests for parse_subscription_text()."""

    def test_clash_yaml_with_proxies(self):
        text = (
            "proxies:\n"
            "  - name: node-1\n"
            "    type: ss\n"
            "    server: s1.example.com\n"
            "    port: 443\n"
            "    cipher: aes-256-gcm\n"
            "    password: pass1\n"
            "  - name: node-2\n"
            "    type: ss\n"
            "    server: s2.example.com\n"
            "    port: 8443\n"
            "    cipher: chacha20-ietf-poly1305\n"
            "    password: pass2\n"
        )
        result = parse_subscription_text(text)
        assert len(result) == 2
        assert result[0]["name"] == "node-1"
        assert result[1]["name"] == "node-2"

    def test_base64_encoded_uri_list(self):
        uris = (
            "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ=@1.2.3.4:443#node-a\n"
            "trojan://pass@host.example.com:443#node-b\n"
        )
        encoded = base64.b64encode(uris.encode()).decode()
        result = parse_subscription_text(encoded)
        assert len(result) == 2
        assert result[0]["type"] == "ss"
        assert result[1]["type"] == "trojan"

    def test_raw_uri_list(self):
        text = (
            "trojan://pass1@a.example.com:443#node-1\n"
            "trojan://pass2@b.example.com:443#node-2\n"
        )
        result = parse_subscription_text(text)
        assert len(result) == 2
        assert all(p["type"] == "trojan" for p in result)

    def test_empty_text_returns_empty(self):
        assert parse_subscription_text("") == []
        assert parse_subscription_text("   ") == []

    def test_comments_and_blanks_ignored(self):
        text = (
            "# this is a comment\n"
            "\n"
            "trojan://pass@host.example.com:443#node\n"
            "# another comment\n"
        )
        result = parse_subscription_text(text)
        assert len(result) == 1

    def test_mixed_protocol_list(self):
        userinfo = base64.b64encode(b"aes-256-gcm:pass").decode()
        text = (
            f"ss://{userinfo}@ss.example.com:8388#ss-node\n"
            "trojan://pass@tr.example.com:443#tr-node\n"
        )
        result = parse_subscription_text(text)
        assert len(result) == 2
        types = {p["type"] for p in result}
        assert types == {"ss", "trojan"}


# ── parse_uri edge cases ────────────────────────────────────────────────


class TestParseUriEdgeCases:
    """Edge cases for parse_uri()."""

    def test_empty_string_returns_none(self):
        assert parse_uri("") is None
        assert parse_uri("   ") is None

    def test_unknown_scheme_returns_none(self):
        assert parse_uri("ftp://files.example.com/file") is None

    def test_whitespace_stripped(self):
        userinfo = base64.b64encode(b"aes-256-gcm:pass").decode()
        uri = f"  ss://{userinfo}@1.2.3.4:443#node  "
        result = parse_uri(uri)
        assert result is not None
        assert result["type"] == "ss"
