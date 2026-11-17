import json
import os
from dataclasses import dataclass

# 以脚本所在目录为基准，保证从任意目录启动都能找到配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@dataclass
class NanoClawConfig:
    """NanoClaw 运行配置"""
    token_budget: int = 6000
    max_tokens: int = 4000
    consolidation_threshold: int = 8000
    api_key: str = ""  # 从 config.json 或环境变量 NANOCLAW_API_KEY 注入
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    workspace: str = BASE_DIR
    max_iterations: int = 32
    qq_app_id: str = ""  # 从 config.json 或环境变量 QQ_APP_ID 注入
    qq_app_secret: str = ""  # 从 config.json 或环境变量 QQ_APP_SECRET 注入
    feishu_app_id: str = ""  # 从 config.json 或环境变量 FEISHU_APP_ID 注入
    feishu_app_secret: str = ""  # 从 config.json 或环境变量 FEISHU_APP_SECRET 注入
    identity_file: str = "identity.md"
    mcp_servers: dict = None  # MCP 服务器配置，默认无，见 config.json

def load_config(config_path: str = "") -> NanoClawConfig:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径（JSON 格式），默认取脚本目录下的 config.json

    Returns:
        NanoClawConfig: 配置对象
    """
    config = NanoClawConfig()

    # 默认配置路径固定在脚本目录，不受启动目录影响
    if not config_path:
        config_path = os.path.join(BASE_DIR, "config.json")

    # 读取 JSON 文件
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                # 新增参数的解析
                if "token_budget" in data:
                    config.token_budget = int(data["token_budget"])
                if "max_tokens" in data:
                    config.max_tokens = int(data["max_tokens"])
                if "consolidation_threshold" in data:
                    config.consolidation_threshold = int(data["consolidation_threshold"])

                if "qq_app_id" in data:
                    config.qq_app_id = data["qq_app_id"]
                if "qq_app_secret" in data:
                    config.qq_app_secret = data["qq_app_secret"]
                if "feishu_app_id" in data:
                    config.feishu_app_id = data["feishu_app_id"]
                if "feishu_app_secret" in data:
                    config.feishu_app_secret = data["feishu_app_secret"]
                if "mcp_servers" in data and isinstance(data["mcp_servers"], dict):
                    config.mcp_servers = data["mcp_servers"]
                for key in ["api_key", "base_url", "model", "workspace", "max_iterations", "identity_file"]:
                    if key in data:
                        setattr(config, key, data[key])
        except FileNotFoundError:
            pass

    # 相对路径的 workspace 一律以脚本目录为基准解析
    if not os.path.isabs(config.workspace):
        config.workspace = os.path.abspath(os.path.join(BASE_DIR, config.workspace))

    # 环境变量优先级最高
    if env_key := os.environ.get("NANOCLAW_API_KEY"):
        config.api_key = env_key
    if env_id := os.environ.get("QQ_APP_ID"):
        config.qq_app_id = env_id
    if env_secret := os.environ.get("QQ_APP_SECRET"):
        config.qq_app_secret = env_secret
    if env_fid := os.environ.get("FEISHU_APP_ID"):
        config.feishu_app_id = env_fid
    if env_fsecret := os.environ.get("FEISHU_APP_SECRET"):
        config.feishu_app_secret = env_fsecret

    return config