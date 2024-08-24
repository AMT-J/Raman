"""This module contains the code for the GUI"""
import threading
from scipy.spatial.distance import directed_hausdorff
import time
import os
import sys
from pathlib import Path
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
                            QLabel, QLineEdit, QPushButton, QTextEdit, QGridLayout, QDialog,QGraphicsDropShadowEffect,
                            QFileDialog, QMessageBox, QListWidget, QListView)
from PyQt6.QtGui import QColor, QShortcut, QKeySequence,QGuiApplication,QIcon
import pyqtgraph as pg
from PyQt6.QtCore import QTimer
import numpy as np
import sqlite3

from utils import find_spectrum_matches, get_unique_mineral_combinations_optimized
from utils import get_xy_from_file, deserialize, baseline_als, get_peaks

from discretize import DraggableGraph, DraggableScatter
from plots import CroppablePlotWidget
from commands import (CommandHistory, LoadSpectrumCommand, PointDragCommand,
                        EstimateBaselineCommand, CorrectBaselineCommand,
                        CropCommand,SmoothSpectrumCommand)

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'Raman Spectra Analyzer'
        self.init_UI()
        self.Resize()
        self.init_keyboard_shortcuts() #初始化键盘快捷键
        #初始化
        self.peaks_x = np.array([])  #初始化峰值坐标
        self.peaks_y = np.array([])  
        self.peak_texts=[]   #初始化峰值标签列表
        self.database_path = None
        self.baseline_data = None
        self.baseline_plot = None
        self.loaded_spectrum = None
        self.spectrum = None
        self.cropping = False
        self.crop_region = None

        with open('config.json', 'r') as f:
            self.config = json.load(f)
        

        self.command_history = CommandHistory()

    def init_UI(self):
        """初始化用户界面
        main_layout
          |--search_layout
          |    |--database_layout
          |    |--peaks_layout
          |    |--tolerance_layout
          |--results_layout
          |--plot1_layout
          |--plot2_layout
        """
        # 设置窗口图标
        self.setWindowIcon(QIcon('1.ico'))
   
        # 全局设置所有样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5faff;   /* 设置主窗口背景为淡蓝色 */
            }
            QPushButton {
                border-radius: 5px;              
                background-color: #ADD8E6;       /* 淡蓝色背景 */
                border: 1px solid #ADD8E6;       /* 边框颜色 */
                font-family: 'Microsoft YaHei UI';   
                font-size: 10pt;
                font: blod;
                padding: 2px 10px;
            }

            QPushButton:hover {
                background-color: #6bb7e0;       /* 悬停时稍深的蓝色 */
                border: 1px solid #6bb7e0;       /* 悬停时的边框颜色 */
            }

            QPushButton:pressed {
                background-color: #5a9acb;       /* 点击时更深的蓝色 */
                border: 2px solid #5a9acb;       /* 点击时的边框颜色 */
            }
            QPushButton:disabled {
                background-color: lightgray;
                color: #505050;
                border: lightgray;
            }      
            QLabel {
                font-family: 'Microsoft YaHei UI';   /* 字体类型 */
                font-size: 12pt;           /* 字体大小 */
                font: blod;
                color: #333333;            /* 字体颜色 */
            }
                    
            QLineEdit {
                border-radius: 5px;                      /* 圆角 */
                border: 1px solid #d6e8ff;              /* 边框颜色和宽度 */
                padding: 5px;                           /* 内边距 */
                background-color: #d6e8ff;              /* 背景色（淡蓝色） */
                font-family: 'Microsoft YaHei UI';                /* 字体 */
                font-size: 10pt;                        /* 字体大小 */
            }

            QLineEdit:hover {
                border: 1px solid #bcd9ff;              /* 鼠标悬停时的边框颜色 */
                background-color: #bcd9ff;              /* 鼠标悬停时的背景色（稍深的蓝色） */
            }

            QLineEdit:focus {
                border: 1px solid #a6ccff;              /* 获取焦点时的边框颜色 */
                background-color: #a6ccff;              /* 获取焦点时的背景色 */
            }
                           
            
            QTextEdit {
                background-color: #ffffff;  /* 白色背景 */
                border: 1px solid #a0aec1;  /* 边框颜色 */
                border-radius: 5px;         /* 圆角边框 */
                font-family: 'Microsoft YaHei UI';    /* 字体类型 */
                font-size: 10pt;            /* 字体大小 */
            }
            QListWidget {
                background-color: #ffffff;        /* 背景色 */
                border: 1px solid #4682b4;         /* 蓝色边框 */
                border-radius: 15px;             /* 圆角半径 */
                padding: 5px;                    /* 内边距 */
                font-family: 'Microsoft YaHei UI';                /* 字体 */
                font-size: 10pt;                        /* 字体大小 */
            }  
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 数据库和搜索区域
        search_layout = QHBoxLayout()
        search_widget = QWidget()
        search_widget.setLayout(search_layout)

        # 数据库选择
        database_layout = QHBoxLayout()
        database_widget = QWidget()
        database_widget.setLayout(database_layout)
        self.database_label = QLabel("数据库：未选择", self)
        self.load_database_button = QPushButton('加载数据库', self)
        self.load_database_button.clicked.connect(self.load_database_file)

        self.apply_shadow_effect(self.load_database_button)

        database_layout.addWidget(self.database_label)
        database_layout.addWidget(self.load_database_button)
        search_layout.addWidget(database_widget)
        
        # 峰值输入
        peaks_layout = QHBoxLayout()
        peaks_widget = QWidget()
        peaks_widget.setLayout(peaks_layout)
        self.label_peaks = QLabel("峰值（逗号分隔）：", self)
        self.textbox_peaks = QLineEdit(self)
        peaks_layout.addWidget(self.label_peaks)
        peaks_layout.addWidget(self.textbox_peaks)
        search_layout.addWidget(peaks_widget)

        # 容差输入
        tolerance_layout = QHBoxLayout()
        tolerance_widget = QWidget()
        tolerance_widget.setLayout(tolerance_layout)
        self.label_tolerance = QLabel("容差：", self)
        self.textbox_tolerance = QLineEdit(self)
        tolerance_layout.addWidget(self.label_tolerance)
        tolerance_layout.addWidget(self.textbox_tolerance)
        search_layout.addWidget(tolerance_widget)

        # 搜索按钮
        self.button_search = QPushButton('搜索', self)
        self.button_search.clicked.connect(self.on_search)
        search_layout.addWidget(self.button_search)
        

        self.apply_shadow_effect(self.button_search)
        main_layout.addWidget(search_widget)

         # 结果显示区域
        results_layout = QHBoxLayout()
        results_widget = QWidget()
        results_widget.setLayout(results_layout)
        self.result_single = QTextEdit(self)
        self.result_double = QTextEdit(self)
        self.result_triple = QTextEdit(self)
        
        # 设置QTextEdit组件为只读
      
        for text_edit in [self.result_single, self.result_double, self.result_triple]:
            text_edit.setReadOnly(True)

            
              
        results_layout.addWidget(self.result_single)
        results_layout.addWidget(self.result_double)
        results_layout.addWidget(self.result_triple)
        main_layout.addWidget(results_widget)

       # 加载光谱图形及其工具
        plot1_layout = QGridLayout()
        plot1_layout.setVerticalSpacing(0)
        plot1_widget = QWidget()
        plot1_widget.setLayout(plot1_layout)
        plot1_layout.setColumnStretch(0, 1) 
        plot1_buttons_layout = QVBoxLayout()
        plot1_buttons_layout.setSpacing(0)
        plot1_buttons_widget = QWidget()
        plot1_buttons_widget.setLayout(plot1_buttons_layout)
        plot1_layout.addWidget(plot1_buttons_widget, 0, 2, 1, 1)
        main_layout.addWidget(plot1_widget)
        
        # 绘图组件1
        self.plot1 = CroppablePlotWidget(self)
        self.plot1.setLabel('left', '强度')
        self.plot1.setLabel('bottom', '拉曼位移', units='cm<sup>-1</sup>')
        plot1_layout.addWidget(self.plot1, 0, 0, 1, 2)

        # 加载文件按钮
        plot1_row1_buttons_layout = QHBoxLayout()
        plot1_row1_buttons_widget = QWidget()
        plot1_row1_buttons_widget.setLayout(plot1_row1_buttons_layout)
        plot1_buttons_layout.addWidget(plot1_row1_buttons_widget)
        
        self.button_load_file = QPushButton('加载文件', self)
        self.button_load_file.clicked.connect(self.load_unknown_spectrum)
        # 将按钮添加到水平布局中
        self.apply_shadow_effect(self.button_load_file)
        plot1_row1_buttons_layout.addWidget(self.button_load_file)

        # 基线估计按钮
        self.button_baseline = QPushButton('基线估计', self)
        self.button_baseline.clicked.connect(self.baseline_callback)

        self.apply_shadow_effect(self.button_baseline)
        plot1_row1_buttons_layout.addWidget(self.button_baseline)

        plot1_row2_buttons_layout = QHBoxLayout()
        plot1_row2_buttons_widget = QWidget()
        plot1_row2_buttons_widget.setLayout(plot1_row2_buttons_layout)
        plot1_buttons_layout.addWidget(plot1_row2_buttons_widget)
        # 基线离散化按钮
        self.button_discretize = QPushButton('基线离散化', self)
        self.button_discretize.clicked.connect(self.discretize_baseline)

        self.apply_shadow_effect(self.button_discretize)
        plot1_row2_buttons_layout.addWidget(self.button_discretize)

        # 裁剪按钮
        self.crop_button = QPushButton("裁剪", self)
        self.crop_button.clicked.connect(self.toggle_crop_mode)

        self.apply_shadow_effect(self.crop_button)
        plot1_row2_buttons_layout.addWidget(self.crop_button)

        # 显示峰值按钮
        plot1_peaks_buttons_layout = QHBoxLayout()
        plot1_peaks_buttons_widget = QWidget()
        plot1_peaks_buttons_widget.setLayout(plot1_peaks_buttons_layout)
        plot1_buttons_layout.addWidget(plot1_peaks_buttons_widget)

        self.button_find_peaks = QPushButton('显示峰值', self)
        self.button_find_peaks.clicked.connect(self.find_peaks)


        self.apply_shadow_effect(self.button_find_peaks)
        plot1_peaks_buttons_layout.addWidget(self.button_find_peaks)

        # 显示标签按钮
        self.button_show_peak_labels = QPushButton('显示标签', self)
        self.button_show_peak_labels.clicked.connect(self.toggle_labels_callback)

        self.apply_shadow_effect(self.button_show_peak_labels)
        plot1_peaks_buttons_layout.addWidget(self.button_show_peak_labels)

        plot1_row3_buttons_layout = QHBoxLayout()
        plot1_row3_buttons_widget = QWidget()
        plot1_row3_buttons_widget.setLayout(plot1_row3_buttons_layout)
        plot1_buttons_layout.addWidget(plot1_row3_buttons_widget)

        # 平滑处理按钮
        self.button_reset = QPushButton('平滑处理', self)
        self.button_reset.clicked.connect(self.smooth_spectrum)

        self.apply_shadow_effect(self.button_reset)
        plot1_row3_buttons_layout.addWidget(self.button_reset)
        
        # 保存光谱按钮
        self.button_save_spectrum = QPushButton('保存光谱', self)
        self.button_save_spectrum.clicked.connect(self.save_edited_spectrum)

        self.apply_shadow_effect(self.button_save_spectrum)
        plot1_row3_buttons_layout.addWidget(self.button_save_spectrum)

        # 输入框：scipy.signal.find_peaks()参数
        plot1_peak_params_layout = QGridLayout()
        plot1_peak_params_widget = QWidget()
        plot1_peak_params_widget.setLayout(plot1_peak_params_layout)
        plot1_buttons_layout.addWidget(plot1_peak_params_widget)

        # 宽度输入框
        self.textbox_width = QLineEdit(self)
        self.textbox_width.setPlaceholderText(' 宽度')
        plot1_peak_params_layout.addWidget(self.textbox_width, 0, 0)

        # 相对高度输入框
        self.textbox_rel_height = QLineEdit(self)
        self.textbox_rel_height.setPlaceholderText(' 相对高度')
        plot1_peak_params_layout.addWidget(self.textbox_rel_height, 0, 1)

        # 高度输入框
        self.textbox_height = QLineEdit(self)
        self.textbox_height.setPlaceholderText(' 高度')
        plot1_peak_params_layout.addWidget(self.textbox_height, 1, 0)

        # 显著性输入框
        self.textbox_prominence = QLineEdit(self)
        self.textbox_prominence.setPlaceholderText(' 显著性')
        plot1_peak_params_layout.addWidget(self.textbox_prominence, 1, 1)

        # Plot 1日志记录列表
        self.plot1_log = QListWidget()
        plot1_buttons_layout.addWidget(self.plot1_log)

        # 绘图区域2（与第一个绘图区域共享工具栏）
        plot2_layout = QGridLayout()
        plot2_widget = QWidget()
        plot2_widget.setLayout(plot2_layout)
        plot2_layout.setColumnStretch(0, 1)
        main_layout.addWidget(plot2_widget)
        plot2_buttons_layout = QVBoxLayout()
        plot2_buttons_widget = QWidget()
        plot2_buttons_widget.setLayout(plot2_buttons_layout)
        plot2_layout.addWidget(plot2_buttons_widget, 0, 2, 1, 1)

        # 第二个绘图组件，显示光谱图
        self.plot2 = CroppablePlotWidget(self)
        self.plot2.setLabel('left', '强度')
        self.plot2.setLabel('bottom', '拉曼位移', units='cm<sup>-1</sup>')
        plot2_layout.addWidget(self.plot2, 0, 0, 1, 2)

        #矿物名称
        self.mineral_input = QLineEdit(self)
        self.mineral_input.setPlaceholderText(" 输入矿物名称")
        plot2_buttons_layout.addWidget(self.mineral_input)

        # 波长
        self.wavelength_input = QLineEdit(self)
        self.wavelength_input.setPlaceholderText(" 输入波长")
        plot2_buttons_layout.addWidget(self.wavelength_input)

        plot2_row1_buttons_layout = QHBoxLayout()
        plot2_row1_buttons_widget = QWidget()
        plot2_row1_buttons_widget.setLayout(plot2_row1_buttons_layout)
        plot2_buttons_layout.addWidget(plot2_row1_buttons_widget)

        # 搜索数据库的按钮  
        self.search_button = QPushButton('搜索', self)
        self.search_button.clicked.connect(self.search_database)
    
        self.apply_shadow_effect(self.search_button)
        plot2_row1_buttons_layout.addWidget(self.search_button)

        # 绘制所选光谱的按钮
        self.plot_button = QPushButton('绘制光谱', self)
        self.plot_button.clicked.connect(self.plot_selected_spectra)

        self.apply_shadow_effect(self.plot_button)
        plot2_row1_buttons_layout.addWidget(self.plot_button)

        plot2_row2_buttons_layout = QHBoxLayout()
        plot2_row2_buttons_widget = QWidget()
        plot2_row2_buttons_widget.setLayout(plot2_row2_buttons_layout)
        plot2_buttons_layout.addWidget(plot2_row2_buttons_widget)

        # 对齐X轴的按钮，使Plot2的X轴范围与Plot1匹配
        self.align_button = QPushButton('对齐X轴', self)
        self.align_button.clicked.connect(self.match_range)
       
        self.apply_shadow_effect(self.align_button)
        plot2_row2_buttons_layout.addWidget(self.align_button)

        self.reset_button = QPushButton('重置数据',self)
        self.reset_button.clicked.connect(self.reset)
        self.apply_shadow_effect(self.reset_button)
        plot2_row2_buttons_layout.addWidget(self.reset_button)

        # 数据库搜索结果的列表组件，允许多选
        self.results_list = QListWidget(self)
        self.results_list.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        plot2_buttons_layout.addWidget(self.results_list)
        
        # 设置主窗口的中央组件及布局
        self.setWindowTitle(self.title)
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setLayout(main_layout)
        self.show()

    def smooth_spectrum(self):
        """"光谱平滑处理"""
        if self.spectrum is None:
            QMessageBox.critical(self, '错误', '请先加载光谱数据！')
            return

        command = SmoothSpectrumCommand(self)
        self.command_history.execute(command)

    def apply_shadow_effect(self,widget):
        """应用阴影效果"""
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(10)  # 模糊半径
        shadow_effect.setXOffset(3)      # X轴偏移
        shadow_effect.setYOffset(3)      # Y轴偏移
        shadow_effect.setColor(QColor(63, 63, 63, 180))  # 阴影颜色
        widget.setGraphicsEffect(shadow_effect)

    def reset(self):
        # 清除加载的数据库、光谱等数据
        self.database_path = None
        self.baseline_data = None
        self.baseline_plot = None
        self.loaded_spectrum = None
        self.spectrum = None
        self.cropping = False
        self.crop_region = None
     
        # 清空 peaks_x 和 peaks_y
        self.peaks_x = np.array([])  
        self.peaks_y = np.array([])  
        self.peak_texts.clear()


        # 重置UI组件到初始状态
        self.database_label.setText("数据库：未选择")
        self.textbox_peaks.clear()
        self.textbox_tolerance.clear()
        
        # 清空搜索结果区域
        self.result_single.clear()
        self.result_double.clear()
        self.result_triple.clear()
        
        # 清除图形绘制区域
        self.plot1.clear()
        self.plot2.clear()
        
        # 清除峰值查找参数输入框
        self.textbox_width.clear()
        self.textbox_rel_height.clear()
        self.textbox_height.clear()
        self.textbox_prominence.clear()
        self.mineral_input.clear()
        self.wavelength_input.clear()
        
        # 重置按钮模式
        self.crop_button.setText("裁剪")
        self.button_show_peak_labels.setText('显示标签')
        self.align_button.setText('对齐X轴')
        self.button_baseline.setText('基线估计')
        self.button_find_peaks.setText('显示峰值')
        # 清空Plot 1日志记录
        self.plot1_log.clear()

        # 清空数据库搜索部分的输入框和列表
        self.results_list.clear()
        

    def resizeEvent(self, event):
        """确保两个绘图部件在调整大小时具有相同的宽度和高度"""
        QApplication.processEvents()

       # 获取两个绘图部件的最大宽度和高度
        max_width = max(self.plot1.width(), self.plot2.width())
        max_height = max(self.plot1.height(), self.plot2.height())

       # 设置两个绘图部件的最小尺寸为最大宽度和高度
        self.plot1.setMinimumWidth(max_width)
        self.plot1.setMinimumHeight(max_height)
        self.plot2.setMinimumWidth(max_width)
        self.plot2.setMinimumHeight(max_height)

        # 此外，将它们的大小策略设置为宽度和高度均优先选择
        policy1 = self.plot1.sizePolicy()
        policy1.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        policy1.setVerticalPolicy(QSizePolicy.Policy.Preferred)
        self.plot1.setSizePolicy(policy1)

        policy2 = self.plot2.sizePolicy()
        policy2.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        policy2.setVerticalPolicy(QSizePolicy.Policy.Preferred)
        self.plot2.setSizePolicy(policy2)

        # 调用基类的方法，确保事件得到正确处理
        super().resizeEvent(event)

        # 将窗口置于屏幕中央
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.geometry()
        new_x = (screen_geometry.width() - window_geometry.width()) // 2
        new_y = (screen_geometry.height() - window_geometry.height()) // 2
        self.move(new_x, new_y)


    def Resize(self):
        """"重置窗口大小"""
        screen_geometry = QApplication.primaryScreen().geometry()
        half_screen_size = screen_geometry.width()  *2// 3, screen_geometry.height() //2
        self.resize(*half_screen_size)

    def show_whats_new(self):
        """"加载首次弹窗"""
        try:
            from whats_new import new_features, WhatsNewDialog
            platform_key = 'nt' if os.name == 'nt' else 'posix'
            messages = new_features.get(platform_key, [])

            # 显示自定义对话框
            dialog = WhatsNewDialog(messages, self)
            response = dialog.exec()
            
            # 如果在查看所有信息后关闭了对话框，则将 show_whats_new 设为 False
            if response == QDialog.DialogCode.Accepted and dialog.current_index == len(messages) - 1:
                self.config['show_whats_new'] = False
                with open('config.json', 'w') as f:
                    json.dump(self.config, f, indent=4)

        except ImportError:
            pass  # 如果找不到 whats_new.py，就跳过显示信息

    def init_keyboard_shortcuts(self):
        """"设置键盘快捷键"""
        undo_shortcut = QShortcut(QKeySequence('Ctrl+Z'), self)
        undo_shortcut.activated.connect(self.undo)

        redo_shortcut = QShortcut(QKeySequence('Ctrl+Y'), self)
        redo_shortcut.activated.connect(self.redo)

        load_spectrum_shortcut = QShortcut(QKeySequence('Ctrl+L'), self)
        load_spectrum_shortcut.activated.connect(self.load_unknown_spectrum)

        crop_shortcut = QShortcut(QKeySequence('Ctrl+R'), self)
        crop_shortcut.activated.connect(self.toggle_crop_mode)

        baseline_shortcut = QShortcut(QKeySequence('Ctrl+E'), self)
        baseline_shortcut.activated.connect(self.baseline_callback)

        discretize_shortcut = QShortcut(QKeySequence('Ctrl+D'), self)
        discretize_shortcut.activated.connect(self.discretize_baseline)

        save_shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        save_shortcut.activated.connect(self.save_edited_spectrum)
        
    def undo(self):
        """"撤销"""
        print('Undo activated')
        self.command_history.undo()
    
    def redo(self):
        """"重做"""
        print('Redo activated')
        self.command_history.redo()

    def toggle_crop_mode(self):
        if self.spectrum == None:
            # 显示错误信息
            QMessageBox.critical(self, '错误', '请先导入光谱数据！')
            return
        if self.cropping:
            self.crop_region = self.plot1.get_crop_region()
            if self.crop_region is None:
                QMessageBox.critical(self,'错误',"请先选中裁剪区域！")
                return
            
            crop_start_x, crop_end_x = self.crop_region.getRegion()
            
            command = CropCommand(self, crop_start_x, crop_end_x)
            self.command_history.execute(command)
            self.crop_button.setText('裁剪')
            self.button_show_peak_labels.setText('显示标签')
            self.button_baseline.setText('基线估计')
            self.button_find_peaks.setText('显示峰值')
            self.cropping = False
            self.plot1.cropping = self.cropping

            # 从绘图中删除 crop_region 项。
            self.plot1.removeItem(self.crop_region)
            self.crop_region = None
            self.plot1.crop_region = None
        else:
            self.crop_button.setText("应用裁剪")
            self.cropping = True
            self.plot1.cropping = self.cropping

    def save_edited_spectrum(self):
        if self.spectrum == None:
            QMessageBox.critical(self, '错误', '请先导入光谱数据！')
            return
        default_name = f"{self.unknown_spectrum_path.stem}_processed.txt"
        suggested_path = self.unknown_spectrum_path.parent / default_name
        fname, _ = QFileDialog.getSaveFileName(self, "保存光谱", str(suggested_path), "Text Files (*.txt)")

        if fname:  # 检查用户是否没有取消对话框
            with open(fname, 'w') as f:
                for x, y in zip(self.spectrum.x, self.spectrum.y):
                    f.write(f"{x} {y}\n")
            
            self.plot1_log.addItem(f'已保存修改后的光谱： {fname}')
            self.to_end()

    def update_discretized_baseline(self):

        """每当用户在离散化后移动一个点时，都会更新已加载频谱的基线数据"""
        self.draggableGraph.setData(pos=np.array(list(zip(self.draggableScatter.data['x'], self.draggableScatter.data['y']))))
        self.baseline_data = np.interp(self.spectrum.x, self.draggableScatter.data['x'], self.draggableScatter.data['y'])
        if hasattr(self, 'interpolated_baseline'):
            self.plot1.removeItem(self.interpolated_baseline)
        pen=pg.mkPen(color='g',width=3)  
        self.interpolated_baseline = self.plot1.plot(self.spectrum.x, self.baseline_data, pen=pen)

    def discretize_baseline(self):
        if self.spectrum == None:
            QMessageBox.critical(self, '错误', '请先导入光谱数据！')
            return
        if self.button_baseline.text().strip() == "基线估计":
            QMessageBox.critical(self, '错误', '请先进行基线估计！')
            return
        
        # 将 self.spectrum.x 和 baseline_data 排序为升序
        sorted_indices = np.argsort(self.spectrum.x)
        sorted_x = self.spectrum.x[sorted_indices]
        sorted_baseline = self.baseline_data[sorted_indices]
        # 将基线离散化
        x_vals = np.arange(sorted_x[0], sorted_x[-1], self.config['discrete baseline step size'])
        y_vals = np.interp(x_vals, self.spectrum.x, sorted_baseline)
       
        # 如果存在上一条离散化基线，则清除它
        if hasattr(self, 'draggableScatter'):
            self.plot1.removeItem(self.draggableScatter)
        if hasattr(self, 'draggableGraph'):
            self.plot1.removeItem(self.draggableGraph)

        self.draggableScatter = DraggableScatter(
            x=x_vals,
            y=y_vals, 
            size=self.config['discrete baseline point size'], 
            symbolBrush=eval(self.config['discrete baseline point color'])
        )
        self.draggableScatter.pointDragged.connect(self.update_discretized_baseline)
        self.draggableScatter.dragFinished.connect(self.handle_drag_finished)

        self.draggableGraph = DraggableGraph(scatter_data={'x': x_vals, 'y': y_vals})
        
        self.plot1.addItem(self.draggableScatter)
        self.plot1.addItem(self.draggableGraph)

       # 用离散化基线替换平滑基线
        self.plot1.removeItem(self.baseline_plot)

    def handle_drag_finished(self, index, startX, startY, endX, endY):
        print('handle_drag_finished was called')
        command = PointDragCommand(self, index, startX, startY, endX, endY)
        self.command_history.execute(command)

    def match_range(self):
        if not self.spectrum:
            QMessageBox.critical(self, '错误', '请先导入光谱数据！')
            return 
        if not self.results_list:
            QMessageBox.critical(self, '错误', '请先进行搜索操作！')
            return

        name = self.align_button.text()
        if name == '对齐X轴':
            self.plot2.setXLink(self.plot1)
            self.align_button.setText('重置X轴')
        else: # 重置
            self.plot2.autoRange()
            self.plot2.setXLink(None)
            self.plot1.autoRange()
            self.align_button.setText('对齐X轴')

    def load_database_file(self):
        
        # 打开文件对话框，默认路径为上级工作目录
        fname = QFileDialog.getOpenFileName(self, '打开数据库', '..', "Database Files (*.db);")
        
        if fname[0]:
            self.database_path = Path(fname[0])
            self.database_label.setText(f"数据库： {self.database_path.name}")


    def load_unknown_spectrum(self):
        fname = QFileDialog.getOpenFileName(self, '选择拉曼光谱', '..',"Text Files (*.txt)")
        if fname[0]:
            self.unknown_spectrum_path = Path(fname[0])
            command = LoadSpectrumCommand(self, *get_xy_from_file(self.unknown_spectrum_path))
            self.command_history.execute(command)

    def baseline_callback(self):
        if self.spectrum == None:
            QMessageBox.critical(self, '错误', '请先导入光谱数据！')
            return
        if self.button_baseline.text().strip() == "基线估计":
            command = EstimateBaselineCommand(self, baseline_als(self.spectrum.y))
            self.command_history.execute(command)
        else:
            command = CorrectBaselineCommand(self)
            self.command_history.execute(command)

    def similarity(self,spectrum1, spectrum2):
        u = np.column_stack((np.arange(len(spectrum1)), spectrum1))
        v = np.column_stack((np.arange(len(spectrum2)), spectrum2))
        distance = max(directed_hausdorff(u, v)[0], directed_hausdorff(v, u)[0])
        similarity = 1 / (1 + distance)
        return similarity
    
    def search_database(self):
        if self.database_label.text().strip() == "数据库：未选择":
            # 显示错误信息
            QMessageBox.critical(self, '错误', '请先导入数据库！')
            return
        if self.spectrum == None:
            QMessageBox.critical(self,'错误','请先导入光谱数据！')
            return
        # 禁用UI组件，防止在搜索进行时操作
        self.reset_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.button_search.setEnabled(False)

        self.mineral_name = self.mineral_input.text()
        self.wavelength = self.wavelength_input.text()
        if not self.mineral_name or not self.wavelength:
            QMessageBox.information(self, '提示', '矿物名称或波长未输入，将自动进行相似度匹配！')
            # 创建一个新的线程来运行搜索操作
            search_thread = threading.Thread(target=self._search_database_thread)
            search_thread.daemon = True  # 设置为守护线程
            search_thread.start()
        else:
            QMessageBox.information(self, '提示', '将根据矿物名称和波长进行检索！')
            _search_thread = threading.Thread(target=self._search_database)
            _search_thread.daemon = True  # 设置为守护线程
            _search_thread.start()
            

    def _search_database(self):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

        # 将矿物名称转换为小写
        mineral_name_lower = self.mineral_name.lower()

        if self.wavelength != '':
            # 在名称列上使用 LOWER 函数，并使用 = 运算符进行比较
            cursor.execute("SELECT filename, data_x, data_y FROM Spectra WHERE LOWER(names) = ? AND wavelength=?", (mineral_name_lower, self.wavelength))
        else:
            cursor.execute("SELECT filename, data_x, data_y FROM Spectra WHERE LOWER(names) = ?", (mineral_name_lower,))
        results = cursor.fetchall()
        connection.close() 
        # 填充结果列表
        self.results_list.clear()
        self.data_to_plot = {}
        if results: 
            for result in results:
                self.results_list.addItem(result[0])
                self.data_to_plot[result[0]] = (result[1], result[2])
        else:
            self.results_list.addItem(f"未找到该矿物和波长所对应的光谱数据")

        self.reset_button.setEnabled(True)
        self.search_button.setEnabled(True)
        self.button_search.setEnabled(True)

    def _search_database_thread(self):
        
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()
        # 从数据库中获取所有光谱数据
        cursor.execute("SELECT filename, data_x, data_y FROM Spectra")
        results = cursor.fetchall()
        connection.close()
        #初始化
        index = 1
        total = len(results)
        # 使用当前处理后的光谱数据
        processed_x = self.spectrum.x
        processed_y = self.spectrum.y
        #unknown_x, unknown_y = get_xy_from_file(self.unknown_spectrum_path)
        # 存储相似度计算结果
        similarity_results = []
        # 初始化结果列表
        self.results_list.clear()
        self.data_to_plot = {}

        for result in results:
            filename, data_x, data_y = result
            
            # 将数据库光谱的x轴和未知光谱的x轴对齐，以确保y值可以比较
            data_x = np.array(eval(data_x))
            data_y = np.array(eval(data_y))
            
            # 对x轴插值，确保x轴一致
            interpolated_y = np.interp(processed_x, data_x, data_y)
            
           # 计算相似度
            similarity = self.similarity(processed_y, interpolated_y)*100
            
            if similarity >= 1 :  # 只保留相似度大于等于1%的结果
                similarity_results.append((filename, similarity))
                self.data_to_plot[filename] = (data_x, data_y)  # 仅存储文件名和对应的光谱数据
            
            # 更新搜索进度
            progress_percent = index / total * 100
            index +=1
            self.results_list.clear()
            self.results_list.addItem(f"正在搜索中: {progress_percent:.2f}%")
            

        time.sleep(0.5)  # 增加延迟，放慢加载速度
        self.results_list.clear()
        self.results_list.addItem(f"已搜索完成！以下是搜索结果：")
        time.sleep(0.5)
        if similarity_results: 
            # 按相似度从高到低排序
            similarity_results.sort(key=lambda x: x[1], reverse=True)
            # 填充结果列表
            self.results_list.clear()
            for filename, similarity in similarity_results:
                self.results_list.addItem(f"相似度{similarity:.2f}%：{filename}")
        
        else:
            self.results_list.addItem(f"未找到相似度大于等于1%的光谱数据")

        self.reset_button.setEnabled(True)
        self.search_button.setEnabled(True)
        self.button_search.setEnabled(True)
        

    def plot_selected_spectra(self):
        if self.spectrum == None:
            QMessageBox.critical(self,'错误','请先导入数据库！')
            return
        
        if  not self.results_list:
            # 显示错误信息
            QMessageBox.critical(self, '错误', '请先进行搜索操作！')
            return
        selected_files = [item.text() for item in self.results_list.selectedItems()]
        if not selected_files :
            QMessageBox.critical(self, '错误','请先在下面输出框选中光谱！')
            return
        # 清除之前的绘图
        self.plot2.clear()

        for file in selected_files:
            # 提取条目中的文件名部分
            filename = file.split("：")[-1].strip()
            data_x, data_y = self.data_to_plot[filename]
            # 如果数据是字符串格式，则进行反序列化
            if isinstance(data_x, str):
                x = deserialize(data_x)
            else:
                x = data_x  # 如果已经是数组，则直接使用

            if isinstance(data_y, str):
                y = deserialize(data_y)
            else:
                y = data_y  # 如果已经是数组，则直接使用
            pen=pg.mkPen(color='k',width=3)
            self.plot2.plot(x, y,pen=pen)
        
        self.plot2.autoRange()

    def toggle_labels_callback(self):

        show = self.button_show_peak_labels.text().strip() == '显示标签'
        if self.spectrum == None:
            QMessageBox.critical(self, '错误', '请先导入光谱数据！')
            return
        if self.button_find_peaks.text().strip() == '显示峰值' and show :
            QMessageBox.critical(self, '错误', '请先显示峰值！')
            return
        
        if show:
            # 创建文本项并将其添加到绘图中
            for x, y in zip(self.peaks_x, self.peaks_y):
                text_item = pg.TextItem(str(round(x, 1)), anchor=(0, 0), color=(255, 0, 0), angle=90)
                text_item.setPos(x, y)  # 调整 Y 位置，使其略高于峰值
                self.plot1.addItem(text_item)
                if not hasattr(self, 'peak_texts'):
                    self.peak_texts = []
                self.peak_texts.append(text_item)
            self.button_show_peak_labels.setText('隐藏标签')
        else:
            # 删除之前的文本项目
            if hasattr(self, 'peak_texts') and self.peak_texts:
                for text_item in self.peak_texts:
                    self.plot1.removeItem(text_item)
                self.peak_texts = []
            self.button_show_peak_labels.setText('显示标签')
        
    def find_peaks(self):
        if self.spectrum is None:
            QMessageBox.critical(self, '错误', '请先导入光谱数据！')
            return
        if self.button_find_peaks.text() =='显示峰值':
            # 获取输入参数
            width = self.textbox_width.text().strip()
            rel_height = self.textbox_rel_height.text().strip()
            height = self.textbox_height.text().strip()
            prominence = self.textbox_prominence.text().strip()
            # 将参数转换为适当的类型
            width = eval(width) if width else None
            rel_height = float(rel_height) if rel_height else None
            height = float(height) if height else None
            prominence = float(prominence) if prominence else None
            # 获取峰值数据
            self.peaks_x, self.peaks_y = get_peaks(
                self.spectrum.x, 
                self.spectrum.y, 
                width=width, 
                rel_height=rel_height, 
                height=height, 
                prominence=prominence)
            # 如果已有峰值图形，移除它
            if hasattr(self, 'peak_plot') and self.peak_plot:
                self.plot1.removeItem(self.peak_plot)
                self.peak_plot = None

            # 绘制新的峰值点
            self.peak_plot = self.plot1.plot(self.peaks_x, self.peaks_y, pen=None, symbol='o', symbolSize=7, symbolBrush=(255, 0, 0))
            # 显示峰值信息到日志和文本框
            if len(self.peaks_x) < 15:
                self.plot1_log.addItem(f'峰值：{", ".join([str(x) for x in sorted(self.peaks_x)])}')
                self.to_end()
                self.textbox_peaks.setText(','.join([str(round(x,1)) for x in sorted(self.peaks_x)]))
            else:
                first_15_peaks = self.peaks_x[:15]
                self.plot1_log.addItem(f'峰值：{", ".join([str(x) for x in sorted(first_15_peaks)])}...')
                self.to_end()
                self.textbox_peaks.setText(','.join([str(round(x,1)) for x in sorted(first_15_peaks)]))
            self.button_find_peaks.setText('隐藏峰值')
        else:
             # 移除显示的峰值点
            if hasattr(self, 'peak_plot') and self.peak_plot:
                self.plot1.removeItem(self.peak_plot)
                self.peak_plot = None
            
            # 移除标签
            if hasattr(self, 'peak_texts') and self.peak_texts:
                for text_item in self.peak_texts:
                    self.plot1.removeItem(text_item)
                self.peak_texts = []

            self.button_show_peak_labels.setText('显示标签')
            self.button_find_peaks.setText('显示峰值')

    def on_search(self):
        if self.database_label.text().strip()== "数据库：未选择":
            # 显示错误信息
            QMessageBox.critical(self, '错误', '请先导入数据库！')
            return
        if not self.textbox_peaks.text().strip() or not self.textbox_tolerance.text().strip():
            QMessageBox.critical(self, '错误', '请先输入峰值和容差！')
            return 
            
        # 创建一个新的线程来运行搜索操作
        on_search_thread = threading.Thread(target=self._on_search_database_thread)
        on_search_thread.daemon = True  # 设置为守护线程
        on_search_thread.start()

    def _on_search_database_thread(self):

        self.reset_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.button_search.setEnabled(False)

        # 从文本框中获取值
        peaks = self.textbox_peaks.text().split(',')
        peaks = [float(x) for x in peaks]
        tolerance = float(self.textbox_tolerance.text().strip())

        # 调用搜索功能
        result = find_spectrum_matches(self.database_path, peaks, tolerance)  
        self.unique_singletons = sorted(get_unique_mineral_combinations_optimized(self.database_path, result[1]))
        self.unique_pairs = sorted(get_unique_mineral_combinations_optimized(self.database_path, result[2]))
        self.unique_triples = sorted(get_unique_mineral_combinations_optimized(self.database_path, result[3]))

        # 准备要显示的消息
        self.msg_singletons = f'找到{len(self.unique_singletons)}种含有峰值的矿物：\n'
        self.msg_pairs = f'找到{len(self.unique_pairs)}与峰值相匹配的2种矿物组合：\n'
        self.msg_triples = f'找到{len(self.unique_triples)}与峰值相匹配的3种矿物组合：\n'

        # 在主线程中更新UI
        QTimer.singleShot(0, self.update_ui_after_search)

    def update_ui_after_search(self):
        # 用结果填充 QTextEdits
        self.result_single.setText(self.msg_singletons)
        self.result_double.setText(self.msg_pairs)
        self.result_triple.setText(self.msg_triples)

        for line in self.unique_singletons:
            self.result_single.append(line[0])
        for line in self.unique_pairs:
            self.result_double.append(f'{line[0]},   {line[1]}')
        for line in self.unique_triples:
            self.result_triple.append(f'{line[0]},   {line[1]},   {line[2]}')

        # 启用UI组件
        self.reset_button.setEnabled(True)
        self.search_button.setEnabled(True)
        self.button_search.setEnabled(True)

    def to_end(self):
        # 选中最后一个项目并滚动到该项目
        self.plot1_log.setCurrentRow(self.plot1_log.count() - 1)
        self.plot1_log.scrollToItem(self.plot1_log.currentItem())
        self.plot1_log.clearSelection()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainApp()      
    ex.show() 
    if ex.config.get('show_whats_new', False):
        # 确保主窗口完全渲染后再显示弹窗
        QTimer.singleShot(120, lambda: (QApplication.processEvents(), ex.show_whats_new()))
    sys.exit(app.exec())
    