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
Config.set('graphics', 'window_state', 'maximized')

ip = "http://192.168.4.1/"
ap_name = "ESP32-Access-Point"
value_file = "data\\values.csv"
raw_data_file = "data\\raw_data.csv"
rps = 100       #records per seconds
tpr = 1/rps     #time in seconds per record
rec_time = 5    #time in seconds for recording

root = None
graphlayout = None

class MyAddButton(Widget):
    
    def addGraph(self):
        graphlayout.remove_widget(self)
        graphlayout.add_widget(MyGraph())
        graphlayout.add_widget(self)


class MyGraph(Widget):
    pass

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
        values.to_csv(value_file, index=False)
        self.completeValues()

    def integrate(self, vals:list) -> list:
        ivals = []
        for i in range(len(vals)):
            ivals.append(round(vals[i]*tpr + np.sum(ivals[0:i]), 2))
        return ivals

    def completeValues(self):
        self.println('completing data')
        values = pd.read_csv(value_file)
        values['velX'] = self.integrate(values['accX'])
        values['velY'] = self.integrate(values['accY'])
        values['velZ'] = self.integrate(values['accZ'])
        values['posX'] = self.integrate(values['velX'])
        values['posY'] = self.integrate(values['velY'])
        values['posZ'] = self.integrate(values['velZ'])
        values['rposX'] = self.integrate(values['rotX'])
        values['rposY'] = self.integrate(values['rotY'])
        values['rposZ'] = self.integrate(values['rotZ'])
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
        root = MyGridLayout()
        return root

def main():
    MyApp().run()
    
main()