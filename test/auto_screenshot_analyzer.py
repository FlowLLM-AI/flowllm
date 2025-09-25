#!/usr/bin/env python3
"""
自动截图分析脚本
每5分钟对Mac电脑进行截图，使用VL模型分析用户正在做什么，并保存分析结果
"""

import os
import time
import json
import base64
from datetime import datetime
from typing import List, Dict
import threading
import signal
import sys

from loguru import logger

# 检查必要的依赖
try:
    from openai import OpenAI
except ImportError:
    print("❌ 错误: 未找到 openai 包")
    print("请运行: pip install openai")
    sys.exit(1)

try:
    from PIL import ImageGrab, Image
except ImportError:
    print("❌ 错误: 未找到 Pillow 包")
    print("请运行: pip install Pillow")
    sys.exit(1)

try:
    from flowllm.utils.common_utils import load_env
except ImportError:
    print("❌ 错误: 未找到 flowllm 包")
    print("请确保已安装 flowllm: pip install -e .")
    sys.exit(1)

# 加载环境变量
load_env()


class AutoScreenshotAnalyzer:
    def __init__(self):
        # 检查必要的环境变量
        api_key = os.getenv("FLOW_LLM_API_KEY")
        if not api_key:
            print("❌ 错误: 未找到 FLOW_LLM_API_KEY 环境变量")
            print("请设置环境变量或在 .env 文件中配置 API Key")
            sys.exit(1)
            
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        
        # 配置参数
        self.model_name = "qwen3-vl-235b-a22b-instruct"
        self.interval_minutes = 2
        self.max_history_context = 10  # 最多保留10条历史记录作为上下文
        
        # 创建保存目录
        self.screenshot_dir = "/Users/yuli/workspace/flowllm/logs/screenshots"
        self.analysis_file = "/Users/yuli/workspace/flowllm/logs/activity_analysis.json"
        
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.analysis_file), exist_ok=True)
        
        # 加载历史分析记录
        self.analysis_history = self.load_analysis_history()
        
        self.running = True
        
    def load_analysis_history(self) -> List[Dict]:
        """加载历史分析记录"""
        if os.path.exists(self.analysis_file):
            try:
                with open(self.analysis_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                print("无法加载历史记录，从空记录开始")
                return []
        return []
    
    def save_analysis_history(self):
        """保存分析历史到文件"""
        try:
            with open(self.analysis_file, 'w', encoding='utf-8') as f:
                json.dump(self.analysis_history, f, ensure_ascii=False, indent=2)
            print(f"✅ 分析历史已保存到: {self.analysis_file}")
        except Exception as e:
            print(f"❌ 保存分析历史失败: {e}")
    
    def get_screen_info(self) -> List[Dict]:
        """获取屏幕信息"""
        try:
            screens = []
            
            # 使用macOS的system_profiler获取详细的显示器信息
            try:
                import subprocess
                import re
                
                result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    output = result.stdout
                    print(f"🖥️  system_profiler 输出:\n{output[:500]}...")
                    
                    # 解析显示器信息
                    displays = []
                    display_blocks = re.split(r'\n\s*([^:]+):\s*\n', output)[1:]  # 跳过第一个空元素
                    
                    for i in range(0, len(display_blocks), 2):
                        if i + 1 >= len(display_blocks):
                            break
                            
                        display_name = display_blocks[i].strip()
                        display_info = display_blocks[i + 1]
                        
                        # 寻找分辨率信息
                        resolution_match = re.search(r'Resolution:\s*(\d+)\s*x\s*(\d+)', display_info)
                        if resolution_match:
                            width = int(resolution_match.group(1))
                            height = int(resolution_match.group(2))
                            displays.append({
                                'name': display_name,
                                'width': width,
                                'height': height,
                                'info': display_info
                            })
                    
                    print(f"🖥️  解析到 {len(displays)} 个显示器")
                    for i, display in enumerate(displays):
                        print(f"   显示器 {i+1}: {display['name']} - {display['width']}x{display['height']}")
                    
                    # 根据解析结果构建屏幕信息
                    if len(displays) >= 2:
                        # 多显示器情况，为每个显示器创建屏幕区域
                        # 假设显示器是水平排列的（这是最常见的情况）
                        x_offset = 0
                        for i, display in enumerate(displays[:2]):  # 最多支持2个屏幕
                            screens.append({
                                'id': i,
                                'bbox': (x_offset, 0, x_offset + display['width'], display['height']),
                                'name': f"显示器{i+1} ({display['name'][:20]})"
                            })
                            x_offset += display['width']
                    
                    elif len(displays) == 1:
                        # 单显示器
                        display = displays[0]
                        screens.append({
                            'id': 0,
                            'bbox': (0, 0, display['width'], display['height']),
                            'name': f"主显示器 ({display['name'][:20]})"
                        })
                
            except Exception as e:
                print(f"❌ system_profiler 解析失败: {e}")
            
            # 如果 system_profiler 解析失败，fallback 到简单的全屏截图
            if not screens:
                print("🖥️  使用 fallback 方案：全屏截图")
                screens.append({
                    'id': 0,
                    'bbox': None,  # None 表示全屏截图
                    'name': '全屏幕'
                })
            
            return screens
            
        except Exception as e:
            print(f"❌ 获取屏幕信息失败: {e}")
            # 返回默认单屏幕配置
            return [{'id': 0, 'bbox': None, 'name': '默认屏幕'}]

    def take_screenshots(self) -> List[str]:
        """截取所有屏幕并保存到文件"""
        screens = self.get_screen_info()
        print(f"🖥️  一共 {len(screens)} 个屏幕")

        screenshot_paths = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for screen in screens:
            print(f"🖥️  处理 {screen['name']} 屏幕")
            
            # 生成文件名
            filename = f"screenshot_{timestamp}_screen{screen['id']}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            
            # 使用 macOS 的 screencapture 命令截取特定显示器
            # -D 参数指定显示器编号 (1, 2, 3...)
            display_num = screen['id'] + 1  # screencapture 的显示器编号从1开始
            
            import subprocess
            try:
                # 使用 screencapture 命令截取特定显示器
                result = subprocess.run([
                    'screencapture', 
                    '-D', str(display_num),  # 指定显示器
                    '-x',  # 不播放快门声音
                    filepath
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0 and os.path.exists(filepath):
                    screenshot_paths.append(filepath)
                    print(f"📸 {screen['name']} 截图已保存: {filepath}")
                else:
                    print(f"❌ screencapture 命令失败: {result.stderr}")
                    # 尝试使用 PIL 作为备用方案
                    if screen['bbox']:
                        screenshot = ImageGrab.grab(bbox=screen['bbox'])
                        screenshot.save(filepath)
                        screenshot_paths.append(filepath)
                        print(f"📸 {screen['name']} 使用PIL备用截图: {filepath}")
                    else:
                        raise Exception(f"screencapture failed and no bbox available")
                        
            except subprocess.TimeoutExpired:
                print(f"❌ screencapture 命令超时")
                raise Exception("screencapture timeout")
            except Exception as e:
                print(f"❌ {screen['name']} 截图失败: {e}")
                raise e
        
        return screenshot_paths
    
    def encode_image(self, image_path: str) -> str:
        """将图像文件转换为Base64编码"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as e:
            print(f"❌ 图像编码失败: {e}")
            return None
    
    def build_context_prompt(self, num_screens: int = 1) -> str:
        """构建包含历史上下文的提示词"""
        if num_screens > 1:
            base_prompt = f"""你是一个智能助手，正在分析用户的多屏幕活动。用户有{num_screens}个屏幕，请根据所有截图内容综合分析用户当前在做什么。

请提供：
1. 每个屏幕的内容简要描述
2. 多屏幕之间的关联性分析
3. 推理用户正在进行的整体活动
4. 一句话总结用户的当前状态

"""
        else:
            base_prompt = """你是一个智能助手，正在分析用户的屏幕活动。请根据截图内容分析用户当前在做什么。

请提供：
1. 当前屏幕内容的简要描述
2. 推理用户正在进行的活动
3. 一句话总结用户的当前状态

"""
        
        # 添加历史上下文
        if self.analysis_history:
            base_prompt += "\n📜 历史活动上下文（最近的活动）:\n"
            recent_history = self.analysis_history[-self.max_history_context:]
            
            for i, record in enumerate(recent_history, 1):
                time_str = record.get('timestamp', '未知时间')
                activity = record.get('activity_summary', '未知活动')
                base_prompt += f"{i}. [{time_str}] {activity}\n"
            
            base_prompt += "\n基于以上历史活动上下文和当前截图，分析用户现在的活动状态。\n"
        
        base_prompt += "\n请用中文回答，保持简洁明了。"
        return base_prompt
    
    def analyze_screenshots(self, image_paths: List[str]) -> Dict:
        """使用VL模型批量分析多张截图"""
        try:
            if not image_paths:
                return None
                
            # 编码所有图像
            image_contents = []
            valid_paths = []
            
            for i, image_path in enumerate(image_paths):
                base64_image = self.encode_image(image_path)
                if base64_image:
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                    })
                    valid_paths.append(image_path)
                    print(f"📷 图像 {i+1} 编码成功: {os.path.basename(image_path)}")
                else:
                    print(f"❌ 图像 {i+1} 编码失败: {image_path}")
            
            if not image_contents:
                return None
            
            # 构建消息 - 支持多张图片
            context_prompt = self.build_context_prompt(num_screens=len(valid_paths))
            
            # 构建用户消息内容：先放所有图片，再放文本提示
            user_content = image_contents + [
                {
                    "type": "text",
                    "text": context_prompt
                }
            ]
            
            messages = [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "你是一个专业的屏幕活动分析助手。"}]
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ]
            
            # 调用模型
            print(f"🤖 正在分析 {len(valid_paths)} 张截图...")
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.3
            )
            
            analysis_result = completion.choices[0].message.content
            print(f"✅ 批量分析完成: {analysis_result[:100]}...")
            
            return {
                "timestamp": datetime.now().isoformat(),
                "screenshot_paths": valid_paths,
                "num_screens": len(valid_paths),
                "analysis_result": analysis_result,
                "activity_summary": self.extract_summary(analysis_result)
            }
            
        except Exception as e:
            logger.exception(e)
            print(f"❌ 批量分析截图失败: {e}")
            raise e
            return None
    
    def extract_summary(self, analysis_text: str) -> str:
        """从分析结果中提取一句话总结"""
        # 简单的提取逻辑，寻找包含"总结"或"状态"的行
        lines = analysis_text.split('\n')
        for line in lines:
            if any(keyword in line for keyword in ['总结', '状态', '正在', '在做']):
                # 移除可能的序号和标点
                summary = line.strip('123456789. ：:').strip()
                if summary:
                    return summary
        
        # 如果没有找到特定格式，返回前50个字符作为总结
        return analysis_text[:50] + "..." if len(analysis_text) > 50 else analysis_text
    
    def process_cycle(self):
        """执行一次完整的截图分析流程"""
        print(f"\n🔄 开始新的分析周期 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1. 多屏幕截图
        screenshot_paths = self.take_screenshots()
        if not screenshot_paths:
            print("❌ 没有截图成功，跳过本次分析")
            return
        
        print(f"📸 成功截取 {len(screenshot_paths)} 个屏幕")
        
        # 2. 批量分析所有截图
        analysis = self.analyze_screenshots(screenshot_paths)
        if not analysis:
            print("❌ 分析失败，跳过本次记录")
            return
        
        # 3. 保存到历史记录
        self.analysis_history.append(analysis)
        
        # 4. 限制历史记录长度，避免文件过大
        max_total_history = 1000  # 最多保留1000条记录
        if len(self.analysis_history) > max_total_history:
            self.analysis_history = self.analysis_history[-max_total_history:]
        
        # 5. 持久化保存
        self.save_analysis_history()
        
        # 6. 显示当前分析结果
        screen_info = f"({analysis['num_screens']} 屏幕)" if analysis['num_screens'] > 1 else ""
        print(f"📊 当前活动总结 {screen_info}: {analysis['activity_summary']}")
    
    def start_monitoring(self):
        """开始监控循环"""
        print(f"🚀 开始自动截图分析监控")
        print(f"⏰ 间隔时间: {self.interval_minutes} 分钟")
        print(f"📁 截图保存目录: {self.screenshot_dir}")
        print(f"📄 分析结果文件: {self.analysis_file}")
        print(f"📜 历史记录数量: {len(self.analysis_history)}")
        print("按 Ctrl+C 停止监控\n")
        
        # 首次执行
        self.process_cycle()
        
        # 开始定时循环
        while self.running:
            try:
                # 等待指定时间
                for _ in range(self.interval_minutes * 60):  # 转换为秒
                    if not self.running:
                        break
                    time.sleep(1)
                
                if self.running:
                    self.process_cycle()
                    
            except KeyboardInterrupt:
                self.stop_monitoring()
                break
            except Exception as e:
                print(f"❌ 监控循环出错: {e}")
                print("等待下一个周期...")
    
    def stop_monitoring(self):
        """停止监控"""
        print("\n🛑 正在停止监控...")
        self.running = False
        self.save_analysis_history()
        print("✅ 监控已停止，数据已保存")
    
    def signal_handler(self, signum, frame):
        """处理系统信号"""
        print(f"\n接收到信号 {signum}")
        self.stop_monitoring()
        sys.exit(0)


def main():
    """主函数"""
    analyzer = AutoScreenshotAnalyzer()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, analyzer.signal_handler)
    signal.signal(signal.SIGTERM, analyzer.signal_handler)
    
    try:
        analyzer.start_monitoring()
    except Exception as e:
        print(f"❌ 程序运行出错: {e}")
        analyzer.stop_monitoring()


if __name__ == "__main__":
    main()
