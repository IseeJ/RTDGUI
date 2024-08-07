import csv
import sys, os
import time
import datetime as dt
import serial
import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QModelIndex, QObject, QTimer
from PyQt5.QtWidgets import *
from PyQt5.QtGui import * 
import pyqtgraph as pg
from pyqtgraph import PlotWidget, AxisItem, ViewBox
from serial import SerialException
from pathlib import Path

import random
from RTDmainwindow import Ui_MainWindow
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo



#https://realpython.com/python-pyqt-qthread/
#https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/
class DateAxisItem(AxisItem):
    def __init__(self, *args, **kwargs):
        AxisItem.__init__(self, *args, **kwargs)

    def tickStrings(self, values, scale, spacing):
        return [dt.datetime.fromtimestamp(value).strftime("%H:%M:%S\n%Y-%m-%d\n\n") for value in values]

class Worker(QThread):
    result = pyqtSignal(str,tuple,tuple)
    
    def __init__(self, port, interval, baud):
        super().__init__()
        self.ser = None
        self.is_running = True
        self.port = port
        self.interval = interval
        self.baud = baud
        print("Starting Serial")
    """
    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=10000)
            while self.is_running:
                write_time1 = dt.datetime.now()
                interval_dt = dt.timedelta(seconds = self.interval) 
                write_time2 = write_time1 + interval_dt
                while dt.datetime.now() <= write_time2:
                    pass
                
                if self.ser.in_waiting:
                    response = self.ser.readline()
                    if response:
                        RTDdata, temperatures = parse_temp(self,response)
                        now_time = dt.datetime.now()
                        current_time = str(now_time.strftime('%Y%m%dT%H%M%S.%f')[:-3])  
                        print(f"Time: {current_time}, Temperatures: {temperatures}")
                        self.result.emit(current_time,temperatures, RTDdata)
                    else:
                        print("No response")

        except serial.SerialException as e:
            print(f"Serial error: {e}")
        finally:
            if self.ser:
                self.ser.close()
    """
    def run(self):
        while self.is_running:
            write_time1 = dt.datetime.now()
            interval_dt = dt.timedelta(seconds = self.interval) 
            write_time2 = write_time1 + interval_dt
            while dt.datetime.now() <= write_time2:
                pass
            RTDdata, temperatures = parse_temp0(self)
            now_time = dt.datetime.now()
            current_time = str(now_time.strftime('%Y%m%dT%H%M%S.%f')[:-3])  
            print(f"Time: {current_time}, Temperatures: {temperatures}")
            self.result.emit(current_time,temperatures, RTDdata)

    def stop(self):
        self.is_running = False
        if self.ser:
            self.ser.close()
        self.quit()
        self.wait()

def parse_temp0(self):
    RTD1 = 0
    RTD2 = 0
    RTD3 = 0
    RTD4 = 0

    R1 = 0
    R2 = 0
    R3 = 0
    R4 = 0

    T1 = float(random.randint(-170,-160))
    T2 = float(random.randint(-170,-160))
    T3 = float(random.randint(-200,-180))
    T4 = float(random.randint(-200,-180))
    RTDdata = []
    
    RTDdata.append(RTD1)
    RTDdata.append(RTD2)
    RTDdata.append(RTD3)
    RTDdata.append(RTD4)
    
    RTDdata.append(R1)
    RTDdata.append(R2)
    RTDdata.append(R3)
    RTDdata.append(R4)

    temperatures = []
    temperatures.append(T1)
    temperatures.append(T2)
    temperatures.append(T3)
    temperatures.append(T4)
    return tuple(RTDdata), tuple(temperatures)
    
def parse_temp(self,response):
    line = str(response.decode('utf-8').strip())

    parts = line.split(',')
    RTD1 = parts[0]
    RTD2 = parts[1]
    RTD3 = parts[2]
    RTD4 = parts[3]

    R1 = parts[4]
    R2 = parts[5]
    R3 = parts[6]
    R4 = parts[7]

    T1 = float(parts[8])
    T2 = float(parts[9])
    T3 = float(parts[10])
    T4 = float(parts[11])
    RTDdata = []
    
    RTDdata.append(RTD1)
    RTDdata.append(RTD2)
    RTDdata.append(RTD3)
    RTDdata.append(RTD4)
    
    RTDdata.append(R1)
    RTDdata.append(R2)
    RTDdata.append(R3)
    RTDdata.append(R4)

    temperatures = []
    temperatures.append(T1)
    temperatures.append(T2)
    temperatures.append(T3)
    temperatures.append(T4)
    
    return tuple(RTDdata), tuple(temperatures)

