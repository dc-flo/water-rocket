from datetime import datetime
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit

x_up = pd.read_csv("data\\x_up.csv")
y_up = pd.read_csv("data\\y_up.csv")
z_up = pd.read_csv("data\\z_up.csv")
z_down = pd.read_csv("data\\z_down.csv")
y_down = pd.read_csv("data\\y_down.csv")
x_down = pd.read_csv("data\\x_down.csv")

g = 9.80665

def off(l: list) -> float:
    return -(np.mean([np.mean(x) for x in l]))

def accel_fit(x, m, n):
    return (m*x)+n

def scale(up:list, down:list, other: list) -> float:
    scale = curve_fit(accel_fit, np.append(np.append(up, down), other),
                np.append(np.append(g*np.ones(np.shape(up)), -g*np.ones(np.shape(down))), 0.0*np.ones(np.shape(other))))[0][0]
    offset = off([x*scale for x in other])
    return scale, offset

def calib():
    return {
                "x_scale" : scale(x_up.accX, x_down.accX, y_down.accX)[0],
                "y_scale" : scale(y_up.accY, y_down.accY, z_up.accY)[0],
                "z_scale" : scale(z_up.accZ, z_down.accZ, y_down.accZ)[0],
                "x_offset" : scale(x_up.accX, x_down.accX, y_up.accX)[1],
                "y_offset" : scale(y_up.accY, y_down.accY, z_up.accY)[1],
                "z_offset" : scale(z_up.accZ, z_down.accZ, x_up.accZ)[1],
                "x_goffset" : off([x_up.rotX, x_down.rotX, y_up.rotX, y_down.rotX, z_up.rotX, z_down.rotX]),
                "y_goffset" : off([x_up.rotY, x_down.rotY, y_up.rotY, y_down.rotY, z_up.rotY, z_down.rotY]),
                "z_goffset" : off([x_up.rotZ, x_down.rotZ, y_up.rotZ, y_down.rotZ, z_up.rotZ, z_down.rotZ]),
            }
    

print(calib())