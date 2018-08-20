# -*- coding: utf-8 -*-
from maya import cmds
from maya import mel
import pymel.core as pm
import maya.api.OpenMaya as om2

from . import common
from . import lang
from . import qt
from . import prof
reload(prof)

import re
import os
import locale
from collections import defaultdict
import copy
import time
import datetime as dt
import itertools
import json
import imp
import webbrowser

from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQWidgetBaseMixin
try:
    imp.find_module('PySide2')
    from PySide2.QtWidgets import *
    from PySide2.QtGui import *
    from PySide2.QtCore import *
except ImportError:
    from PySide.QtGui import *
    from PySide.QtCore import *

VERSION = 'r1.0.1'

MAYA_VER = int(cmds.about(v=True)[:4])

#速度計測結果を表示するかどうか
COUNTER_PRINT = True
COUNTER_PRINT = False

WIDGET_HEIGHT = 32
BUTTON_HEIGHT = 22

MAXIMUM_DIGIT = 1.0

#GitHub
HELP_PATH = 'https://github.com/ShikouYamaue/SIVertexColorEditor/blob/master/README.md'
#リリースページ
REREASE_PATH = 'https://github.com/ShikouYamaue/SIVertexColorEditor/releases'

#焼きこみプラグインをロードしておく
try:
    check = cmds.pluginInfo('bake_vertex_color.py', query=True, l=True)
    if not check:
        cmds.loadPlugin('bake_vertex_color.py', qt=True)
        cmds.pluginInfo('bake_vertex_color.py', e=True, autoload=True)
except Exception as e:
    e.message
    
def timer(func):
    #戻す用関数を定義
    def wrapper(*args, **kwargs):
        start = time.time()#開始時間
        func(*args, **kwargs)#関数実行
        end = time.time()#終了時間
        #結果をプリント
        print '-'*50
        print 'Execution time :', func.__name__, end - start
        print '-'*50
    return wrapper
    
def timer(func):
    return func
        
#イベント追加したカスタムスピンボックス
class EditorDoubleSpinbox(QDoubleSpinBox):
    wheeled = Signal()
    focused = Signal()
    keypressed = Signal()
    mousepressed = Signal()
    
    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)
        self.installEventFilter(self)
        
    #ホイールイベントをのっとる
    def wheelEvent(self,e):
        pass
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            self.sel_all_input()
            self.focused.emit()
        if event.type() == QEvent.Wheel:
            delta = event.delta()
            delta /= abs(delta)#120単位を1単位に直す
            shift_mod = self.check_shift_modifiers()
            ctrl_mod = self.check_ctrl_modifiers()
            if window.mode_but_group.checkedId() == 2 or MAXIMUM_DIGIT == 100:
                offset = 100.0
            else:
                offset = 1.0
            
            if shift_mod:
                self.setValue(self.value()+delta*0.001*offset)
            elif ctrl_mod:
                self.setValue(self.value()+delta*0.1*offset)
            else:
                self.setValue(self.value()+delta*0.01*offset)
            cmds.scriptJob(ro=True, e=("idle", self.emit_wheel_event), protected=True)
        if event.type() == QEvent.KeyPress:
            self.keypressed.emit()
        if event.type() == QEvent.MouseButtonPress:
            self.mousepressed.emit()
        return False
        
    def emit_wheel_event(self):
        self.wheeled.emit()
        
    #入力窓を選択するジョブ
    def sel_all_input(self):
        cmds.scriptJob(ro=True, e=("idle", self.select_box_all), protected=True)
        
    #スピンボックスの数値を全選択する
    def select_box_all(self):
        try:
            self.selectAll()
        except:
            pass
            
    def sel_all_input(self):
        cmds.scriptJob(ro=True, e=("idle", self.select_box_all), protected=True)
            
    def check_shift_modifiers(self):
        mods = QApplication.keyboardModifiers()
        isShiftPressed =  mods & Qt.ShiftModifier
        shift_mod = bool(isShiftPressed)
        return shift_mod
        
    def check_ctrl_modifiers(self):
        mods = QApplication.keyboardModifiers()
        isCtrlPressed =  mods & Qt.ControlModifier
        ctrl_mod = bool(isCtrlPressed)
        return ctrl_mod
        
class EditorSpinbox(QSpinBox):
    wheeled = Signal(int)
    focused = Signal()
    keypressed = Signal()
    mousepressed = Signal()
    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)
        self.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            self.focused.emit()
            self.sel_all_input()
        if event.type() == QEvent.Wheel:
            cmds.scriptJob(ro=True, e=("idle", self.emit_wheel_event), protected=True)
        if event.type() == QEvent.KeyPress:
            self.keypressed.emit()
        if event.type() == QEvent.MouseButtonPress:
            self.mousepressed.emit()
        return False
    #ウェイト入力窓を選択するジョブ
    def sel_all_input(self):
        cmds.scriptJob(ro=True, e=("idle", self.select_box_all), protected=True)
    #スピンボックスの数値を全選択する
    def select_box_all(self):
        try:
            self.selectAll()
        except:
            pass
            
    def emit_wheel_event(self):
        self.wheeled.emit(self.value)
            
    def check_shift_modifiers(self):
        mods = QApplication.keyboardModifiers()
        isShiftPressed =  mods & Qt.ShiftModifier
        shift_mod = bool(isShiftPressed)
        return shift_mod
        
    def check_ctrl_modifiers(self):
        mods = QApplication.keyboardModifiers()
        isCtrlPressed =  mods & Qt.ControlModifier
        ctrl_mod = bool(isCtrlPressed)
        return ctrl_mod
        
class PopInputBox(qt.SubWindow):
    closed = Signal()
    def __init__(self, parent = None, value=0.0, float_flag=True, mode=0, direct=False, pos=None):
        super(self.__class__, self).__init__(parent)
        #↓ウインドウ枠消す設定
        self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint)
        
        #ラインエディットを作成、フォーカスが外れたら消えるイベントを設定
        if direct:
            self.input = qt.LineEdit(self)
            self.setCentralWidget(self.input)
            self.input.setText(value)
        else:
            self.input = QDoubleSpinBox(self)
            self.setCentralWidget(self.input)
            self.input.setButtonSymbols(QAbstractSpinBox.NoButtons)
            if mode == 0:
                if float_flag:
                    self.input.setDecimals(3)
                    self.input.setRange(0, 9.0)
                else:
                    self.input.setDecimals(0)
                    self.input.setRange(0, 999)
                self.input.setValue(value)
            elif mode == 1:
                if float_flag:
                    self.input.setDecimals(3)
                    self.input.setRange(-9.0, 9.0)
                else:
                    self.input.setDecimals(0)
                    self.input.setRange(-999, 999)
                self.input.setValue(value)
            elif mode == 2:
                    self.input.setDecimals(1)
                    self.input.setRange(-999, 999)
            self.input.selectAll()
        
        #位置とサイズ調整
        self.resize(50, 24)
        pos = QCursor.pos()
        
        self.move(pos.x()-20, pos.y()-12)
        self.input.editingFinished.connect(self.close)
        self.show()
        
        #ウィンドウを最前面にしてフォーカスを取る
        self.activateWindow()
        self.raise_()
        self.input.setFocus()
        
    def closeEvent(self, e):
        self.closed.emit()
        
        
#右クリックウィジェットクラスの作成
class RightClickTableView(QTableView):
    rightClicked = Signal()
    keyPressed = Signal(str)
    ignore_key_input = False
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.RightButton:
            self.rightClicked.emit()
        else:
            super(self.__class__, self).mouseReleaseEvent(e)
            
    def keyPressEvent(self, e):
        self.keyPressed.emit(e.text())
        #スーパークラスに行かないとキー入力無効になっちゃうので注意
        if self.ignore_key_input:
            return
        super(self.__class__, self).keyPressEvent(e)
            
class TableModel(QAbstractTableModel):
    norm = False
    def __init__(self, data={}, parent=None, mesh_rows=[], v_header_list=[]):
        super(TableModel, self).__init__(parent)
        self.mesh_rows = mesh_rows
        self._data = data
        self.v_header_list = v_header_list
        
        
    #ヘッダーを設定する関数をオーバーライド
    header_list = ['  Red ', 'Green', ' Blue ', 'Alpha', 'Color']
    def headerData(self, id, orientation, role):
        u"""見出しを返す"""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header_list[id]
            
        if orientation == Qt.Vertical:
            if role == Qt.DisplayRole:
                return self.v_header_list[id]
                
        return None
        
    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._data[0]) if self.rowCount() else 0
        
    r_color = QColor(230, 64, 64)
    g_color = QColor(64, 230, 64)
    b_color = QColor(64, 64, 230)
    a_color = QColor(*[200]*3)
    c_color = QColor(*[93]*3)
    h_color = QColor(*[238]*3)
    #データ設定関数をオーバーライド流れてくるロールに応じて処理
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            row = index.row()
            if 0 <= row < self.rowCount():
                column = index.column()
                if 0 <= column < self.columnCount()-1:
                    try:
                        data = self._data[row][7][column]
                    except:
                        return
                    if not self.norm:
                        try:
                            data = int(data*255)
                        except:
                            pass
                    else:
                        try:
                            data = round(data, 3)
                        except:
                            pass
                        
                    return data
        elif role == Qt.BackgroundRole:#バックグラウンドロールなら色変更する
            column = index.column()
            row = index.row()
            if column == 4:
                color = self._data[row]
                if color[0] == '':
                    return self.c_color
                color = map(lambda a, b:int(a*255) if b!=3 else 255, color[7], xrange(4))
                return QColor(*color)
            if row in self.mesh_rows:
                if column == 0:
                    return self.r_color
                elif column == 1:
                    return self.g_color
                elif column == 2:
                    return self.b_color
                elif column == 3:
                    return self.a_color
                    
    def get_data(self, index=None, row=0, column=0):
        try:
            if index:
                value  = self._data[index.row()][7][index.column()]
            else:
                value  = self._data[row][7][column]
        except:
            value = 0
        return value
        
    #データセットする関数をオーバライド
    def setData(self, index, value, role=Qt.EditRole):
        if not isinstance(index, tuple):
            if not index.isValid() or not 0 <= index.row() < len(self._data):
                return
            row = index.row()
            column = index.column()
        else:
            row = index[0]
            column = index[1]
        if role == Qt.EditRole and value != "":
            self._data[row][7][column] = value
            self.dataChanged.emit((row, column), (row, column))#データをアップデート
            return True
        else:
            return False
            
    # 各セルのインタラクション
    def flags(self, index):
        row = index.row()
        column = index.column()
        if column == 4 or row in self.mesh_rows:
            return Qt.ItemIsEnabled
        else:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
      
        
#モデルのアイテムインデックスを全部返してくれる。便利。
def model_iter(model, parent_index=QModelIndex(), col_iter=True):
    """ モデルのイテレータ
    :rtype: generator(QModelIndex)
    :type col_iter: bool
    :type parent_index: QModelIndex
    :type model: QAbstractItemModel
    """
    index = model.index(0, 0, parent_index)

    while True:
        if col_iter:
            for col in range(0, model.columnCount(parent_index)):
                yield index.sibling(index.row(), col)
        else:
            yield index

        if model.rowCount(index) > 0:
            for _ in model_iter(model, index, col_iter):
                yield _

        index = index.sibling(index.row() + 1, index.column())
        if not index.isValid():
            break
            
class Option():
    def __init__(self):
        global window
        try:
            window.closeEvent(None)
            window.close()
        except Exception as e:
            print e.message
        window = MainWindow()
        window.init_flag=False
        for i in range(0, 800, 50):
            window.resize(1000 - i, 800)
        window.resize(window.sw, window.sh)
        window.move(window.pw-8, window.ph-31)
        window.show()
        
