# GitHub 推送指南

## 📋 完整步骤

### 第一步：检查 Git 状态

```bash
cd binance_bot
git status
```

### 第二步：初始化 Git 仓库（如果还没有）

如果还没有初始化 Git 仓库：

```bash
git init
```

### 第三步：配置 Git（如果还没有配置）

```bash
# 设置用户名（替换为你的 GitHub 用户名）
git config user.name "你的用户名"

# 设置邮箱（替换为你的 GitHub 邮箱）
git config user.email "your.email@example.com"

# 或者全局配置（所有项目都使用）
git config --global user.name "你的用户名"
git config --global user.email "your.email@example.com"
```

### 第四步：添加文件到暂存区

```bash
# 添加所有文件（.gitignore 会自动排除不需要的文件）
git add .

# 或者只添加特定文件
git add README.md
git add core/
git add strategies/
# ...
```

### 第五步：提交更改

```bash
git commit -m "Initial commit: Binance Bot - 币安合约交易机器人"
```

### 第六步：在 GitHub 创建仓库

1. 登录 GitHub
2. 点击右上角的 **+** 号，选择 **New repository**
3. 填写仓库信息：
   - **Repository name**: `binance-bot`（或你喜欢的名字）
   - **Description**: `币安合约交易机器人 - Binance Futures Trading Bot`
   - **Visibility**: 选择 Public（公开）或 Private（私有）
   - **不要**勾选 "Initialize this repository with a README"（因为我们已经有了）
4. 点击 **Create repository**

### 第七步：添加远程仓库并推送

GitHub 创建仓库后会显示命令，通常是这样：

```bash
# 添加远程仓库（替换 YOUR_USERNAME 和 YOUR_REPO_NAME）
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 或者使用 SSH（如果你配置了 SSH key）
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git

# 推送代码到 GitHub
git branch -M main
git push -u origin main
```

### 完整命令示例

假设你的 GitHub 用户名是 `albert`，仓库名是 `binance-bot`：

```bash
# 1. 进入项目目录
cd binance_bot

# 2. 初始化（如果还没有）
git init

# 3. 添加所有文件
git add .

# 4. 提交
git commit -m "Initial commit: Binance Bot - 币安合约交易机器人"

# 5. 添加远程仓库
git remote add origin https://github.com/albert/binance-bot.git

# 6. 推送到 GitHub
git branch -M main
git push -u origin main
```

## 🔐 身份验证

### 方法1：使用 Personal Access Token（推荐）

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. 点击 **Generate new token (classic)**
3. 设置权限：至少勾选 `repo`
4. 生成后**复制 token**（只显示一次！）
5. 推送时使用 token 作为密码：

```bash
# 用户名：你的 GitHub 用户名
# 密码：粘贴你的 token
git push -u origin main
```

### 方法2：使用 SSH Key

1. 生成 SSH key：
```bash
ssh-keygen -t ed25519 -C "your.email@example.com"
```

2. 复制公钥：
```bash
# Windows
type %USERPROFILE%\.ssh\id_ed25519.pub

# Linux/Mac
cat ~/.ssh/id_ed25519.pub
```

3. 添加到 GitHub：
   - GitHub → Settings → SSH and GPG keys → New SSH key
   - 粘贴公钥内容

4. 使用 SSH URL：
```bash
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git
```

## ⚠️ 重要提示

### 确保 .env 文件不被提交

`.gitignore` 已经包含了 `.env`，但请确认：

```bash
# 检查 .env 是否会被提交
git check-ignore .env
# 如果输出 .env，说明已被忽略 ✅
```

### 如果 .env 已经被跟踪

如果之前已经提交了 `.env`，需要移除：

```bash
# 从 Git 中移除但保留本地文件
git rm --cached .env
git commit -m "Remove .env from repository"
git push
```

## 📝 后续更新

以后更新代码时：

```bash
# 1. 查看更改
git status

# 2. 添加更改的文件
git add .

# 3. 提交
git commit -m "描述你的更改"

# 4. 推送
git push
```

## 🐛 常见问题

### 问题1：推送被拒绝

**错误**: `error: failed to push some refs`

**解决**:
```bash
# 先拉取远程更改
git pull origin main --rebase

# 然后再推送
git push -u origin main
```

### 问题2：需要输入用户名密码

**解决**: 使用 Personal Access Token 作为密码

### 问题3：.env 文件被提交了

**解决**:
```bash
# 从 Git 历史中移除
git rm --cached .env
git commit -m "Remove .env"
git push

# 如果已经推送，需要从历史中完全删除（谨慎使用）
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch .env" --prune-empty --tag-name-filter cat -- --all
git push origin --force --all
```

## ✅ 检查清单

推送前确认：

- [ ] `.env` 文件在 `.gitignore` 中
- [ ] 没有硬编码的 API Key
- [ ] README.md 已更新
- [ ] 代码可以正常运行
- [ ] 已提交所有需要的文件

## 🎉 完成！

推送成功后，你可以在 GitHub 上看到你的代码了！

访问：`https://github.com/YOUR_USERNAME/YOUR_REPO_NAME`
