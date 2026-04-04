import json
import os
import re

import requests

from dailycheckin import CheckIn


class AnyRouter(CheckIn):
    name = "AnyRouter"
    _xor_key = "3000176000856006061501533003690027800375"
    _unsbox_order = [
        0xF,
        0x23,
        0x1D,
        0x18,
        0x21,
        0x10,
        0x1,
        0x26,
        0xA,
        0x9,
        0x13,
        0x1F,
        0x28,
        0x1B,
        0x16,
        0x17,
        0x19,
        0xD,
        0x6,
        0xB,
        0x27,
        0x12,
        0x14,
        0x8,
        0xE,
        0x15,
        0x20,
        0x1A,
        0x2,
        0x1E,
        0x7,
        0x4,
        0x5,
        0x3,
        0x11,
        0x24,
        0x0,
        0x22,
        0x25,
        0xC,
    ]

    def __init__(self, check_item):
        self.check_item = check_item

    @staticmethod
    def _parse_cookie(cookie_str):
        cookies = {}
        for item in cookie_str.split(";"):
            item = item.strip()
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            cookies[key.strip()] = value.strip()
        return cookies

    @classmethod
    def _unsbox(cls, arg1):
        result = [""] * len(cls._unsbox_order)
        for idx, char in enumerate(arg1):
            if idx >= len(cls._unsbox_order):
                break
            result[cls._unsbox_order[idx]] = char
        return "".join(result)

    @classmethod
    def _hex_xor(cls, a, b):
        out = []
        max_len = min(len(a), len(b))
        for i in range(0, max_len, 2):
            out.append(f"{int(a[i:i + 2], 16) ^ int(b[i:i + 2], 16):02x}")
        return "".join(out)

    @classmethod
    def _build_acw_sc_v2(cls, html):
        match = re.search(r"arg1='([0-9A-F]+)'", html or "")
        if not match:
            return ""
        arg1 = match.group(1)
        return cls._hex_xor(cls._unsbox(arg1), cls._xor_key)

    @classmethod
    def _is_challenge_page(cls, text):
        return bool(text) and text.lstrip().startswith("<html") and "arg1='" in text

    @classmethod
    def sign(cls, session, user_id):
        url = "https://anyrouter.top/api/user/sign_in"
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cache-control": "no-store",
            "content-length": "0",
            "new-api-user": str(user_id),
            "origin": "https://anyrouter.top",
            "referer": "https://anyrouter.top/console",
            "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
        }

        response = session.post(url=url, headers=headers, timeout=30)
        body = response.text or ""
        retried = "否"

        if cls._is_challenge_page(body):
            acw_sc_v2 = cls._build_acw_sc_v2(body)
            if acw_sc_v2:
                session.cookies.set("acw_sc__v2", acw_sc_v2, domain="anyrouter.top")
                response = session.post(url=url, headers=headers, timeout=30)
                body = response.text or ""
                retried = "是"

        request_id = response.headers.get("x-oneapi-request-id", "")
        status_code = response.status_code
        msg = [
            {"name": "请求状态码", "value": status_code},
            {"name": "挑战页重试", "value": retried},
            {"name": "请求ID", "value": request_id or "无"},
        ]

        try:
            data = response.json()
            success = bool(data.get("success"))
            detail = data.get("message", "") or "无"
            msg += [
                {"name": "签到结果", "value": "成功" if success else "失败"},
                {"name": "返回信息", "value": detail},
            ]
        except Exception:
            msg += [
                {"name": "签到结果", "value": "失败"},
                {"name": "返回信息", "value": "响应不是 JSON"},
            ]
        return msg

    def main(self):
        cookie = self.check_item.get("cookie", "")
        user_id = self.check_item.get("user_id", "")
        if not cookie or not user_id:
            msg = [
                {"name": "帐号信息", "value": "配置错误"},
                {"name": "签到结果", "value": "缺少 cookie 或 user_id"},
            ]
            return "\n".join([f"{one.get('name')}: {one.get('value')}" for one in msg])

        session = requests.session()
        requests.utils.add_dict_to_cookiejar(session.cookies, self._parse_cookie(cookie))
        msg = self.sign(session=session, user_id=user_id)
        return "\n".join([f"{one.get('name')}: {one.get('value')}" for one in msg])


if __name__ == "__main__":
    with open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json"),
        encoding="utf-8",
    ) as f:
        datas = json.loads(f.read())
    _check_item = datas.get("ANYROUTER", [])[0]
    print(AnyRouter(check_item=_check_item).main())
