"""
钉钉机器人推送模块
支持文本消息和 Markdown 消息推送
"""
import hashlib
import hmac
import base64
import time
import urllib.parse
import urllib.request
import json
from typing import Optional, Dict, Any


class DingTalkNotifier:
    """
    钉钉机器人通知器

    使用方法：
        notifier = DingTalkNotifier(webhook_url, secret)
        notifier.send_text("测试消息")
        notifier.send_markdown("标题", "## 内容")
    """

    def __init__(self, webhook_url: str, secret: str = ""):
        """
        初始化钉钉通知器

        Args:
            webhook_url: 钉钉机器人 Webhook 地址
            secret: 加签密钥（可选，用于安全验证）
        """
        self.webhook_url = webhook_url
        self.secret = secret

    def _generate_sign(self, timestamp: int) -> str:
        """生成签名"""
        if not self.secret:
            return ""

        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return sign

    def _build_url(self) -> str:
        """构建带签名的完整 URL"""
        if not self.secret:
            return self.webhook_url

        timestamp = int(time.time() * 1000)
        sign = self._generate_sign(timestamp)
        return f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"

    def _send_request(self, data: Dict[str, Any]) -> bool:
        """发送 HTTP 请求"""
        url = self._build_url()
        headers = {"Content-Type": "application/json;charset=utf-8"}
        body = json.dumps(data).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("errcode") == 0
        except Exception as e:
            print(f"[DingTalk] 发送失败: {e}")
            return False

    def send_text(self, content: str, at_all: bool = False) -> bool:
        """
        发送文本消息

        Args:
            content: 文本内容
            at_all: 是否 @所有人

        Returns:
            是否发送成功
        """
        data = {
            "msgtype": "text",
            "text": {"content": content},
            "at": {"isAtAll": at_all}
        }
        return self._send_request(data)

    def send_markdown(self, title: str, content: str, at_all: bool = False) -> bool:
        """
        发送 Markdown 消息

        Args:
            title: 消息标题
            content: Markdown 格式内容
            at_all: 是否 @所有人

        Returns:
            是否发送成功
        """
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
            },
            "at": {"isAtAll": at_all}
        }
        return self._send_request(data)

    def send_signal_alert(self, symbol: str, price: float, drop_pct: float,
                          volume_ratio: float, pump_days: int,
                          position_advice: str, at_all: bool = True) -> bool:
        """
        发送做空信号警报（15分钟暴跌）

        Args:
            symbol: 交易对
            price: 当前价格
            drop_pct: 跌幅百分比
            volume_ratio: 放量倍数
            pump_days: 霸榜天数
            position_advice: 仓位建议
            at_all: 是否 @所有人

        Returns:
            是否发送成功
        """
        title = f"⚠️ 15分钟暴跌信号 - {symbol}"
        content = f"""## ⚠️ 15分钟暴跌信号

**币种**: {symbol}
**当前价格**: {price:.6f}
**跌幅**: {drop_pct:.2%}
**放量倍数**: {volume_ratio:.1f}x
**霸榜天数**: {pump_days} 天

---

### 📊 操作建议

**建议仓位**: {position_advice}

{"**可考虑建立头仓**" if drop_pct >= 0.05 else "**持续观察**"}

---
*时间: {time.strftime('%Y-%m-%d %H:%M:%S')}*
"""
        return self.send_markdown(title, content, at_all)

    def send_daily_report(self, report_summary: str, top_symbols: list,
                          at_all: bool = False) -> bool:
        """
        发送每日报告摘要

        Args:
            report_summary: 报告摘要
            top_symbols: 关注币种列表
            at_all: 是否 @所有人

        Returns:
            是否发送成功
        """
        title = f"📊 山寨币做空信号报告 - {time.strftime('%Y-%m-%d %H:%M')}"

        symbols_text = "\n".join([
            f"- **{s['symbol']}** | 霸榜 {s['pump_days']} 天 | 评分 {s['score']:.2f} | 建议 {s['position_advice']}"
            for s in top_symbols[:5]  # 只显示前5个
        ])

        content = f"""## 📊 山寨币做空信号报告

**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}

---

### 🎯 重点关注

{symbols_text}

---

{report_summary}

---
*完整报告已保存到 reports/ 目录*
"""
        return self.send_markdown(title, content, at_all)


# 便捷函数
_notifier: Optional[DingTalkNotifier] = None


def init_notifier(webhook_url: str, secret: str = "") -> DingTalkNotifier:
    """初始化全局通知器"""
    global _notifier
    _notifier = DingTalkNotifier(webhook_url, secret)
    return _notifier


def get_notifier() -> Optional[DingTalkNotifier]:
    """获取全局通知器"""
    return _notifier
