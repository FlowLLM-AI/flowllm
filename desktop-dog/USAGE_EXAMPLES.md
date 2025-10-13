# 📖 使用示例

## 基本使用

### 1. 启动应用

```bash
npm install
npm run dev
```

小狗会出现在屏幕右下角。

### 2. 移动小狗

用鼠标拖拽小狗到任意位置：

```
按住左键 → 拖动 → 释放
```

### 3. 和小狗聊天

点击小狗，输入问题：

```
你好！
今天天气怎么样？
给我讲个笑话
```

### 4. 让小狗跑步

双击小狗，它会在屏幕上跑来跑去：

```
双击 → 开始跑步
再次双击 → 停止跑步
```

## 高级使用

### 自定义 API 配置

编辑 `.env` 文件配置不同的 API：

```bash
# 使用 OpenAI
VITE_API_KEY=sk-...
VITE_API_BASE=https://api.openai.com/v1
VITE_MODEL=gpt-4

# 使用本地 Ollama
VITE_API_KEY=dummy
VITE_API_BASE=http://localhost:11434/v1
VITE_MODEL=llama2

# 使用阿里云通义千问
VITE_API_KEY=sk-...
VITE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
VITE_MODEL=qwen-max
```

**注意：** 修改 `.env` 后需要重启应用才能生效。

### 修改小狗外观

编辑 `src/components/DesktopDog.tsx` 的 `DogSVG` 组件:

```tsx
// 修改颜色
<ellipse cx="75" cy="130" rx="45" ry="35" fill="#YOUR_COLOR" />

// 修改大小
<svg width="200" height="240" viewBox="0 0 150 180">

// 添加装饰
<circle cx="100" cy="60" r="5" fill="red" /> // 红色蝴蝶结
```

### 修改对话框样式

编辑 `src/components/ChatBubble.css`:

```css
/* 修改颜色主题 */
.chat-bubble-container {
  background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%);
  border: 3px solid #2196F3;
}

/* 修改大小 */
.chat-bubble {
  width: 500px;
  height: 300px;
}

/* 修改字体 */
.chat-input {
  font-size: 16px;
  font-family: 'Comic Sans MS', cursive;
}
```

### 添加新的右键菜单项

编辑 `src/components/ContextMenu.tsx`:

```tsx
// 添加新菜单项
<div className="context-menu-item" onClick={handleCustomAction}>
  🎵 播放音乐
</div>

// 在 DesktopDog 中实现
const handleCustomAction = () => {
  // 自定义逻辑
  console.log('Custom action!');
};
```

### 自定义窗口行为

编辑 `electron/main.ts`:

```typescript
mainWindow = new BrowserWindow({
  width: 200,           // 更大的窗口
  height: 240,
  transparent: true,    
  alwaysOnTop: true,    
  resizable: true,      // 允许调整大小
  skipTaskbar: false,   // 显示在任务栏
  // 更多选项...
});
```

## 实际场景

### 场景 1: 桌面助手

让小狗帮你查询信息：

```
用户: 今天的新闻有什么？
小狗: [AI 回答新闻摘要]

用户: 帮我写个邮件模板
小狗: [AI 提供邮件模板]
```

### 场景 2: 编程助手

向小狗请教代码问题：

```
用户: TypeScript 的泛型怎么用？
小狗: [AI 解释泛型并提供示例]

用户: 这段代码有什么问题？[粘贴代码]
小狗: [AI 分析并给出建议]
```

### 场景 3: 学习伴侣

用小狗帮助学习：

```
用户: 解释一下量子力学的基本原理
小狗: [AI 简单易懂的解释]

用户: 用简单的话解释递归
小狗: [AI 用生动的比喻解释]
```

### 场景 4: 放松娱乐

和小狗聊天放松：

```
用户: 给我讲个笑话
小狗: [AI 讲笑话]

用户: 陪我聊聊天
小狗: [AI 友好对话]
```

## 开发示例

### 添加新表情

```tsx
// 在 DesktopDog.tsx 中
const [expression, setExpression] = useState('normal');

// 添加新表情状态
type Expression = 'normal' | 'happy' | 'sad' | 'excited' | 'sleeping';

// 在 DogSVG 中实现
const DogSVG: React.FC<{ expression: Expression }> = ({ expression }) => {
  if (expression === 'sleeping') {
    return (
      // 画闭眼的小狗
      <line x1="55" y1="70" x2="65" y2="70" stroke="black" />
      <line x1="85" y1="70" x2="95" y2="70" stroke="black" />
      // ... ZZZ 符号
    );
  }
  // 其他表情...
};
```

### 添加声音效果

```tsx
// 创建 src/utils/sound.ts
export const playBark = () => {
  const audio = new Audio('/sounds/bark.mp3');
  audio.play();
};

// 在组件中使用
const handleClick = () => {
  playBark();
  setShowChat(true);
};
```

### 添加数据持久化

```tsx
// 保存位置
useEffect(() => {
  localStorage.setItem('dogPosition', JSON.stringify(position));
}, [position]);

// 读取位置
useEffect(() => {
  const saved = localStorage.getItem('dogPosition');
  if (saved) {
    setPosition(JSON.parse(saved));
  }
}, []);
```

### 添加快捷键

```tsx
useEffect(() => {
  const handleKeyPress = (e: KeyboardEvent) => {
    if (e.ctrlKey && e.key === 'd') {
      setShowChat(true);
    }
  };
  
  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, []);
```

## 调试技巧

### 查看控制台

开发模式下打开开发者工具：

```typescript
// electron/main.ts
mainWindow.webContents.openDevTools({ mode: 'detach' });
```

### 调试 API 调用

```typescript
// src/services/llmService.ts
console.log('Sending message:', userMessage);
console.log('API response:', data);
```

### 调试状态

```tsx
// 使用 useEffect 监控状态
useEffect(() => {
  console.log('Position changed:', position);
}, [position]);

useEffect(() => {
  console.log('Running state:', isRunning);
}, [isRunning]);
```

## 常见问题解决

### Q: 小狗不见了怎么办？

右键菜单 → 回到角落

或重启应用，会回到默认位置。

### Q: 对话框在屏幕外怎么办？

移动小狗到屏幕中央再打开对话框。

### Q: 如何更换 AI 模型？

编辑 `.env` 文件，修改 `VITE_MODEL` 环境变量，然后重启应用。

### Q: 如何禁用跑步功能？

注释掉双击处理代码：

```tsx
// if (now - lastClickTime.current < 300) {
//   handleDoubleClick();
// }
```

### Q: 如何改变跑步速度？

修改步进值：

```tsx
const step_size = 8; // 改为更大或更小的值
```

## 贡献示例

欢迎提交你的自定义版本！可以：

1. Fork 项目
2. 创建特性分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送到分支: `git push origin feature/amazing-feature`
5. 提交 Pull Request

快来创造你自己的桌面宠物吧！🐕✨

