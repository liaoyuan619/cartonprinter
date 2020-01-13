# -*- coding: utf-8 -*-

import ctypes
import logging
import configparser
import sys
import os
import requests
import json
import time
import io

if hasattr(sys, 'frozen'):
    os.environ['PATH'] = sys._MEIPASS + ";" + os.environ['PATH']
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QFileDialog, QMessageBox, QInputDialog
from PyQt5.QtCore import QStringListModel
from PyQt5.QtGui import QIcon
from tscprinterUi import Ui_MainWindow

from testdata import *
import apprcc_rc
import qrcode
from PIL import Image

class MainUiWin(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainUiWin, self).__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon(':/pic/box.png'))

        self.action_load.triggered.connect(self.openFileDiag)
        self.action_exit.triggered.connect(self.close)
        self.action_about.triggered.connect(self.openAboutDiag)
        self.action_print.triggered.connect(self.manual_print)
        self.action_printtest.triggered.connect(self.test_print)
        self.action_tsc_speed.triggered.connect(self.adjust_tsc_speed)
        self.action_tsc_density.triggered.connect(self.adjust_tsc_density)

        # self.lineEdit.returnPressed.connect(self.barcodeInputScaned)
        self.lineEdit.editingFinished.connect(self.barcodeInputScaned)

        self.snList = []
        self.version = "版本:1.0.3"
        self.packCount = 100

        self.boxmask = ""
        self.date = ""
        self.color = ""

        self.servaddr = ""
        self.servport = ""

        self.dataQRcode1 = ""
        self.dataQRcode2 = ""

        self.tsc_speed = 2
        self.tsc_density = 8

    def adjust_tsc_speed(self):
        speed, ok = QInputDialog.getInt(self, "打印速度", "打印速度", value=2, min=1, max=12)
        if ok:
            self.tsc_speed = speed
            self.log("打印速度：{}，".format(self.tsc_speed) + "打印浓度：{}".format(self.tsc_density))

    def adjust_tsc_density(self):
        density, ok = QInputDialog.getInt(self, "打印浓度", "打印浓度", value=8, min=0, max=15)
        if ok:
            self.tsc_density = density
            self.log("打印速度：{}，".format(self.tsc_speed) + "打印浓度：{}".format(self.tsc_density))

    def test_print(self):
        self.log("打印测试箱唛，仅供试纸")
        self.tscPrint("{}".format(self.tsc_speed), "{}".format(self.tsc_density),  "6940278310101", "2099-01-01",
                      "100", "T20191224WS191001A*****", test_qrcode1, test_qrcode2)

    def do_print(self):
        self.log("向服务器查询箱流水号...")
        boxserial = self.getBoxSerial()
        if boxserial:
            boxindex = int(boxserial[-5:])
            self.log("获取箱流水号：" + "{:0>5d}".format(boxindex))

            boxindex += 1
            if self.uploadData(self.snList, self.boxmask + "{:0>5d}".format(boxindex)):
                self.log("箱号：" + self.boxmask + "{:0>5d}".format(boxindex) + " 数据上传服务器成功")

                self.log("打印箱唛,{}台".format(len(self.snList)))
                self.tscPrint("{}".format(self.tsc_speed), "{}".format(self.tsc_density),
                              self.color, self.date, "{}".format(len(self.snList)),
                              self.boxmask + "{:0>5d}".format(boxindex),
                              self.dataQRcode1, self.dataQRcode2)

                self.snList = []
                self.dataQRcode1 = ""
                self.dataQRcode2 = ""

                self.lcdNumber.display(len(self.snList))
                self.listWidget.clear()

            else:
                self.log("上传服务器失败！")
        else:
            self.log("获取箱流水号失败！")

    def manual_print(self):
        self.log("打印箱唛")

        if not len(self.snList):
            self.log("已扫描计数为0！")
            return

        logging.debug(self.snList)

        self.dataQRcode1 = ''
        self.dataQRcode2 = ''

        if len(self.snList) > self.packCount//2:
            for element in self.snList[:self.packCount//2]:
                self.dataQRcode1 += element
                self.dataQRcode1 += "\r\n"

            for element in self.snList[self.packCount//2:]:
                self.dataQRcode2 += element
                self.dataQRcode2 += "\r\n"

            for _ in range(len(self.snList), self.packCount):
                self.dataQRcode2 += "                "
                self.dataQRcode2 += "\r\n"
        else:
            for element in self.snList:
                self.dataQRcode1 += element
                self.dataQRcode1 += "\r\n"

            for _ in range(len(self.snList), self.packCount//2):
                self.dataQRcode1 += "                "
                self.dataQRcode1 += "\r\n"

        logging.debug(self.dataQRcode1)
        logging.debug(self.dataQRcode2)

        self.do_print()

    def log(self, msg):
        self.textEdit.append(msg)

    def openAboutDiag(self):
        QMessageBox.about(self, "关于", self.version)

    def openFileDiag(self):
        fpath, ok = QFileDialog.getOpenFileName(self, "选择配置文件", "./", "Config Files (*.conf);;All Files (*)")

        if fpath:
            self.boxmask, self.date, self.color, self.servaddr, self.servport = self.load_config(fpath)
            self.log("箱号掩码：" + self.boxmask + "*****")
            self.lineEdit.setEnabled(True)
            self.lcdNumber.setEnabled(True)
            self.listWidget.setEnabled(True)
            self.action_print.setEnabled(True)
            self.action_printtest.setEnabled(False)
        else:
            # self.generate_qrcode()
            pass

    def barcodeInputScaned(self):
        sn = self.lineEdit.text()
        if sn:
            if len(sn) < 16:
                self.log("输入：" + sn + " 格式错误！")
                self.lineEdit.clear()
                return

            if self.verifySn(sn, self.color):
                if self.snList.count(sn):
                    self.log(sn + " 重复扫描！")
                else:
                    self.log("查询：" + sn + " 成功")
                    self.snList.append(sn)
                    self.lcdNumber.display(len(self.snList))
                    self.listWidget.addItem(sn)

                    if len(self.snList) == self.packCount:
                        self.log("数量达到{}，即将打印".format(self.packCount))
                        logging.debug(self.snList)
                        for element in self.snList[:self.packCount//2]:
                            self.dataQRcode1 += element
                            self.dataQRcode1 += "\r\n"

                        for element in self.snList[self.packCount//2:]:
                            self.dataQRcode2 += element
                            self.dataQRcode2 += "\r\n"

                        logging.debug(self.dataQRcode1)
                        logging.debug(self.dataQRcode2)

                        self.do_print()
            else:
                self.log("查询：" + sn + " 失败！")
            # 清空输入
            self.lineEdit.clear()

    def getBoxSerial(self):
        boxserial = ""
        url = "http://{}:{}/api/getBoxSerial".format(self.servaddr, self.servport)
        timeout = 5

        while timeout:
            try:
                r = requests.get(url)
                if r.json()['ret']:
                    if r.json()['data']:
                        if not r.json()['data']['boxID_hit']:
                            boxserial = r.json()['data']['boxID']
                            break
                        else:
                            self.log("等待服务器分配箱流水号，重试：" + "{}".format(timeout) + "...")
                            timeout -= 1
                            time.sleep(1)
                    else:
                        boxserial = "00000"
                        break
                else:
                    raise Exception("查询失败")
            except Exception as e:
                logging.debug(str(e))
                break

        return boxserial

    def uploadData(self, snlist, boxserial):
        ret = True
        url = "http://{}:{}/api/ecasetestlist".format(self.servaddr, self.servport)

        strsnlist = ""
        for element in snlist:
            strsnlist += element
            strsnlist += ','

        headers = {"Content-Type": "application/json"}
        data = {
            "snlist": strsnlist[:-1],
            "boxID": boxserial,
            "package_verify": True,
            "test_result": True
        }

        logging.debug(json.dumps(data))
        try:
            r = requests.post(url=url, headers=headers, data=json.dumps(data))
            logging.debug(r.content)
            if not r.json()['ret']:
                raise Exception("response false")
        except Exception as e:
            logging.debug(str(e))
            ret = False

        return ret

    def verifySn(self, sn, color):
        ret = True
        url = "http://{}:{}/api/devicesn/".format(self.servaddr, self.servport) + sn

        try:
            r = requests.get(url)
            logging.debug(r.content)
            if r.json()['ret']:
                if not color == r.json()['data']['barcode_color']:
                    self.log("颜色不一致！")
                    raise Exception("%s dismatch %s" % (color, r.json()['data']['barcode_color']))
            else:
                raise Exception("not exist")
        except Exception as e:
            logging.debug(str(e))
            ret = False

        return ret

    def generate_qrcode(self):
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1)
        qr.add_data(test_qrcode_40)
        qr.make(fit=True)

        img = qr.make_image()
        logging.debug("mode:{},".format(img.mode) + "size:{},".format(img.size))
        width, height = img.size
        logging.debug("width:{},".format(width) + "height:{}".format(height))

        img.save("./qrcode.png")
        # img.show()

        pixel = Image.open("./qrcode.png").load()
        logging.debug(type(pixel[0, 0]))

        pixel_bytes = b'BITMAP 700,440,1,121,0'

        for x in range(0, width):
            for y in range(0, height):
                pixel_bytes += int(pixel[x, y]).to_bytes(length=1, byteorder='little', signed=False)

        print(pixel_bytes)

        # 转换为字节序列
        img_bytes_array = io.BytesIO()
        img.save(img_bytes_array, format='PNG')
        img_bytes_array = img_bytes_array.getvalue()
        # print(b'BITMAP 700,440,' + img_bytes_array)

        return img

    def tscPrint(self, speed, density, color, date, quantity, boxSerial, qrcode1, qrcode2):
        tsc_dll = ctypes.windll.LoadLibrary('.\TSCLIB.dll')

        logging.debug("open printer")
        tsc_dll.openport(b"TSC TE344")

        logging.debug("setup printer")
        tsc_dll.setup(b"100", b"70", speed.encode('utf-8'), density.encode('utf-8'), b"0", b"3", b"0")
        tsc_dll.clearbuffer()

        tsc_dll.windowsfontU(100, 50, 64, 0, 0, 0, "微软雅黑", "产品型号：WS1910")

        if color == "6940278310101":
            tsc_dll.windowsfontU(100, 150, 64, 0, 0, 0, "微软雅黑", "产品颜色：雪峰白")
        elif color == "6940278310118":
            tsc_dll.windowsfontU(100, 150, 64, 0, 0, 0, "微软雅黑", "产品颜色：幻影黑")
        elif color == "6940278310125":
            tsc_dll.windowsfontU(100, 150, 64, 0, 0, 0, "微软雅黑", "产品颜色：极夜蓝")

        tsc_dll.windowsfontU(100, 250, 64, 0, 0, 0, "微软雅黑", "数        量：" + quantity + "台")
        tsc_dll.windowsfontU(100, 350, 64, 0, 0, 0, "微软雅黑", "生产日期：" + date)

        tsc_dll.barcode(b"140", b"440", b"EAN13", b"96", b"1", b"0", b"3", b"7", color.encode('utf-8'))
        tsc_dll.windowsfontU(140, 580, 64, 0, 0, 0, "Arial", "Carton No：")
        tsc_dll.barcode(b"100", b"640", b"128", b"96", b"1", b"0", b"2", b"5", boxSerial.encode('utf-8'))

        if qrcode1:
            tsc_dll.sendcommand('QRCODE 780,50,M,3,A,0,M2,S3,"{}"'.format(qrcode1).encode('utf-8'))
        if qrcode2:
            tsc_dll.sendcommand('QRCODE 780,440,M,3,A,0,M2,S3,"{}"'.format(qrcode2).encode('utf-8'))

        tsc_dll.sendcommand(b'PRINT 1,1')

        logging.debug("close printer")
        tsc_dll.closeport()

    def load_config(self, fpath):
        cf = configparser.ConfigParser()
        cf.read(fpath)

        factory = cf.get("箱号编码规则", "生产工厂代码")
        year = cf.get("箱号编码规则", "生产年份")
        month = cf.get("箱号编码规则", "生产月份")
        day = cf.get("箱号编码规则", "生产日期")
        model = cf.get("箱号编码规则", "产品型号")
        order = cf.get("箱号编码规则", "订单号")
        color = cf.get("箱号编码规则", "颜色")

        mask = factory + year + month + day + model + order + color
        logging.debug(mask)

        # 雪峰白
        if color == "A":
            color = "6940278310101"
        # 幻影黑
        elif color == "B":
            color = "6940278310118"
        # 极夜蓝
        elif color == "C":
            color = "6940278310125"

        host = cf.get("server", "host")
        port = cf.get("server", "port")

        return mask, "{}-{}-{}".format(year, month, day), color, host, port

if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s',
                        level=logging.DEBUG)

    app = QApplication(sys.argv)
    win = MainUiWin()
    win.show()
    sys.exit(app.exec_())

