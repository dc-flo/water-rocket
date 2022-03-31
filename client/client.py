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
from sympy import integrate
from kivy.garden.graph import Graph, MeshLinePlot
from kivy.lang import Builder
from kivymd.app import MDApp
import scipy.integrate  

ip = "http://192.168.1.1/"
ap_name = "ESP32-Access-Point"
value_file = "data\\values.csv"
raw_data_file = "data\\raw_data.csv"
rps = 100       #records per seconds
tpr = 1/rps     #time in seconds per record
rec_time = 5    #time in seconds for recording

root = None
graphlayout = None

def short(a: np.array, l: int):
    x = len(a)/l
    arr = []
    for i in range(l):
        arr.append(np.mean(a[int(x*i):int(x*i+1)]))
    return arr

class MyAddButton(Widget):
    
    def addGraph(self):
        graphlayout.remove_widget(self)
        graphlayout.add_widget(MyGraph())
        graphlayout.add_widget(self)


class MyGraph(Widget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        data = pd.read_csv(value_file)
        self.graph = self.children[0].children[1]
        self.graph.xmax = np.max(data.time)
        #self.graph.ymax = np.max(np.abs(data.posX))
        self.plot = MeshLinePlot()
        time = data.time
        pos = data.barheightT1
        self.plot.points = [(time[x], pos[x]) for x in range(len(time))]
        print(self.plot.points)
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
            r = requests.get(ip + "get", timeout=3)
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
        values["accX"] = round(values["accX"] - values["accX"][0], 2)
        values["accY"] = round(values["accY"] - values["accY"][0], 2)
        values["accZ"] = round(values["accZ"] - values["accZ"][0], 2)
        values["rotX"] = round(values["rotX"] - values["rotX"][0], 2)
        values["rotY"] = round(values["rotY"] - values["rotY"][0], 2)
        values["rotZ"] = round(values["rotZ"] - values["rotZ"][0], 2)
        values["time"] = round(values["time"] - values["time"][0], 2)
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
                h.append(round(h[i-1] + (np.log(p[i]/p[i-1])/-((M*g)/(R*T[i]))), 2))
        return h


    def completeValues(self):
        self.println('completing data')
        values = pd.read_csv(value_file)
        values['velX'] = np.round(scipy.integrate.cumulative_trapezoid(values.accX, x=np.divide(values.time, 1000), initial=0), 2)
        values['velY'] = np.round(scipy.integrate.cumulative_trapezoid(values.accY, x=np.divide(values.time, 1000), initial=0), 2)
        values['velZ'] = np.round(scipy.integrate.cumulative_trapezoid(values.accZ, x=np.divide(values.time, 1000), initial=0), 2)
        values['posX'] = np.round(scipy.integrate.cumulative_trapezoid(values.velX, x=np.divide(values.time, 1000), initial=0), 2)
        values['posY'] = np.round(scipy.integrate.cumulative_trapezoid(values.velY, x=np.divide(values.time, 1000), initial=0), 2)
        values['posZ'] = np.round(scipy.integrate.cumulative_trapezoid(values.velZ, x=np.divide(values.time, 1000), initial=0), 2)
        values['rposX'] = np.round(scipy.integrate.cumulative_trapezoid(values.rotX, x=np.divide(values.time, 1000), initial=0), 2)
        values['rposY'] = np.round(scipy.integrate.cumulative_trapezoid(values.rotY, x=np.divide(values.time, 1000), initial=0), 2)
        values['rposZ'] = np.round(scipy.integrate.cumulative_trapezoid(values.rotZ, x=np.divide(values.time, 1000), initial=0), 2)
        values['barheightT1'] = self.barheight(values.press, values.temp1)
        values['barheightT2'] = self.barheight(values.press, values.temp2)
        values.drop(0)
        values.to_csv(value_file, index=False)
        self.println('finished data gathering')

    def printValues(self):
        self.print(pd.read_csv(value_file))

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