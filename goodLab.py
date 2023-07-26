from time import sleep
import pyvisa
import os
import csv
from datetime import datetime
import sys

Settings = {
    "group_name" : "G7_2023",
    # test parameters
    "v_min" : 2.5,
    "v_max" : 4.2,
    "i_sequence" : [[10, 0],[20, 20]],    # [[i0, i1, i2...], [t0, t1, t2...]] in A and s respectively
    "slew_rate" : 0.1,      # A/us
    # oscilloscope settings
    "v_channel" : 1,    # which Oscope channel is measuring cell voltage?
    "i_channel" : 2,    # which Oscope channel is connected to current monitor output on the load?
    "i_scale_factor" : 3,   # scale factor for current monitor output from load
}

def debug(str, forcePrint = False):
    log(str)
    if '-v' in sys.argv or forcePrint:
        print(str)
    return

def log(str):
    dt_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    with open("log.txt", "a") as logFile:
        logFile.write(f'{dt_str}: {str}\n')

def errors(str_list, source = ''):
    for str in str_list:
        str = f'ERROR:{source}: {str}'
        log(str)
        print(str)
    return

class Load:
    def __init__(self, load_res):
        self.load_res = load_res

        self.write('*RST')      # reset to default settings
        self.write('FUNCtion:MODE FIXed')       # it has to be in fixed mode to set up the list
        self.write('FUNCtion CURRent')      # set to constant current mode
        self.write('CURRent 0')     # set current to 0 A so we don't have current flowing before we start running through the list
        self.write('LIST:SLOWrate 0')    # this determines the units for the slew rate. 0: A/us, 1: A/ms
        irange = max(Settings['i_sequence'][0])    # set the range so that it includes the max current we want
        self.write(f'LIST:RANGE {irange}')
        self.write('LIST:COUNt 1')      # we only want to run through the list 1 time
        num_steps = len(Settings['i_sequence'][0])   # number of steps in the list
        self.write(f'LIST:STEP {num_steps}')
        for i in range(1, num_steps + 1):
            self.write(f"LIST:LEVel {i}, {Settings['i_sequence'][0][i-1]}")     # amplitude (A)
            self.write(f"LIST:WIDth {i}, {Settings['i_sequence'][1][i-1]}")     # duration (s)
            self.write(f"LIST:SLEW:BOTH {i}, {Settings['slew_rate']}")        # slew rate (A/us)
        self.write('FUNCtion:MODE LIST')    # now we can switch to list mode
        self.write('TRIGger:SOURce BUS')    # we want to trigger the load over VISA

    def write(self, str:str):
        debug(f'    sending to load: {str}')
        self.load_res.write(str)
        sleep(0.1)
        err = self.ll_query('SYSTem:ERRor?').split(',')
        while (err[0] != '0'):
            errors(err, 'load')
            sleep(0.1)
            err = self.ll_query('SYSTem:ERRor?')

    def ll_query(self, str:str):
        debug(f'    asking load: {str}')
        reply = self.load_res.query(str)
        debug(f'    load replied: {reply}')
        return reply

    def trigger(self):
        self.write('INP 1')     # we have to enable input, otherwise it'll run through the list but not actually draw any current
        self.write('*TRG')    # this starts the list
        sleep(sum(Settings['i_sequence'][1]) + 1.5)   # wait for the list to finish
        self.write('INP 0')    # disable input again just to be safe

    def i(self):
        i = float(self.ll_query('FETCh:CURRent?'))
        return i
    
    def v(self):
        v = float(self.ll_query('FETCh:VOLTage?'))
        return v
    
