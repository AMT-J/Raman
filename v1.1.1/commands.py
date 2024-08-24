"""此模块包含处理光谱操作的命令

除 CommandSpectrum 和 CommandHistory 之外的每个类都继承自 Command 类。
每个类都有一个 `undo` 和 `execute` 方法。命令存储在 GUI 的 `command_history` 列表中。此结构实现了 GUI 中的撤销/重做功能。
"""
import numpy as np
import pyqtgraph as pg
from scipy.signal import savgol_filter


class Command:
    """命令的基类"""

    def execute(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError



class CommandSpectrum:
    """表示命令类的光谱"""
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def copy(self):
        """深度拷贝"""
        return CommandSpectrum(self.x.copy(), self.y.copy())

    def __iter__(self):
        return [self.x, self.y].__iter__()



class CommandHistory:
    """命令序列的容器类"""

    def __init__(self):
        self.commands = []
        self.index = -1

    def execute(self, command):
        """在执行后禁用进一步的重做"""
        self.commands = self.commands[:self.index + 1]
        command.execute()
        self.commands.append(command)
        self.index += 1
    
    def undo(self):
        """撤销最后执行的命令"""
        if self.index < 0:
            return
     
        self.commands[self.index].undo()
        self.index -= 1

    def redo(self):
        """重做最后撤销的命令"""
        if self.index == len(self.commands) - 1:
            return
      
        self.index += 1
        self.commands[self.index].execute()


class LoadSpectrumCommand(Command):
    """加载光谱的命令"""
    def __init__(self, app, xdata, ydata):
        self.app = app
        self.new_spectrum = CommandSpectrum(xdata, ydata)
        if self.app.spectrum is not None:
            self.old_spectrum = self.app.spectrum.copy()
        else:
            self.old_spectrum = None

        self.old_plot1_log = []

    def execute(self):
        """执行加载光谱命令"""
        # 备份绘图日志
        for idx in range(self.app.plot1_log.count()):
            line_to_back_up = self.app.plot1_log.item(idx).text()
            #print('backing up:', line_to_back_up)
            self.old_plot1_log.append(line_to_back_up)

        # 更新界面
        self.app.plot1_log.clear()
        self.app.button_baseline.setText('基线估计')
        self.app.button_show_peak_labels.setText('显示标签')
        self.app.button_find_peaks.setText('显示峰值')
        self.app.crop_button.setText("裁剪")

        self.app.spectrum = self.new_spectrum
        if self.app.spectrum is not None:
            self.app.plot1.clear()
            pen=pg.mkPen(color='k',width=3)
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y,pen=pen)
            self.app.plot1.autoRange()

        # 添加加载信息到日志
        self.app.plot1_log.addItem(f"已加载文件： {str(self.app.unknown_spectrum_path)}")
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()

    def undo(self):
        """撤销加载光谱命令"""
        self.app.button_baseline.setText('基线估计')
        self.app.button_show_peak_labels.setText('显示标签')
        self.app.button_find_peaks.setText('显示峰值')
        self.app.crop_button.setText("裁剪")
        if self.old_plot1_log:
            self.app.plot1_log.clear()
            self.app.plot1_log.addItems(self.old_plot1_log)
            # 选中最后一个项目并滚动到该项目
            self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
            self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
            self.app.plot1_log.clearSelection()

        self.app.spectrum = self.old_spectrum
        if self.app.spectrum is not None:
            self.app.plot1.clear()
            pen=pg.mkPen(color='k',width=3)        
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y,pen=pen)
            self.app.plot1.autoRange()
        else:
            self.app.plot1.clear()



class PointDragCommand(Command):
    """拖动基线上的点的命令"""
    def __init__(self, app, index, startX, startY, endX, endY):
        self.app = app
        self.index = index
        self.startX = startX
        self.startY = startY
        self.endX = endX
        self.endY = endY

    def execute(self):
        """执行拖动点命令"""
        self.app.draggableScatter.data['x'][self.index] = self.endX
        self.app.draggableScatter.data['y'][self.index] = self.endY
        self.app.update_discretized_baseline()
    
    def undo(self):
        """撤销拖动点命令"""
        self.app.draggableScatter.data['x'][self.index] = self.startX
        self.app.draggableScatter.data['y'][self.index] = self.startY
        self.app.update_discretized_baseline()
    


