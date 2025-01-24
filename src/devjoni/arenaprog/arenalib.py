'''Python library for the controlling the arena9
'''

import os
import platform

import serial


class FakeSerial:
    def write(self, message):
        return f'fakeserial: {message}'
    def readline(self):
        return ''

def _say(ser, message):
    ser.write(message.encode('ASCII'))
    return ser.readline()

def detect_controller_devices():
    devs = []

    system = platform.system()
    if system == "Linux":
        devs = [os.path.join('/dev', fn) for fn in os.listdir(
            '/dev') if fn.startswith('ttyACM')]
    elif system== "Windows":
        coms = [f'COM{i}' for i in range(256)]
        for com in coms:
            try:
                ser = serial.Serial(com, 9600)
                ser.close()
                devs.append(com)
            except:
                pass
    else:
        raise NotImplementedError(f'Unkown system: {system}')
    return devs


def toggle_led(ser, i_led, value):
    leds_off = ['a', 'b', 'c', 'd', 'e', 'f']
    leds_on = ['A', 'B', 'C', 'D', 'E', 'F']
    
    if not 0 <= i_led <= len(leds_off)-1:
        return ValueError("i_led has to be between 0 and 3")

    if value > 0:
        message = leds_on[i_led]
    else:
        message = leds_off[i_led]
    return _say(ser, message)


def move_platform_up(ser, N_steps):
    N_steps = int(round(N_steps))
    return _say(ser, str('r'*N_steps))

def move_platform_down(ser, N_steps):
    N_steps = int(round(N_steps))
    return _say(ser, str('l'*N_steps))

def step_end_align(ser):
    return _say(ser, 'x')


class Arena:
    '''Control the Alice Arena9

    Attributes
    ----------
    ser : obj
        The serial library object
    '''
    def __init__(self, device=None, fake_serial=None):
        
        self.pos = 0
        self.led_states = {}
        
        if fake_serial:
            self.ser = FakeSerial()
            return

        if device is None:
            devs = detect_controller_devices()
            if not devs:
                raise RuntimeError("Could not detect the arena")
            device = devs[0]

        self.ser = serial.Serial(device, 9600)
        
        

    def set_led(self, i_led, value):
        '''Set an LED on or off
        '''
        self.led_states[i_led] = value
        return toggle_led(self.ser, i_led, value)

    def get_led(self, i_led):
        '''Returns True if the LED is on, otherwise False
        '''
        return bool(self.led_states.get(i_led, False))


    def get_N_leds(self):
        '''Returns the total amount of leds
        '''
        # In the future, this will be checked from the device
        # likely but the first shipped proto has 6 leds :)
        return 6

    def move_platform(self, N_steps):
        '''Move the platform up or down

        Arguments
        N_steps : int
            Positive for rising steps, moving the platform up.
            Negative for going down. Zero doesn't do anything.
        '''

        self.pos += N_steps

        if N_steps > 0: 
            return move_platform_up(self.ser, N_steps)
        elif N_steps < 0:
            return move_platform_down(self.ser, -N_steps)
    
    def step_end_align(self):
        '''Do the end align with little torque
        '''
        self.pos = 0
        return step_end_align(self.ser)


def main():

    arena = Arena()
    ser = arena.ser

    while True:
        
        message = input('LETTER >> ')
        print( _say(ser, message)) 


if __name__ == "__main__":
    main()
