#!/usr/bin/env python3
"""
macOS 桌面小宠物 - 超可爱版本 🐱✨

特性：
- 🎨 温暖奶茶色配色，更加可爱
- ✨ 闪亮的琥珀色大眼睛，带渐变效果
- 💕 粉嫩鼻子和小嘴，带可爱腮红
- 🐾 渐变粉色肉垫，更多细节
- 🌊 轻柔的呼吸动画（透明度变化）
- 👁️ 自动眨眼动画（每3.5秒）
- 🎯 尾巴自动摆动动画
- 🎪 悬停时有反应（显示问号表情）
- 🦘 点击时弹跳动画
- 💬 美化的渐变色对话气泡
- 🏃 双击让猫咪奔跑
- 🖱️ 拖拽移动、右键菜单
- 🤖 AI智能对话
"""
import sys
import os
import random
import asyncio
from typing import Optional
from PyQt6.QtWidgets import (QApplication, QLabel, QMenu, QWidget, 
                              QTextEdit, QVBoxLayout, QPushButton, 
                              QHBoxLayout, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QPainter, QColor, QFont, QAction, QPainterPath, QRegion
from qasync import QEventLoop

# 添加项目路径以便导入flowllm模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowllm.llm.openai_compatible_llm import OpenAICompatibleLLM
from flowllm.schema.message import Message
from loguru import logger

class ResponseBubble(QWidget):
    """AI回答气泡窗口"""
    
    closed = pyqtSignal()  # 关闭信号
    
    def __init__(self, pet_pos: QPoint, initial_text: str = ""):
        super().__init__()
        self.response_text = initial_text
        self.init_ui(pet_pos)
        
    def init_ui(self, pet_pos: QPoint):
        """初始化UI"""
        # 窗口设置
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 初始大小
        self.bubble_width = 350
        self.bubble_height = 150
        self.setFixedSize(self.bubble_width + 20, self.bubble_height + 20)
        
        # 位置在宠物右侧
        bubble_x = pet_pos.x() + 130
        bubble_y = pet_pos.y() - 50
        
        # 确保不超出屏幕
        screen = QApplication.primaryScreen().geometry()
        bubble_x = max(20, min(bubble_x, screen.width() - self.bubble_width - 40))
        bubble_y = max(20, min(bubble_y, screen.height() - self.bubble_height - 40))
        
        self.move(bubble_x, bubble_y)
        
        # 创建主容器
        self.main_widget = QWidget(self)
        self.main_widget.setGeometry(10, 10, self.bubble_width, self.bubble_height)
        self.main_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(245, 255, 245, 255),
                    stop:1 rgba(232, 245, 233, 250));
                border: 3px solid #66BB6A;
                border-radius: 15px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
        """)
        
        layout = QVBoxLayout(self.main_widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)
        
        # 标题栏（带关闭按钮）
        title_layout = QHBoxLayout()
        title_label = QLabel("✨ AI小助手")
        title_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #2E7D32;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 右上角关闭按钮
        close_button = QPushButton("✕")
        close_button.setFixedSize(20, 20)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #81C784;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
            QPushButton:pressed {
                background-color: #4CAF50;
            }
        """)
        close_button.clicked.connect(self.close_bubble)
        title_layout.addWidget(close_button)
        
        layout.addLayout(title_layout)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #E8F5E9;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #81C784;
                border-radius: 4px;
            }
        """)
        
        # 创建内容标签（单个标签显示所有内容）
        self.content_label = QLabel()
        self.content_label.setWordWrap(True)
        self.content_label.setTextFormat(Qt.TextFormat.RichText)
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.content_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                padding: 5px;
            }
        """)
        
        scroll_area.setWidget(self.content_label)
        layout.addWidget(scroll_area, stretch=1)
        
        # 设置初始文本
        if self.response_text:
            self.update_response('answer', self.response_text)
        
    def get_chunk_style(self, chunk_type: str) -> dict:
        """获取不同chunk类型的样式配置"""
        styles = {
            'answer': {
                'color': '#333333',
                'prefix': ''
            },
            'think': {
                'color': '#FF8C00',
                'prefix': '🤔 '
            },
            'error': {
                'color': '#DC143C',
                'prefix': '❌ '
            },
            'tool': {
                'color': '#1E90FF',
                'prefix': '🔧 '
            }
        }
        return styles.get(chunk_type, styles['answer'])
    
    def update_response(self, chunk_type: str, content: str):
        """流式追加内容，根据类型使用不同颜色"""
        # 只处理这四种类型，忽略其他类型（如usage）
        if chunk_type not in ['answer', 'think', 'error', 'tool']:
            return
        
        # 获取样式
        style = self.get_chunk_style(chunk_type)
        
        # 格式化新内容
        content_html = content.replace('\n', '<br>')
        new_html = f'<span style="color: {style["color"]};">{style["prefix"]}{content_html}</span>'
        
        # 追加到现有内容
        current_html = self.content_label.text()
        self.content_label.setText(current_html + new_html)
        
        # 调整标签大小以适应内容
        self.content_label.adjustSize()
        
        # 计算新的气泡大小
        content_height = self.content_label.height()
        new_height = min(max(150, content_height + 80), 500)  # 最小150，最大500
        new_width = 350
        
        if new_height != self.bubble_height or new_width != self.bubble_width:
            self.bubble_width = new_width
            self.bubble_height = new_height
            
            # 平滑调整大小
            self.setFixedSize(self.bubble_width + 20, self.bubble_height + 20)
            self.main_widget.setGeometry(10, 10, self.bubble_width, self.bubble_height)
    
    def close_bubble(self):
        """关闭气泡"""
        self.closed.emit()
        self.close()
    
    def paintEvent(self, event):
        """绘制圆角阴影"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制阴影
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(12, 12, self.bubble_width, self.bubble_height, 15, 15)
        painter.fillPath(shadow_path, QColor(0, 0, 0, 30))


class ChatBubble(QWidget):
    """对话气泡窗口"""
    
    closed = pyqtSignal()  # 关闭信号
    
    def __init__(self, pet_pos: QPoint, llm_client: OpenAICompatibleLLM, pet_widget):
        super().__init__()
        self.llm_client = llm_client
        self.pet_widget = pet_widget
        self.init_ui(pet_pos)
        self.is_streaming = False
        self.response_bubble: Optional[ResponseBubble] = None
        
    def init_ui(self, pet_pos: QPoint):
        """初始化UI"""
        # 窗口设置
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 设置大小和位置（缩小气泡）
        self.setFixedSize(400, 200)
        bubble_x = pet_pos.x() - 420  # 在宠物左侧
        bubble_y = pet_pos.y() - 150  # 在宠物上方
        
        # 确保不超出屏幕
        screen = QApplication.primaryScreen().geometry()
        bubble_x = max(20, min(bubble_x, screen.width() - 420))
        bubble_y = max(20, min(bubble_y, screen.height() - 220))
        
        self.move(bubble_x, bubble_y)
        
        # 创建主容器
        main_widget = QWidget(self)
        main_widget.setGeometry(10, 10, 380, 180)
        main_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 250, 252, 255),
                    stop:1 rgba(255, 240, 245, 250));
                border: 3px solid #FF69B4;
                border-radius: 20px;
                box-shadow: 0 4px 8px rgba(255, 105, 180, 0.2);
            }
        """)
        
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 标题栏（带关闭按钮）
        title_layout = QHBoxLayout()
        title_label = QLabel("💕 和我聊天吧~")
        title_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #E91E63;
                font-size: 16px;
                font-weight: bold;
                border: none;
                text-shadow: 1px 1px 2px rgba(233, 30, 99, 0.2);
            }
        """)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 右上角关闭按钮
        close_button = QPushButton("✕")
        close_button.setFixedSize(24, 24)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #FFB6C1;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF69B4;
            }
            QPushButton:pressed {
                background-color: #FF1493;
            }
        """)
        close_button.clicked.connect(self.close_bubble)
        title_layout.addWidget(close_button)
        
        layout.addLayout(title_layout)
        
        # 输入框
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("输入你想说的话...（按回车发送）")
        self.input_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 2px solid #FFB6C1;
                border-radius: 10px;
                padding: 8px;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.input_text, stretch=1)
        
        # 支持回车发送
        self.input_text.installEventFilter(self)
        
        # 设置焦点到输入框
        self.input_text.setFocus()
        
    def eventFilter(self, obj, event):
        """事件过滤器 - 处理回车发送"""
        if obj == self.input_text and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                # Enter 发送
                self.send_message()
                return True
        return super().eventFilter(obj, event)
    
    def send_message(self):
        """发送消息"""
        message = self.input_text.toPlainText().strip()
        if not message:
            return
        
        if self.is_streaming:
            return
        
        # 清空输入框并禁用
        self.input_text.clear()
        self.input_text.setEnabled(False)
        self.input_text.setPlaceholderText("思考中...")
        
        # 异步调用LLM
        asyncio.create_task(self.call_llm(message))
    
    async def call_llm(self, user_message: str):
        """调用LLM并在新气泡中流式显示回答"""
        self.is_streaming = True
        
        try:
            # 小猫表情变为思考状态
            self.pet_widget.current_expression = "(=^･ω･^=)🤔"
            self.pet_widget.update()
            
            # 创建回答气泡
            self.response_bubble = ResponseBubble(self.pet_widget.pos(), "")
            self.response_bubble.closed.connect(self.on_response_bubble_closed)
            self.response_bubble.show()
            
            # 创建消息列表
            messages = [
                Message(role="system", content="你是一个可爱的桌面宠物助手，用温暖友好的语气回答问题。回答要简洁但有帮助。"),
                Message(role="user", content=user_message)
            ]
            
            # 小猫表情变为回答状态
            self.pet_widget.current_expression = "(=^ω^=)💡"
            self.pet_widget.update()
            
            # 流式接收并更新回答气泡
            async for chunk_content, chunk_type in self.llm_client.astream_chat(messages):
                if chunk_content and self.response_bubble:
                    # 根据类型追加内容
                    self.response_bubble.update_response(chunk_type, chunk_content)
                    # 让UI有时间更新
                    await asyncio.sleep(0.01)
            
            # 回答完成，开心表情
            self.pet_widget.current_expression = "(=^ω^=)✨"
            self.pet_widget.update()
            
        except Exception as e:
            logger.exception(f"出错了: {str(e)}")
            if self.response_bubble:
                self.response_bubble.update_response('error', f"抱歉，出错了: {str(e)}")
            # 错误表情
            self.pet_widget.current_expression = "(=ＴェＴ=)"
            self.pet_widget.update()
        
        finally:
            self.is_streaming = False
            self.input_text.setEnabled(True)
            self.input_text.setPlaceholderText("输入你想说的话...（按回车发送）")
            self.input_text.setFocus()
    
    def on_response_bubble_closed(self):
        """回答气泡关闭时的回调"""
        self.response_bubble = None
    
    def close_bubble(self):
        """关闭气泡"""
        self.closed.emit()
        self.close()
    
    def paintEvent(self, event):
        """绘制圆角阴影"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制阴影
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(12, 12, 380, 180, 20, 20)
        painter.fillPath(shadow_path, QColor(0, 0, 0, 30))


class DesktopPet(QLabel):
    """桌面宠物类"""
    
    def __init__(self, llm_client: OpenAICompatibleLLM):
        super().__init__()
        self.llm_client = llm_client
        self.chat_bubble: Optional[ChatBubble] = None
        self.init_ui()
        self.init_animation()
        self.dragging = False
        self.drag_position = QPoint()
        self.drag_start_pos = QPoint()
        
        # 双击检测
        self.last_click_time = 0
        self.double_click_threshold = 300  # 毫秒
        
        # 跑步状态
        self.is_running = False
        self.run_timer = QTimer(self)
        self.run_timer.timeout.connect(self.run_step)
        self.run_direction = 1  # 1向右，-1向左
        
    def init_ui(self):
        """初始化UI"""
        # 窗口设置
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |  # 无边框
            Qt.WindowType.WindowStaysOnTopHint |  # 置顶
            Qt.WindowType.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)  # 启用悬停事件
        
        # 宠物大小
        self.pet_size = 150
        self.setFixedSize(self.pet_size, self.pet_size + 30)  # 增加高度以容纳尾巴
        
        # 初始位置（屏幕右下角）
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 200, screen.height() - 200)
        
        # 宠物状态
        self.state = "idle"
        self.expressions = ["(=^･ω･^=)", "(=^‥^=)", "(=^･ｪ･^=)", "(=ＴェＴ=)", "(=^ω^=)"]
        self.current_expression = self.expressions[0]
        self.is_hovered = False  # 悬停状态
        
    def init_animation(self):
        """初始化动画"""
        # 表情变化定时器（默认禁用）
        self.expression_timer = QTimer(self)
        self.expression_timer.timeout.connect(self.change_expression)
        # self.expression_timer.start(3000)  # 每3秒换表情 - 默认禁用
        
        # 随机移动定时器（默认禁用）
        self.move_timer = QTimer(self)
        self.move_timer.timeout.connect(self.random_move)
        # self.move_timer.start(8000)  # 每8秒随机移动 - 默认禁用
        
        # 动画效果
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setDuration(1500)
        
        # 自动行为开关
        self.auto_behavior_enabled = False
        
        # 呼吸动画（轻微缩放效果）
        self.breath_animation = QPropertyAnimation(self, b"windowOpacity")
        self.breath_animation.setDuration(2000)
        self.breath_animation.setStartValue(0.95)
        self.breath_animation.setEndValue(1.0)
        self.breath_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.breath_animation.setLoopCount(-1)  # 无限循环
        self.breath_animation.start()
        
        # 眨眼动画计数器
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.blink)
        self.blink_timer.start(3500)  # 每3.5秒眨眼一次
        self.is_blinking = False
        
        # 尾巴摆动动画
        self.tail_angle = 0
        self.tail_timer = QTimer(self)
        self.tail_timer.timeout.connect(self.wag_tail)
        self.tail_timer.start(50)  # 每50ms更新尾巴角度
        
    def paintEvent(self, event):
        """绘制宠物 - 超可爱长毛英短形象"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtGui import QPolygon, QPainterPath, QPen, QRadialGradient
        from PyQt6.QtCore import QPointF
        
        # 更温暖可爱的配色 - 奶茶色/米白色
        if not self.dragging:
            body_base = QColor(220, 200, 180)  # 奶茶色
            body_light = QColor(240, 230, 220)  # 米白色
            body_dark = QColor(180, 160, 140)   # 深奶茶色
        else:
            body_base = QColor(230, 210, 190)
            body_light = QColor(250, 240, 230)
            body_dark = QColor(190, 170, 150)
        
        # === 绘制阴影 ===
        painter.setBrush(QColor(0, 0, 0, 40))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(25, 152, 100, 25)
        
        # === 绘制蓬松的摆动尾巴（在身体后面，很粗） ===
        import math
        # 根据尾巴角度计算摆动位置
        tail_offset = math.sin(self.tail_angle) * 8
        tail_path = QPainterPath()
        tail_path.moveTo(QPointF(118, 125))
        tail_path.cubicTo(
            QPointF(135 + tail_offset, 110),
            QPointF(142 + tail_offset, 135),
            QPointF(130 + tail_offset, 155)
        )
        # 蓬松尾巴 - 画得很粗，带渐变
        tail_gradient = QRadialGradient(130 + tail_offset, 140, 15)
        tail_gradient.setColorAt(0, body_light)
        tail_gradient.setColorAt(1, body_base)
        tail_pen = QPen(body_base, 20, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(tail_pen)
        painter.drawPath(tail_path)
        
        # 尾巴尖端毛茸茸效果（随尾巴摆动）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(tail_gradient)
        painter.drawEllipse(int(120 + tail_offset), 148, 18, 18)
        painter.setBrush(body_light)
        painter.drawEllipse(int(124 + tail_offset), 152, 14, 14)
        
        # === 绘制圆润的身体（长毛效果 - 多层） ===
        painter.setPen(Qt.PenStyle.NoPen)
        
        # 外层毛发（浅色）
        painter.setBrush(body_light)
        painter.drawEllipse(28, 92, 94, 72)
        
        # 中层身体
        painter.setBrush(body_base)
        painter.drawEllipse(32, 95, 86, 66)
        
        # === 绘制圆圆的头部（长毛英短的大圆脸） ===
        # 外层毛茸茸效果
        painter.setBrush(body_light)
        painter.drawEllipse(22, 28, 106, 95)
        
        # 脸部主体
        painter.setBrush(body_base)
        painter.drawEllipse(28, 32, 94, 87)
        
        # 脸颊毛茸茸（英短特征）
        painter.setBrush(body_light)
        painter.drawEllipse(20, 65, 35, 28)  # 左脸颊
        painter.drawEllipse(95, 65, 35, 28)  # 右脸颊
        
        # === 绘制圆耳朵（英短的小圆耳） ===
        painter.setBrush(body_base)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # 左耳 - 圆润的
        painter.drawEllipse(30, 25, 28, 30)
        # 右耳
        painter.drawEllipse(92, 25, 28, 30)
        
        # 耳朵毛茸茸边缘
        painter.setBrush(body_light)
        painter.drawEllipse(33, 28, 22, 24)
        painter.drawEllipse(95, 28, 22, 24)
        
        # 耳朵内部（粉色）
        painter.setBrush(QColor(255, 200, 210))
        painter.drawEllipse(37, 35, 14, 16)
        painter.drawEllipse(99, 35, 14, 16)
        
        # === 绘制超萌大眼睛（闪亮亮的） ===
        # 眼窝阴影（更柔和）
        painter.setBrush(body_dark)
        painter.drawEllipse(44, 60, 26, 28)
        painter.drawEllipse(80, 60, 26, 28)
        
        # 眼白（更大更圆）- 如果眨眼则缩小
        if self.is_blinking:
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(46, 73, 24, 6)  # 眯眼效果
            painter.drawEllipse(80, 73, 24, 6)
        else:
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(46, 62, 24, 26)
            painter.drawEllipse(80, 62, 24, 26)
        
        # 眼珠（温暖的琥珀色 - 超可爱）- 只在睁眼时显示
        if not self.is_blinking:
            if not self.dragging:
                iris_gradient = QRadialGradient(58, 72, 10)
                iris_gradient.setColorAt(0, QColor(255, 180, 100))  # 亮琥珀色
                iris_gradient.setColorAt(1, QColor(200, 130, 60))   # 深琥珀色
                painter.setBrush(iris_gradient)
            else:
                painter.setBrush(QColor(200, 180, 160))  # 温暖灰色
            
            painter.drawEllipse(52, 68, 16, 18)
            painter.drawEllipse(84, 68, 16, 18)
            
            # 瞳孔（竖线状 - 猫咪特征）
            painter.setBrush(QColor(0, 0, 0))
            painter.drawEllipse(57, 72, 5, 12)
            painter.drawEllipse(89, 72, 5, 12)
            
            # 超闪亮的眼睛高光（多层次）
            painter.setBrush(QColor(255, 255, 255, 230))
            painter.drawEllipse(54, 70, 6, 7)  # 主高光
            painter.drawEllipse(86, 70, 6, 7)
            painter.setBrush(QColor(255, 255, 255, 150))
            painter.drawEllipse(60, 77, 3, 4)  # 副高光
            painter.drawEllipse(92, 77, 3, 4)
        
        # === 绘制粉嫩小鼻子（超可爱） ===
        # 鼻子主体（渐变粉色）
        nose_gradient = QRadialGradient(75, 96, 5)
        nose_gradient.setColorAt(0, QColor(255, 180, 190))  # 浅粉
        nose_gradient.setColorAt(1, QColor(240, 140, 160))  # 深粉
        painter.setBrush(nose_gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        nose_polygon = QPolygon([
            QPoint(75, 93),
            QPoint(70, 98),
            QPoint(80, 98)
        ])
        painter.drawPolygon(nose_polygon)
        
        # 鼻子高光（更闪亮）
        painter.setBrush(QColor(255, 220, 230, 200))
        painter.drawEllipse(73, 94, 3, 3)
        
        # === 绘制超萌微笑嘴巴（猫咪式微笑） ===
        painter.setPen(QPen(QColor(160, 100, 100), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        mouth_path = QPainterPath()
        mouth_path.moveTo(QPointF(75, 98))
        mouth_path.lineTo(QPointF(75, 103))
        # 可爱的微笑嘴角（更弯更可爱）
        mouth_path.moveTo(QPointF(75, 103))
        mouth_path.quadTo(QPointF(68, 107), QPointF(63, 104))
        mouth_path.moveTo(QPointF(75, 103))
        mouth_path.quadTo(QPointF(82, 107), QPointF(87, 104))
        painter.drawPath(mouth_path)
        
        # 添加腮红（更可爱）
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 150, 150, 60))
        painter.drawEllipse(35, 85, 20, 15)  # 左腮红
        painter.drawEllipse(95, 85, 20, 15)  # 右腮红
        
        # === 绘制胡须（细而长） ===
        whisker_pen = QPen(QColor(140, 140, 140), 1.5)
        painter.setPen(whisker_pen)
        # 左边胡须
        painter.drawLine(45, 88, 12, 82)
        painter.drawLine(45, 92, 10, 92)
        painter.drawLine(45, 96, 12, 102)
        # 右边胡须
        painter.drawLine(105, 88, 138, 82)
        painter.drawLine(105, 92, 140, 92)
        painter.drawLine(105, 96, 138, 102)
        
        # === 绘制超可爱毛茸茸前爪 ===
        painter.setPen(Qt.PenStyle.NoPen)
        
        # 左爪（渐变效果）
        left_paw_gradient = QRadialGradient(52, 159, 15)
        left_paw_gradient.setColorAt(0, body_light)
        left_paw_gradient.setColorAt(1, body_base)
        painter.setBrush(left_paw_gradient)
        painter.drawEllipse(38, 145, 28, 30)
        
        # 右爪（渐变效果）
        right_paw_gradient = QRadialGradient(96, 159, 15)
        right_paw_gradient.setColorAt(0, body_light)
        right_paw_gradient.setColorAt(1, body_base)
        painter.setBrush(right_paw_gradient)
        painter.drawEllipse(84, 145, 28, 30)
        
        # 粉嫩肉垫（渐变粉色，更可爱）
        paw_gradient = QRadialGradient(52, 162, 6)
        paw_gradient.setColorAt(0, QColor(255, 200, 210))
        paw_gradient.setColorAt(1, QColor(255, 160, 180))
        painter.setBrush(paw_gradient)
        painter.drawEllipse(47, 159, 10, 8)  # 左爪主肉垫
        
        paw_gradient2 = QRadialGradient(96, 162, 6)
        paw_gradient2.setColorAt(0, QColor(255, 200, 210))
        paw_gradient2.setColorAt(1, QColor(255, 160, 180))
        painter.setBrush(paw_gradient2)
        painter.drawEllipse(91, 159, 10, 8)  # 右爪主肉垫
        
        # 小肉垫（脚趾）
        painter.setBrush(QColor(255, 180, 190))
        painter.drawEllipse(42, 157, 5, 5)  # 左爪小肉垫
        painter.drawEllipse(58, 157, 5, 5)
        painter.drawEllipse(86, 157, 5, 5)  # 右爪小肉垫
        painter.drawEllipse(102, 157, 5, 5)
        
        # === 绘制胸前的白色毛（长毛英短特征） ===
        painter.setBrush(QColor(230, 235, 240, 180))
        painter.drawEllipse(58, 115, 34, 25)
        
        # 如果正在拖拽，显示提示
        if self.dragging:
            painter.setPen(QColor(140, 150, 160))
            font = QFont("Arial", 11, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(0, -12, 0, 0), 
                           Qt.AlignmentFlag.AlignCenter, "喵~ (=ＴェＴ=)")
    
    def blink(self):
        """眨眼动画"""
        if not self.dragging and not self.is_running:
            self.is_blinking = True
            self.update()
            # 150毫秒后睁开眼睛
            QTimer.singleShot(150, self.open_eyes)
    
    def open_eyes(self):
        """睁开眼睛"""
        self.is_blinking = False
        self.update()
    
    def wag_tail(self):
        """摆动尾巴"""
        import math
        # 平滑的摆动效果
        self.tail_angle += 0.15
        if self.tail_angle > 2 * math.pi:
            self.tail_angle = 0
        self.update()
    
    def change_expression(self):
        """改变表情"""
        if not self.dragging:
            self.current_expression = random.choice(self.expressions)
            self.update()
    
    def random_move(self):
        """随机移动"""
        if self.dragging or self.animation.state() == QPropertyAnimation.State.Running:
            return
            
        screen = QApplication.primaryScreen().geometry()
        
        # 随机选择新位置（保持在屏幕内）
        new_x = random.randint(50, screen.width() - self.width() - 50)
        new_y = random.randint(50, screen.height() - self.height() - 50)
        
        # 执行动画移动
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(QPoint(new_x, new_y))
        self.animation.start()
        
        # 移动时换个开心的表情
        self.current_expression = "(=^ω^=)✨"
        self.update()
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event.globalPosition().toPoint())
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if event.buttons() == Qt.MouseButton.LeftButton:
            # 计算移动距离
            move_distance = (event.globalPosition().toPoint() - self.drag_start_pos).manhattanLength()
            
            # 如果移动超过5像素，认为是拖拽
            if move_distance > 5:
                if not self.dragging:
                    self.dragging = True
                    self.current_expression = "(=ＴェＴ=)"
                    self.update()
                
                new_pos = event.globalPosition().toPoint() - self.drag_position
                
                # 限制在屏幕范围内
                screen = QApplication.primaryScreen().geometry()
                new_pos.setX(max(0, min(new_pos.x(), screen.width() - self.width())))
                new_pos.setY(max(0, min(new_pos.y(), screen.height() - self.height())))
                
                self.move(new_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 如果没有拖拽（移动距离很小），认为是点击
            move_distance = (event.globalPosition().toPoint() - self.drag_start_pos).manhattanLength()
            
            if move_distance <= 5 and not self.dragging:
                # 检测双击
                import time
                current_time = time.time() * 1000  # 转换为毫秒
                if current_time - self.last_click_time < self.double_click_threshold:
                    # 双击 - 让猫跑起来
                    self.handle_double_click()
                else:
                    # 单击 - 打开聊天
                    self.handle_click()
                self.last_click_time = current_time
            
            if self.dragging:
                self.dragging = False
                self.current_expression = random.choice(["(=^･ω･^=)", "(=^ω^=)"])
                self.update()
            
            event.accept()
    
    def handle_click(self):
        """处理点击事件"""
        # 点击弹出对话框
        self.show_chat_bubble()
        self.current_expression = "(=^･ω･^=)💬"
        self.bounce_animation()  # 添加弹跳动画
        self.update()
    
    def handle_double_click(self):
        """处理双击事件 - 切换跑步状态"""
        if self.is_running:
            # 停止跑步
            self.stop_running()
        else:
            # 开始跑步
            self.start_running()
    
    def start_running(self):
        """开始跑步"""
        self.is_running = True
        self.current_expression = "(=^ω^=)💨"
        self.update()
        
        # 确定跑步方向（朝向最近的屏幕边缘相反方向）
        screen = QApplication.primaryScreen().geometry()
        center_x = self.pos().x() + self.width() / 2
        if center_x < screen.width() / 2:
            self.run_direction = 1  # 向右跑
        else:
            self.run_direction = -1  # 向左跑
        
        # 开始跑步定时器（更快的更新频率）
        self.run_timer.start(30)  # 30毫秒更新一次
    
    def stop_running(self):
        """停止跑步"""
        self.is_running = False
        self.run_timer.stop()
        self.current_expression = "(=^･ω･^=)"
        self.update()
    
    def run_step(self):
        """跑步的每一步"""
        if not self.is_running:
            return
        
        screen = QApplication.primaryScreen().geometry()
        current_pos = self.pos()
        
        # 每步移动的距离
        step_size = 8
        new_x = current_pos.x() + (step_size * self.run_direction)
        
        # 检查是否到达屏幕边缘
        if new_x <= 0:
            # 到达左边缘，转向右
            new_x = 0
            self.run_direction = 1
        elif new_x >= screen.width() - self.width():
            # 到达右边缘，转向左
            new_x = screen.width() - self.width()
            self.run_direction = -1
        
        # 移动猫咪
        self.move(new_x, current_pos.y())
        
        # 跑步时的表情动画
        run_expressions = ["(=^ω^=)💨", "(=^･ω･^=)💨", "(=^ω^=)✨"]
        self.current_expression = random.choice(run_expressions)
        self.update()
    
    def show_chat_bubble(self):
        """显示对话气泡"""
        if self.chat_bubble is None or not self.chat_bubble.isVisible():
            self.chat_bubble = ChatBubble(self.pos(), self.llm_client, self)
            self.chat_bubble.closed.connect(self.on_bubble_closed)
            self.chat_bubble.show()
    
    def on_bubble_closed(self):
        """对话气泡关闭时的回调"""
        self.current_expression = random.choice(self.expressions)
        self.update()
    
    def bounce_animation(self):
        """可爱的弹跳动画"""
        original_pos = self.pos()
        
        # 向上跳
        jump_height = 15
        self.move(original_pos.x(), original_pos.y() - jump_height)
        
        # 100毫秒后回到原位
        QTimer.singleShot(100, lambda: self.move(original_pos))
        
        # 改变表情显得更可爱
        old_expr = self.current_expression
        self.current_expression = "(=^ω^=)✨"
        self.update()
        QTimer.singleShot(200, lambda: setattr(self, 'current_expression', old_expr) or self.update())
    
    def toggle_auto_behavior(self):
        """切换自动行为开关"""
        self.auto_behavior_enabled = not self.auto_behavior_enabled
        
        if self.auto_behavior_enabled:
            # 启用自动行为
            self.expression_timer.start(3000)
            self.move_timer.start(8000)
        else:
            # 禁用自动行为
            self.expression_timer.stop()
            self.move_timer.stop()
    
    def show_context_menu(self, pos):
        """显示右键菜单"""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFF5F7;
                border: 2px solid #FFB6C1;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #FFD6E0;
            }
        """)
        
        # 聊天选项
        chat_action = QAction("💬 和我聊天", self)
        chat_action.triggered.connect(self.show_chat_bubble)
        menu.addAction(chat_action)
        
        menu.addSeparator()
        
        # 自动行为开关
        auto_behavior_text = "🔕 禁用自动行为" if self.auto_behavior_enabled else "🔔 启用自动行为"
        auto_behavior_action = QAction(auto_behavior_text, self)
        auto_behavior_action.triggered.connect(self.toggle_auto_behavior)
        menu.addAction(auto_behavior_action)
        
        menu.addSeparator()
        
        # 表情菜单
        expression_menu = menu.addMenu("切换表情 (=^･ω･^=)")
        for expr in self.expressions:
            action = QAction(expr, self)
            action.triggered.connect(lambda checked, e=expr: self.set_expression(e))
            expression_menu.addAction(action)
        
        menu.addSeparator()
        
        # 回到角落
        corner_action = QAction("回到角落 🏠", self)
        corner_action.triggered.connect(self.move_to_corner)
        menu.addAction(corner_action)
        
        # 随机漫步（单次）
        wander_action = QAction("随机漫步 🚶", self)
        wander_action.triggered.connect(self.random_move)
        menu.addAction(wander_action)
        
        # 跑步切换
        run_text = "停止跑步 🛑" if self.is_running else "开始跑步 🏃"
        run_action = QAction(run_text, self)
        run_action.triggered.connect(self.handle_double_click)
        menu.addAction(run_action)
        
        menu.addSeparator()
        
        # 退出
        exit_action = QAction("再见~ 👋", self)
        exit_action.triggered.connect(self.close_app)
        menu.addAction(exit_action)
        
        menu.exec(pos)
    
    def set_expression(self, expression):
        """设置表情"""
        self.current_expression = expression
        self.update()
    
    def move_to_corner(self):
        """移动到角落"""
        screen = QApplication.primaryScreen().geometry()
        target_pos = QPoint(screen.width() - 200, screen.height() - 200)
        
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(target_pos)
        self.animation.start()
    
    def close_app(self):
        """关闭应用"""
        self.current_expression = "(=ＴェＴ=)"
        self.update()
        QTimer.singleShot(500, QApplication.quit)
    
    def event(self, event):
        """处理悬停事件"""
        if event.type() == event.Type.HoverEnter:
            self.is_hovered = True
            if not self.dragging and not self.is_running:
                self.current_expression = "(=^･ω･^=)?"
                self.update()
        elif event.type() == event.Type.HoverLeave:
            self.is_hovered = False
            if not self.dragging and not self.is_running:
                self.current_expression = self.expressions[0]
                self.update()
        return super().event(event)


def main():
    """主函数"""
    # 使用qasync支持异步
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    app.setQuitOnLastWindowClosed(True)
    
    # 从环境变量读取LLM配置
    api_key = os.getenv("FLOW_LLM_API_KEY", "")
    api_base = os.getenv("FLOW_LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.getenv("FLOW_LLM_MODEL", "qwen3-max")
    
    # 初始化LLM客户端
    llm_client = OpenAICompatibleLLM(
        api_key=api_key,
        base_url=api_base,
        model_name=model
    )
    
    pet = DesktopPet(llm_client)
    pet.show()
    
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()

