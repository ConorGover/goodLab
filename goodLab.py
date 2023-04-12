# This program is currently in pre-pre-pre-alpha. Don't try to use it yet.

# Performs discharge tests on batteries. Discharges at constant current with periodic high-current pulses.
# Discharge continues until the battery voltage falls below a preset threshold.
#   At that point the discharge capacity is recorded.
# Waveform data from each pulse is saved to the oscilliscope's hard drive.
#   The pulse data can be analyzed to determine the impedance of the battery.

# This program is designed to work with a Tektronix oscilloscope and a Keithley electronic load.
# The oscilloscope must be connected to the same LAN as the computer running this program.
# The load must be connected to the computer via USB.
#   The computer must have the Keithley I/O Layer installed.(https://www.tek.com/en/support/software/application/850c10)


import sys
import subprocess
from typing import NamedTuple
from time import sleep
import pyvisa

rm = pyvisa.ResourceManager()

class Settings(NamedTuple):
    min_v: float = 2.5

class Load:
    def __init__(self):
        self.com_port = None
        self.load = None
        try:
            self.list = rm.list_resources()
            first3 = ''
            n = 0
            while first3 != 'USB':
                first3 = self.list[n][0:3]
                n += 1
        except:
            raise Exception('Ensure electronic load is powered on and connected to computer.')
        self.com_port = self.list[n-1]
        self.load = rm.open_resource(self.com_port)
        sleep(0.5)
        # TODO: set up list file on load

    def trigger(self):
        self.load.write('*TRG')
    
class Oscope:
    def __init__(self):
        self.name = None
        self.oscope = None
        try:
            self.list = rm.list_resources()
            first3 = ''
            n = 0
            while first3 != 'TCP':
                first3 = self.list[n][0:3]
                n += 1
        except:
            raise Exception("can't find")
        self.name = self.list[n-1]
        self.oscope = rm.open_resource(self.name)
        sleep(0.5)

    def recall_setup(self,setup_name):
        self.oscope.write(f"RECAll:SETUp {setup_name}")     # TODO: fill in path

    def cd(self,dir):
        self.oscope.write(f"FILES:CWD {dir}")

    def mkdir(self,dir):
        self.oscope.write(f"FILES:MKDIR {dir}")

    def save_waveforms(self,filename):
        self.oscope.write(f"SAVE:WAVEFORM ALL, \"{filename}.wfm\"")
        self.oscope.write(f"SAVe:IMAGe, \"{filename}.png\"")
        
    def min(self):
        min = float(self.oscope.query('MEASUrement:MEAS:RESUlts:CURRentacq:MINimum?'))
        return min
    
scope = Oscope()
scope.cd('C:\\Users\\Public\\Desktop\\Battery testing\\')  # TODO

load = Load()

while True:
    cell_num = int(input('Enter cell number: '))
    # create a folder for that cell
    scope.mkdir(f'cell_{cell_num}')
    scope.cd(f'cell_{cell_num}')
    load.trigger()

    while min_v > Settings.min_v:
        sleep(11)       # TODO: wait until scope has been triggered
        min_v = scope.min()
        print(f'minimum voltage: {min_v}')
    
    scope.cd('../')
