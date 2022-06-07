import math
import sys
import requests
import re
import pandas as pd
import numpy as np
from kivy.app import App
from kivy.uix.widget import Widget
import threading
from kivy.clock import Clock
from kivy.properties import ObjectProperty, NumericProperty
import subprocess
import os
from kivy.config import Config
from kivy.garden.graph import Graph, MeshLinePlot
from kivy.lang import Builder
import scipy.integrate
import vector
from calib import calib
import webbrowser

ip = "http://192.168.1.1/"
ap_name = "ESP32-Access-Point"
value_file = "data\\values.csv"
raw_data_file = "data\\raw_data.csv"
rps = 100       #recordings per seconds
tpr = 1/rps     #time in seconds per recording
rec_time = 20    #time in seconds for recording
cal = calib()
g = 9.80665

root = None
graphlayout = None

class MyAddButton(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.x_input = ObjectProperty(None)
        self.y_input = ObjectProperty(None)
        self.y_min = ObjectProperty(None)
        self.y_max = ObjectProperty(None)

    def addGraph(self):
        graphlayout.remove_widget(self)
        graphlayout.add_widget(MyGraph(self.x_input.text, self.y_input.text, self.y_min.text, self.y_max.text))
        graphlayout.add_widget(self)

class MyGraph(Widget):
    def __init__(self, x, y, ymin, ymax, **kwargs):
        super().__init__(**kwargs)
        self.createGraph(x, y, ymin, ymax)

    def createGraph(self, nx, ny, ymin, ymax):
        data = pd.read_csv(value_file)
        self.graph = self.children[0].children[1]
        self.plot = MeshLinePlot()
        if nx == "" or ny == "":
            self.plot.points = []
            self.graph.add_plot(self.plot)
            self.graph.ymax = int(ymax) if ymax != "" else math.ceil(np.max(y)) if math.ceil(np.max(y)) > 0 else 0
            self.graph.ymin = int(ymin) if ymin != "" else math.floor(np.min(y)) if math.floor(np.min(y)) < 0 else 0
            return
        x = data[nx]
        y = data[ny]
        self.graph.xmax = np.max(x)
        self.graph.ymax = int(ymax) if ymax != "" else math.ceil(np.max(y)) if math.ceil(np.max(y)) > 0 else 0
        self.graph.ymin = int(ymin) if ymin != "" else math.floor(np.min(y)) if math.floor(np.min(y)) < 0 else 0
        self.graph.xlabel = nx
        self.graph.ylabel = ny
        self.plot.points = [(x[i], y[i]) for i in range(len(x))]
        self.graph.add_plot(self.plot)

    def deleteSelf(self):
        graphlayout.remove_widget(self)

class MyGridLayout(Widget):
    
    loglabel = ObjectProperty(None)
    gridheight = NumericProperty(1000)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        global graphlayout, gridheight
        graphlayout = self.ids.graphlayout

    def connectToWifi(self):
        if os.system(f'cmd /c "netsh wlan connect name=\"{ap_name}\""') == 1:
            self.println('failed connecting to esp hotspot, try connecting manualy', 'error')
        else:
            self.println('connected to hotspot successfully')

    def start(self):
        if self.checkWifi():
            requests.get(ip + f'start?rec_time={rec_time}&rps={rps}')
            self.println(f'started recording data for {rec_time} seconds . . .')
            evt = Clock.schedule_interval(lambda dt: self.print('. '), 1)
            Clock.schedule_once(lambda dt: evt.cancel(), rec_time)
            Clock.schedule_once(lambda dt: self.println('finished recording'), rec_time)

    def checkWifi(self):
        if ap_name in subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces']).decode('utf-8', errors ="backslashreplace"):
            return True
        else:
            self.println('connection error, make sure the device is connected to the esp hotspot', 'error')
            return False

    def getValues(self):
        threading.Thread(target=self.getValuesThread).start()
    
    def getValuesThread(self):
        self.println('try to download data from esp32 . . .')
        try:
            r = requests.get(ip + "get")
        except:
            self.println('failed to download data, check connection!')
            sys.exit()
        
        self.println('successfully downloaded data')
        self.println('writing to raw file')
        file = open(raw_data_file, "w")
        file.write(re.sub("(\r\n)+", "\n", r.text))
        file.close()
        self.correctValues()

    def correctValues(self):
        self.println('correcting data')
        values = pd.read_csv(raw_data_file)
        values["accX"] = [(cal["x_scale"]*x) + cal["x_offset"] for x in values["accX"]]
        values["accY"] = [(cal["y_scale"]*x) + cal["y_offset"] for x in values["accY"]]
        values["accZ"] = [(cal["z_scale"]*x) + cal["z_offset"] for x in values["accZ"]]
        values["rotX"] = [x+cal["x_goffset"] for x in values["rotX"]]
        values["rotY"] = [x+cal["y_goffset"] for x in values["rotY"]]
        values["rotZ"] = [x+cal["z_goffset"] for x in values["rotZ"]]
        values["time"] = values["time"] - values["time"][0]
        values.drop(values.tail(1).index, inplace=True)
        values.to_csv(value_file, index=False)
        self.completeValues()

    def barheight(self, p, T):
        M = 0.02869
        g = 9.807
        R = 8.314
        h = []
        T = np.add(T, 273.15)

        for i in range(len(p)):
            if i == 0:
                h.append(0)
            else:
                h.append(h[i-1] + (np.log(p[i]/p[i-1])/-((M*g)/(R*T[i]))))
        return h

    def completeValues(self):
        self.println('completing data')
        values = pd.read_csv(value_file)
        values['rposX'] = scipy.integrate.cumulative_trapezoid(values.rotX, x=np.divide(values.time, 1000), initial=0)
        values['rposY'] = scipy.integrate.cumulative_trapezoid(values.rotY, x=np.divide(values.time, 1000), initial=0)
        values['rposZ'] = scipy.integrate.cumulative_trapezoid(values.rotZ, x=np.divide(values.time, 1000), initial=0)
        values['velX'] = scipy.integrate.cumulative_trapezoid(values.accX, x=np.divide(values.time, 1000), initial=0)
        values['velY'] = scipy.integrate.cumulative_trapezoid(values.accY, x=np.divide(values.time, 1000), initial=0)
        values['velZ'] = scipy.integrate.cumulative_trapezoid(values.accZ, x=np.divide(values.time, 1000), initial=0)
        values['posX'] = scipy.integrate.cumulative_trapezoid(values.velX, x=np.divide(values.time, 1000), initial=0)
        values['posY'] = scipy.integrate.cumulative_trapezoid(values.velY, x=np.divide(values.time, 1000), initial=0)
        values['posZ'] = scipy.integrate.cumulative_trapezoid(values.velZ, x=np.divide(values.time, 1000), initial=0)
        taccX = []
        taccY = []
        taccZ = []
        for i in range(len(values.accX)):
            v = vector.obj(x=values.accX[i], y=values.accY[i], z=values.accZ[i])
            v = v.rotateX(values.rposX[i])
            v = v.rotateY(values.rposY[i])
            v = v.rotateZ(values.rposZ[i])
            taccX.append(v.x)
            taccY.append(v.y)
            taccZ.append(v.z)
        values['taccX'] = taccX
        values['taccY'] = taccY
        values['taccZ'] = taccZ
        values.taccZ = np.subtract(values.taccZ, g)
        values['tvelX'] = scipy.integrate.cumulative_trapezoid(values.taccX, x=np.divide(values.time, 1000), initial=0)
        values['tvelY'] = scipy.integrate.cumulative_trapezoid(values.taccY, x=np.divide(values.time, 1000), initial=0)
        values['tvelZ'] = scipy.integrate.cumulative_trapezoid(values.taccZ, x=np.divide(values.time, 1000), initial=0)
        values['tposX'] = scipy.integrate.cumulative_trapezoid(values.tvelX, x=np.divide(values.time, 1000), initial=0)
        values['tposY'] = scipy.integrate.cumulative_trapezoid(values.tvelY, x=np.divide(values.time, 1000), initial=0)
        values['tposZ'] = scipy.integrate.cumulative_trapezoid(values.tvelZ, x=np.divide(values.time, 1000), initial=0)

        values['barheightT1'] = self.barheight(values.press, values.temp1)
        values['barheightT2'] = self.barheight(values.press, values.temp2)
        values.drop(0)
        values.to_csv(value_file, index=False)
        self.println('finished data gathering')

    def printValues(self):
        self.print(pd.read_csv(value_file))
    
    def openValues(self):
        webbrowser.open(value_file)

    def println(self, text, type='info'):
        if type == 'info':
            self.loglabel.text = self.loglabel.text + f'{text}\n'
        if type == 'warning':
            self.loglabel.text = self.loglabel.text + f'[color=f7f72a]{text}[/color]\n'
        if type == 'error':
            self.loglabel.text = self.loglabel.text + f'[color=ff3333]{text}[/color]\n'
    
    def print(self, text, type='info'):
        if type == 'info':
            self.loglabel.text = self.loglabel.text + f'{text}'
        if type == 'warning':
            self.loglabel.text = self.loglabel.text + f'[color=f7f72a]{text}[/color]'
        if type == 'error':
            self.loglabel.text = self.loglabel.text + f'[color=ff3333]{text}[/color]'
    
    def log_clear(self):
        self.loglabel.text = ""
        
class MyApp(App):
    def on_stop(self):
        self.root.stop.set()

    def build(self):
        global root
        Builder.load_file('layout.kv')
        Config.set('graphics', 'window_state', 'maximized')
        root = MyGridLayout()
        return root

def main():
    MyApp().run()
    
main()