#!/usr/bin/env python3
"""
macOS 桌面小宠物 - 可拖拽、带动画、置顶显示、AI对话
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

from flowllm.llm.openai_compatible_llm import OpenAICompatibleBaseLLM
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
                background-color: rgba(232, 245, 233, 250);
                border: 3px solid #81C784;
                border-radius: 15px;
            }
        """)
        
        layout = QVBoxLayout(self.main_widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)
        
        # 标题栏（带关闭按钮）
        title_layout = QHBoxLayout()
        title_label = QLabel("🐾 AI回答")
        title_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #4CAF50;
                font-size: 13px;
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
    
    def __init__(self, pet_pos: QPoint, llm_client: OpenAICompatibleBaseLLM, pet_widget):
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
                background-color: rgba(255, 245, 247, 250);
                border: 3px solid #FFB6C1;
                border-radius: 20px;
            }
        """)
        
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 标题栏（带关闭按钮）
        title_layout = QHBoxLayout()
        title_label = QLabel("💬 和我聊天吧~")
        title_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #FF69B4;
                font-size: 16px;
                font-weight: bold;
                border: none;
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
            # 创建回答气泡
            self.response_bubble = ResponseBubble(self.pet_widget.pos(), "")
            self.response_bubble.closed.connect(self.on_response_bubble_closed)
            self.response_bubble.show()
            
            # 创建消息列表
            messages = [
                Message(role="system", content="你是一个可爱的桌面宠物助手，用温暖友好的语气回答问题。回答要简洁但有帮助。"),
                Message(role="user", content=user_message)
            ]
            
            # 流式接收并更新回答气泡
            async for chunk_content, chunk_type in self.llm_client.astream_chat(messages):
                if chunk_content and self.response_bubble:
                    # 根据类型追加内容
                    self.response_bubble.update_response(chunk_type, chunk_content)
                    # 让UI有时间更新
                    await asyncio.sleep(0.01)
            
        except Exception as e:
            logger.exception(f"出错了: {str(e)}")
            if self.response_bubble:
                self.response_bubble.update_response('error', f"抱歉，出错了: {str(e)}")
        
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
    
    def __init__(self, llm_client: OpenAICompatibleBaseLLM):
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
        
    def paintEvent(self, event):
        """绘制宠物 - 长毛英短形象"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtGui import QPolygon, QPainterPath, QPen, QRadialGradient
        from PyQt6.QtCore import QPointF
        
        # 长毛英短配色 - 奶灰色/蓝灰色
        if not self.dragging:
            body_base = QColor(180, 190, 200)  # 蓝灰色
            body_light = QColor(200, 210, 220)  # 浅灰色
            body_dark = QColor(140, 150, 160)   # 深灰色
        else:
            body_base = QColor(190, 200, 210)
            body_light = QColor(210, 220, 230)
            body_dark = QColor(150, 160, 170)
        
        # === 绘制阴影 ===
        painter.setBrush(QColor(0, 0, 0, 40))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(25, 152, 100, 25)
        
        # === 绘制蓬松的尾巴（在身体后面，很粗） ===
        tail_path = QPainterPath()
        tail_path.moveTo(QPointF(118, 125))
        tail_path.cubicTo(
            QPointF(135, 110),
            QPointF(142, 135),
            QPointF(130, 155)
        )
        # 蓬松尾巴 - 画得很粗
        tail_pen = QPen(body_base, 20, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(tail_pen)
        painter.drawPath(tail_path)
        
        # 尾巴尖端毛茸茸效果
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(body_base)
        painter.drawEllipse(120, 148, 18, 18)
        painter.drawEllipse(124, 152, 14, 14)
        
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
        
        # === 绘制大眼睛（英短的圆眼睛） ===
        # 眼窝阴影
        painter.setBrush(body_dark)
        painter.drawEllipse(46, 62, 24, 26)
        painter.drawEllipse(80, 62, 24, 26)
        
        # 眼白
        painter.setBrush(QColor(255, 255, 250))
        painter.drawEllipse(48, 64, 22, 24)
        painter.drawEllipse(80, 64, 22, 24)
        
        # 眼珠（橙色/铜色 - 英短特征）
        if not self.dragging:
            iris_color = QColor(220, 140, 60)  # 铜橙色
        else:
            iris_color = QColor(180, 180, 180)  # 灰色
        
        painter.setBrush(iris_color)
        painter.drawEllipse(52, 69, 14, 16)
        painter.drawEllipse(84, 69, 14, 16)
        
        # 瞳孔（细线状 - 猫在明亮环境）
        painter.setBrush(QColor(0, 0, 0))
        painter.drawEllipse(57, 73, 4, 10)
        painter.drawEllipse(89, 73, 4, 10)
        
        # 眼睛高光
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawEllipse(55, 71, 4, 5)
        painter.drawEllipse(87, 71, 4, 5)
        painter.drawEllipse(60, 76, 2, 3)
        painter.drawEllipse(92, 76, 2, 3)
        
        # === 绘制小巧的鼻子 ===
        painter.setBrush(QColor(240, 160, 170))
        nose_polygon = QPolygon([
            QPoint(75, 94),
            QPoint(71, 98),
            QPoint(79, 98)
        ])
        painter.drawPolygon(nose_polygon)
        
        # 鼻子高光
        painter.setBrush(QColor(255, 200, 210))
        painter.drawEllipse(74, 95, 2, 2)
        
        # === 绘制嘴巴（英短的小嘴） ===
        painter.setPen(QColor(120, 120, 120))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        mouth_path = QPainterPath()
        mouth_path.moveTo(QPointF(75, 98))
        mouth_path.lineTo(QPointF(75, 102))
        # 微笑的嘴角
        mouth_path.moveTo(QPointF(75, 102))
        mouth_path.quadTo(QPointF(70, 105), QPointF(66, 103))
        mouth_path.moveTo(QPointF(75, 102))
        mouth_path.quadTo(QPointF(80, 105), QPointF(84, 103))
        painter.drawPath(mouth_path)
        
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
        
        # === 绘制毛茸茸的前爪 ===
        painter.setPen(Qt.PenStyle.NoPen)
        
        # 左爪
        painter.setBrush(body_light)
        painter.drawEllipse(40, 145, 26, 28)
        painter.setBrush(body_base)
        painter.drawEllipse(42, 147, 22, 24)
        
        # 右爪
        painter.setBrush(body_light)
        painter.drawEllipse(84, 145, 26, 28)
        painter.setBrush(body_base)
        painter.drawEllipse(86, 147, 22, 24)
        
        # 肉垫（粉色）
        painter.setBrush(QColor(255, 180, 190))
        # 左爪肉垫
        painter.drawEllipse(48, 160, 8, 6)
        # 右爪肉垫
        painter.drawEllipse(92, 160, 8, 6)
        
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
        """弹跳动画"""
        original_size = self.size()
        
        # 放大
        self.resize(int(self.pet_size * 1.2), int(self.pet_size * 1.2))
        QTimer.singleShot(100, lambda: self.resize(original_size))
    
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


def main():
    """主函数"""
    # 使用qasync支持异步
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    app.setQuitOnLastWindowClosed(True)
    
    # 从环境变量读取LLM配置
    api_key = "sk-d5c95707168b43a59463efd7c025465f"
    api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = "qwen3-max"
    
    # 初始化LLM客户端
    llm_client = OpenAICompatibleBaseLLM(
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