class EstimateBaselineCommand(Command):
    """存储基线估计的计算结果并执行必要的GUI更新"""
    def __init__(self, app, estimated_baseline):
        self.app = app
        self.new_baseline = estimated_baseline
        if self.app.baseline_data is not None:
            self.old_baseline = self.app.baseline_data.copy()
        else:
            self.old_baseline = None

    def execute(self):

        """执行基线估计命令"""
        self.app.button_baseline.setText('应用基线校准')
        self.app.plot1_log.addItem('基线估计已计算') 
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()

        # 更新数据
        self.app.baseline_data = self.new_baseline
        
        # 更新绘图
        if self.app.baseline_plot is not None:
            self.app.plot1.removeItem(self.app.baseline_plot)
        pen=pg.mkPen(color='r',width=3)
        self.app.baseline_plot = self.app.plot1.plot(self.app.spectrum.x, self.app.baseline_data, pen=pen)
        
    def undo(self):
        """撤销基线估计命令"""
        self.app.button_baseline.setText('基线估计')
        self.app.button_show_peak_labels.setText('显示标签')
        self.app.button_find_peaks.setText('显示峰值')
        self.app.crop_button.setText("裁剪")

        self.app.baseline_data = self.old_baseline
        
        # 更新绘图
        if self.app.baseline_plot is not None:
            self.app.plot1.removeItem(self.app.baseline_plot)
            self.app.baseline_data = None
        
        if self.app.baseline_data is not None:
            pen=pg.mkPen(color='r',width=3)
            self.app.baseline_plot = self.app.plot1.plot(self.app.spectrum.x, self.app.baseline_data, pen=pen)
        self.app.plot1_log.addItem("基线估计已撤销")
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()



class CorrectBaselineCommand(Command):
    """校正基线的命令"""
    def __init__(self, app):
        self.app = app

        # 存储旧的光谱
        if self.app.spectrum is not None:
            self.old_spectrum = self.app.spectrum.copy()
        else:
            self.old_spectrum = None

        # 更新新的光谱
        if self.app.baseline_data is not None:
            self.new_spectrum = CommandSpectrum(self.app.spectrum.x, self.app.spectrum.y - self.app.baseline_data)
            self.old_baseline_data = self.app.baseline_data.copy()
        else:
            self.new_spectrum = CommandSpectrum(self.app.spectrum.x, self.app.spectrum.y)
            self.old_baseline_data = None
        
    def execute(self):
        """执行基线校正命令"""
        self.app.button_baseline.setText('基线估计')


        self.app.plot1_log.addItem("基线已修正")
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()
        
        self.app.spectrum = self.new_spectrum
        self.app.plot1.clear()
        pen=pg.mkPen(color='k',width=3)        
        self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y,pen=pen)
        self.app.plot1.autoRange()

    def undo(self):
        """撤销基线校正命令"""
        self.app.button_baseline.setText('应用基线校准')
        self.app.button_show_peak_labels.setText('显示标签')
        self.app.button_find_peaks.setText('显示峰值')
        self.app.spectrum = self.old_spectrum
        self.app.baseline_data = self.old_baseline_data # Resture baseline data from before subtraction
        self.app.plot1.clear()
        if self.app.spectrum is not None:
            pen=pg.mkPen(color='k',width=3)        
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y,pen=pen)
        if self.app.baseline_data is not None:
            pen=pg.mkPen(color='r',width=3)
            self.app.baseline_plot = self.app.plot1.plot(self.app.spectrum.x, self.app.baseline_data, pen=pen)
        self.app.plot1.autoRange()

        # Message
        self.app.plot1_log.addItem("基线已恢复")
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()