class Oscope:
    def __init__(self, scope_res):
        self.scope_res = scope_res
        self.prev_settings = self.get_current_settings()

    def write(self, str:str):
        debug(f'    sending to scope: {str}')
        self.scope_res.write(str)
        self.scope_res.write('*OPC')    # tell it to let us know when it's done processing the command
        errors = done = False
        while not done:
            sleep(0.1)
            esr = int(self.ll_query('*ESR?'))    # check the event status register (this also clears it)
            if esr & 0b00111100 != 0:   # bits 2-5 represent errors
                errors = True
                errs = self.ll_query('ALLEV?')   # get the error messages
                errs = errs.split(',')
                errors(errs, 'scope')
            done = bool(esr & 0b1)  # when bit 0 is set it means it's finished processing the command
        return errors
    
    def ll_query(self, str:str):
        debug(f'    asking scope: {str}')
        reply = self.scope_res.query(str)
        debug(f'    scope replied: {reply}')
        return reply
    
    def get_current_settings(self):
        return self.scope_res.query('SET?')
    
    def restore_settings(self, settings = ''):
        if settings == '':
            settings = self.prev_settings
        self.scope_res.write(settings)
    
    def query_value(self, scpi_str:str):
        reply_str = self.ll_query(scpi_str)
        reply_str = reply_str.split('E')   # it sometimes returns values in scientific notation
        if len(reply_str) == 2:
            value = float(reply_str[0]) * (10 ** int(reply_str[1]))
        else:
            value = float(reply_str[0])
        return value
    
    def times_triggered(self):
        return int(self.ll_query('ACQuire:NUMACq?'))

    def set_acq_duration_s(self, secs:float):
        secs = secs + 1
        sec_per_div = secs / 10
        self.write(f'HORizontal:MODE:SCAle {sec_per_div:.4E}')
        div_per_sec = 1 / sec_per_div
        self.write(f'HORizontal:POSition {(0.5 * div_per_sec):.4E}')

    def set_v_range(self, channel:int, v_min:float, v_max:float):
        v_range = v_max - v_min
        v_per_div = v_range / 10
        self.write(f'CH{channel}:SCAle {v_per_div:.4E}')
        pos_offset = -1 * (5 + v_min / v_per_div)
        if -10 < pos_offset < 10:
            self.write(f'CH{channel}:POSition {-1 * (5 + v_min / v_per_div)}')
        else:
            self.write(f'CH{channel}:OFFSET {(v_range / 2 + v_min):.4E}')

    def measure_resistance_at(self, step:int, freq:float):
        t_values = [0]
        for i in range(len(Settings['i_sequence'][1])):
            t_values.append(t_values[i] + Settings['i_sequence'][1][i])

        a_time = t_values[step] - (0.5 / freq)
        b_time = t_values[step] + (0.5 / freq)
        self.write(f'DISplay:WAVEView1:CURSor:CURSOR1:VBArs:APOSition {a_time:.4E}')
        self.write(f'DISplay:WAVEView1:CURSor:CURSOR1:VBArs:BPOSition {b_time:.4E}')
        dv = -(self.query_value('DISplay:WAVEView1:CURSor:CURSOR1:HBArs:DELTa?'))

        i_values = [0] + Settings['i_sequence'][0] + [0]
        di = i_values[step + 1] - i_values[step]

        return dv / di
    
    def measure_resistance_over(self, step:int):
        t_values = [0]
        for i in range(len(Settings['i_sequence'][1])):
            t_values.append(t_values[i] + Settings['i_sequence'][1][i])

        a_time = t_values[step] - 1e-3
        b_time = t_values[step + 1] - 1e-3
        self.write(f'DISplay:WAVEView1:CURSor:CURSOR1:VBArs:APOSition {a_time:.4E}')
        self.write(f'DISplay:WAVEView1:CURSor:CURSOR1:VBArs:BPOSition {b_time:.4E}')
        dv = self.query_value('DISplay:WAVEView1:CURSor:CURSOR1:HBArs:DELTa?')

        i_values = [0] + Settings['i_sequence'][0] + [0]
        di = i_values[step + 1] - i_values[step]

        return dv / di
        
    def min(self):
        min = self.query_value('MEASUrement:MEAS:RESUlts:CURRentacq:MINimum?')
        return min

    def recall_setup(self, setup_name:str):
        self.write(f'RECAll:SETUp "{setup_name}"')

    def cd(self, dir:str):
        self.write(f'FILES:CWD "{dir}"')

    def mkdir(self, dir:str):
        self.write(f'FILES:MKDIR "{dir}"')

    def save_waveforms(self, filename:str):
        self.write(f'SAVE:WAVEFORM CH{Settings["v_channel"]}, "{filename}_V.mat"')
        self.write(f'SAVE:WAVEFORM CH{Settings["i_channel"]}, "{filename}_I.mat"')


#############################################################################################################


rm = pyvisa.ResourceManager()

visa_list = rm.list_resources()    # find all connected VISA instruments
load_res = scope_res = {}
for i in range(len(visa_list)):
    try:
        instr = rm.open_resource(visa_list[i])
        try:
            if load_res == {}:
                instr.query('source:current?')      # if it has a current setting, it's probably the load
                i_source = instr.query('*IDN?')
                debug(f'Found load: {i_source}', True)
                load_res = instr
        except:
            try:
                if scope_res == {}:
                    instr.query('*ESR?')    # the scope will have errors from the previous source command, this clears them
                    instr.query('ALLEV?')
                    oscope_id = instr.query('*IDN?')        # if it's a VISA instrument and it's not the load, we'll assume it's the scope
                    debug(f'Found oscilloscope: {oscope_id}', True)     # there should be a better way to do this but this'll work ¯\_(ツ)_/¯
                    scope_res = instr
            except:
                errors([f"Couldn't read ID from {visa_list[i]}. ¯\_(ツ)_/¯"])
    except:
        debug(f'{visa_list[i]} is not a VISA instrument. Skipping...')      # any serial ports will show up even if they're not VISA instruments
    