class TempModel(QObject):
    dataChanged = pyqtSignal()

    def __init__(self, parent=None):
        super(TempModel, self).__init__(parent)
        self.data = []

    def lenData(self, parent=QModelIndex()):
        return len(self.data)

    def appendData(self, time, *temps):
        self.data.append((time,) + temps)
        self.dataChanged.emit()

    def clearData(self):
        self.data = []
        self.dataChanged.emit()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            row = index.row()
            return self.data[row]

    def reset(self):
        self.data = []
        return None

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowIcon(QIcon('logo.png'))
        self.worker = None
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.startStopButton.pressed.connect(self.toggleRun)
        self.ui.clearButton.pressed.connect(self.clearPlot)
        self.ui.LogButton.pressed.connect(self.startLogging)
        self.ui.refreshButton.pressed.connect(self.refreshSerialPorts)
        self.ui.saveDirectoryButton.pressed.connect(self.chooseSaveDirectory)

        self.model = TempModel()
        self.initGraph()
        self.filename = None
        self.serialPort = None
        self.saveDirectory = None
        self.interval = 1 #2 sec default
        self.baud = 9600
        
    def initFile(self):
        now = dt.datetime.now()
        self.filename = "temp_log_" + str(now.strftime('%Y%m%dT%H%M%S')) + ".csv"
        try:
            with open(f"{self.saveDirectory}/{self.filename}", 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Time', 'RTD1', 'RTD2', 'RTD3', 'RTD4', 'R1', 'R2', 'R3', 'R4', 'T1', 'T2', 'T3', 'T4'])
        except Exception as e:
            print(f"Error opening file: {e}")

    def initGraph(self):
        self.ui.graphWidget.setBackground("w")
        styles = {"color": "black", "font-size": "18px"}
        self.ui.graphWidget.setLabel("left", "Temperature (°C)", **styles)
        self.ui.graphWidget.setLabel("bottom", "Time", **styles)
        self.ui.graphWidget.getAxis('bottom').setStyle(tickTextOffset=10)
        self.ui.graphWidget.setAxisItems({'bottom': DateAxisItem(orientation='bottom')})
        self.ui.graphWidget.showGrid(x=True, y=True, alpha=0.4)
        self.time = []
        self.data = [[] for _ in range(8)]
        self.plotLines = []
        self.colors = [(183, 101, 224), (93, 131, 212), (49, 205, 222), (36, 214, 75)]
        for i in range(4):
            plot_line = self.ui.graphWidget.plot(self.time, self.data[i], pen=pg.mkPen(color=self.colors[i], width=2))
            self.plotLines.append(plot_line)

    def toggleRun(self):
        if self.worker is not None:
            self.stopRun()
        else:
            self.startRun()

    def startRun(self):
        self.serialPort = self.ui.ComboBox_1.currentText()
        self.baud = int(self.ui.ComboBox_2.currentText())
        
        if 'COM' not in self.serialPort:
            self.serialPort = "/dev/" + self.ui.ComboBox_1.currentText()
    
        print(f"Connected to: {self.serialPort}")
        print(f"Set baud rate to: {self.baud}")
        
        if self.serialPort is None:
            print(self, "No port selected")
            return
            
        try:
            self.interval = int(self.ui.intervalInput.text())
            print(f"Using input interval: {self.interval} seconds")
        except ValueError:
            print("Using default interval: 2 seconds")
            self.interval = 2

        try:
            self.worker = Worker(self.serialPort, self.interval, self.baud)
            self.worker.result.connect(self.updateData)
            self.worker.start()
            print("Starting Worker")
        except serial.SerialException as e:
            print(f"Could not open serial port: {e}")
            self.worker = None

    def stopRun(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
            print("Stopping Serial")

    def clearPlot(self):
        self.time = []
        self.data = [[] for _ in range(8)]
        for i in range(8):
            self.plotLines[i].setData(self.time, self.data[i])

    def startLogging(self):
        self.initFile()
        self.ui.fileLabel.setText(f"{self.saveDirectory}/{self.filename}")
 
    def refreshSerialPorts(self):
        self.ui.ComboBox_1.clear()
        ports = QSerialPortInfo.availablePorts()
        for port in ports:
            self.ui.ComboBox_1.addItem(port.portName())

    def chooseSaveDirectory(self):
        self.saveDirectory = QFileDialog.getExistingDirectory(self, "Save Directory")
        if self.saveDirectory:
            self.ui.fileLabel.setText(f"{self.saveDirectory}")

    @pyqtSlot(str, tuple, tuple)
    def updateData(self, current_time, temperatures, RTDdata):
        for i in range(4):
            if temperatures[i] != 'err':
                self.ui.labels[i].setText(f"T{i + 1}: {temperatures[i]}")
                if temperatures[i] <= -185.8:
                    self.ui.labels[i].setStyleSheet(f"font-weight: bold; font-size: 14px; color: black; background-color: yellow; border: 1px solid black;")
                else:
                    self.ui.labels[i].setStyleSheet(f"font-weight: bold; font-size: 14px; color: black; background-color: white; border: 1px solid black;")
            else:
                self.ui.labels[i].setText(f"T{i + 1}: err")

        active_ch = tuple(temperatures[i] if self.ui.checkboxes[i].isChecked() else np.nan for i in range(4))
        self.model.appendData(current_time, *active_ch)

        formattime = dt.datetime.strptime(current_time, '%Y%m%dT%H%M%S.%f').timestamp()
        self.time.append(formattime)

        for i in range(4):
            self.data[i].append(temperatures[i])
            if self.ui.checkboxes[i].isChecked():
                self.plotLines[i].setData(self.time, self.data[i])

        if self.filename:
            self.LogData(current_time, temperatures, RTDdata)

    def LogData(self, timestamp, temperatures, RTDdata):
        try:
            with open(f"{self.saveDirectory}/{self.filename}", 'a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([timestamp] + list(RTDdata)+list(temperatures))
        except Exception as e:
            print(f"Error writing to file: {e}")

app = QApplication(sys.argv)
path = os.path.join(os.path.dirname(sys.modules[__name__].__file__), 'RTDicon.PNG')

app.setWindowIcon(QIcon(path))
window = MainWindow()
window.show()
app.exec_()