class CropCommand(Command):
    """裁剪光谱的命令"""
    def __init__(self, app, crop_start_x, crop_end_x):
        self.app = app
        self.crop_start_x = crop_start_x
        self.crop_end_x = crop_end_x
        
        # 如果光谱不为空，备份旧光谱      
        if self.app.spectrum is not None:
            self.old_spectrum = self.app.spectrum.copy()
        else:
            self.old_spectrum = None
        
        self.new_spectrum = self._get_cropped_spectrum()

    def _get_cropped_spectrum(self):
        """获取裁剪后的光谱"""
        indices_to_crop = np.where((self.old_spectrum.x >= self.crop_start_x) & (self.old_spectrum.x <= self.crop_end_x))
        new_y = self.old_spectrum.y.copy()
        new_y[indices_to_crop] = np.nan
        return CommandSpectrum(self.old_spectrum.x, new_y)

    def execute(self):
        """执行裁剪命令"""
        self.app.spectrum = self.new_spectrum
        self.app.plot1.clear()
        pen=pg.mkPen(color='k',width=3)  
        self.app.plot1.plot(*self.app.spectrum,pen=pen)
        self.app.plot1_log.addItem(f'已从{round(self.crop_start_x)}至{round(self.crop_end_x)}(cm^-1)进行光谱裁剪')
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()


    def undo(self):
        """撤销裁剪命令"""
        self.app.spectrum = self.old_spectrum
        self.app.button_baseline.setText('基线估计')
        self.app.button_show_peak_labels.setText('显示标签')
        self.app.button_find_peaks.setText('显示峰值')
        self.app.crop_button.setText("裁剪")
        self.app.plot1.clear()
        if self.app.spectrum is not None:
            pen=pg.mkPen(color='k',width=3)  
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y,pen=pen)
        self.app.plot1_log.addItem(f'光谱裁剪已撤销')
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()

class SmoothSpectrumCommand(Command):
    """光谱平滑处理的命令"""
    def __init__(self, app):
        self.app = app
        if self.app.spectrum is not None:
            self.old_spectrum = self.app.spectrum.copy()  # 备份旧光谱
        else:
            self.old_spectrum = None
        

    def execute(self):
        """执行光谱平滑处理"""
        # 处理 NaN 数据
        valid_indices = ~np.isnan(self.app.spectrum.y)
        valid_x = self.app.spectrum.x[valid_indices]
        valid_y = self.app.spectrum.y[valid_indices]

        # 如果有效数据不足以进行平滑处理，则跳过平滑处理
        if len(valid_y) < 11:
            # 添加平滑处理信息到日志
            self.app.plot1_log.addItem('有效数据点不足，无法进行平滑处理')
            self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
            self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
            self.app.plot1_log.clearSelection()
            return

        # 设置平滑窗口和多项式阶数
        window_length = min(11, len(valid_y))  # 确保窗口长度不超过有效数据的长度
        polyorder = min(3, window_length - 1)  # 多项式阶数应小于窗口长度
        
        smoothed_y = savgol_filter(valid_y, window_length, polyorder)
        # 用平滑后的数据更新光谱数据
        smoothed_spectrum = CommandSpectrum(valid_x, smoothed_y)
        self.app.spectrum = smoothed_spectrum
        self.app.button_baseline.setText('基线估计')
        self.app.button_show_peak_labels.setText('显示标签')
        self.app.button_find_peaks.setText('显示峰值')
        # 更新光谱数据并重新绘制
        self.app.spectrum.y = smoothed_y
        self.app.plot1.clear()
        pen = pg.mkPen(color='k', width=3)  
        self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y, pen=pen)
        self.app.plot1.autoRange()

        # 添加平滑处理信息到日志
        self.app.plot1_log.addItem('已为光谱添加平滑处理')
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()
    
    def undo(self):
        """撤销光谱平滑处理"""
        self.app.button_baseline.setText('基线估计')
        self.app.button_show_peak_labels.setText('显示标签')
        self.app.button_find_peaks.setText('显示峰值')

        self.app.spectrum = self.old_spectrum  # 恢复旧光谱
        if self.app.spectrum is not None:
            self.app.plot1.clear()
            pen = pg.mkPen(color='k', width=3)  
            self.app.plot1.plot(self.app.spectrum.x, self.app.spectrum.y, pen=pen)
            self.app.plot1.autoRange()
        else:
            self.app.plot1.clear()

        self.app.plot1_log.addItem(f'平滑处理已撤销')
        # 选中最后一个项目并滚动到该项目
        self.app.plot1_log.setCurrentRow(self.app.plot1_log.count() - 1)
        self.app.plot1_log.scrollToItem(self.app.plot1_log.currentItem())
        self.app.plot1_log.clearSelection()