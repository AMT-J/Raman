"""本模块实现了可拖动的散点图，用于离散化和编辑光谱基线"""

import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6 import QtCore
import pyqtgraph as pg

class DraggableScatter(pg.ScatterPlotItem):
    # 定义拖动点和拖动完成的信号
    pointDragged = QtCore.pyqtSignal()
    dragFinished = QtCore.pyqtSignal(int, float, float, float, float) # 信号携带索引和起始、结束坐标

    def __init__(self, *args, **kwargs):
         # 初始化，设置初始拖动的点索引和起始位置
        super().__init__(*args, **kwargs)
        self.draggedPointIndex = None
        self.startPos = None
    
    def mousePressEvent(self, ev):
        """处理鼠标按下事件"""
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:  # 检查是否是左键按下
            pos = ev.pos() # 获取鼠标位置
            points = self.pointsAt(pos)  # 获取当前位置的点
            if points :
                # 如果存在点，保存该点的索引和位置
                self.draggedPointIndex = points[0].index()
                self.startPos = (self.data['x'][self.draggedPointIndex], self.data['y'][self.draggedPointIndex])
            else:
                self.draggedPointIndex = None   # 重置被拖动的点索引

        ev.accept()
        super().mousePressEvent(ev)

    def mouseDragEvent(self, ev):
        """处理鼠标拖动事件"""
        if self.draggedPointIndex is not None:  # 如果有被拖动的点
            pos = ev.pos()   # 获取鼠标当前位置
            self.data['x'][self.draggedPointIndex] = pos.x()
            self.data['y'][self.draggedPointIndex] = pos.y()
            self.setData(x=self.data['x'], y=self.data['y'])  # 更新散点图数据
            self.pointDragged.emit()  # 发送拖动点信号

        ev.accept()  # 接受事件

    def mouseReleaseEvent(self, ev):
        """处理鼠标释放事件"""
        if self.draggedPointIndex is not None:  # 如果有被拖动的点
            endPos = (self.data['x'][self.draggedPointIndex], self.data['y'][self.draggedPointIndex])  # 获取结束位置
            self.dragFinished.emit(self.draggedPointIndex, *self.startPos, *endPos)  # 发送拖动完成信号
        
        self.draggedPointIndex = None   # 重置被拖动的点索引
        ev.accept()
        super().mouseReleaseEvent(ev)


class DraggableGraph(pg.GraphItem):

    def __init__(self, scatter_data):
        """初始化拖动图表，将散点数据转化为图形数据"""
        super().__init__()
        self.scatter_data = scatter_data
        self.graph_data = {
            # 创建图形的邻接矩阵，表示点与点之间的连线
            'adj': np.array([[i, i+1] for i in range(len(scatter_data['x'])-1)], dtype=np.int32),
            'pen': pg.mkPen('r')  # 设置连线颜色为红色
        }
        # 使用散点数据创建图形
        self.setData(pos=np.array(list(zip(self.scatter_data['x'], self.scatter_data['y']))), adj=self.graph_data['adj'], pen=self.graph_data['pen'])

