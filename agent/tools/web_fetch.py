"""网页抓取工具模块"""

import re
from urllib.parse import urlparse

import httpx
import html2text

from agent.tools.base import Tool

class WebFetchTool(Tool):
    """网页抓取工具

    抓取指定 URL 的网页内容，转换成纯文本返回。
    """

    MAX_OUTPUT_LENGTH = 12000  # 输出最大字符数
    TIMEOUT = 15  # 请求超时秒数
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "抓取指定 URL 的网页内容。"
            "当你需要阅读某个具体网页的详细内容时使用。"
            "通常配合 web_search 工具先搜索再抓取。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页 URL"
                }
            },
            "required": ["url"]
        }

    async def execute(self, **kwargs) -> str:
        """执行网页抓取

        Args:
            url: 要抓取的网页 URL

        Returns:
            str: 网页内容或错误信息
        """
        url = kwargs.get("url", "")

        if not url or not isinstance(url, str):
            return "抓取失败：URL 不能为空"

        # 1. URL 安全检查
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return "安全拦截：只允许 http/https 协议"
            if not parsed.netloc:
                return "抓取失败：URL 格式无效"
        except Exception as e:
            return f"抓取失败：URL 解析错误 - {str(e)}"

        # 2. 发送 HTTP GET 请求
        try:
            async with httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": self.USER_AGENT}
            ) as client:
                response = await client.get(url)

                if not (200 <= response.status_code < 300):
                    return f"抓取失败：HTTP {response.status_code}"

                html_content = response.text

        except httpx.TimeoutException:
            return "抓取失败：请求超时"
        except httpx.NetworkError as e:
            return f"抓取失败：网络错误 - {str(e)}"
        except httpx.HTTPStatusError as e:
            return f"抓取失败：HTTP 状态错误 - {str(e)}"
        except Exception as e:
            return f"抓取失败：{str(e)}"

        # 3. HTML 转换为纯文本
        try:
            h = html2text.HTML2Text()
            h.ignore_links = False  # 保留链接
            h.ignore_images = True  # 忽略图片
            h.body_width = 0  # 不自动换行

            text_content = h.handle(html_content)

        except Exception as e:
            return f"内容转换失败：{str(e)}"

        # 4. 清理输出
        # 去除连续多个空行
        text_content = re.sub(r"\n{3,}", "\n\n", text_content)

        # 去除首尾空白
        text_content = text_content.strip()

        # 截断过长内容
        if len(text_content) > self.MAX_OUTPUT_LENGTH:
            text_content = text_content[:self.MAX_OUTPUT_LENGTH] + "\n...(内容过长，已截断)"

        return text_content