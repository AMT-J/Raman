"""该模块包含一个 PlotWidget 的子类，可以进行裁剪"""

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QLabel, QLineEdit, QPushButton, QTextEdit, QGridLayout,QGraphicsRectItem,
                            QFileDialog, QMessageBox, QListWidget, QAbstractItemView, QListView)
from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg

class CroppablePlotWidget(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cropping = False
        self.start_crop_pos = None
        self.crop_region = None
        # Initialize the background and other styles
        self.init_styles()
    def init_styles(self):
        # Set the background color of the plot area to a lighter blue
        self.setBackground('#f5faff')  # Lighter cyan background color

        # Customize the view box's background
        self.getPlotItem().vb.setBackgroundColor('#f5faff')  # Lighter cyan background color

       # Customize the axis labels and tick labels
        for axis in ['left', 'bottom', 'right', 'top']:
            axis_item = self.getPlotItem().getAxis(axis)
            axis_item.setTextPen(pg.mkPen('#000000'))  # Black text for axis labels and ticks
           # Adjust the tick text font and offset to move labels away from the border
            axis_item.setStyle(tickFont=QFont('Microsoft YaHei UI', 10))  # Adjust the offset and font

        self.setStyleSheet("border: 1px solid black;")

    def get_crop_region(self):
        return self.crop_region

    def mousePressEvent(self, event):
        if self.cropping:
            self.start_crop_pos = self.getPlotItem().vb.mapSceneToView(QtCore.QPointF(event.pos())).x()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.cropping:
            self.start_crop_pos = None  # Reset start position
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.cropping:
            if event.buttons() == Qt.MouseButton.LeftButton:  # Check if left mouse button is pressed
                if self.start_crop_pos is not None:
                    end_crop_pos = self.getPlotItem().vb.mapSceneToView(QtCore.QPointF(pos)).x()
                    if self.crop_region is None:
                        self.crop_region = pg.LinearRegionItem([self.start_crop_pos, end_crop_pos], movable=False, brush=pg.mkBrush(128, 128, 128, 100))
                        self.addItem(self.crop_region)
                    else:
                        self.crop_region.setRegion([self.start_crop_pos, end_crop_pos])
                event.accept()
            else:
                event.ignore()
        else:
            super().mouseMoveEvent(event)
