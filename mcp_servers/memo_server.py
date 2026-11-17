"""备忘录 MCP Server。

提供 add_memo / list_memos / search_memo 三个工具。
数据保存在本地 JSON 文件（output/memos.json），重启不丢失。
"""

import json
import os
import time

from mcp.server.fastmcp import FastMCP

# 数据文件：相对本文件定位到 CLAW/output/memos.json
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MEMO_FILE = os.path.join(_BASE_DIR, "output", "memos.json")


def _load_memos() -> list[dict]:
    """从磁盘加载备忘录。"""
    try:
        with open(_MEMO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save_memos(memos: list[dict]) -> None:
    """把备忘录写回磁盘。"""
    os.makedirs(os.path.dirname(_MEMO_FILE), exist_ok=True)
    with open(_MEMO_FILE, "w", encoding="utf-8") as f:
        json.dump(memos, f, ensure_ascii=False, indent=2)


# 创建 FastMCP 实例
mcp = FastMCP("memo-server")


@mcp.tool()
def add_memo(content: str) -> str:
    """新增一条备忘录。

    Args:
        content: 备忘录内容，不能为空

    Returns:
        新增成功后的备忘录编号与内容
    """
    if not content or not content.strip():
        return "请提供备忘录内容，不能为空"

    memos = _load_memos()
    memo = {
        "id": len(memos) + 1,
        "content": content.strip(),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    memos.append(memo)
    _save_memos(memos)
    return f"已添加备忘录 #{memo['id']}：{memo['content']}"


@mcp.tool()
def list_memos() -> str:
    """列出所有备忘录。

    Returns:
        全部备忘录（按编号、时间、内容展示），或空列表提示
    """
    memos = _load_memos()
    if not memos:
        return "暂无备忘录"

    lines = [f"共有 {len(memos)} 条备忘录："]
    for memo in memos:
        lines.append(f"#{memo['id']} [{memo['created_at']}] {memo['content']}")
    return "\n".join(lines)


@mcp.tool()
def search_memo(keyword: str) -> str:
    """按关键词搜索备忘录。

    在备忘录内容中模糊匹配包含关键词的记录。

    Args:
        keyword: 搜索关键词

    Returns:
        匹配的备忘录列表，或未找到提示
    """
    if not keyword or not keyword.strip():
        return "请提供搜索关键词"

    keyword = keyword.strip().lower()
    results = [
        memo
        for memo in _load_memos()
        if keyword in memo["content"].lower()
    ]

    if not results:
        return "未找到包含该关键词的备忘录"

    lines = [f"找到 {len(results)} 条匹配结果："]
    for memo in results:
        lines.append(f"#{memo['id']} [{memo['created_at']}] {memo['content']}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")