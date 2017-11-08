#

from time import sleep
from PyQt5.QtCore import Qt, QCoreApplication, QIODevice
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo


class SerialPort(QSerialPort):
    """docstring for SerialPort"""

    def __init__(self, serial_config, logger=None, parent=None):
        super(SerialPort, self).__init__(parent)
        self.writeline_data = ''
        self.readline_ready = False
        self.readline_data = ''
        self.workerbreak = False
        self.apply_settings(serial_config)

    def apply_settings(self, settings):
        self.setPortName(settings['portName'])
        self.setBaudRate(settings['baudRate'])
        self.setDataBits(settings['dataBits'])
        self.setParity(settings['parity'])
        self.setStopBits(settings['stopBits'])
        self.setFlowControl(settings['flowControl'])
        self.linedelay = settings['linedelay']

    def open(self):
        if not self.isOpen():
            return super().open(QIODevice.ReadWrite)
        return True

    def close(self):
        if self.isOpen():
            return super().close()
        return True

    def transaction(self, data, callback=None):
        if not self.open():
            raise OSError('cant open port - '+self.portName())
        #
        for s in data.split('\r\n'):
            s = s + '\r\n'
            # write line
            self.write( bytearray(s, 'utf-8') )
            #
            if not self.waitForBytesWritten(200):
                raise BaseException('error write data - ' + str(data))
            #
            # read response
            if not self.waitForReadyRead(200):
                raise BaseException('transaction response timeout error')
            #
            response = self.readAll()
            while self.waitForReadyRead(200):
                response += self.readAll()
            response = str(response, 'utf-8')
            #
            start_index = response.find(s)
            if start_index != -1:
                response = response[ start_index+len(s): ]
            #
            if callback:
                callback(response)
            #
            sleep(self.linedelay/1000)
        #
        self.close()


class PyEsp(QCoreApplication):
    """docstring for PyEsp"""
    _api_file = {
        'MPY': 'data/api/mpython.json',
        'NODE': 'data/api/node.json'
    }

    def __init__(self, serialconfig, platform='USER', api_file=None, loglevel=0):
        super(PyEsp, self).__init__([])
        #
        self.platform = platform
        #
        if platform in PyEsp._api_file.keys():
            api_file = PyEsp._api_file[platform]
            try:
                import json
                with open(api_file, 'r') as f:
                    self.api = json.loads(f.read())
            except Exception as e:
                raise e('error load api json file, key - '+platform)
        elif api_file is None:
            raise BaseException('wrong api key or api json file')
        #
        self.serialconfig = serialconfig
        self.serialport = SerialPort( self.serialconfig )
        #
        self.callback = None

    def send(self, command, callback=None, **kwargs):
        """ """
        self.callback = callback
        # esp memory optimization, split file data
        if command == 'filewrite':
            lines = kwargs.get('data', '').split('\n')
            kwargs['data'] = ''
            for line in lines:
                kwargs['data'] += self.api['filewriteline'].format( data = line.replace("'", '"') + '\\n' ) + '\r\n'
        # format command and data field
        if command != 'line':
            txfer = self.api[command].format(**kwargs)
        else:
            txfer = kwargs['data']
        # prepare to send
        txfer.replace(r'\r', r'\\r').replace(r'\n', r'\\n')
        # send txfer to esp
        self.serialport.transaction( txfer, callback=self.read )

    def read(self, data):
        # print(self.api)
        if self.platform == 'MPY':
            end = data.find('>>>')
            if end != -1:
                data = data[ :end ]
        #
        if len(data) and self.callback:
            self.callback( data )
