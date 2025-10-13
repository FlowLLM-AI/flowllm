# 🔧 安装指南

## 系统要求

### 最低要求
- **操作系统**: macOS 10.13+ / Windows 10+ / Linux (Ubuntu 18.04+)
- **Node.js**: 18.0 或更高版本
- **npm**: 8.0 或更高版本
- **内存**: 4GB RAM
- **磁盘空间**: 500MB 可用空间

### 推荐配置
- **操作系统**: macOS 13+ / Windows 11 / Linux (最新 LTS)
- **Node.js**: 20.0+ LTS
- **npm**: 10.0+
- **内存**: 8GB+ RAM
- **磁盘空间**: 1GB 可用空间

## 安装步骤

### 1. 安装 Node.js

#### macOS
```bash
# 使用 Homebrew
brew install node

# 或下载安装包
# https://nodejs.org/
```

#### Windows
```bash
# 下载安装包
# https://nodejs.org/

# 或使用 Chocolatey
choco install nodejs
```

#### Linux
```bash
# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Fedora
sudo dnf install nodejs

# Arch
sudo pacman -S nodejs npm
```

### 2. 验证安装

```bash
node --version  # 应该显示 v18.0.0 或更高
npm --version   # 应该显示 8.0.0 或更高
```

### 3. 克隆或下载项目

```bash
# 如果从 Git 克隆
git clone <repository-url>
cd desktop-dog

# 或直接下载 ZIP 并解压
cd desktop-dog
```

### 4. 安装依赖

```bash
npm install
```

这会安装所有必要的依赖包，可能需要几分钟时间。

### 5. 配置 API (可选但推荐)

编辑 `src/services/llmService.ts`:

```typescript
const API_KEY = 'your-api-key-here';
const API_BASE = 'https://api.openai.com/v1';
const MODEL = 'gpt-4';
```

支持的 API 提供商：
- **OpenAI**: GPT-3.5, GPT-4
- **Alibaba Cloud**: Qwen (通义千问)
- **Anthropic**: Claude (需要代理)
- **本地**: Ollama, LocalAI

### 6. 运行应用

#### 开发模式
```bash
npm run dev
```

#### 生产模式
```bash
npm run build
npm start
```

## 常见问题

### Q1: npm install 失败

**问题**: 依赖安装失败或超时

**解决方案**:
```bash
# 清除 npm 缓存
npm cache clean --force

# 使用国内镜像 (中国用户)
npm config set registry https://registry.npmmirror.com

# 重新安装
rm -rf node_modules package-lock.json
npm install
```

### Q2: Electron 下载失败

**问题**: Electron 二进制文件下载失败

**解决方案**:
```bash
# 设置 Electron 镜像
export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"

# 重新安装
npm install electron
```

### Q3: TypeScript 编译错误

**问题**: TypeScript 编译失败

**解决方案**:
```bash
# 确保 TypeScript 正确安装
npm install -D typescript@latest

# 清除构建缓存
rm -rf dist/
npm run build:electron
```

### Q4: Vite 启动失败

**问题**: Vite 开发服务器无法启动

**解决方案**:
```bash
# 检查端口 3000 是否被占用
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows

# 修改端口 (vite.config.ts)
server: {
  port: 3001  // 改为其他端口
}
```

### Q5: 应用无法启动

**问题**: npm run dev 后应用不显示

**解决方案**:
```bash
# 检查构建输出
npm run build:electron

# 检查是否有错误日志
# 查看终端输出

# 尝试完全重建
rm -rf node_modules dist
npm install
npm run dev
```

## 平台特定问题

### macOS

#### 权限问题
```bash
# 如果遇到权限错误
sudo chown -R $(whoami) ~/desktop-dog
```

#### M1/M2 芯片兼容性
```bash
# 如果遇到架构问题
arch -x86_64 npm install
```

### Windows

#### 路径长度限制
```bash
# 启用长路径支持 (管理员权限)
git config --system core.longpaths true
```

#### PowerShell 执行策略
```powershell
# 允许脚本执行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Linux

#### 依赖问题
```bash
# Ubuntu/Debian
sudo apt-get install -y libgtk-3-0 libnotify4 libnss3 libxss1 libxtst6 xdg-utils

# Fedora
sudo dnf install gtk3 libnotify nss libXScrnSaver libXtst xdg-utils

# Arch
sudo pacman -S gtk3 libnotify nss libxss libxtst xdg-utils
```

## 打包为独立应用

### macOS (DMG)
```bash
npm run build:mac
# 输出: release/Desktop Dog-1.0.0.dmg
```

### Windows (EXE)
```bash
npm run build:win
# 输出: release/Desktop Dog Setup 1.0.0.exe
```

### Linux (AppImage)
```bash
npm run build:linux
# 输出: release/Desktop Dog-1.0.0.AppImage
```

## 卸载

### 删除应用
```bash
# 删除项目文件
cd ..
rm -rf desktop-dog
```

### 清理全局缓存
```bash
# 清理 npm 缓存
npm cache clean --force

# 清理 Electron 缓存
rm -rf ~/.cache/electron
```

### 删除已安装的应用

#### macOS
```bash
# 拖动到废纸篓或
rm -rf "/Applications/Desktop Dog.app"
```

#### Windows
```
控制面板 → 程序和功能 → 卸载 Desktop Dog
```

#### Linux
```bash
rm -rf ~/Desktop\ Dog-1.0.0.AppImage
```

## 升级

### 升级依赖
```bash
# 检查过时的包
npm outdated

# 升级所有依赖
npm update

# 升级到最新版本
npm install <package>@latest
```

### 升级到新版本
```bash
# 拉取最新代码
git pull origin main

# 重新安装依赖
npm install

# 重新构建
npm run build
```

## 开发环境设置

### 推荐的 IDE
- **VS Code** (推荐)
  - 安装扩展: ESLint, Prettier, TypeScript
  - 配置自动格式化
  
- **WebStorm**
  - 内置 TypeScript 支持
  - 配置 Node.js 解释器

### VS Code 配置

创建 `.vscode/settings.json`:
```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "typescript.tsdk": "node_modules/typescript/lib"
}
```

### 推荐的 npm 脚本
```bash
# 开发
npm run dev           # 启动开发模式

# 构建
npm run build         # 构建所有
npm run build:electron # 只构建 Electron
npm run build:mac     # 构建 macOS 应用
npm run build:win     # 构建 Windows 应用
npm run build:linux   # 构建 Linux 应用

# 运行
npm start             # 运行已构建的应用
```

## 获取帮助

如果遇到问题：

1. 查看 [常见问题](#常见问题)
2. 阅读 [项目文档](./README.md)
3. 搜索已有的 Issues
4. 创建新的 Issue 并提供:
   - 操作系统和版本
   - Node.js 和 npm 版本
   - 错误信息和日志
   - 重现步骤

## 下一步

安装完成后，请阅读：
- [快速开始指南](./QUICKSTART.md)
- [使用示例](./USAGE_EXAMPLES.md)
- [功能详解](./FEATURES.md)

祝你使用愉快！🐕✨