class MainWindow(qt.MainWindow):
    selection_mode = 'tree'
    filter_type = 'scene'
    icon_path = os.path.join(os.path.dirname(__file__), 'icon/')
    
    def init_save(self):
        temp = __name__.split('.')
        self.dir_path = os.path.join(
            os.getenv('MAYA_APP_dir'),
            'Scripting_Files')
        self.w_file = self.dir_path+'/'+temp[-1]+'_window.json'
        self.custom_color_path = self.dir_path+'/'+temp[-1]+'_custom_color.json'
    
    #セーブファイルを読み込んで返す　   
    def load_window_data(self, init_pos=False):
        #セーブデータが無いかエラーした場合はデフォファイルを作成
        if init_pos:
            print 'Init Window Position'
            self.init_save_data()
            return
        #読み込み処理
        if os.path.exists(self.w_file):#保存ファイルが存在したら
            try:
                with open(self.w_file, 'r') as f:
                    save_data = json.load(f)
                    self.pw = save_data['pw']
                    self.ph = save_data['ph']
                    self.sw = save_data['sw']
                    self.sh = save_data['sh']
                    self.hilite_vtx = save_data['hilite']
                    self.lock = save_data['lock'] 
                    self.mesh = save_data['mesh']
                    self.comp = save_data['comp']
                    self.add5 = save_data['add5']
                    self.mode = save_data['mode']
                    self.rgba = save_data['rgba']
                    self.norm = save_data['norm']
                    self.copy_colors = save_data['copy_color']
            except Exception as e:
                print e.message, 'in load data'
                self.init_save_data()
        else:
            self.init_save_data()
            
    def init_save_data(self):
        self.pw = 200
        self.ph = 200
        self.sw = 440
        self.sh = 700
        self.hilite_vtx = False
        self.lock = False
        self.mesh = True
        self.comp = True
        self.add5 = False
        self.mode = 0
        self.rgba = 0
        self.norm = False
        self.copy_colors = [0.502, 0.502, 0.502, 1.0]
    
    def save_window_data(self, display=True):
        if not os.path.exists(self.dir_path):
            os.makedirs(self.dir_path)
        #print('# ' + self.showRepr())
        save_data = {}
        dock_dtrl = self.parent()
        pos = self.pos()
        size = self.size()
        save_data['pw'] = pos.x()+8
        save_data['ph'] = pos.y()+31
        save_data['sw'] = size.width()
        save_data['sh'] = size.height()
        save_data['hilite'] = self.highlite_but.isChecked()
        save_data['lock'] = self.lock_but.isChecked()
        save_data['mesh'] = self.show_mesh_but.isChecked()
        save_data['comp'] = self.show_comp_but.isChecked()
        save_data['add5'] = self.add_5_but.isChecked()
        save_data['mode'] = self.mode_but_group.checkedId()
        save_data['rgba'] = self.channel_but_group.checkedId()
        save_data['norm'] = self.norm_but.isChecked()
        save_data['copy_color'] = self.copy_colors
        if not os.path.exists(self.dir_path):
            os.makedirs(self.dir_path)
        with open(self.w_file, 'w') as f:
            json.dump(save_data, f)
        
    pre_selection_node = []
    def __init__(self, parent = None, init_pos=False):
        super(self.__class__, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.init_save()
        self.load_window_data()
        global MAXIMUM_DIGIT
        if not self.norm:
            MAXIMUM_DIGIT = 100
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.icon_path = os.path.join(os.path.dirname(__file__), 'icons/')
        self.init_list_dict()
        self._init_ui()
    
    
    def _init_ui(self, job_create=True):
        self.counter = prof.LapCounter()
        self.init_flag=True
        sq_widget = QScrollArea(self)
        sq_widget.setWidgetResizable(True)#リサイズに中身が追従するかどうか
        sq_widget.setFocusPolicy(Qt.NoFocus)#スクロールエリアをフォーカスできるかどうか
        sq_widget.setMinimumHeight(1)#ウィンドウの最小サイズ
        self.setWindowTitle(u'SI Vertex Color Editor / ver_'+VERSION)
        self.setCentralWidget(sq_widget)
        
        self.main_layout = QVBoxLayout()
        sq_widget.setLayout(self.main_layout)
        
        self.unique_layout = QGridLayout()
        self.unique_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        self.main_layout.addLayout(self.unique_layout)
        
        self.but_list = []
        
        self.ui_color = 68
        self.hilite = 100
        self.lock_col = [180, 60, 60]
        but_h = BUTTON_HEIGHT
        
        #表示ボタンをはめる
        show_widget = QWidget()
        show_widget.setGeometry(QRect(0, 0, 0 ,0))
        show_layout = QHBoxLayout()
        show_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        show_widget.setLayout(show_layout)
        but_w = 60
        norm_w =75
        space = 13
        show_widget.setMinimumWidth(but_w*3+space)
        show_widget.setMaximumWidth(but_w*3+space)
        show_widget.setMaximumHeight(WIDGET_HEIGHT)
        tip = lang.Lang(en='Show only selected cells', ja=u'選択セルのみ表示').output()
        self.show_but = qt.make_flat_btton(name='Show', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Show all cells', ja=u'全てのセルを表示').output()
        self.show_all_but = qt.make_flat_btton(name='Show All', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        # self.focus_but = qt.make_flat_btton(name='Forcus', text=128, bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    # flat=True, hover=True, checkable=True, destroy_flag=True)
        # self.focus_but.setDisabled(True)#無効化
        # self.filter_but = qt.make_flat_btton(name='Filter', text=128, bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    # flat=True, hover=True, checkable=True, destroy_flag=True)
        # self.filter_but.setDisabled(True)#無効化
        tip = lang.Lang(en='Highlite points in 3D view to reflect the color editor selection', ja=u'カラーエディタの選択をポイントハイライトに反映').output()
        self.highlite_but = qt.make_flat_btton(name='Highlite', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        self.highlite_but.setChecked(self.hilite_vtx)
        self.show_but.clicked.connect(self.show_selected_cells)
        self.show_all_but.clicked.connect(self.show_all_cells)
        self.highlite_but.clicked.connect(self.reset_hilite)
        show_layout.addWidget(self.show_but)
        show_layout.addWidget(self.show_all_but)
        #show_layout.addWidget(self.focus_but)
        #show_layout.addWidget(self.filter_but)
        show_layout.addWidget(self.highlite_but)
        self.but_list.append(show_widget)
        
        #アイコンボタン群
        icon_widget = QWidget()
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        icon_widget.setLayout(icon_layout)
        icon_widget.setMaximumHeight(WIDGET_HEIGHT)
        but_w = BUTTON_HEIGHT#常に正方形になるように高さと合わせる
        space = 10
        icon_widget.setMinimumWidth(but_w*4+space)
        icon_widget.setMaximumWidth(but_w*4+space)
        tip = lang.Lang(en='Lock display mesh', ja=u'表示メッシュのロック').output()
        self.lock_but = qt.make_flat_btton(name='', bg=self.lock_col, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, icon=self.icon_path+'lock.png', tip=tip)
        tip = lang.Lang(en='Update the view based on object selection', ja=u'オブジェクト選択に基づきビューを更新').output()
        self.cycle_but = qt.make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=self.icon_path+'cycle.png', tip=tip)
        tip = lang.Lang(en='Clear the view', ja=u'ビューのクリア').output()
        self.clear_but = qt.make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=self.icon_path+'clear.png', tip=tip)
        tip = lang.Lang(en='Select vertices from cell selection', ja=u'セル選択からフェース頂点を選択').output()
        self.adjust_but = qt.make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=self.icon_path+'adjust.png', tip=tip)
        self.lock_but.setChecked(self.lock)
        self.lock_but.clicked.connect(self.check_unlock)
        self.cycle_but.clicked.connect(lambda : self.get_set_vertex_color(cycle=True))
        self.clear_but.clicked.connect(lambda : self.get_set_vertex_color(clear=True))
        self.adjust_but.clicked.connect(self.select_vertex_from_cells)
        
        icon_layout.addWidget(self.lock_but)
        icon_layout.addWidget(self.cycle_but)
        icon_layout.addWidget(self.clear_but)
        icon_layout.addWidget(self.adjust_but)
        self.but_list.append(icon_widget)
        
        #オプション設定
        option_widget = QWidget()
        option_widget.setGeometry(QRect(0, 0, 0 ,0))
        option_layout = QHBoxLayout()
        option_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        option_widget.setLayout(option_layout)
        option_widget.setMaximumHeight(WIDGET_HEIGHT)
        but_w = 40
        space = 5
        option_widget.setMinimumWidth(but_w*5+space)
        option_widget.setMaximumWidth(but_w*5+space)
        tip = lang.Lang(en='Reflect mesh selection change in UI', ja=u'メッシュ選択変更をUIに反映する').output()
        self.show_mesh_but = qt.make_flat_btton(name='Mesh', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Reflect component selection change in UI', ja=u'コンポーネント選択変更をUIに反映する').output()
        self.show_comp_but = qt.make_flat_btton(name='Comp', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='In the 255 display mode, 0.5 is added to the burning result\n255 -> 1.0 What to do when fractions are truncated when restoring 255 by calculation error after conversion', 
                    ja=u'255表示モード時、焼き付け結果に0.5加算する\n255→1.0変換後、計算誤差で255復元したときに端数が切り捨てられる時の対処').output()
        self.add_5_but = qt.make_flat_btton(name='+0.5', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Display vertex color of all meshes', ja=u'全メッシュの頂点カラーを表示').output()
        self.show_color_but = qt.make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=':/colorPresetSpectrum.png', tip=tip)
        tip = lang.Lang(en='Hide vertex color of all meshes', ja=u'全メッシュの頂点カラーを非表示').output()
        self.hide_color_but = qt.make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=':/colorPresetGrayscale.png', tip=tip)
        self.show_mesh_but.setChecked(self.mesh)
        self.show_comp_but.setChecked(self.comp)
        self.add_5_but.setChecked(self.add5)
        self.show_color_but.clicked.connect(self.show_all_vertex_color)
        self.hide_color_but.clicked.connect(self.hide_all_vertex_color)
        
        option_layout.addWidget(self.show_mesh_but)
        option_layout.addWidget(self.show_comp_but)
        option_layout.addWidget(self.add_5_but)
        option_layout.addWidget(self.show_color_but)
        option_layout.addWidget(self.hide_color_but)
        self.but_list.append(option_widget)
        
        #計算モードボタンをはめる
        mode_widget = QWidget()
        mode_widget.setGeometry(QRect(0, 0, 0 ,0))
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        mode_widget.setLayout(mode_layout)
        mode_widget.setMaximumHeight(WIDGET_HEIGHT)
        but_w = 55
        norm_w =60
        space = 0
        mode_widget.setMinimumWidth(but_w*3+norm_w+space)
        mode_widget.setMaximumWidth(but_w*3+norm_w+space)
        self.mode_but_group = QButtonGroup()
        tip = lang.Lang(en='Values entered represent absolute values', ja=u'絶対値で再入力').output()
        self.abs_but = qt.make_flat_btton(name='Abs', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Values entered are added to exisiting values', ja=u'既存値への加算入力').output()
        self.add_but = qt.make_flat_btton(name='Add', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Values entered are percentages added to exisiting values', ja=u'既存値への率加算入力').output()
        self.add_par_but = qt.make_flat_btton(name='Add%  ', bg=self.hilite, w_max=but_w+10, w_min=but_w+10, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Change view normalize(0.0-1.0 <> 0-255)', ja=u'カラーの正規化表示切替（0.0～1.0⇔0～255）').output()
        self.norm_but = qt.make_flat_btton(name='1<>255', bg=self.hilite, w_max=norm_w, w_min=norm_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        self.mode_but_group.buttonClicked[int].connect(self.change_add_mode)
        self.norm_but.setChecked(self.norm)
        self.norm_but.clicked.connect(self.change_normal_mode)
        self.norm_but.clicked.connect(lambda : self.change_add_mode(self.mode_but_group.checkedId()))
        self.mode_but_group.addButton(self.abs_but, 0)
        self.mode_but_group.addButton(self.add_but, 1)
        self.mode_but_group.addButton(self.add_par_but, 2)
        self.mode_but_group.button(self.mode).setChecked(True)
        mode_layout.addWidget(self.abs_but)
        mode_layout.addWidget(self.add_but)
        mode_layout.addWidget(self.add_par_but)
        mode_layout.addWidget(self.norm_but)
        self.but_list.append(mode_widget)
        
        #チャンネル表示ボタン
        channel_widget = QWidget()
        channel_widget.setGeometry(QRect(0, 0, 0 ,0))
        channel_layout = QHBoxLayout()
        channel_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        channel_widget.setLayout(channel_layout)
        channel_widget.setMaximumHeight(WIDGET_HEIGHT)
        but_w = 45
        norm_w = 75
        channel_widget.setMinimumWidth(but_w*6+12)
        channel_widget.setMaximumWidth(but_w*6+12)
        self.channel_but_group = QButtonGroup()
        tip = lang.Lang(en='Draw RGBA channels', ja=u'RGBAチャンネル表示').output()
        self.rgba_but = qt.make_flat_btton(name='RGBA', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Draw RGB channel (Exclude alpha)', ja=u'RGBチャンネル表示（αを除く）').output()
        self.rgb_but = qt.make_flat_btton(name='RGB', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Draw only Red channel', ja=u'Redチャンネルのみ表示').output()
        self.red_but = qt.make_flat_btton(name='Red', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Draw only Green channel', ja=u'Greenチャンネルのみ表示').output()
        self.green_but = qt.make_flat_btton(name='Green', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Draw only Blue channel', ja=u'Blueチャンネルのみ表示').output()
        self.blue_but = qt.make_flat_btton(name='Blue', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = lang.Lang(en='Draw only alpha channel', ja=u'Alphaチャンネルのみ表示').output()
        self.alpha_but = qt.make_flat_btton(name='Alpha', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        self.channel_but_group.buttonClicked.connect(qt.Callback(self.change_view_channel))
        self.channel_but_group.addButton(self.rgba_but, 0)
        self.channel_but_group.addButton(self.rgb_but, 1)
        self.channel_but_group.addButton(self.red_but, 2)
        self.channel_but_group.addButton(self.green_but, 3)
        self.channel_but_group.addButton(self.blue_but, 4)
        self.channel_but_group.addButton(self.alpha_but, 5)
        self.channel_but_group.button(self.rgba).setChecked(True)
        self.pre_channel_id = self.rgba
        channel_layout.addWidget(self.rgba_but)
        channel_layout.addWidget(self.rgb_but)
        channel_layout.addWidget(self.red_but)
        channel_layout.addWidget(self.green_but)
        channel_layout.addWidget(self.blue_but)
        channel_layout.addWidget(self.alpha_but)
        self.but_list.append(channel_widget)
        
        #コピペ
        copy_widget = QWidget()
        copy_widget.setGeometry(QRect(0, 0, 0 ,0))
        copy_layout = QHBoxLayout()
        copy_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        copy_widget.setLayout(copy_layout)
        but_w = 40
        widget_w = 240
        copy_widget.setMinimumWidth(widget_w)
        copy_widget.setMaximumWidth(widget_w)
        copy_widget.setMaximumHeight(WIDGET_HEIGHT)
        tip = lang.Lang(en='Copy Color', ja=u'カラーのコピー').output()
        self.copy_but = qt.make_flat_btton(name='Copy', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        self.copy_but.clicked.connect(self.copy_color)
        copy_layout.addWidget(self.copy_but)
        tip = lang.Lang(en='Paste Color\nLeft click >> RGB paste\nRight click >> RGBA paste', ja=u'カラーのペースト\n左クリック→RGBペースト\n右クリック→RGBAペースト').output()
        self.paste_but = qt.make_flat_btton(name='Paste', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        self.paste_but.clicked.connect(self.paste_color)
        self.paste_but.rightClicked.connect(lambda : self.paste_color(alpha=True))
        copy_layout.addWidget(self.paste_but)
        tip = lang.Lang(en='Open Color Setting', ja=u'カラー設定を開く').output()
        color = map(lambda c : int(c*255), self.copy_colors)[0:3]
        self.color_but = qt.make_flat_btton(name='', bg=color, ui_color=color, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=False, checkable=False, destroy_flag=True, tip=tip)
        self.color_but.clicked.connect(self.open_color_dialog)
        copy_layout.addWidget(self.color_but)
        rgba_text = self.make_rgba_text(self.copy_colors)
        but_w = 110
        self.rgb_value_but = qt.make_flat_btton(name=rgba_text, text=160, bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        copy_layout.addWidget(self.rgb_value_but)
        self.rgb_value_but.setDisabled(True)#無効化
        copy_layout.addWidget(self.rgb_value_but)
        
        self.but_list.append(copy_widget)
        
        #追加ツール群
        tool_widget = QWidget()
        tool_widget.setGeometry(QRect(0, 0, 0 ,0))
        tool_layout = QHBoxLayout()
        tool_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        tool_widget.setLayout(tool_layout)
        but_w = 55
        widget_w = 125
        tool_widget.setMinimumWidth(widget_w)
        tool_widget.setMaximumWidth(widget_w)
        tool_widget.setMaximumHeight(WIDGET_HEIGHT)
        tip = lang.Lang(en='Start vertex color paint tool', ja=u'頂点カラーペイントツール起動').output()
        self.paint_but = qt.make_flat_btton(name='Paint', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        self.paint_but.clicked.connect(lambda : mel.eval('PaintVertexColorTool;'))
        tool_layout.addWidget(self.paint_but)
        but_w = 62
        tip = lang.Lang(en='Start color set editor', ja=u'カラーセットエディターを起動').output()
        self.color_set_but = qt.make_flat_btton(name='SetEditor', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        self.color_set_but.clicked.connect(lambda : mel.eval('colorSetEditor;'))
        tool_layout.addWidget(self.color_set_but)
        self.but_list.append(tool_widget)
        
        self.set_column_stretch()#ボタン間隔が伸びないようにする
        #self.init_but_width_list(but_list=self.but_list)#配置実行
        
        self.main_layout.addWidget(qt.make_h_line())
        
        #スライダー作成
        sld_layout = QHBoxLayout()
        self.weight_input = EditorDoubleSpinbox()#スピンボックス
        self.weight_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.weight_input.setRange(0, 255)
        self.weight_input.setValue(0.0)#値を設定
        self.weight_input.setDecimals(0)#値を設定
        #qt.change_widget_color(self.weight_input, textColor=string_col, bgColor=mid_color, baseColor=bg_col)
        sld_layout.addWidget(self.weight_input)
        #スライダバーを設定
        self.weight_input_sld = QSlider(Qt.Horizontal)
        self.weight_input_sld.setRange(0, 255)
        sld_layout.addWidget(self.weight_input_sld)
        #スライダーとボックスの値をコネクト
        self.weight_input.valueChanged.connect(self.change_from_spinbox)
        self.weight_input.wheeled.connect(lambda : self.store_keypress(True))
        self.weight_input.wheeled.connect(lambda : self.calc_cell_value(from_spinbox=True))
        self.weight_input.editingFinished.connect(lambda : self.calc_cell_value(from_spinbox=True))
        self.weight_input.focused.connect(lambda : self.store_keypress(False))
        self.weight_input.keypressed.connect(lambda : self.store_keypress(True))
        #self.weight_input.focused.connect(lambda : self.sel_all_weight_input(widget=self.weight_input))
        
        self.weight_input_sld.valueChanged.connect(self.change_from_sld)
        self.weight_input_sld.sliderPressed.connect(self.sld_pressed)
        self.weight_input_sld.valueChanged.connect(lambda : self.calc_cell_value(from_spinbox=False))
        self.weight_input_sld.sliderReleased.connect(self.sld_released)
        
        self.main_layout.addLayout(sld_layout)
        
        #テーブル作成-----------------------------------------------------------------------
        self.view_widget = RightClickTableView(self)
        self.view_widget.verticalHeader().setDefaultSectionSize(20)
        self.view_widget.rightClicked.connect(self.get_clicke_item_value)
        self.view_widget.keyPressed .connect(self.direct_cell_input)
        self.main_layout.addWidget(self.view_widget)
        
        #Hueスライダー作成----------------------------------------------------------------
        hs_layout = QHBoxLayout()
        self.main_layout.addLayout(hs_layout)
        
        hue_layout = QHBoxLayout()
        hs_layout.addLayout(hue_layout)
        
        label = QLabel('H - ')
        hue_layout.addWidget(label)
        
        tip = lang.Lang(en='Hue', ja=u'Hue / 色相').output()
        self.hue_input = EditorSpinbox()#スピンボックス
        self.hue_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.hue_input.setRange(-180, 180)
        self.hue_input.setValue(0.0)#値
        self.hue_input.setToolTip(tip)
        hue_layout.addWidget(self.hue_input)
        #スライダバーを設定
        self.hue_input_sld = QSlider(Qt.Horizontal)
        self.hue_input_sld.setRange(-180, 180)
        self.hue_input_sld.setToolTip(tip)
        hue_layout.addWidget(self.hue_input_sld)
        #スライダーとボックスの値をコネクト
        self.hue_input_sld.sliderPressed.connect(self.hsv_sld_pressed)
        self.hue_input.wheeled.connect(lambda : self.store_keypress(True))
        self.hue_input.wheeled.connect(lambda : self.hue_input_sld.setValue(self.hue_input.value()))
        self.hue_input.editingFinished.connect(lambda : self.hue_input_sld.setValue(self.hue_input.value()))
        self.hue_input.focused.connect(lambda : self.store_keypress(False))
        self.hue_input.keypressed.connect(lambda : self.store_keypress(True))
        self.hue_input_sld.valueChanged[int].connect(self.hue_input.setValue)
        self.hue_input_sld.valueChanged.connect(lambda : self.change_color_hsv(mode='hue'))
        self.hue_input_sld.sliderReleased.connect(self.hsv_sld_released)
        
        hs_layout.addWidget(qt.make_v_line())
        #saturationスライダー作成----------------------------------------------------------------
        saturation_layout = QHBoxLayout()
        hs_layout.addLayout(saturation_layout)
        label = QLabel('S - ')
        saturation_layout.addWidget(label)
        
        tip = lang.Lang(en='Saturation', ja=u'Saturation / 彩度').output()
        self.saturation_input = EditorSpinbox()#スピンボックス
        self.saturation_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.saturation_input.setRange(-255, 255)
        self.saturation_input.setValue(0.0)#値を設定
        self.saturation_input.setToolTip(tip)#値を設定
        saturation_layout.addWidget(self.saturation_input)
        #スライダバーを設定
        self.saturation_input_sld = QSlider(Qt.Horizontal)
        self.saturation_input_sld.setRange(-255, 255)
        self.saturation_input_sld.setToolTip(tip)#値を設定
        saturation_layout.addWidget(self.saturation_input_sld)
        #スライダーとボックスの値をコネクト
        self.saturation_input_sld.sliderPressed.connect(self.hsv_sld_pressed)
        self.saturation_input.wheeled.connect(lambda : self.store_keypress(True))
        self.saturation_input.wheeled.connect(lambda : self.saturation_input_sld.setValue(self.saturation_input.value()))
        self.saturation_input.editingFinished.connect(lambda : self.saturation_input_sld.setValue(self.saturation_input.value()))
        self.saturation_input.focused.connect(lambda : self.store_keypress(False))
        self.saturation_input.keypressed.connect(lambda : self.store_keypress(True))
        self.saturation_input_sld.valueChanged[int].connect(self.saturation_input.setValue)
        self.saturation_input_sld.valueChanged.connect(lambda : self.change_color_hsv(mode='saturation'))
        self.saturation_input_sld.sliderReleased.connect(self.hsv_sld_released)
        
        #Valueスライダー作成----------------------------------------------------------------
        vc_layout = QHBoxLayout()
        self.main_layout.addLayout(vc_layout)
        
        value_layout = QHBoxLayout()
        vc_layout.addLayout(value_layout)
        label = QLabel('V - ')
        value_layout.addWidget(label)
        
        self.value_input = EditorSpinbox()#スピンボックス
        self.value_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.value_input.setRange(-255, 255)
        self.value_input.setValue(0.0)#値を設定
        tip = lang.Lang(en='Value', ja=u'Value / 明度').output()
        self.value_input.setToolTip(tip)
        value_layout.addWidget(self.value_input)
        #スライダバーを設定
        self.value_input_sld = QSlider(Qt.Horizontal)
        self.value_input_sld.setRange(-255, 255)
        self.value_input_sld.setToolTip(tip)
        value_layout.addWidget(self.value_input_sld)
        #スライダーとボックスの値をコネクト
        self.value_input_sld.sliderPressed.connect(self.hsv_sld_pressed)
        self.value_input.wheeled.connect(lambda : self.store_keypress(True))
        self.value_input.wheeled.connect(lambda : self.value_input_sld.setValue(self.value_input.value()))
        self.value_input.editingFinished.connect(lambda : self.value_input_sld.setValue(self.value_input.value()))
        self.value_input.focused.connect(lambda : self.store_keypress(False))
        self.value_input.keypressed.connect(lambda : self.store_keypress(True))
        self.value_input_sld.valueChanged[int].connect(self.value_input.setValue)
        self.value_input_sld.valueChanged.connect(lambda : self.change_color_hsv(mode='value'))
        self.value_input_sld.sliderReleased.connect(self.hsv_sld_released)
        
        vc_layout.addWidget(qt.make_v_line())
        #contrastスライダー作成----------------------------------------------------------------
        contrast_layout = QHBoxLayout()
        vc_layout.addLayout(contrast_layout)
        label = QLabel('C - ')
        contrast_layout.addWidget(label)
        
        self.contrast_input = EditorSpinbox()#スピンボックス
        self.contrast_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.contrast_input.setRange(-100, 100)
        self.contrast_input.setValue(0.0)#値を設定
        tip = lang.Lang(en='Contrast', ja=u'Contrast / コントラスト').output()
        self.contrast_input.setToolTip(tip)
        contrast_layout.addWidget(self.contrast_input)
        #スライダバーを設定
        self.contrast_input_sld = QSlider(Qt.Horizontal)
        self.contrast_input_sld.setRange(-100, 100)
        self.contrast_input_sld.setToolTip(tip)
        contrast_layout.addWidget(self.contrast_input_sld)
        #スライダーとボックスの値をコネクト
        self.contrast_input_sld.sliderPressed.connect(self.hsv_sld_pressed)
        self.contrast_input.wheeled.connect(lambda : self.store_keypress(True))
        self.contrast_input.wheeled.connect(lambda : self.contrast_input_sld.setValue(self.contrast_input.value()))
        self.contrast_input.editingFinished.connect(lambda : self.contrast_input_sld.setValue(self.contrast_input.value()))
        self.contrast_input.focused.connect(lambda : self.store_keypress(False))
        self.contrast_input.keypressed.connect(lambda : self.store_keypress(True))
        self.contrast_input_sld.valueChanged[int].connect(self.contrast_input.setValue)
        self.contrast_input_sld.valueChanged.connect(lambda : self.change_color_hsv(mode='contrast'))
        self.contrast_input_sld.sliderReleased.connect(self.hsv_sld_released)
        
        #multiplyスライダー作成----------------------------------------------------------------
        m_layout = QHBoxLayout()
        self.main_layout.addLayout(m_layout)
        
        multiply_layout = QHBoxLayout()
        m_layout.addLayout(multiply_layout)
        label = QLabel('M - ')
        multiply_layout.addWidget(label)
        
        self.multiply_input = EditorDoubleSpinbox()#スピンボックス
        self.multiply_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.multiply_input.setRange(0, 5)
        self.multiply_input.setValue(1.0)#値を設定
        tip = lang.Lang(en='Multiply', ja=u'Multiply / 乗算').output()
        self.multiply_input.setToolTip(tip)
        multiply_layout.addWidget(self.multiply_input)
        #スライダバーを設定
        self.multiply_input_sld = QSlider(Qt.Horizontal)
        self.multiply_input_sld.setRange(0, 500)
        self.multiply_input_sld.setValue(100)
        self.multiply_input_sld.setToolTip(tip)
        multiply_layout.addWidget(self.multiply_input_sld)
        #スライダーとボックスの値をコネクト
        self.multiply_input_sld.sliderPressed.connect(self.hsv_sld_pressed)
        self.multiply_input.wheeled.connect(lambda : self.store_keypress(True))
        self.multiply_input.wheeled.connect(lambda : self.multiply_input_sld.setValue(self.multiply_input.value()*100))
        self.multiply_input.editingFinished.connect(lambda : self.multiply_input_sld.setValue(self.multiply_input.value()*100))
        self.multiply_input.focused.connect(lambda : self.store_keypress(False))
        self.multiply_input.keypressed.connect(lambda : self.store_keypress(True))
        self.multiply_input_sld.valueChanged.connect(lambda : self.multiply_input.setValue(self.multiply_input_sld.value()/100.0))
        self.multiply_input_sld.valueChanged.connect(lambda : self.change_color_hsv(mode='multiply'))
        self.multiply_input_sld.sliderReleased.connect(self.hsv_sld_released)
        
        multiply_layout.addWidget(qt.make_v_line())
        
        tip = lang.Lang(en='Reset color adjustment slider', ja=u'カラー調整スライダーをリセット').output()
        self.reset_but = qt.make_flat_btton(name=' Reset HSV ', bg=self.hilite, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        self.reset_but.clicked.connect(self.reset_hsv_palm)
        multiply_layout.addWidget(self.reset_but)
        
        self.main_layout.addWidget(qt.make_h_line())
        
        #--------------------------------------------------------------------------------------------
        msg_layout = QHBoxLayout()
        
        tip = lang.Lang(en='Show latest release page', ja=u'最新リリースページを表示').output()
        self.release_but = qt.make_flat_btton(name='', bg=self.hilite, border_col=180, w_max=BUTTON_HEIGHT, w_min=BUTTON_HEIGHT, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=self.icon_path+'release.png', tip=tip)
        self.release_but.clicked.connect(lambda : webbrowser.open(REREASE_PATH))
        msg_layout.addWidget(self.release_but)
        
        tip = lang.Lang(en='Display help page', ja=u'ヘルプページの表示').output()
        self.help_but = qt.make_flat_btton(name='', bg=self.hilite, border_col=180, w_max=BUTTON_HEIGHT, w_min=BUTTON_HEIGHT, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=self.icon_path+'help.png', tip=tip)
        self.help_but.clicked.connect(lambda : webbrowser.open(HELP_PATH))
        msg_layout.addWidget(self.help_but)
        
        msg_layout.addWidget(qt.make_v_line())
        
        #実行時間のお知らせ
        self.main_layout.addLayout(msg_layout)
        self.time_label = QLabel('- Calculation Time - 0.00000 sec')
        self.time_label.setMaximumWidth(200)
        self.time_label.setMinimumWidth(200)
        msg_layout.addWidget(self.time_label)
        
        msg_layout.addWidget(qt.make_v_line())
        
        #ウェイトエディタからの通知
        self.msg_label = QLabel('')
        msg_layout.addWidget(self.msg_label)
        
        msg_layout.setSpacing(6)#ウェジェットどうしの間隔を設定する
        
        self.get_set_vertex_color()#起動時に取得実行
        self.create_job()
        self.change_add_mode(id=self.mode)
        
    def reset_hsv_palm(self):
        self.sel_model_init_flag = False
        self.restore_hsv_sld_value()
        self.restore_flag = False
        
    #hsvスライダリリース時の特殊処理
    restore_flag = False
    def hsv_sld_pressed(self):
        self.pushed_data = []
        for data in self._data:
            if len(data) >= 8:
                color_data = data[7]
                pushed_color = [c for c in color_data]
                self.pushed_data.append(pushed_color)
            else:
                self.pushed_data.append('')
                
        self.pushed_hue_value = self.pre_pre_hue_value
        self.pushed_saturation_value = self.pre_pre_saturation_value
        self.pushed_value_value = self.pre_pre_value_value
        self.pushed_contrast_value = self.pre_pre_contrast_value
        self.change_flag = True#スライダー操作中のみ値の変更を許可するフラグ
        
    #hsvスライダリリース時の特殊処理
    restore_flag = False
    def hsv_sld_released(self):
        self.change_flag = False
        #self.change_color_hsv()
        self.bake_vertex_color(realbake=False, ignoreundo=False)
        #self.restore_hsv_sld_value()
        if self.open_chunk_flag:
            self.open_chunk_flag = False
        #print 'close cunk in slider released'
        cmds.undoInfo(closeChunk=True)
        
    pre_hue_value = 0.0
    pre_saturation_value = 0.0
    pre_value_value = 0.0
    pre_contrast_value = 0.0
    pre_multiply_value = 1.0
    pre_pre_hue_value = 0.0
    pre_pre_saturation_value = 0.0
    pre_pre_value_value = 0.0
    pre_pre_contrast_value = 0.0
    pre_pre_multiply_value = 1.0
    bake_times = 0
    open_chunk_flag = False
    def change_color_hsv(self, mode='hue'):
        if mode == 'hue':
            if self.hue_input.value() == self.pre_hue_value:
                print 'same hue values return :'
                return
                
        if mode == 'saturation':
            if self.saturation_input.value() == self.pre_saturation_value:
                print 'same saturation values return :'
                return
                
        if mode == 'value':
            if self.value_input.value() == self.pre_value_value:
                print 'same value values return :'
                return
                
        if mode == 'contrast':
            if self.contrast_input.value() == self.pre_contrast_value:
                print 'same value values return :'
                return
                
        if mode == 'multiply':
            if self.multiply_input.value() == self.pre_multiply_value:
                print 'same multiply values return :'
                return
                
        if self.restore_flag :
            #print 'restore_sld return :'
            self.pre_hue_value = self.hue_input.value()
            self.pre_saturation_value = self.saturation_input.value()
            self.pre_value_value = self.value_input.value() / 255.0
            self.pre_contrast_value = self.contrast_input.value()
            self.pre_multiply_value = self.multiply_input.value()
            self.restore_flag = False
            return
            
        if not self.selected_items:
            all_rows = list(set(xrange(self.all_rows))-set(self.mesh_rows))
        else:
            all_rows = set([item.row()  for item in self.selected_items])
            
            
        if self.change_flag:
            contrast_value = (self.contrast_input.value() - self.pushed_contrast_value) / 50.0 + 1.0
            hue_value = self.hue_input.value() - self.pushed_hue_value
            saturation_value = self.saturation_input.value() - self.pushed_saturation_value
            value_value = self.value_input.value()  / 255.0 - self.pushed_value_value
            multiply_value = self.multiply_input.value()
        else:
            contrast_value = (self.contrast_input.value() - self.pre_contrast_value) / 50.0 + 1.0
            hue_value = self.hue_input.value() - self.pre_hue_value
            saturation_value = self.saturation_input.value() - self.pre_saturation_value
            value_value = self.value_input.value()  / 255.0 - self.pre_value_value
            if self.pre_multiply_value != 0.0:
                multiply_value = self.multiply_input.value() / self.pre_multiply_value
            else:
                multiply_value = self.multiply_input.value()
        #HSVに直してから再計算
        for row in all_rows:
            node, vid = self.get_row_vf_node_data(row)
            if self.change_flag:
                org_colors = [col for col in self.pushed_data[row]]
            else:
                org_colors = [col for col in self._data[row][7]]
            temp_rgb = org_colors[:3]
            hue, saturation, value = self.rgb2hsv(temp_rgb)
            if mode == 'contrast':
                for rgba in range(3):
                    offset = 0
                    col = org_colors[rgba] - 0.5
                    if col < 0 and contrast_value < 0:
                        max_value = 0.5
                    else:
                        max_value = 1.0
                    if col >= 0 and contrast_value < 0:
                        min_value = 0.5
                    else:
                        min_value = 0.0
                    if col == 0:
                        col = 0.004
                        offset = 0.004
                    col = col * contrast_value + 0.5
                    col = min([1.0, max([0, col])])
                    col = min([max_value, max([min_value, col])])
                    self.mesh_color_dict[node][vid][rgba] = col 
            elif mode == 'multiply':
                for rgba in range(3):
                    col = org_colors[rgba] * multiply_value
                    col = min([1.0, max([0, col])])
                    self.mesh_color_dict[node][vid][rgba] = col
            else:
                if mode == 'hue':
                    hue += hue_value
                elif mode == 'saturation':
                    if len(set(temp_rgb)) != 1 :
                        saturation += saturation_value
                        saturation = max([0, saturation])
                        saturation = min([255, saturation])
                elif mode == 'value':
                    value += value_value
                new_rgb = self.hsv2rgb(hue, saturation, value)
                if mode == 'value':
                    new_rgb = [min([1.0, max([0, rgb])]) for rgb in new_rgb]
                #メッシュ辞書の値を更新するだけでよい
                for rgba in range(3):
                    self.mesh_color_dict[node][vid][rgba] = new_rgb[rgba]
                
        #焼きこみ
        #print 'bake times :', self.bake_times, self.change_flag
        self.bake_times += 1
        
        if not self.key_pressed  and not self.change_flag:
            #print 'slider press in beking func  open chunk:'
            self.open_chunk_flag = True
            cmds.undoInfo(openChunk=True)
            #self.bake_vertex_color(realbake=False, ignoreundo=True)
            #self.change_flag = True
        if self.channel_but_group.checkedId() == 0:
            self.bake_vertex_color(realbake=True, ignoreundo=self.change_flag)#焼き付け実行
        else:
            self.bake_vertex_color(realbake=False, ignoreundo=self.change_flag)#アンドゥ履歴だけ残しにいく。実際のベイクはしない。
            self.change_view_channel()
        
        #スライダー復帰のために前々回入力を保持
        self.pre_pre_hue_value = self.pre_hue_value
        self.pre_pre_saturation_value = self.pre_saturation_value
        self.pre_pre_value_value = self.pre_value_value
        self.pre_pre_contrast_value = self.pre_contrast_value
        self.pre_pre_multiply_value = self.pre_multiply_value
            
        self.pre_hue_value = self.hue_input.value()
        self.pre_saturation_value = self.saturation_input.value()
        self.pre_value_value = self.value_input.value() / 255.0
        self.pre_contrast_value = self.contrast_input.value()
        self.pre_multiply_value = self.multiply_input.value()
        
    sel_model_init_flag = False
    def restore_hsv_sld_value(self):
        #print 'restore_hsv_value :', self.sel_model_init_flag
        if self.sel_model_init_flag:
            self.restore_flag = False
            self.sel_model_init_flag = False
        else:
            self.restore_flag = True
            self.hue_input_sld.setValue(0)
            self.restore_flag = True
            self.saturation_input_sld.setValue(0)
            self.restore_flag = True
            self.value_input_sld.setValue(0)
            self.restore_flag = True
            self.contrast_input_sld.setValue(0)
            self.restore_flag = True
            self.multiply_input_sld.setValue(100.0)
            self.pre_hue_value = 0.0
            self.pre_saturation_value = 0.0
            self.pre_value_value = 0.0
            self.pre_contrast_value = 0.0
            self.pre_multiply_value = 1.0
            self.pre_pre_hue_value = 0.0
            self.pre_pre_saturation_value = 0.0
            self.pre_pre_value_value = 0.0
            self.pre_pre_contrast_value = 0.0
            self.pre_pre_multiply_value = 1.0
            
    def hsv2rgb(self, hue, saturation, value):
        max_rgb = value
        min_rgb = max_rgb - ((saturation / 255) * max_rgb)
        if hue < 0:
            hue += 360
        elif hue > 360:
            hue -= 360
            
        if 0 <= hue <= 60:
            r = max_rgb
            g = (hue / 60) * (max_rgb - min_rgb) + min_rgb
            b= min_rgb
        elif 60 < hue <= 120:
            r = ((120 - hue) / 60) * (max_rgb - min_rgb) + min_rgb
            g = max_rgb
            b= min_rgb
        elif 120 < hue <= 180:
            r = min_rgb
            g = max_rgb
            b= ((hue - 120) / 60) * (max_rgb - min_rgb) + min_rgb
        elif 180 < hue <= 240:
            r = min_rgb
            g = ((240 - hue) / 60) * (max_rgb - min_rgb) + min_rgb
            b = max_rgb
        elif 240 < hue <= 300:
            r= ((hue - 240) / 60) * (max_rgb - min_rgb) + min_rgb
            g= min_rgb
            b = max_rgb
        elif 300 < hue <= 360:
            r = max_rgb
            g= min_rgb
            b = ((360 - hue) / 60) * (max_rgb - min_rgb) + min_rgb
        #print r, g, b
        return [r, g, b]
        
    #rgbをhsvに変換して返す
    def rgb2hsv(self, rgb):
        hue =0 
        #rgb = map(lambda c : c*255, rgb)
        max_rgb = max(rgb)
        min_rgb = min(rgb)
        if len(set(rgb)) == 1:
            hue = 0
        else:
            if rgb[0] == max_rgb:
                hue = 60 * ((rgb[1] - rgb [2]) / (max_rgb - min_rgb))
            elif rgb[1] == max_rgb:
                hue = 60 * ((rgb[2] - rgb [0]) / (max_rgb - min_rgb)) + 120
            elif rgb[2] == max_rgb:
                hue = 60 * ((rgb[0] - rgb [1]) / (max_rgb - min_rgb)) + 240
        if hue < 0:
            hue += 360
        
        if max_rgb != 0.0:
            saturation = (max_rgb - min_rgb) / max_rgb * 255
        else:
            saturation = 0.0
        
        value = max_rgb
        #print  hue, saturation, value
        return hue, saturation, value
    
    #カラーダイアログを開く
    def open_color_dialog(self):
        self.colorDialog = QColorDialog()
        color = map(lambda c : int(c*255), self.copy_colors)[0:3]
        self.colorDialog.setCurrentColor(QColor(*color))
        #カスタムカラー取得
        if os.path.exists(self.custom_color_path):#保存ファイルが存在したら
            with open(self.custom_color_path, 'r') as f:
                self.custom_color = json.load(f)
            #カスタムカラーを設定する
            for i, c in self.custom_color.items():
                self.colorDialog.setCustomColor(int(i), c)
        response = self.colorDialog.exec_()
        if response != QDialog.Accepted:
            return
        chosen = self.colorDialog.currentColor()
        color = [chosen.red(), chosen.green(), chosen.blue()]
        qt.change_button_color(self.color_but, textColor=0, bgColor=color, hiColor=color, 
                                            mode='button', hover=False, destroy=True)
        self.copy_colors = map(lambda c : c/255.0, color) + [self.copy_colors[3]]
        #カスタムカラー保存--------------------------------
        costom_colors = {}
        for i in range(17):
            #print 'save change custom color :', self.colorDialog.customColor(i)
            costom_colors[i] = self.colorDialog.customColor(i)
        with open(self.custom_color_path, 'w') as f:
            #print 'save'
            json.dump(costom_colors, f)
        
    def make_rgba_text(self, colors):
        text_list = [str(int(color*255)) for color in colors]
        text = ':'.join(text_list)
        return text
        
    #カラーのコピー
    copy_colors = [0.502, 0.502, 0.502, 1.0]
    def copy_color(self):
        if self.selected_items:
            row = self.selected_items[0].row()
        else:
            selectable_rows = list(set(xrange(self.all_rows))-set(self.mesh_rows))
            if not selectable_rows:
                return
            row = selectable_rows[0]
        self.copy_colors = [col for col in self._data[row][7]]
        color = map(lambda c : int(c*255), self.copy_colors)[0:3]
        qt.change_button_color(self.color_but, textColor=0, bgColor=color, hiColor=color, 
                                            mode='button', hover=False, destroy=True)
        rgba_text = self.make_rgba_text(self.copy_colors)
        self.rgb_value_but.setText(rgba_text)
                      
    #カラーのペースト
    def paste_color(self, alpha=False):
        copy_colors = self.copy_colors[:]
        if not self.selected_items:
            all_rows = list(set(xrange(self.all_rows))-set(self.mesh_rows))
        else:
            all_rows = set([item.row()  for item in self.selected_items])
        for row in all_rows:
            node, vid = self.get_row_vf_node_data(row)
            if alpha:
                color_num = 4
            else:
                org_colors = [col for col in self._data[row][7]]
                copy_colors[3] = org_colors[3]
                color_num = 3
            #メッシュ辞書の値を更新するだけでよい
            for rgba in range(color_num):
                self.mesh_color_dict[node][vid][rgba] = copy_colors[rgba]
        #焼きこみ
        if self.channel_but_group.checkedId() == 0:
            self.bake_vertex_color(realbake=True, ignoreundo=self.change_flag)#焼き付け実行
        else:
            self.bake_vertex_color(realbake=False, ignoreundo=self.change_flag)#アンドゥ履歴だけ残しにいく。実際のベイクはしない。
            self.change_view_channel()
            
     #ロックボタン解除されたら更新する
    def check_unlock(self):
        if not self.lock_but.isChecked():
            self.get_set_vertex_color()
        
    #ウェイト入力窓を選択するジョブ
    def sel_all_weight_input(self, widget=None):
        cmds.scriptJob(ro=True, e=("idle", lambda : self.select_box_all(widget=widget)), protected=True)
        
    def select_box_all(self, widget=None):
        try:
            widget.selectAll()
        except:
            pass
            
    numeric_list = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '-', '.']
    def direct_cell_input(self, string):
        if not self.sel_model.selectedIndexes():
            return
        if string in self.numeric_list:
            self.view_widget.ignore_key_input = True#一時的にテーブルへのキー入力無効
            self.input_box = PopInputBox(value=string, 
                                        mode=self.mode_but_group.checkedId(),
                                        direct=True)
            self.input_box.closed.connect(lambda : self.apply_input_box_value(direct=True))
            
    #右クリックしたときの小窓を反映する。
    def get_clicke_item_value(self):
        #ヘッダーの幅を取得してカラム位置をオフセットする
        v_header = self.view_widget.verticalHeader()
        v_header_width = v_header.sizeHint().width()
        h_header = self.view_widget.horizontalHeader()
        h_header_height = h_header.sizeHint().height()
        
        pos = self.view_widget.mapFromGlobal(QCursor.pos())
        pos_x = pos.x() - v_header_width - 2#誤差補正
        pos_y = pos.y() - h_header_height -2 #誤差補正
        row = self.view_widget.rowAt(pos_y)
        column = self.view_widget.columnAt(pos_x)
        if column == -1:
            column = 3
        text = self.color_model.get_data(row=row, column=column)
        try:
            if self.norm_but.isChecked():
                value = float(text)
            else:
                value = int(float(text)*255)
            self.input_box = PopInputBox(value = value, float_flag=self.norm_but.isChecked(),  mode=self.mode_but_group.checkedId())
            self.input_box.closed.connect(self.apply_input_box_value)
        except:
            pass
    
    #右クリック入力を確定して反映する
    def apply_input_box_value(self, direct=True):
        if direct:
            try:
                self.input_box_value = float(self.input_box.input.text())
            except:
                return
        else:
            self.input_box_value = self.input_box.input.value()
        self.calc_cell_value(from_spinbox=True, from_input_box=True)
        
        #フォーカスを取る
        self.activateWindow()
        self.raise_()
        #Pyside1だとなぜか繰り返さないとフォーカス取れない
        self.view_widget.setFocus()
        self.weight_input.clearFocus()
        self.view_widget.setFocus()
        #キー入力受付をもとに戻す
        self.view_widget.ignore_key_input = False
        
    #加算モードが変更されたらスライダー反映式を変える
    add_mode = 0
    def change_from_sld(self):
        if self.norm_but.isChecked():
            if self.add_mode == 0 or self.add_mode == 1:
                div_num = 1000.0
        else:
            if self.add_mode == 0 or self.add_mode == 1:
                div_num = 1
        if self.add_mode == 2:
                div_num = 10.0
        self.weight_input.setValue(self.weight_input_sld.value()/div_num)
        
    def change_from_spinbox(self):
        if self.norm_but.isChecked():
            if self.add_mode == 0 or self.add_mode == 1:
                mul_num = 1000.0
        else:
            if self.add_mode == 0 or self.add_mode == 1:
                mul_num = 1
        if self.add_mode == 2:
                mul_num = 10.0
        self.weight_input_sld.setValue(self.weight_input.value()*mul_num)
    
    #加算モード変更時、最大最小と小数点以下桁数を変更する
    def change_add_mode(self, id, change_only=False):
        #print 'change add mode :', id
        self.add_mode = id
        if id == 0:
            if len(self.selected_items) ==1:
                value = self.color_model.get_data(self.selected_items[0])
                #print 'get single abs value :', value
                if self.norm_but.isChecked():
                        self.weight_input_sld.setValue(float(value)*1000)
                else:
                        self.weight_input_sld.setValue(int(value*255))
                if change_only:
                    return
        if self.norm_but.isChecked():
            if id == 0:
                self.weight_input.setRange(0, 1)
                self.weight_input.setDecimals(3)
                self.weight_input_sld.setRange(0, 1000)
            if id == 1:
                self.weight_input.setRange(-1, 1)
                self.weight_input.setDecimals(3)
                self.weight_input_sld.setRange(-1000, 1000)
        else:
            if id == 0:
                self.weight_input.setRange(0, 255)
                self.weight_input.setDecimals(0)
                self.weight_input_sld.setRange(0, 255)
            if id == 1:
                self.weight_input.setRange(-255, 255)
                self.weight_input.setDecimals(0)
                self.weight_input_sld.setRange(-255, 255)
        if id == 2:
            self.weight_input.setRange(-100, 100)
            self.weight_input.setDecimals(1)
            self.weight_input_sld.setRange(-1000, 1000)
            self.weight_input_sld.setValue(0)
        self.pre_add_value = 0.0
        self.weight_input.setValue(0)
        self.weight_input_sld.setValue(0)
        #self.get_source_value()#ソースリストを取得
            
    #ボタンが左詰めになるように調整
    def set_column_stretch(self):
        self.def_but_width_list = self.init_but_width_list(self.but_list)
        for i in range(self.def_but_width_list[-1]):
            self.unique_layout.setColumnStretch(i, 0)
        self.unique_layout.setColumnStretch(i+1, 1)
        
    def init_but_width_list(self, but_list):
        but_width_list = [0]
        sum_width = 0
        for but in but_list:
            sum_width += but.width()
            but_width_list.append(sum_width)
        return but_width_list
        
    def resizeEvent(self, event):
        if self.init_flag:
            return
        #print 'resize event : ', event.size()
        win_x = event.size().width()
        self.re_arrangement_but(win_x=win_x, grid_v=0, but_list=self.but_list, loop=0)
        
    check_window_dict = defaultdict(lambda: -1)
    def check_window_size(self, win_x, but_width_list):
        self.def_but_width_list
        for i, but_width in enumerate(self.def_but_width_list[::-1][:-1]):
            if win_x > but_width+40:#ウィンドウの幅がボタン幅より広かったら配置して次の再帰へ
                self.window_size_id = i
                break
        if self.window_size_id == self.check_window_dict[str(but_width_list)]:
            return False
        self.check_window_dict[str(but_width_list)] = self.window_size_id
        return True
        
    pre_row_count = 0
    def re_arrangement_but(self, win_x, grid_v, but_list, loop):
        if loop >100:
            return
        if not but_list:
            return
        but_width_list = self.init_but_width_list(but_list)
        arrangement_list = [0]
        for i, but_width in enumerate(but_width_list[::-1][:-1]):
            if win_x > but_width+40:#ウィンドウの幅がボタン幅より広かったら配置して次の再帰へ
                if i != 0:
                    set_but_list = but_list[:-i]
                else:
                    set_but_list = but_list[:]
                for j, but in enumerate(set_but_list):
                    self.unique_layout.addWidget(but, grid_v, but_width_list[j], 1, but.width())
                break
        but_num = len(but_list)-i
        new_but_list = but_list[but_num:]
        self.re_arrangement_but(win_x=win_x, grid_v=grid_v+1, but_list=new_but_list, loop=loop+1)
        
    def init_list_dict(self):
        self.mesh_color_dict = {}
        self.pre_hl_nodes = []
        self.hl_nodes = []
        self.pre_sel = []
        self.pre_sel_vertices = []
        self.temp_vf_face_dict = {}
        self.temp_vf_vtx_dict = {}
        self.node_vertex_dict_dict = {}#頂点とIDの対応辞書のノードごとの辞書
        self.node_vertex_dict = {}#メッシュとフェース頂点ID辞書
        self.hilite_flag = False
        self.sel_vertices_dict = defaultdict(lambda : [])
        self.show_flag = False
    
    #UIに選択コンポーネントのバーテックスカラーを反映
    #@prof.profileFunction()
    @timer
    def get_set_vertex_color(self, sel_vertices=None, cycle=False, clear=False, reselect=False):
        try:
            if cmds.selectMode(q=True, o=True) and not self.show_mesh_but.isChecked():
                return
            if cmds.selectMode(q=True, co=True) and not self.show_comp_but.isChecked():
                return
        except Exception as e:
            print e.message
            #print 'UI Allready Closed :'
            return
        if self.hilite_flag:
            self.hilite_flag = False
            #print 'in select from ui mode return :'
            return
            
        self.counter.reset()
        
        
        self.pre_mesh_color_dict = {}
        for mesh, color_list in self.mesh_color_dict.items():
            self.pre_mesh_color_dict[mesh] = color_list[:]
        
        #クリアボタン押されたときは全部初期化
        if clear:
            sel = []
            self.hl_nodes = []
            sel_vertices = []
        else:#
            sel = cmds.ls(sl=True, l=True)
            #ロックボタンが押されているときの挙動
            if self.lock_but.isChecked() and self.pre_hl_nodes and not cycle:
                self.hl_nodes = self.pre_hl_nodes
            else:
                self.hl_nodes = cmds.ls(sl=True, l=True, tr=True)+cmds.ls(hl=True, l=True)
                self.hl_nodes = common.search_polygon_mesh(self.hl_nodes, fullPath=True)
                self.hl_nodes = list(set(self.hl_nodes))
            if sel_vertices is None:
                self.sel_vertices_dict = defaultdict(lambda : [])
                sel_vertices = []
                #現在選択している頂点を取得
                sList = om2.MGlobal.getActiveSelectionList()
                iter = om2.MItSelectionList(sList)
                while not iter.isDone():
                    dagPath, component = iter.getComponent() 
                    mesh_path_name = dagPath.fullPathName()
                    if cmds.nodeType(mesh_path_name) == 'mesh':
                        mesh_path_name = cmds.listRelatives(mesh_path_name, p=True, f=True)[0]
                    #ロック時に前回ハイライトの中に含まれてなかったらスキップ
                    if not mesh_path_name in self.hl_nodes:
                        iter.next()
                        continue
                    meshFn = om2.MFnMesh(dagPath)
                    fv_array, _, _ = self.convert_comp_to_fv_list(dagPath, meshFn, component)
                    self.sel_vertices_dict[mesh_path_name] = fv_array
                    sel_vertices += fv_array
                    iter.next()
            else:
                if sel_vertices:
                    self.sel_vertices_dict = sel_vertices
        self.view_vertices = sel_vertices
                
        if self.pre_sel == sel and sel_vertices is None:
            return
            
            
        self.pre_sel_vertices = sel_vertices
        self.counter.count(string='get mesh vtx :')
        
        #カラーセットが切り替えられたときにRGB復旧する用の辞書
        self.current_color_dict = {}
        if not reselect:
            for node in self.hl_nodes[:]:
                sList = om2.MSelectionList()
                sList.add(node)
                dagPath, component = sList.getComponent(0)
                
                meshTr = om2.MFnTransform(dagPath)
                meshFn = om2.MFnMesh(dagPath)
                
                cur_color_set_list = cmds.polyColorSet(meshFn.fullPathName(), q=True, currentColorSet=True)
                #colorSerがない場合は処理をスキップしてぬける
                if cur_color_set_list == None:
                    self.hl_nodes.remove(node)
                    continue
                else:
                    cur_color_set = cur_color_set_list[0]
                self.current_color_dict[node] = cur_color_set
                mesh_vtx_colors = meshFn.getFaceVertexColors(cur_color_set)
                
                #色変更のために辞書格納しておく
                if self.channel_but_group.checkedId() == 0 or not node in self.pre_hl_nodes:
                    self.mesh_color_dict[meshTr.fullPathName()] = mesh_vtx_colors
                    shape = cmds.listRelatives(node, s=True, fullPath=True)
                    fv_array, f_array, v_array = self.convert_comp_to_fv_list(dagPath, meshFn, component)
                    self.temp_vf_face_dict[node] = f_array
                    self.temp_vf_vtx_dict[node] = v_array
                    self.node_vertex_dict[node] = fv_array
                    self.node_vertex_dict_dict[node] = {fv:i for i, fv in enumerate(fv_array)}
                    
            self.org_mesh_color_dict = {}#アンドゥできるコマンドのためにオリジナルの値を保持
            for mesh, color_list in self.mesh_color_dict.items():
                self.org_mesh_color_dict[mesh] = color_list[:]
            
        self.counter.count(string='get vtx color :')
        
        if not sel_vertices:
            sel_vertices = []
        self.norm_value_list = []
        
        norm_flag = self.norm_but.isChecked()
        self.all_rows = 0#右クリックウィンドウ補正用サイズを出すため全行の桁数を数える
        self._data = []#全体のテーブルデータを格納する
        self.mesh_rows = []
        self.vtx_row_dict = {}#行と頂点の対応辞書
        self.v_header_list = []#縦ヘッダーの表示リスト
        for node in self.hl_nodes:
            self.mesh_rows.append(self.all_rows)
            self.all_rows += 1
            items = ['', '', '', '', '']
            self._data.append(items)
            
            node_vertices = self.node_vertex_dict[node]
            
            target_vertices = self.sel_vertices_dict[node]#メッシュごとの選択頂点
            
            self.v_header_list.append(node.split('|')[-1].split(':')[-1])
            
            if target_vertices:
                vertex_dict = self.node_vertex_dict_dict[node]
                rgba_list = self.mesh_color_dict[node]
                items = []#各行のカラムを格納するアイテムリスト
                #integrater = prof.IntegrationCounter()
                for vf_id in target_vertices:
                    vid = vertex_dict[vf_id]
                    #integrater.count('vid   ')
                    rgba = rgba_list[vid]#APIのMColorを取得
                    #integrater.count('rgba  ')
                    self.v_header_list.append(str(vf_id))
                    #header_name = str(vf_id).replace('(', 'v[').replace(')', ']').replace(', ', '] f[')#結構処理負荷
                    #integrater.count('header')
                    self._data.append([rgba[0], rgba[1], rgba[2], rgba[3], node, vid, vf_id, rgba])
                    #integrater.count('append')
                    self.all_rows += 1#全体の行数を数えておく
                    #integrater.count('all count')
                #integrater.integration_print()
            
        self.counter.count('setup ui data :')
        
        try:#都度メモリをきれいに
            del self.color_model._data
            self.color_model._data = {}
        except Exception as e:
            print e.message, 'in get set'
        try:#テーブルモデル消す
            self.color_model.deleteLater()
            del self.color_model
        except Exception as e:
            print e.message, 'in get set'
        try:#選択モデルも消す
            self.sel_model.deleteLater()
            del self.sel_model
        except Exception as e:
            print e.message, 'in get set'
            
        self.color_model = TableModel(self._data, self.view_widget, self.mesh_rows, self.v_header_list)
        self.color_model.norm = self.norm_but.isChecked()#ノーマル状態かどうかを渡しておく
        
        self.sel_model = QItemSelectionModel(self.color_model)#選択モデルをつくる
        self.sel_model.selectionChanged.connect(self.cell_changed)#シグナルをつなげておく
        self.sel_model.selectionChanged.connect(self.restore_hsv_sld_value)#シグナルをつなげておく
        self.view_widget.setModel(self.color_model)#表示用モデル設定
        self.view_widget.setSelectionModel(self.sel_model)#選択用モデルを設定
        
        #HSBスライダーをリセット
        self.sel_model_init_flag = False
        self.restore_hsv_sld_value()
        self.sel_model_init_flag = True
        self.restore_flag = False
        
        self.set_color_channel()
        #カラーチャンネル変更があったらリセット
        self.reset_color_channel()
        self.pre_sel = sel
        self.selected_items = []
        
        #Showしとかないと起動時選択があった場合にset_header_widthがめちゃ遅くなる
        if not self.show_flag:
            self.show_flag = True
            self.show()
        
        self.counter.count('ui data finalaize :')
        
        set_header_width(self.view_widget, self.color_model)
        #前回の選択を格納
        self.pre_hl_nodes = self.hl_nodes
        self.counter.count('ui create model list dict :')
        
        self.counter.lap_print(print_flag=COUNTER_PRINT, window=self)
        
    
    #コンポーネント選択、メッシュ選択をアレイに変換して返す
    def convert_comp_to_fv_list(self, meshDag, meshFn, component):
        fv_array = []
        f_array = []
        v_array = []
        #現在選択中のコンポーネントを取得
        cmpType = None
        #フェースバーテックスならそのまま取得
        if component.hasFn(om2.MFn.kMeshVtxFaceComponent):
            cmpType = "facevtx"
            compFn = om2.MFnDoubleIndexedComponent(component)
            fv_array = compFn.getElements()
            pre_fid = None
            v_array = set()
            for fv in fv_array:
                fid = fv[1]
                vid = fv[0]
                v_array.add(vid)
                if pre_fid != fid:
                    f_array.append(fid)
                    pre_fid = fid
        #頂点なら全フェースバーテックスを捜査して含まれるものを取得
        elif component.hasFn(om2.MFn.kMeshVertComponent):
            cmpType = "vtx"
            compFn = om2.MFnSingleIndexedComponent(component)
            vids = compFn.getElements()
            v_dict = {vid:None for vid in vids}
            polyIter = om2.MItMeshPolygon(meshDag)
            for fid in range(polyIter.count()):
                f_array.append(fid)
                vtxArray = polyIter.getVertices()
                for vid in vtxArray:
                    try:
                        v_dict[vid]
                        v_array.append(vid)
                        fv_array.append((vid, fid))
                    except:
                        pass
                polyIter.next(1)
        #エッジならいったん重複のない頂点セットに置き換えてフェースバーテックスを走査
        elif component.hasFn(om2.MFn.kMeshEdgeComponent):
            cmpType = "edge"
            compFn = om2.MFnSingleIndexedComponent(component)
            eid = compFn.getElements()
            eSet = []
            v_dict = {}
            for e in eid:
                evid = meshFn.getEdgeVertices(e)
                eSet.extend(evid)
                v_dict[evid[0]] = None
                v_dict[evid[1]] = None
            vids = list(set(eSet))
            polyIter = om2.MItMeshPolygon(meshDag)
            for fid in range(polyIter.count()):
                f_array.append(fid)
                vtxArray = polyIter.getVertices()
                for vid in vtxArray:
                    try:
                        v_dict[vid]
                        v_array.append(vid)
                        fv_array.append((vid, fid))
                    except:
                        pass
                polyIter.next(1)
        #フェースなら含まれるバーテックスを取得してID生成
        elif component.hasFn(om2.MFn.kMeshPolygonComponent):
            cmpType = "face"
            compFn = om2.MFnSingleIndexedComponent(component)
            fids = compFn.getElements()
            fSet = []
            for fid in fids:
                f_array.append(fid)
                vids = meshFn.getPolygonVertices(fid)
                for vid in vids:
                    v_array.append(vid)
                    fv_array.append((vid, fid))
        #メッシュなら事前取得分をそのまま適用
        if not cmpType:
            #全てのコンポーネントも取っておく       
            polyIter = om2.MItMeshPolygon(meshDag)
            for fid in range(polyIter.count()): 
                vtxArray = polyIter.getVertices()
                #print 'mesh iter :', fid, vtxArray
                for vid in vtxArray:
                    f_array.append(fid)
                    v_array.append(vid)
                    fv_array.append((vid, fid))
                polyIter.next(1)
        
        return fv_array, f_array, v_array
        
    def hide_all_vertex_color(self):
        tr = cmds.ls(tr=True)
        cmds.polyOptions(tr,colorShadedDisplay=False)
        
    def show_all_vertex_color(self):
        tr = cmds.ls(tr=True)
        cmds.polyOptions(tr, colorShadedDisplay=True)
        cmds.polyOptions(tr,colorMaterialChannel='ambientDiffuse')

    #セルの選択変更があった場合に現在の選択セルを格納する
    selected_items = []
    @timer
    def cell_changed(self, selected, deselected):
        self.select_change_flag = True
        self.selected_items =  self.sel_model.selectedIndexes()
        self.change_add_mode(self.add_mode, change_only=True)
        self.pre_add_value = 0.0#加算量を初期化
        if self.highlite_but.isChecked():
            self.hilite_vertices()
        
    @timer
    def hilite_vertices(self):
        self.counter.reset()
        self.sel_rows = list(set([item.row() for item in self.selected_items]))
        if len(self.sel_rows) == len(self.view_vertices):
            #全行選択された場合は選択時間短縮のためワイルドカードを与える
            #10～60倍くらい早い
            vertices = self.view_vertices
            vertices = []
            for node in self.hl_nodes:
                 vertices.append(node + '.vtxFace[*][*]')
        else:
            vertices = []
            for r in self.sel_rows:
                node = self._data[r][4]
                vf = self._data[r][6]
                vertices.append(node + '.vtxFace['+str(vf[0])+']['+str(vf[1])+']')
        cmds.selectMode(co=True)
        self.hilite_flag = True
        self.counter.count(string='get cell vtx :')
        #コンポーネントが細かく分かれているから選択に時間がかかるっぽい
        cmds.select(vertices, r=True)
        self.counter.count(string='select vtx :')
        self.counter.lap_print(print_flag=COUNTER_PRINT)
            
    def reset_hilite(self):
        if not self.highlite_but.isChecked():
            self.hilite_flag = True
            cmds.select(cl=True)
        else:
            self.cell_changed(self.selected_items, None)
        
    #Adjustボタン押したとき、頂点選択しにいく
    def select_vertex_from_cells(self):
        #print 'select_vertex_from_cells'
        rows = list(set([item.row() for item in self.selected_items]))
        vertices = []
        for r in rows:
            node = self._data[r][4]
            vf = self._data[r][6]
            vertices.append(node + '.vtxFace['+str(vf[0])+']['+str(vf[1])+']')
        if vertices:
            cmds.selectMode(co=True)
            cmds.select(vertices, r=True)
            
    #選択されているセルの行のみの表示に絞る
    def show_selected_cells(self):
        rows = list(set([item.row() for item in self.selected_items]))
        sel_vertices_dict = defaultdict(lambda : {})
        for r in rows:
            node = self._data[r][4]
            vid = self._data[r][5]
            vf = self._data[r][6]
            vertex_dict = sel_vertices_dict[node]
            vertex_dict[vf] = vid
        #sel_vertices_dict[node] += vf
        self.get_set_vertex_color(sel_vertices=sel_vertices_dict, reselect=True)
                
    def show_all_cells(self):
        self.get_set_vertex_color(cycle=True)
            
    #スピンボックスがフォーカス持ってからきーが押されたかどうかを格納しておく
    def store_keypress(self, pressed):
        self.key_pressed = pressed
        
    #行の情報をまとめて返す
    def get_row_vf_node_data(self, row):
        row_datas = self._data[row]
        return row_datas[4], row_datas[5]
        
    pre_add_value = 0.0
    selected_items = []
    select_change_flag = True
    #入力値をモードに合わせてセルの値と合算、セルに値を戻す
    @timer
    def calc_cell_value(self, from_spinbox=False, from_input_box=False):
        if not self.selected_items:
            #print 'culc cell value , nothing selection return:'
            return
        self.text_value_list = []
        if not self.change_flag and not from_spinbox:
            return
        #絶対値モードでフォーカス外したときに0だった時の場合分け
        if from_spinbox and not self.key_pressed and not from_input_box:
            #print 'forcus error :'
            return
        
        self.counter.reset()
        
        if not from_input_box:
            add_value = self.weight_input.value()
        else:
            add_value = self.input_box_value
        
        self.counter.count(string='set add value :')
        
        #絶対値の時の処理
        if self.add_mode == 0:#abs
            self.norm_value_list = []
            if self.norm_but.isChecked():
                new_value = add_value
            else:
                #計算誤差修正モードの場合は255値に0.5足して計算する
                if self.add_5_but.isChecked():
                    add_value += 0.5
                new_value = int(add_value)/255.0
            #0-1.0でクランプ
            new_value = min([1.0, new_value])
            new_value = max([0, new_value])
            
            #まとめてデータ反映
            for cell_id in self.selected_items:
                #self.color_model.setData(cell_id, new_value)
                #焼き込みようリストを更新しておく
                row = cell_id.row()
                column = cell_id.column() 
                rgba = column
                node, vid = self.get_row_vf_node_data(row)
                self.mesh_color_dict[node][vid][rgba] = new_value#全ての頂点の情報更新
            if self.norm_but.isChecked():
                after_value = new_value
            else:
                after_value = int(new_value*255)
        else:
            #最大最小を設定しておく
            min_value = 0.0
            max_n_value = 1.0
            max_value = 255
            if self.add_5_but.isChecked():
                add5_value = 0.5
            else:
                add5_value = 0.0
            #加算の時の処理
            sub_value = add_value - self.pre_add_value
            ratio = add_value/100
            for cell_id in self.selected_items:
                #焼き込みようリストを更新しておく
                row = cell_id.row()
                column = cell_id.column() 
                rgba = column
                
                #元の値を取得
                node, vid = self.get_row_vf_node_data(row)
                rgba_list = self.mesh_color_dict[node]
                org_value = rgba_list[vid][rgba]
                
                if self.add_mode == 1:#add
                    if self.norm_but.isChecked():
                        new_value = org_value + sub_value
                    else:#誤差補正のため一旦255に戻して計算する
                        new_value = (int(org_value * 255) + sub_value + add5_value) / 255.0
                    
                if self.add_mode == 2:#add%
                    if self.norm_but.isChecked():
                        new_value = org_value * (1.0 + ratio)
                    else:#誤差補正のため一旦255に戻して計算する
                        int_value = org_value*255
                        new_value = (int_value + int(int_value * ratio) + add5_value) / 255.0
                    
                if new_value > 1.0:
                    new_value = 1.0
                elif new_value < 0.0:
                    new_value = 0.0
                    
                #self.color_model.setData(cell_id, new_value)
                self.mesh_color_dict[node][vid][rgba] = new_value#全ての頂点の情報更新
                
            #処理後のスピンボックスの値を設定
            if from_spinbox:
                after_value = 0.0
                self.pre_add_value = 0.0
            else:
                self.pre_add_value = add_value
                after_value = add_value
            
        self.weight_input.setValue(after_value)#UIのスピンボックスに数値反映
        
        self.counter.count(string='calc values :')
        
        #焼きこみ
        if self.channel_but_group.checkedId() == 0:
            self.bake_vertex_color(realbake=True, ignoreundo=self.change_flag)#焼き付け実行
        else:
            self.bake_vertex_color(realbake=False, ignoreundo=self.change_flag)#アンドゥ履歴だけ残しにいく。実際のベイクはしない。
            self.change_view_channel()
            
        self.counter.count(string='bake vertex color :')
        
        self.counter.lap_print(print_flag=COUNTER_PRINT, window=self)
            
    #@timer
    def bake_vertex_color(self, realbake=True, ignoreundo=False):
        #APIでアンドゥ実装したカスタムコマンドのためにグローバル空間に値を保持しておく
        bake_color_dict = {}
        #リドゥが正しく聞くように参照形式から切り離したリストを渡す
        for mesh, color_list in self.mesh_color_dict.items():
            bake_color_dict[mesh] = color_list[:]
        set_current_data(self.hl_nodes, bake_color_dict, self.mesh_color_dict, self.org_mesh_color_dict, self.temp_vf_face_dict, self.temp_vf_vtx_dict)
        cmds.bakeVertexColor(rb=realbake, iu=ignoreundo)
        #アンドゥ履歴用カラーを更新しておく
        self.org_mesh_color_dict = {}
        for mesh, color_list in self.mesh_color_dict.items():
            self.org_mesh_color_dict[mesh] = color_list[:]
        self.refresh_table_view()
        
    #パーセントの時の特殊処理、元の値を保持する
    change_flag = False
    def sld_pressed(self):
        cmds.undoInfo(openChunk=True)
        #マウスプレス直後に履歴を残す焼き込みする。実際のベイクはしない。
        self.bake_vertex_color(realbake=False, ignoreundo=False)
        self.change_flag = True#スライダー操作中のみ値の変更を許可するフラグ
            
    #パーセントの特殊処理、値をリリースして初期値に戻る
    def sld_released(self):
        self.calc_cell_value()
        self.change_flag = False
        if self.add_mode == 1 or self.add_mode == 2:
            self.weight_input.setValue(0.0)
            self.change_from_spinbox()
            self.pre_add_value = 0.0
        cmds.undoInfo(closeChunk=True)
        
    #ノーマルモードを切り替える
    @timer
    def change_normal_mode(self):
        self.pre_add_value = 0.0#加算量を初期化
        self.color_model.norm = self.norm_but.isChecked()#ノーマル状態かどうかを渡しておく
        self.refresh_table_view()
        global MAXIMUM_DIGIT
        if self.norm_but.isChecked():
            MAXIMUM_DIGIT = 1.0
        else:
            MAXIMUM_DIGIT = 100
        
    #ビューの状態を更新する
    def refresh_table_view(self):
        #フォーカス移してテーブルの状態を更新する
        #self.setFocus()
        self.view_widget.setFocus()
        self.view_widget.clearFocus()
        #self.raise_()
            
    #チャンネル表示変更、API版
    @timer
    def change_view_channel(self, id=None, change_node=None, reset=False):
        self.cc_counter = prof.LapCounter()
        self.cc_counter.reset()
        if id is None:
            id = self.channel_but_group.checkedId()
        if id == 0 and self.pre_channel_id == 0 and not reset:
            #print 'not need reset, pre_id is RGBA return :'
            return
        if change_node:#選択が変わったときの変更処理
            target_nodes = change_node
            if self.channel_but_group.checkedId() == 0:
                #print 'not need reset channel return :'
                return
            mesh_color_dict = self.mesh_color_dict
        else:#UIからの変更処理
            target_nodes = self.hl_nodes
            mesh_color_dict = self.mesh_color_dict
        #print 'change color channel :', id
        #print 'change node flag :', change_node
        #print 'reset flag :', reset
        if id == 0:#RGBA全て表示
            #以前がRGBAチャンネル以外の表示の時のみ特殊処理で復旧する
            self.reset_to_rgba(target_nodes, self.pre_channel_id)
        else:
            for node in target_nodes:
                #print 'change view channel :', node
                vertices = self.node_vertex_dict[node]
                if not vertices:
                    continue
                #print 'check target vert :', target_vertices
                temp_rgba_list = mesh_color_dict[node][:]#OM2のMColorArray
                if id == 1:#RGBAのみ表示
                    for color in temp_rgba_list:
                        color[3] = 1.0
                else:#各チャンネル表示
                    cid = id - 2
                    alpha = [1.0]
                    for color in temp_rgba_list:
                        color[0] = color[cid]
                        color[1] = color[cid]
                        color[2] = color[cid]
                        color[3] = 1.0
                self.cc_counter.count(string='culc vtx rgba data:')
        
                #dagPathを名前から取得してくる
                sList = om2.MSelectionList()
                sList.add(node)
                dagPath = sList.getDagPath(0)
                #meshTr  = om2.MFnTransform(dagPath)
                meshFn = om2.MFnMesh(dagPath)
                #チャンネル変更は履歴残さないのでそのまま焼き付け
                meshFn.setFaceVertexColors(temp_rgba_list,  self.temp_vf_face_dict[node], self.temp_vf_vtx_dict[node])
        
        self.pre_channel_id = id
        #print 'change pre channnel id :', id
        self.cc_counter.count(string='change color channel:')
            
        self.cc_counter.lap_print(print_flag=COUNTER_PRINT, window=self)
        
    #各チャンネルの変更を考慮してオリジナルチャンネルに復旧する
    def reset_to_rgba(self, target_nodes, pre_id):
        #print 'reset to rgba', target_nodes
        rgba_id = pre_id - 2
        for node in target_nodes:
            #print 'reset to origin :', node, pre_id
            sList = om2.MSelectionList()
            sList.add(node)
            dagPath, component = sList.getComponent(0)
            meshFn = om2.MFnMesh(dagPath)
            cur_color_set_list = cmds.polyColorSet(meshFn.fullPathName(), q=True, currentColorSet=True)
            if cur_color_set_list == None:
                continue
            else:
                cur_color_set= cur_color_set_list[0]
            #print 'temp_color_set :', cur_color_set
            #現在のチャンネルカラー
            temp_colors = meshFn.getFaceVertexColors(cur_color_set)
            
            org_colors = self.mesh_color_dict[node]#OM2のMColorArray
            #print 'check_org_color :', org_colors
            #print 'check_tmp_color :', temp_colors 
            
            if pre_id == 1:#RGB表示の場合
                for temp_color, org_color in zip(temp_colors, org_colors):
                    org_color[0] = temp_color[0]
                    org_color[1] = temp_color[1]
                    org_color[2] = temp_color[2]
            else:#各チャンネル表示の場合はオリジナルカラーの単独チャネル置き換え
                #print 'check rgba id :', rgba_id
                for temp_color, org_color in zip(temp_colors, org_colors):
                    org_color[rgba_id] = temp_color[0]
            #self.up_data_color_data(node, new_colors)
            #print 'check_org_color :', org_colors
        pre_hl_nodes = self.hl_nodes
        self.hl_nodes = target_nodes
        self.bake_vertex_color()
        self.refresh_table_view()
        self.hl_nodes = pre_hl_nodes
        
        
    #ペイント検出
    color_job_list = list()
    def create_color_job(self):
        #print 'create_color_job'
        self.kill_color_job()
        self.color_job_list = list()
        
        selection = set(cmds.ls(sl=True, l=True, tr=True)+cmds.ls(hl=True, l=True, tr=True))
        #print 'create color attr job :', selection
        for node in selection:
            shape = cmds.listRelatives(node, s=True, f=True)
            color_hist = cmds.ls(cmds.listHistory(node), type='polyColorPerVertex')
            if shape:
                try:
                    job = cmds.scriptJob(attributeChange=[shape[0] + '.colorSet[0].representation', self.update_colors])
                    self.color_job_list.append(job)
                except:
                    pass
            if color_hist:
                try:
                    job = cmds.scriptJob(attributeChange=[color_hist[0] + '.output', self.update_colors])
                    self.color_job_list.append(job)
                except:
                    pass
                    
    #ペイント、セット変更の更新をUIに反映する
    up_count = 0
    def update_colors(self, nodes=None, force=False, id=None):
        if self.restore_rgb_flag and not force:
            #print 'update colors in restore_rgb_colors , restore flag return :'
            return
        #アクティブウィンドウが自分自身ならアップデート不要なので逃げる
        if QApplication.activeWindow() == self:
            #print 'active window is self return :'
            return
        #print 'update_colors **-*-*-*-*-', self.up_count, nodes
        self.up_count += 1
        #print 'update color data :'
        if id is None:
            id = self.channel_but_group.checkedId()
        loop_list = [range(4), range(3), [0], [1], [2], [3]][id]
        if nodes is None:
            nodes = self.hl_nodes
        for node in nodes:
            sList = om2.MSelectionList()
            sList.add(node)
            dagPath, component = sList.getComponent(0)
            meshFn = om2.MFnMesh(dagPath)
            
            cur_color_set_list = cmds.polyColorSet(node, q=True, currentColorSet=True)
            if cur_color_set_list == None:
                continue
            else:
                cur_color_set= cur_color_set_list[0]
            temp_colors = meshFn.getFaceVertexColors(cur_color_set)
            
            org_colors = self.mesh_color_dict[node]#OM2のMColorArray
            
            for temp_color, org_color in zip(temp_colors, org_colors):
                for col_id in loop_list:
                    if id <= 4:
                        org_color[col_id] = temp_color[col_id]
                    else:
                        org_color[col_id] = temp_color[0]
        #self.activateWindow()
        #PySide2からリセット方法が変わっているので注意
        #print 'check maya ver :', MAYA_VER
        if MAYA_VER <= 2016:
            #PySide1
            self.color_model.reset()
        else:
            #PySide2
            self.color_model.beginResetModel()
            self.color_model.endResetModel()
            
    #カラージョブを破棄する
    def kill_color_job(self):
        #print 'kill color job :', self.color_job_list
        for job in self.color_job_list:
            #print 'kill color job :', job
            cmds.scriptJob(k=job, f=True)
        self.color_job_list = list()
        
    def kill_reset_color_job(self):
        #print 'kill reset_color job :', self.reset_job_list
        for job in self.reset_job_list:
            #print 'kill reset color job :', job
            cmds.scriptJob(k=job, f=True)
        self.reset_job_list = list()
        
    #カレントカラーセット切替ジョブ
    reset_job_list = list()
    color_job_group_id = 0#アトリビュート重複で複数回回らないように管理するID
    def reset_color_job(self):
        self.kill_reset_color_job()#一旦全部無効化する
        for node in self.hl_nodes:
            #print 'create currentColorSetJob :', node
            try:
                shape = cmds.listRelatives(node, s=True, f=True)
            except:
                continue
            job = cmds.scriptJob(attributeChange=[shape[0] + '.currentColorSet', self.create_color_job])
            self.reset_job_list.append(job)
            #job = cmds.scriptJob(attributeChange=[shape[0] + '.currentColorSet', self.update_colors])
            #self.reset_job_list.append(job)
            job = cmds.scriptJob(attributeChange=[shape[0] + '.currentColorSet', self.restore_rgb_colors])
            self.reset_job_list.append(job)
    
    #カレントカラーが切り替えられたとき、RGBカラーを正しく復旧しておく
    reset_times = 0
    restore_rgb_flag = False
    def restore_rgb_colors(self):
        self.restore_rgb_flag = True#カラーレストア中は変更再適用しないフラグ
        #print self.restore_rgb_flag
        #self.kill_reset_color_job()#カラージョブ一旦無効
        #print 'restore rgb color :', '/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*', self.reset_times
        cur_color_set_dict = {}#一時変更したカレントカラーセットをもとに戻す辞書
        for node in self.hl_nodes:
            pre_color_set = self.current_color_dict[node]
            #print 'pre cor color set :', node, pre_color_set
            cur_color_set_list = cmds.polyColorSet(node, q=True, currentColorSet=True)
            #現在のカラーセットがなければスルー
            if cur_color_set_list == None:
                #print 'no color set :', node
                continue
            else:
                cur_color_set = cur_color_set_list[0]
                #print 'changed cor color set :', node, cur_color_set
            #現在と変更前が同じだったらスルー
            if cur_color_set == pre_color_set:
                #print 'color set no change return :', node, cur_color_set, pre_color_set
                continue
            #RGBA表示なら復旧不要なのでデータ更新のみ
            if not self.channel_but_group.checkedId() == 0:
                #再変更前の現在のカラーセットを記録
                cur_color_set_dict[node] = cur_color_set
                #以前のカラーセットに戻してチャンネル復旧
                cmds.polyColorSet(node, currentColorSet=True, colorSet=pre_color_set)
                #print 'set to pre color set :', node, pre_color_set
                self.change_view_channel(id=0, change_node=[node], reset=True)
                #print 'reset view channel :', pre_color_set
                #変更後のカラーセットに戻してからビューチャンネル変更
                cmds.polyColorSet(node, currentColorSet=True, colorSet=cur_color_set)
            #print 'run update colors'
            self.update_colors(nodes=[node], force=True, id=0)
            #print 'update_color form restore rgb :', node
            self.change_view_channel(change_node=[node])#一旦RGBAに戻しておく
                
            #最後に現在のカラーセットを更新
            self.current_color_dict[node] = cur_color_set
        self.reset_times += 1
        cmds.scriptJob(ro=True, e=("idle", self.init_restore_rgb_flag), protected=True)
    
    def init_restore_rgb_flag(self):
        self.restore_rgb_flag = False
        

    #カレントカラーセットジョブを破棄する
    def kill_reset_job(self):
        for job in self.reset_job_list:
            #print 'kill reset job :', job
            cmds.scriptJob(k=job, f=True)
        self.reset_job_list = list()
        
    #選択変更時に解除されたメッシュのチャンネル表示を元に戻す
    def reset_color_channel(self):
        target_nodes = list(set(self.pre_hl_nodes)-set(self.hl_nodes))
        if target_nodes:
            qt.Callback(self.change_view_channel(id=0, change_node=target_nodes, reset=True))
        
    #選択変更時に新たに選択されたメッシュのチャンネルを変更する
    def set_color_channel(self):
        channel_id = self.channel_but_group.checkedId()
        if channel_id == 0:
            return
        target_nodes = list(set(self.hl_nodes)-set(self.pre_hl_nodes))
        if target_nodes:
            qt.Callback(self.change_view_channel(id=channel_id, change_node=target_nodes))
        
    #ウィンドウ閉じたら全部チャンネル初期化する
    def reset_channel_as_close(self):
        channel_id = self.channel_but_group.checkedId()
        if channel_id == 0:
            return
        if self.lock_but.isChecked():
            target_nodes = self.hl_nodes
        else:
            if cmds.selectMode(q=True, co=True):
                target_nodes = cmds.ls(hl=True, l=True)
            else:
                target_nodes = cmds.ls(sl=True, l=True, tr=True)
        if target_nodes:
            qt.Callback(self.change_view_channel(id=0, change_node=target_nodes, reset=False))
                
    select_job = None
    color_job = None
    corrent_set_job = None
    def create_job(self):
        if self.select_job:
            cmds.scriptJob(k=self.select_job, f=True)
        self.select_job = cmds.scriptJob(cu=True, e=("SelectionChanged", self.get_set_vertex_color))
        
        #ペイント検出
        if self.color_job:
            cmds.scriptJob(k=self.color_job, f=True)
        self.color_job = cmds.scriptJob(cu=True, e=("SelectionChanged", self.create_color_job))
        self.create_color_job()
        
        #カラーセット変更ジョブ
        if self.corrent_set_job:
            cmds.scriptJob(k=self.corrent_set_job, f=True)
        self.corrent_set_job = cmds.scriptJob(cu=True, e=("SelectionChanged", self.reset_color_job))
        self.reset_color_job()
        
    def remove_job(self):
        if self.select_job:
            cmds.scriptJob(k=self.select_job, f=True)
            self.select_job = None
            
        #ペイント検出試行錯誤中
        if self.color_job:
            cmds.scriptJob(k=self.color_job, f=True)
            self.color_job = None
        self.kill_color_job()
        
        if self.corrent_set_job:
            cmds.scriptJob(k=self.corrent_set_job, f=True)
            self.corrent_set_job = None
        self.kill_reset_job()
        
        
    def closeEvent(self, e):
        print 'window close :'
        self.remove_job()
        self.reset_channel_as_close()
        self.save_window_data()
        self.erase_func_data()
        self.deleteLater()
        
    def erase_func_data(self):
        print 'erase func data :'
        #ちゃんと消さないと莫大なUIデータがメモリに残り続けるので注意
        try:
            del self.color_model._data
            del self.color_model.mesh_rows
        except Exception as e:
            print e.message, 'in close'
        try:
            self.color_model.deleteLater()
            del self.color_model
        except Exception as e:
            print e.message, 'in close'
        try:#選択モデルも消す
            self.sel_model.deleteLater()
            del self.sel_model
        except Exception as e:
            print e.message, 'in close'
        self.deleteLater()
        try:
            #クラス内変数をすべて初期化
            del self.mesh_color_dict
            del self.pre_hl_nodes
            del self.pre_sel_vertices
            del self.temp_vf_face_dict
            del self.temp_vf_vtx_dict
            del self.node_vertex_dict_dict#頂点とIDの対応辞書のノードごとの辞書
            del self.node_vertex_dict#メッシュとフェース頂点ID辞書
            del self.all_rows#右クリックウィンドウ補正用サイズを出すため全行の桁数を数える
            del self._data#全体のテーブルデータを格納する
            del self.mesh_rows
            del self.vtx_row_dict#行と頂点の対応辞書
        except Exception as e:
            print e.message, 'in close'
            
#アンドゥ辞書を更新しておく。
def update_dict(color_dict):
    window.mesh_color_dict = color_dict
    
#アンドゥリドゥの時に読み直す
def refresh_window():
    global window
    window.get_set_vertex_color(cycle=True)
        
#焼き込みコマンドに渡すためにグローバルに要素を展開
def set_current_data(nodes, bake_color, color, org_color, face, vtx):
    global hl_nodes
    global bake_color_dict
    global color_dict
    global org_color_dict
    global face_dict
    global vtx_dict
    bake_color_dict = bake_color
    hl_nodes = nodes
    color_dict = color
    org_color_dict = org_color
    face_dict = face
    vtx_dict = vtx

def get_current_data():
    global hl_nodes
    global bake_color_dict
    global color_dict
    global org_color_dict
    global face_dict
    global vtx_dict
    return hl_nodes, bake_color_dict, color_dict, org_color_dict, face_dict, vtx_dict
    
# index :Noneの場合全列処理
#@prof.profileFunction()
def set_header_width(view, model, index=None, space=55, add=0):
    if hasattr(view.horizontalHeader(), 'setResizeMode'):
        resize_mode = view.horizontalHeader().setResizeMode  # PySide
    else:
        resize_mode = view.horizontalHeader().setSectionResizeMode # PySide2

    def __resize_main(index):
        width = space + add
        view.setColumnWidth(index, width)

    if index is None:
        count = model.columnCount()
        for i in range(count):
            __resize_main(i)
    else:
        __resize_main(index)
        