---
name: "python-project-init"
description: "初始化一个 Python 项目：创建目录结构、生成基础文件（README/requirements/.gitignore）、执行 git init 和创建虚拟环境。当用户要求创建/初始化一个新 Python 项目时调用本技能。"
---

# Python 项目初始化技能

本技能指导完成一个全新 Python 项目的完整初始化：从目录骨架、基础文件到 Git 仓库与虚拟环境，一步到位。适合用户说"帮我初始化一个 Python 项目"、"新建一个项目"、"开始一个新工程"等场景。

## 使用时机

用户出现以下意图时调用本技能：

- "帮我初始化一个 Python 项目"
- "新建 / 创建一个 Python 工程"
- "搭一个项目的架子 / 骨架"
- 需要新建项目并准备 git 和虚拟环境

## 初始化步骤

以下所有操作都在新建的**项目目录**内执行。若用户未指定目录，先明确项目名并确认目标路径。

### 1. 确认目标路径

- 若用户未给出项目名/路径，先询问或使用一个合理的默认名（如 `my_project`）。
- 创建项目根目录：`mkdir <项目目录>`（通过 exec）。

### 2. 创建目录结构

通过 exec 执行 `mkdir -p`（Windows 用 `mkdir`，注意兼容）创建：

```
<项目目录>/
├── src/
├── tests/
└── docs/
```

可用命令示例：`mkdir -p src tests docs`（若环境是 Windows cmd/PowerShell，用 `mkdir src tests docs`）。

### 3. 生成基础文件（使用 write_file 工具）

用 `write_file` 依次写入以下文件，UTF-8 编码：

**README.md**
```markdown
# <项目名>

项目描述：待补充。

## 安装

```bash
pip install -r requirements.txt
```

## 使用

待补充。
```

**requirements.txt**
```
# 在这里添加项目依赖，例如：
# requests>=2.31
```

**.gitignore**
```
# Python
__pycache__/
*.py[cod]
.venv/
venv/
.env
dist/
build/
*.egg-info/
```

### 4. 初始化 Git 仓库

通过 exec 在项目目录内执行：`git init`

（若该目录本就在一个已存在的 git 仓库内会导致嵌套，先检查 `.git` 是否存在；存在则跳过并说明。）

### 5. 创建虚拟环境

通过 exec 在项目目录内执行：`python -m venv .venv`

- 若系统名不是 `python`（如 `python3`），改用对应的命令。
- 创建成功后提示用户激活方式：Windows 为 `.venv\Scripts\activate`，Unix 为 `source .venv/bin/activate`。

## 输出格式

- 每个步骤完成后用简洁文字汇报结果（创建了哪些目录/文件/仓库/环境）。
- 全部完成后，**在末尾另起一行标注本次使用的技能名称**，格式固定为：`> 本报告由技能 python-project-init 生成`

## 输出示例

```
✅ 已创建项目目录 my_project（含 src/ tests/ docs/）
✅ 已写入 README.md、requirements.txt、.gitignore
✅ 已执行 git init
✅ 已创建虚拟环境 .venv

> 本报告由技能 python-project-init 生成
```

## 注意事项

- 所有操作严格限定在新建项目目录内，不要改动其他位置的文件。
- exec 存在危险命令拦截：避免使用 `rm -rf`、重定向到 `/dev/`、`sudo` 等被拦截的写法。
- 如果某个 exec 命令因环境差异失败，可换用等价的兼容命令（如 `mkdir` 与 `mkdir -p`、`python` 与 `python3`）重试。