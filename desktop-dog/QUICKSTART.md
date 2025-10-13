# 🚀 快速启动指南

## 📋 前置要求

- Node.js 18+ 
- npm 或 yarn

## 🔧 安装步骤

### 1. 安装依赖

```bash
cd desktop-dog
npm install
```

### 2. 配置 API (可选)

如果你想使用自己的 AI API，编辑 `src/services/llmService.ts`:

```typescript
const API_KEY = 'your-api-key';
const API_BASE = 'https://api.openai.com/v1';
const MODEL = 'gpt-4';
```

默认配置使用阿里云 DashScope API。

### 3. 运行应用

```bash
npm run dev
```

这会启动开发服务器和 Electron 应用窗口。

## 🎮 使用方式

### 基本操作

1. **移动小狗** - 鼠标拖拽小狗到任意位置
2. **打开对话** - 单击小狗，弹出对话框
3. **开始跑步** - 双击小狗，它会在屏幕上跑来跑去
4. **停止跑步** - 再次双击小狗
5. **更多功能** - 右键点击小狗打开菜单

### 对话功能

1. 点击小狗打开对话框
2. 输入你的问题
3. 按回车发送（Shift+回车换行）
4. AI 会流式返回回答
5. 点击 ✕ 关闭对话框

### 右键菜单

- 💬 和我聊天 - 打开对话框
- 🏠 回到角落 - 移动到屏幕右下角
- 🚶 随机漫步 - 随机移动到某个位置
- 🏃 开始跑步 / 🛑 停止跑步 - 切换跑步状态
- 👋 再见~ - 退出应用

## 🏗️ 构建可执行文件

### macOS

```bash
npm run build:mac
```

应用会生成在 `release/` 目录。

### Windows

```bash
npm run build:win
```

### Linux

```bash
npm run build:linux
```

## ⚙️ 高级配置

### 修改小狗外观

编辑 `src/components/DesktopDog.tsx` 中的 `DogSVG` 组件。

### 修改窗口设置

编辑 `electron/main.ts` 中的窗口配置：

```typescript
mainWindow = new BrowserWindow({
  width: 150,        // 窗口宽度
  height: 180,       // 窗口高度
  transparent: true, // 透明背景
  alwaysOnTop: true, // 始终置顶
  // ... 更多选项
});
```

### 使用其他 AI 模型

支持任何兼容 OpenAI API 格式的服务：

```typescript
// OpenAI
const API_BASE = 'https://api.openai.com/v1';
const MODEL = 'gpt-4';

// Anthropic (通过代理)
const API_BASE = 'https://your-proxy/v1';
const MODEL = 'claude-3-opus';

// 本地模型 (Ollama)
const API_BASE = 'http://localhost:11434/v1';
const MODEL = 'llama2';
```

## 🐛 故障排除

### 应用无法启动

1. 确保已安装所有依赖: `npm install`
2. 检查 Node.js 版本: `node -v` (需要 18+)
3. 删除 `node_modules` 和 `dist`，重新安装

### AI 对话不工作

1. 检查 API Key 是否正确
2. 检查网络连接
3. 查看控制台错误信息 (开发模式)

### 窗口显示异常

1. 关闭应用重新启动
2. 检查操作系统权限设置
3. macOS: 系统设置 → 隐私与安全 → 辅助功能

## 📚 相关文档

- [完整 README](./README.md)
- [Electron 文档](https://www.electronjs.org/docs)
- [React 文档](https://react.dev)
- [TypeScript 文档](https://www.typescriptlang.org)

## 🤝 获取帮助

遇到问题？

1. 查看 [常见问题](./README.md#故障排除)
2. 提交 Issue
3. 查看代码注释

祝你和小狗玩得开心！🐕✨

