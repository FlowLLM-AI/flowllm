# 🐕 Desktop Dog - 桌面小狗宠物

一个可爱的桌面小狗宠物应用，支持AI对话功能。使用 Electron + React + TypeScript 开发。

## ✨ 功能特性

- 🎨 **可爱的小狗形象** - 手绘风格的小狗，带有多种表情
- 🖱️ **可拖拽** - 鼠标拖拽移动小狗位置
- 💬 **AI对话** - 点击小狗弹出对话框，支持流式AI对话
- 🏃 **跑步动画** - 双击小狗让它在屏幕上跑来跑去
- 📌 **置顶显示** - 始终显示在其他窗口之上
- 🎯 **右键菜单** - 提供快捷操作菜单

## 🎮 操作方式

- **左键点击** - 打开对话窗口
- **左键双击** - 开始/停止跑步
- **拖拽** - 移动小狗位置
- **右键点击** - 打开功能菜单

## 🚀 快速开始

### 安装依赖

```bash
npm install
```

### 配置 API

1. 复制环境变量示例文件：

```bash
cp env.example .env
```

2. 编辑 `.env` 文件，填入你的 API 配置：

```bash
# API Key for LLM service
VITE_API_KEY=sk-your-actual-api-key-here

# Base URL for the API endpoint
VITE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# Model name to use
VITE_MODEL=qwen-max
```

**注意：** `.env` 文件包含敏感信息，已添加到 `.gitignore`，不会被提交到版本控制。

### 开发模式运行

```bash
npm run dev
```

这会同时启动 Vite 开发服务器和 Electron 应用。

### 打包应用

```bash
# macOS
npm run build:mac

# Windows
npm run build:win

# Linux
npm run build:linux
```

## 📁 项目结构

```
desktop-dog/
├── electron/           # Electron 主进程代码
│   └── main.ts        # 主进程入口
├── src/               # React 应用代码
│   ├── components/    # React 组件
│   │   ├── DesktopDog.tsx      # 主宠物组件
│   │   ├── ChatBubble.tsx      # 对话气泡
│   │   ├── ResponseBubble.tsx  # AI回答气泡
│   │   └── ContextMenu.tsx     # 右键菜单
│   ├── services/      # 服务层
│   │   └── llmService.ts       # LLM API 集成
│   ├── App.tsx        # 应用主组件
│   └── main.tsx       # React 入口
├── package.json       # 项目配置
├── tsconfig.json      # TypeScript 配置
└── vite.config.ts     # Vite 配置
```

## 🎨 自定义

### 修改小狗外观

编辑 `src/components/DesktopDog.tsx` 中的 `DogSVG` 组件，修改 SVG 路径和颜色。

### 修改对话样式

编辑相应的 CSS 文件：
- `ChatBubble.css` - 对话输入框样式
- `ResponseBubble.css` - AI回答气泡样式

### 切换 AI 模型

编辑 `src/services/llmService.ts`，修改 API 配置和模型名称。支持任何兼容 OpenAI API 格式的服务。

## 🔧 技术栈

- **Electron** - 跨平台桌面应用框架
- **React** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 快速构建工具
- **CSS3** - 样式和动画

## 📝 与 Python 版本的对比

这是 `todo_files/desktop_pet.py` 的 TypeScript 重写版本，主要差异：

- ✅ 使用 Electron 替代 PyQt6，更容易跨平台部署
- ✅ 使用 React 组件化开发，代码更易维护
- ✅ 使用 TypeScript 提供类型安全
- ✅ 保留了所有核心功能：拖拽、对话、跑步、右键菜单
- ✅ 改进了 UI 样式，使用 CSS3 动画
- ✅ 小狗替代小猫，SVG绘制更简洁

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 License

MIT License