scope = Oscope(scope_res)
load = Load(load_res)

try:
    path = os.path.dirname(os.path.realpath(__file__))      # get the path this Python file is in
    scope.cd(path)
    scope.recall_setup('scope_setup.set')
    scope.write('HORizontal:MODE MANual')    # manual mode allows us to set the acquisition time precisely
    duration_s = sum(Settings['i_sequence'][1])     # add up the time values to get the total duration
    scope.set_acq_duration_s(duration_s)
    scope.set_v_range(Settings['v_channel'], Settings['v_min'], Settings['v_max'])
    scope.set_v_range(Settings['i_channel'], -0.1, (max(Settings['i_sequence'][0]) / Settings['i_scale_factor']) + 1)

    if not os.path.exists(f"{path}\{Settings['group_name']}"):     # make a folder for the data if it doesn't already exist
        scope.mkdir(f"{Settings['group_name']}")
    scope.cd(f"{path}\{Settings['group_name']}")

    cell_data = []
    if not os.path.exists(f"{Settings['group_name']}.csv"):     # make a CSV file for the data if it doesn't already exist
        with open(f"{Settings['group_name']}.csv", 'w') as csvfile:
            csvfile.write('num,v0,res_st,res_lt\n')
            header = ['num','v0', 'res_st', 'res_lt']
    else:
        with open(f"{Settings['group_name']}.csv", 'r') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)
            for row in reader:
                cell = {header[i]: float(value_str) for i, value_str in enumerate(row)}
                cell_data.append(cell)
        debug(f'Loaded previous test data for {len(cell_data)} cells.', True)

#########################################################################################################################

    while True:
        cell_num = int(input('\nEnter cell number: '))
        try:
            all_lt_res = [cell['res_lt'] for cell in cell_data]
            mean_lt_res = sum(all_lt_res) / len(all_lt_res)
        except:
            mean_lt_res = 0
        v0 = load.v()
        inp = {}
        if v0 - max(Settings['i_sequence'][0]) * mean_lt_res < Settings['v_min']:
            while inp != 'Y' and inp != 'y' and inp != 'N' and inp != 'n':
                inp = input(f'Cell voltage is only {v0:.2f}. It may drop below the minimum of {Settings["v_min"]:.2f}. Continue? [Y/N]')
        if inp == 'Y' or inp == 'y' or inp == {}:
            # scope.mkdir(f'cell_{cell_num:03d}')     # make a folder for the cell
            # scope.cd(f'cell_{cell_num:03d}')    # and switch to it

            times = scope.times_triggered()
            load.trigger()
            if not scope.times_triggered() > times:
                errors(['Oscilloscope was not triggered.'], 'scope')
            else:
                scope.save_waveforms(f'cell_{cell_num:03d}_{datetime.now().strftime("%Y-%m-%d  %H-%M-%S")}')

                dip_v = scope.min()
                if dip_v < Settings['v_min']:
                    debug(f'OMG! Cell voltage dipped to {dip_v:.2f} which is below minimum!', True)

                res_st = scope.measure_resistance_at(1, 2000)
                res_lt = scope.measure_resistance_over(0)
                cell_data.append({"num": cell_num, "v0": v0, "res_st": res_st, "res_lt": res_lt})
                with open(f"{Settings['group_name']}.csv", 'a', newline = '') as csvfile:
                    writer = csv.writer(csvfile)
                    csvRow = []
                    for i in range(len(header)):
                        if header[i] == 'num':
                            csvRow.append(f"{cell_data[-1]['num']:03d}")
                        else:
                            csvRow.append(f'{cell_data[-1][header[i]]}')
                    writer.writerow(csvRow)
                cells_tested = len(cell_data)
                cell_data_sorted_st = sorted(cell_data, key=lambda k: k['res_st'], reverse = True)
                cell_data_sorted_lt = sorted(cell_data, key=lambda k: k['res_lt'], reverse = True)
                # find the rank of the current cell
                rank_st = rank_lt = 0
                for i in range(cells_tested):
                    if cell_data_sorted_st[i]['num'] == cell_num:
                        rank_st = i + 1
                    if cell_data_sorted_lt[i]['num'] == cell_num:
                        rank_lt = i + 1
                print(f'              2 kHz             {Settings["i_sequence"][1][0]} sec')
                print(f'Resistance: {res_st * 1000 :.3f}e-3         {res_lt * 1000 :.3f}e-3')
                print(f'Rank:        {rank_st} of {cells_tested}            {rank_lt} of {cells_tested}')
                print(f'Percentile:   {(cells_tested - rank_st) / (cells_tested - 1) * 100:.0f}%               {(cells_tested - rank_lt) / (cells_tested - 1) * 100:.0f}%\n')

                # scope.cd('..')      # go back up a directory

finally:
    load.write('INP 0')
    scope.restore_settings()
