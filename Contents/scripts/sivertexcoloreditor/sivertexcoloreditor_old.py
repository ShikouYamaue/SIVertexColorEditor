# -*- coding: utf-8 -*-
from maya import cmds
from maya import mel
import pymel.core as pm
from . import common
from . import lang
from . import qt
from . import prof
import re
import os
import locale
from collections import defaultdict
import copy
import time
import datetime as dt
import maya.api.OpenMaya as om2
import itertools
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya.app.general.mayaMixin import MayaQWidgetBaseMixin
import json
import imp
try:
    imp.find_module('PySide2')
    from PySide2.QtWidgets import *
    from PySide2.QtGui import *
    from PySide2.QtCore import *
except ImportError:
    from PySide.QtGui import *
    from PySide.QtCore import *

#速度計測結果を表示するかどうか
COUNTER_PRINT = False

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
    
#速度計測結果を表示するかどうか
COUNTER_PRINT = True
#COUNTER_PRINT = False
        
#イベント追加したカスタムスピンボックス
class EditorDoubleSpinbox(QDoubleSpinBox):
    wheeled = Signal()
    focused = Signal()
    keypressed = Signal()
    mousepressed = Signal()
    
    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)
        self.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            #print 'focusin'
            self.focused.emit()
            #return True
        if event.type() == QEvent.Wheel:
            #print 'wheeled'
            cmds.scriptJob(ro=True, e=("idle", self.emit_wheel_event), protected=True)
            #return True
        if event.type() == QEvent.KeyPress:
            self.keypressed.emit()
        if event.type() == QEvent.MouseButtonPress:
            #print 'mousePressed'
            self.mousepressed.emit()
        return False
    def emit_wheel_event(self):
        self.wheeled.emit()
        
class PopInputBox(MayaQWidgetBaseMixin, QMainWindow):
    closed = Signal()
    def __init__(self, parent = None, value=0.0, float_flag=True, mode=0):
        super(self.__class__, self).__init__(parent)
        #↓ウインドウ枠消す設定、MayaUIだとなんかバグる
        #self.setWindowFlags(Qt.FramelessWindowHint| Qt.WindowStaysOnTopHint)
        self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint)
        #self.setWindowFlags(Qt.Window|Qt.WindowStaysOnTopHint)
        
        #wrapper = QWidget(self)
        #self.setCentralWidget(wrapper)
        #p_layout = QVBoxLayout()
        #wrapper.setLayout(p_layout)
        
        #ラインエディットを作成、フォーカスが外れたら消えるイベントを設定
        self.input = QDoubleSpinBox(self)
        self.setCentralWidget(self.input)
        self.input.setButtonSymbols(QAbstractSpinBox.NoButtons)
        if mode == 0:
            if float_flag:
                self.input.setDecimals(3)
                self.input.setRange(0, 1.0)
            else:
                self.input.setDecimals(0)
                self.input.setRange(0, 255)
            self.input.setValue(value)
        elif mode == 1:
            if float_flag:
                self.input.setDecimals(3)
                self.input.setRange(-1.0, 1.0)
            else:
                self.input.setDecimals(0)
                self.input.setRange(-255, 255)
            self.input.setValue(value)
        elif mode == 2:
                self.input.setDecimals(1)
                self.input.setRange(-999, 999)
        #p_layout.addWidget(self.input)
        self.input.installEventFilter(self)
        #入力が終了したら消える
        self.input.editingFinished.connect(self.close)
        self.input.selectAll()
        
        #位置とサイズ調整
        self.resize(50, 24)
        pos = QCursor.pos()
        self.move(pos.x()-20, pos.y()-12)
        self.show()
        
        #ウィンドウを最前面にしてフォーカスを取る
        self.activateWindow()
        self.raise_()
        self.input.setFocus()
        
    def closeEvent(self, e):
        print 'pop up window closed :', self.input.value()
        self.closed.emit()
        
        
#右クリックウィジェットクラスの作成
class RightClickTableView(QTableView):
    rightClicked = Signal()
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.RightButton:
            self.rightClicked.emit()
        else:
            super(self.__class__, self).mouseReleaseEvent(e)
            
class TableModel(QAbstractTableModel):
    norm = False
    def __init__(self, data, parent=None, mesh_rows=[]):
        self.mesh_rows = mesh_rows
        print 'init mesh row :', self.mesh_rows
        super(TableModel, self).__init__(parent)
        self._data = data
        self.set_index()
        #self.set_header()
        
    def set_index(self):#インデックス一覧を作る
        rows = len(self._data)
        columns = len(self._data[0]) if self.rowCount() else 0
        self.indexes = [(r, c) for r, c in itertools.product(range(rows), range(columns))]
        #print self.indexes
        
    #ヘッダーを設定する関数をオーバーライド
    header_list = ['', '  Red ', 'Green', ' Blue ', 'Alpha', 'Color']
    def headerData(self, col, orientation, role):
        u"""見出しを返す"""
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            #print col
            return self.header_list[col]
        return None
        
    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._data[0]) if self.rowCount() else 0
        
    #データ設定関数をオーバーライド流れてくるロールに応じて処理
    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            row = index.row()
            if 0 <= row < self.rowCount():
                column = index.column()
                #if column == 5:
                    #print 'color column :', row, column
                if 0 <= column < self.columnCount():
                    return self._data[row][column]
        elif role == Qt.BackgroundRole:#バックグラウンドロールなら色変更する
            column = index.column()
            if column == 5:
                row = index.row()
                color = self._data[row][1:4]
                if color[0] == '':
                    return
                if self.norm:
                    color = map(lambda a:int(a*255), color)
                #print color
                return QColor(*color)
                
    def get_data(self, index=None, row=0, column=0):
        try:
            if index:
                value  = self._data[index.row()][index.column()]
            else:
                value  = self._data[row][column]
        except:
            value = 0
        return value
        
    #データセットする関数をオーバライド
    def setData(self, index, value, role=Qt.EditRole):
        if not isinstance(index, tuple):
            #print 'set new value :', index.row(), index.column(), value
            if not index.isValid() or not 0 <= index.row() < len(self._data):
                return
            row = index.row()
            column = index.column()
        else:
            row = index[0]
            column = index[1]
        if role == Qt.EditRole and value != "":
            self._data[row][column] = value
            self.dataChanged.emit((row, column), (row, column))#データをアップデート
            return True
        else:
            return False
            
    # 各セルのインタラクション
    def flags(self, index):
        #print 'set cell flags :', index.row(), index.column()
        row = index.row()
        column = index.column()
        if column in [0, 5] or row in self.mesh_rows:
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
        print 'option'
        global window
        try:
            window.dockCloseEventTriggered()
            window.close()
            #window.deleteLater()
            #del window
        except Exception as e:
            print e.message
        window = MainWindow()
        window.init_flag=False
        if window.floating is False and window.area is not None:
            #window = SiShelfWeight()
            #print 'show'
            window.show(
                dockable=True,
                area=window.area,
                floating=window.floating,
                width=window.sw,
                height=window.sh
            )
        else:
            #print 'show dockable'
            window.resize(window.sw, window.sh)
            window.move(window.pw-8, window.ph-31)
            window.show(dockable=True)
        #window.show(dockable=True,  area='left',  floating=False)
        
class MainWindow(MayaQWidgetDockableMixin, QMainWindow):
    selection_mode = 'tree'
    filter_type = 'scene'
    icon_path = os.path.join(os.path.dirname(__file__), 'icon/')
    
    def init_save(self):
        temp = __name__.split('.')
        self.dir_path = os.path.join(
            os.getenv('MAYA_APP_dir'),
            'Scripting_Files')
        self.w_file = self.dir_path+'/'+temp[-1]+'_window.json'
    
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
                    self.floating = save_data['floating']
                    self.area = save_data['area']
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
            except Exception as e:
                self.init_save_data()
        else:
            self.init_save_data()
            
    def init_save_data(self):
        self.floating = True
        self.area = None
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
    
    def save_window_data(self, display=True):
        if not os.path.exists(self.dir_path):
            os.makedirs(self.dir_path)
        #print('# ' + self.showRepr())
        save_data = {}
        save_data['floating'] = self.isFloating()
        save_data['area'] = self.dockArea()
        dock_dtrl = self.parent()
        pos = dock_dtrl.mapToGlobal(QPoint(0, 0))
        size = self.size()
        save_data['pw'] = pos.x()
        save_data['ph'] = pos.y()
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
        if not os.path.exists(self.dir_path):
            os.makedirs(self.dir_path)
        with open(self.w_file, 'w') as f:
            json.dump(save_data, f)
        
    pre_selection_node = []
    def __init__(self, parent = None, init_pos=False):
        super(self.__class__, self).__init__(parent)
        self.init_save()
        self.wdata = self.load_window_data()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.icon_path = os.path.join(os.path.dirname(__file__), 'icons/')
        print self.icon_path
        #self.setAcceptDrops(True)#ドロップ可能にしておく
        self._init_ui()
        #self.show_window()#Showしてないとなぜかモデルデータ取得が遅いので最初にShow
    
    show_flag = False
    def show_window(self):
        self.show_flag = True
        self.resize(440, 700)
        self.move(0, 100)
        self.show(dockable=True)
    
    def _init_ui(self, job_create=True):
        self.counter = prof.LapCounter()
        self.init_flag=True
        sq_widget = QScrollArea(self)
        sq_widget.setWidgetResizable(True)#リサイズに中身が追従するかどうか
        sq_widget.setFocusPolicy(Qt.NoFocus)#スクロールエリアをフォーカスできるかどうか
        sq_widget.setMinimumHeight(1)#ウィンドウの最小サイズ
        self.setWindowTitle(u'SI Vertex Color Editor')
        self.setCentralWidget(sq_widget)
        
        self.main_layout = QVBoxLayout()
        sq_widget.setLayout(self.main_layout)
        
        self.unique_layout = QGridLayout()
        self.unique_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        self.main_layout.addLayout(self.unique_layout)
        
        self.but_list = []
        
        self.ui_color = 68
        self.hilite = 100
        
        #表示ボタンをはめる
        show_widget = QWidget()
        show_widget.setGeometry(QRect(0, 0, 0 ,0))
        show_layout = QHBoxLayout()
        show_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        show_widget.setLayout(show_layout)
        but_w = 60
        norm_w =75
        but_h = 24
        space = 13
        show_widget.setMinimumWidth(but_w*5+space)
        show_widget.setMaximumWidth(but_w*5+space)
        tip = Lang(en='Show only selected cells', jp=u'選択セルのみ表示').output()
        self.show_but = make_flat_btton(name='Show', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        tip = Lang(en='Show all cells', jp=u'全てのセルを表示').output()
        self.show_all_but = make_flat_btton(name='Show All', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, tip=tip)
        self.focus_but = make_flat_btton(name='Forcus', text=128, bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True)
        self.focus_but.setDisabled(True)#無効化
        self.filter_but = make_flat_btton(name='Filter', text=128, bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True)
        self.filter_but.setDisabled(True)#無効化
        tip = Lang(en='Highlite points in 3D view to reflect the color editor selection', jp=u'カラーエディタの選択をポイントハイライトに反映').output()
        self.highlite_but = make_flat_btton(name='Highlite', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        self.highlite_but.setChecked(self.hilite_vtx)
        self.show_but.clicked.connect(self.show_selected_cells)
        self.show_all_but.clicked.connect(self.show_all_cells)
        self.highlite_but.clicked.connect(self.reset_hilite)
        show_layout.addWidget(self.show_but)
        show_layout.addWidget(self.show_all_but)
        show_layout.addWidget(self.focus_but)
        show_layout.addWidget(self.filter_but)
        show_layout.addWidget(self.highlite_but)
        self.but_list.append(show_widget)
        
        #アイコンボタン群
        icon_widget = QWidget()
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(0)#ウェジェットどうしの間隔を設定する
        icon_widget.setLayout(icon_layout)
        but_w = 24
        but_h = 24
        space = 13
        icon_widget.setMinimumWidth(but_w*4+space)
        icon_widget.setMaximumWidth(but_w*4+space)
        tip = Lang(en='Lock display mesh', jp=u'表示メッシュのロック').output()
        self.lock_but = make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, icon=self.icon_path+'lock.png', tip=tip)
        tip = Lang(en='Update the view based on object selection', jp=u'オブジェクト選択に基づきビューを更新').output()
        self.cycle_but = make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=self.icon_path+'cycle.png', tip=tip)
        tip = Lang(en='Clear the view', jp=u'ビューのクリア').output()
        self.clear_but = make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=self.icon_path+'clear.png', tip=tip)
        tip = Lang(en='Select vertices from cell selection', jp=u'セル選択からフェース頂点を選択').output()
        self.adjust_but = make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
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
        but_w = 40
        but_h = 24
        space = 5
        option_widget.setMinimumWidth(but_w*5+space)
        option_widget.setMaximumWidth(but_w*5+space)
        tip = Lang(en='Reflect mesh selection change in UI', jp=u'メッシュ選択変更をUIに反映する').output()
        self.show_mesh_but = make_flat_btton(name='Mesh', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Reflect component selection change in UI', jp=u'コンポーネント選択変更をUIに反映する').output()
        self.show_comp_but = make_flat_btton(name='Comp', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='In the 255 display mode, 0.5 is added to the burning result (error correction for tmd4)', jp=u'255表示モード時、焼き付け結果に0.5加算する(tmd4用誤差修正) ').output()
        self.add_5_but = make_flat_btton(name='+0.5', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Display vertex color of all meshes', jp=u'全メッシュの頂点カラーを表示').output()
        self.show_color_but = make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=False, destroy_flag=True, icon=':/colorPresetSpectrum.png', tip=tip)
        tip = Lang(en='Hide vertex color of all meshes', jp=u'全メッシュの頂点カラーを非表示').output()
        self.hide_color_but = make_flat_btton(name='', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
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
        but_w = 55
        norm_w =60
        but_h = 24
        space = 0
        mode_widget.setMinimumWidth(but_w*3+norm_w+space)
        mode_widget.setMaximumWidth(but_w*3+norm_w+space)
        self.mode_but_group = QButtonGroup()
        tip = Lang(en='Values entered represent absolute values', jp=u'絶対値で再入力').output()
        self.abs_but = make_flat_btton(name='Abs', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Values entered are added to exisiting values', jp=u'既存値への加算入力').output()
        self.add_but = make_flat_btton(name='Add', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Values entered are percentages added to exisiting values', jp=u'既存値への率加算入力').output()
        self.add_par_but = make_flat_btton(name='Add%  ', bg=self.hilite, w_max=but_w+10, w_min=but_w+10, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Change view normalize(0.0-1.0 <> 0-255)', jp=u'カラーの正規化表示切替（0.0～1.0⇔0～255）').output()
        self.norm_but = make_flat_btton(name='Normalize', bg=self.hilite, w_max=norm_w, w_min=norm_w, h_max=but_h, h_min=but_h, 
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
        but_w = 45
        norm_w =75
        but_h = 24
        channel_widget.setMinimumWidth(but_w*6+12)
        channel_widget.setMaximumWidth(but_w*6+12)
        self.channel_but_group = QButtonGroup()
        tip = Lang(en='Draw RGBA channels', jp=u'RGBAチャンネル表示').output()
        self.rgba_but = make_flat_btton(name='RGBA', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Draw RGB channel (Exclude alpha)', jp=u'RGBチャンネル表示（αを除く）').output()
        self.rgb_but = make_flat_btton(name='RGB', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Draw only Red channel', jp=u'Redチャンネルのみ表示').output()
        self.red_but = make_flat_btton(name='Red', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Draw only Green channel', jp=u'Greenチャンネルのみ表示').output()
        self.green_but = make_flat_btton(name='Green', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Draw only Blue channel', jp=u'Blueチャンネルのみ表示').output()
        self.blue_but = make_flat_btton(name='Blue', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        tip = Lang(en='Draw only alpha channel', jp=u'Alphaチャンネルのみ表示').output()
        self.alpha_but = make_flat_btton(name='Alpha', bg=self.hilite, w_max=but_w, w_min=but_w, h_max=but_h, h_min=but_h, 
                                                    flat=True, hover=True, checkable=True, destroy_flag=True, tip=tip)
        self.channel_but_group.buttonClicked.connect(qt.Callback(self.change_view_channel))
        self.channel_but_group.addButton(self.rgba_but, 0)
        self.channel_but_group.addButton(self.rgb_but, 1)
        self.channel_but_group.addButton(self.red_but, 2)
        self.channel_but_group.addButton(self.green_but, 3)
        self.channel_but_group.addButton(self.blue_but, 4)
        self.channel_but_group.addButton(self.alpha_but, 5)
        self.channel_but_group.button(self.rgba).setChecked(True)
        channel_layout.addWidget(self.rgba_but)
        channel_layout.addWidget(self.rgb_but)
        channel_layout.addWidget(self.red_but)
        channel_layout.addWidget(self.green_but)
        channel_layout.addWidget(self.blue_but)
        channel_layout.addWidget(self.alpha_but)
        self.but_list.append(channel_widget)
        
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
        #mainLayout.addWidget(self.__pushSld)
        #スライダーとボックスの値をコネクト。連動するように設定。
        #self.weight_input.editingFinished.connect(self.change_from_spinbox)
        self.weight_input.valueChanged.connect(self.change_from_spinbox)
        self.weight_input.wheeled.connect(lambda : self.store_keypress(True))
        self.weight_input.wheeled.connect(lambda : self.culc_cell_value(from_spinbox=True))
        self.weight_input.editingFinished.connect(lambda : self.culc_cell_value(from_spinbox=True))
        self.weight_input.focused.connect(lambda : self.store_keypress(False))
        self.weight_input.keypressed.connect(lambda : self.store_keypress(True))
        self.weight_input.focused.connect(self.sel_all_weight_input)
        
        self.weight_input_sld.valueChanged.connect(self.change_from_sld)
        self.weight_input_sld.sliderPressed.connect(self.sld_pressed)
        self.weight_input_sld.valueChanged.connect(lambda : self.culc_cell_value(from_spinbox=False))
        self.weight_input_sld.sliderReleased.connect(self.sld_released)
        
        self.main_layout.addLayout(sld_layout)
        
        #self.test_but = QPushButton('reset channel')
        #self.main_layout.addWidget(self.test_but)
        #self.test_but.clicked.connect(self.reset_color_channel)
        
        #self.bake_but = QPushButton('bake')
        #self.main_layout.addWidget(self.bake_but)
        #self.bake_but.clicked.connect(qt.Callback(self.bake_vertex_color))
        
        #テーブル作成
        self.view_widget = RightClickTableView(self)
        #self.view_widget.horizontalHeader().setResizeMode(1, QHeaderView.ResizeToContents)
        #self.view_widget.horizontalHeader().setResizeMode(1, QHeaderView.Interactive)
        #self.view_widget.horizontalHeader().setResizeMode(QHeaderView.Fixed)
        #self.view_widget.horizontalHeader().setDefaultSectionSize(100)
        #self.view_widget.horizontalHeader().resizeSection(1, 1000)
        #self.view_widget.setColumnWidth(1, 1000)
        self.view_widget.verticalHeader().setDefaultSectionSize(20)
        self.view_widget.rightClicked.connect(self.get_clicke_item_value)
        self.main_layout.addWidget(self.view_widget)
        #set_header_width(self.view_widget, self.color_model)
        self.get_set_vertex_color()#起動時に取得実行
        self.create_job()
        self.change_add_mode(id=self.mode)
        
    def check_unlock(self):
        if not self.lock_but.isChecked():
            self.get_set_vertex_color()
        
    #ウェイト入力窓を選択するジョブ
    def sel_all_weight_input(self):
        #self.weight_input.selectAll()
        #print 'select all /*/*/*/*/*/*/*/*/*/*/*/*/'
        cmds.scriptJob(ro=True, e=("idle", self.select_box_all), protected=True)
        
    def select_box_all(self):
        try:
            self.weight_input.selectAll()
        except:
            pass
    #右クリックしたときの小窓を反映する。
    def get_clicke_item_value(self):
        print 'check row count :', self.all_rows, len(str(self.all_rows))
        #offset = 10+8*len(str(self.all_rows))
        pos = self.view_widget.mapFromGlobal(QCursor.pos())
        pos_x = pos.x()-6#誤差補正
        pos_y = pos.y()-24#誤差補正
        #pos = QCursor.pos()
        row = self.view_widget.rowAt(pos_y)
        column = self.view_widget.columnAt(pos_x)
        text = self.color_model.get_data(row=row, column=column)
        try:
            int(text)
        except:
            return
        print  'get item text :', text, pos, row, column
        if self.norm_but.isChecked():
            value = float(text)
        else:
            value = int(text)
        self.input_box = PopInputBox(value = value, float_flag=self.norm_but.isChecked(),  mode=self.mode_but_group.checkedId())
        self.input_box.closed.connect(self.apply_input_box_value)
    
    #右クリック入力を確定して反映する
    def apply_input_box_value(self):
        self.input_box_value = self.input_box.input.value()
        print 'apply float input box value :', self.input_box_value
        self.culc_cell_value(from_spinbox=True, from_input_box=True)
        
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
        print 'change add mode :', id
        self.add_mode = id
        if id == 0:
            if len(self.selected_items) ==1:
                value = self.color_model.get_data(self.selected_items[0])
                print 'get single abs value :', value
                if self.norm_but.isChecked():
                        self.weight_input_sld.setValue(float(value)*1000)
                else:
                        self.weight_input_sld.setValue(int(value))
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
        #if id == 1 or id == 2:
            #self.get_source_value()#元の値を格納しておく
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
        #print 'get all but sum width :', but_width_list
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
        #print self.window_size_id , self.pre_window_size_id
        if self.window_size_id == self.check_window_dict[str(but_width_list)]:
            print 'same id return', self.window_size_id, str(but_width_list)
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
        
    #UIに選択コンポーネントのバーテックスカラーを反映
    all_vtx_rgbs = []
    all_vtx_rgbas = []
    all_vtx_alpha = []
    vrgba_list = []
    vnrgba_list = []
    #nrgba_list = []
    mesh_color_dict = {}
    pre_hl_nodes = []
    hl_nodes = None
    pre_sel = None
    pre_sel_vertices = []
    temp_vf_face_dict = {}
    temp_vf_vtx_dict = {}
    node_vertex_dict_dict = {}#頂点とIDの対応辞書のノードごとの辞書
    hilite_flag = False
    @timer
    def get_set_vertex_color(self, sel_vertices=None, cycle=False, clear=False):
        try:
            if cmds.selectMode(q=True, o=True) and not self.show_mesh_but.isChecked():
                return
            if cmds.selectMode(q=True, co=True) and not self.show_comp_but.isChecked():
                return
        except Exception as e:
            print e.message
            print 'UI Allready Closed :'
            return
        if self.hilite_flag:
            self.hilite_flag = False
            print 'in select from ui mode return :'
            return
        self.pre_mesh_color_dict = {}
        for mesh, color_list in self.mesh_color_dict.items():
            self.pre_mesh_color_dict[mesh] = color_list[:]
        self.counter.reset()
        self.pre_all_vertices = copy.copy(self.all_vertices)#選択解除用に事前選択頂点を格納リセット前に忘れずに
        #self.pre_rgbs = copy.copy(self.all_vtx_rgbs)
        #self.pre_alpha = copy.copy(self.all_vtx_alpha)
        self.pre_rgbas = self.all_vtx_rgbas[:]#カラーチャンネルリセット用に格納
        
        print 'get_set_vertex_color :/*/*/*/*/*/*/*/'
        #self.pre_hl_nodes = self.hl_nodes
        #self.view_widget.setModel(self.color_model)
        
        #クリアボタン押されたときは全部初期化
        if clear:
            sel = []
            self.hl_nodes = []
            sel_vertices = []
        #ロックボタンが押されているときの挙動
        elif self.lock_but.isChecked() and self.pre_hl_nodes and not cycle:
            self.hl_nodes = self.pre_hl_nodes
            if cmds.selectMode(q=True, o=True):
                sel_vertices = common.conv_comp(self.pre_sel, mode='vf')#現在選択している頂点
                print 'get selection vert in lock obj mode :', len(sel_vertices)
                return
            else:
                sel_vertices = common.conv_comp(cmds.ls(sl=True, l=True), mode='vf')
                if not sel_vertices:
                    sel_vertices = []
                check_vertices = list(set(self.all_vertices) & set(sel_vertices))
                print check_vertices
                if not check_vertices:
                    print 'no vert in lock selection :'
                    sel_vertices = self.pre_sel_vertices
                    return
                #self.pre_sel = sel_vertices
            sel = sel_vertices
        else:#ロックされてないとき
            sel = cmds.ls(sl=True, l=True)
            if cmds.selectMode(q=True, co=True):
                self.hl_nodes = cmds.ls(hl=True, l=True)
            else:
                self.hl_nodes = cmds.ls(sl=True, l=True, tr=True)
                self.hl_nodes = common.search_polygon_mesh(self.hl_nodes, fullPath=True)
            if sel_vertices is None:
                sel_vertices = common.conv_comp(sel, mode='vf')#現在選択している頂点
        self.view_vertices = sel_vertices
                
        if sel_vertices:
            print 'check sel vert :', len(sel_vertices)
        if not self.hl_nodes:
            self.all_vertices = []#リセットタイミングに注意
            
        print 'check hilite node :', self.hl_nodes
        
        if self.pre_sel == sel and sel_vertices is None:
            print 'same selection return :'
            return
            
        self.pre_sel_vertices = sel_vertices
        self.counter.count(string='get mesh vtx :')
        
        print '/*/*/*/*/*/*/*/*/ hilite model changed/*/*/*/*/*/*/*/*/'
        #全ての頂点とバーテックスカラーを格納しておく
        #try:
        self.all_vertices = common.conv_comp(self.hl_nodes, mode='vf')#全ノードの頂点を格納
        if self.all_vertices is None:
            print '*/*/*/*/*/*//*/*/*/*/*/*/*/ no vertex :'
            self.all_vertices = []
        print 'check all vert :', len(self.all_vertices)
        self.all_vtx_id_dict = {vtx:i for i, vtx in enumerate(self.all_vertices)}#インデックス探索は遅いのでリストIDと頂点の対応を辞書管理
        self.pre_all_vtx_id_dict = {vtx:i for i, vtx in enumerate(self.pre_all_vertices)}
        
        #selList = om2.MGlobal.getActiveSelectionList()
        self.all_vtx_rgbas = om2.MColorArray()#空のMColorArrayを用意しておく
        for node in self.hl_nodes[:]:
            sList = om2.MSelectionList()
            sList.add(node)
            mDagPath = sList.getDagPath(0)
            
            self.targetObj = om2.MFnTransform(mDagPath)
            #print 'get om2 obj :', mDagPath.fullPathName()
            self.targetObjMesh = om2.MFnMesh(mDagPath)
            
            # 中間オブジェクトがあるか確認
            historyList = cmds.bakePartialHistory(self.targetObjMesh.fullPathName(), q=True, prePostDeformers=True) or []
            if len(historyList) > 0:
                self.hasIntermediateObject = True
                
            curColorSetList = cmds.polyColorSet(self.targetObjMesh.fullPathName(), q=True, currentColorSet=True)
            # colorSerがない場合は処理をスキップしてぬける
            if curColorSetList == None:
                self.hl_nodes.remove(node)
                continue
            else:
                curColorSet = curColorSetList[0]

            self.baseColorSet = curColorSet
            print 'store base rgba color :', node, self.baseColorSet
            #self.baseColorSerRep = cmds.polyColorSet(q=True, currentColorSet=True, representation=True)
            mesh_vtx_colors = self.targetObjMesh.getFaceVertexColors(self.baseColorSet)
            #mesh_face_vertices = self.targetObjMesh.getPolygonVertices(0)
            self.all_vtx_rgbas += mesh_vtx_colors
            #色変更のために辞書格納しておく
            if self.channel_but_group.checkedId() == 0 or not node in self.pre_hl_nodes:
                self.mesh_color_dict[self.targetObj.fullPathName()] = mesh_vtx_colors
                shape = cmds.listRelatives(node, s=True, fullPath=True)
                print 'check node name :', node, shape
                vertices = common.conv_comp(shape, mode='vf')
                self.temp_vf_face_dict[node] = [int(fv.replace(']', '').split('[')[-1]) for fv in vertices]
                self.temp_vf_vtx_dict[node] = [int(fv.replace(']', '').split('[')[-2]) for fv in vertices]
                self.node_vertex_dict_dict[node] = {v:i for i, v in enumerate(vertices)}
                
        self.org_mesh_color_dict = {}#アンドゥできるコマンドのためにオリジナルの値を保持
        for mesh, color_list in self.mesh_color_dict.items():
            self.org_mesh_color_dict[mesh] = color_list[:]
            
        self.counter.count(string='get vtx color :')
        
        #print 'check all face vert :', self.all_vertices
        #フェースとバーテックスの対になるリストをそれぞれ作っておく
        #self.all_vf_face_list = [int(fv.replace(']', '').split('[')[-1]) for fv in self.all_vertices]
        #self.all_vf_vtx_list = [int(fv.replace(']', '').split('[')[-2]) for fv in self.all_vertices]
        #print 'create vtxface - face list :', self.all_vf_face_list
        #print 'create vtxface - vtx list :', self.all_vf_vtx_list
        #print 'get all sel vtx :', sel_vertices, self.hl_nodes
        if not sel_vertices:
            sel_vertices = []
        self.vrgba_list = list()#表示用RGBAデータを丸ごと格納
        self.vnrgba_list = list()#同255版
        print 'check hl node :', self.hl_nodes
        
        self.counter.count(string='ajust list dict :')
        
        self.norm_value_list = []
        norm_flag = self.norm_but.isChecked()
        self.all_rows = 0#右クリックウィンドウ補正用サイズを出すため全行の桁数を数える
        self._data = []#全体のテーブルデータを格納する
        self.mesh_rows = []
        self.vtx_row_dict = {}#行と頂点の対応辞書
        for node in self.hl_nodes:
            self.mesh_rows.append(self.all_rows)
            self.all_rows += 1
            #self.color_model.append_item(node.split('|')[-1], selectable=False, mesh=True)
            items = [node.split('|')[-1], '', '', '', '', '']
            self._data.append(items)
            shape = cmds.listRelatives(node, s=True, fullPath=True)
            node_vertices = common.conv_comp(shape, mode='vf')
            #print 'select vertex :', len(sel_vertices)
            #print 'node  vertex :', len(node_vertices)
            target_vertices = list(set(sel_vertices) & set(node_vertices))#メッシュごとに順番に表示するための論理積
            print 'target  vertex :', len(target_vertices)
            #print 'target vert :', target_vertices
            if target_vertices:
                #print 'check node in pre selection :', node, self.pre_hl_nodes
                #print 'check pre dict :', self.pre_all_vtx_id_dict
                vertex_dict = self.node_vertex_dict_dict[node]
                rgba_list = self.mesh_color_dict[node]
                print 'new selection refar in maku ui :', node
                print 'check rgba list', len(rgba_list)
                items = []#各行のカラムを格納するアイテムリスト
                for i, v in enumerate(target_vertices):
                    vf_id = v[v.find('['):]
                    vid = vertex_dict[v]
                    rgba = rgba_list[vid]#APIのMColorを取得
                    #内部データとは別に表示用のデータを作る
                    #print 'vtx roop ---------------------------------------------'
                    vnrgba = map(lambda c:round(c, 3), rgba)
                    vrgba = map(lambda n:int(n*255), rgba)
                    self.vnrgba_list += vnrgba
                    self.vrgba_list += vrgba
                    '''
                    self.color_model.append_item(vfid=vf_id, vnr=vnrgba[0], vng=vnrgba[1], vnb=vnrgba[2], vna=vnrgba[3], 
                                                            vr= vrgba[0], vg=vrgba[1], vb=vrgba[2], va=vrgba[3],
                                                            selectable=True, vtxname=v, node=node, vid=vid, norm=norm_flag)
                    '''
                    if norm_flag:
                        items = [vf_id, vnrgba[0], vnrgba[1], vnrgba[2], vnrgba[3], '']
                    else:
                        items = [vf_id, vrgba[0], vrgba[1], vrgba[2], vrgba[3], '']
                        
                    self._data.append(items)
                    #データ編集用にフェース頂点、ノード名、フェース頂点のID、セルのスキップ数を格納しておく
                    self.vtx_row_dict[self.all_rows] = [v, node, vid, len(self.mesh_rows)*6]
                    self.all_rows += 1#全体の行数を数えておく
        
        try:#都度メモリをきれいに
            self.color_model.deleteLater()
            del self.color_model
        except Exception as e:
            print e.message, 'in get set'
            print 'faild to delete color model in remake :'
        self.color_model = TableModel(self._data, self.view_widget, self.mesh_rows)
        self.color_model.norm = self.norm_but.isChecked()#ノーマル状態かどうかを渡しておく
        #self.color_model.set_header()
        
        self.counter.count('setup ui model :')
            
        try:#選択モデルも消す
            self.sel_model.deleteLater()
            del self.sel_model
        except Exception as e:
            print e.message, 'in get set'
            print 'faild to delete selection model in remake :'
        self.sel_model = QItemSelectionModel(self.color_model)#選択モデルをつくる
        self.sel_model.selectionChanged.connect(self.cell_changed)#シグナルをつなげておく
        self.view_widget.setModel(self.color_model)#表示用モデル設定
        self.view_widget.setSelectionModel(self.sel_model)#選択用モデルを設定
        self.set_color_channel()
        self.reset_color_channel()
        self.pre_sel = sel
        self.selected_items = []
        
        if not self.show_flag:
            self.show_flag = True
            self.show()
        
        self.counter.count('ui data finalaize :')
        
        #self.model_index = [cell_id for cell_id in model_iter(self.color_model)]#モデルのインデックス番号をあらかじめ取得
        self.model_index = self.color_model.indexes#モデルのインデックス番号をあらかじめ取得
        self.model_id_dict = {cell_id:i for i, cell_id in enumerate(self.model_index)}
        set_header_width(self.view_widget, self.color_model)
        #前回の選択を格納
        self.pre_hl_nodes = self.hl_nodes
        
        self.counter.count('ui create model list dict :')
        
        self.counter.lap_print(print_flag=COUNTER_PRINT)
        
    def hide_all_vertex_color(self):
        tr = cmds.ls(tr=True)
        cmds.polyOptions(tr,colorShadedDisplay=False)
    def show_all_vertex_color(self):
        tr = cmds.ls(tr=True)
        cmds.polyOptions(tr, colorShadedDisplay=True)
        cmds.polyOptions(tr,colorMaterialChannel='ambientDiffuse')

    #セルの選択変更があった場合に現在の選択セルを格納する
    @timer
    def cell_changed(self, selected, deselected):
        self.select_change_flag = True
        self.selected_items =  self.sel_model.selectedIndexes()
        #print 'change cell selection', len(self.selected_items)
        self.change_add_mode(self.add_mode, change_only=True)
        #self.get_source_value()
        self.pre_add_value = 0.0#加算量を初期化
        self.sel_rows = list(set([item.row() for item in self.selected_items]))
        if self.highlite_but.isChecked():
            self.hilite_vertices()
        
    @timer
    def hilite_vertices(self):
        self.counter.reset()
        if len(self.sel_rows) == len(self.view_vertices):
            #全行選択された場合は選択時間短縮のためワイルドカードを与える
            #10～60倍くらい早い
            print 'select all rows in hilete mode :'
            vertices = self.view_vertices
            vertices = []
            for node in self.hl_nodes:
                 vertices.append(node + '.vtxFace[*][*]')
        else:
            rows = list(set([item.row() for item in self.selected_items]))
            vertices = [self.vtx_row_dict[r][0] for r in rows]
        #self.hilite_flag = True
        #print 'hilite comp :', vertices
        cmds.selectMode(co=True)
        self.hilite_flag = True
        self.counter.count(string='get cell vtx :')
        #print 'check sel vert :', vertices
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
            #self.hilite_flag = False
        
            
    #Adjustボタン押したとき、頂点選択しにいく
    def select_vertex_from_cells(self):
        print 'select_vertex_from_cells'
        rows = list(set([item.row() for item in self.selected_items]))
        vertices = [self.vtx_row_dict[r][0] for r in rows]
        if vertices:
            cmds.selectMode(co=True)
            cmds.select(vertices, r=True)
            
    #選択されているセルの行のみの表示に絞る
    def show_selected_cells(self):
        rows = list(set([item.row() for item in self.selected_items]))
        vertices = [self.vtx_row_dict[r][0] for r in rows]
        print 'show selection vert :', vertices
        self.get_set_vertex_color(sel_vertices=vertices)
                
    def show_all_cells(self):
        vertices = common.conv_comp(self.hl_nodes, mode='vf')#現在選択している頂点
        if vertices:
            print 'show all cells :', vertices
            self.get_set_vertex_color(sel_vertices=vertices, cycle=True)
            
    #スピンボックスがフォーカス持ってからきーが押されたかどうかを格納しておく
    def store_keypress(self, pressed):
        self.key_pressed = pressed
        
    #行の情報をまとめて返す
    def get_row_vf_node_data(self, row):
        row_datas = self.vtx_row_dict[row]
        return row_datas[0], row_datas[1], row_datas[2], row_datas[3]
        
    pre_add_value = 0.0
    selected_items = []
    select_change_flag = True
    #入力値をモードに合わせてセルの値と合算、セルに値を戻す
    @timer
    def culc_cell_value(self, from_spinbox=False, from_input_box=False):
        if not  self.selected_items:
            print 'culc cell value , nothing selection return:'
            return
        #add_value ボックス入力値
        #after_value 入力後のボックス値
        #n_value 正規化された値をリストに戻すための変数
        self.text_value_list = []
        if not self.change_flag and not from_spinbox:
            return
        if not self.selected_items:
            return
        #絶対値モードでフォーカス外したときに0だった時の場合分け
        if from_spinbox and not self.key_pressed and not from_input_box:
            print 'forcus error :'
            return
        if not from_input_box:
            add_value = self.weight_input.value()
        else:
            add_value = self.input_box_value
        #print 'culc cell value event', add_value,  self.selected_items
        
        #絶対値の時の処理
        if self.add_mode == 0:#abs
            self.norm_value_list = []
            if self.norm_but.isChecked():
                int_value = int(add_value*255)
                norm_value = add_value
                new_value = round(norm_value, 3)
            else:
                #計算誤差修正モードの場合は255値に0.5足して計算する
                if self.add_5_but.isChecked():
                    add_value += 0.5
                int_value = int(add_value)
                norm_value = add_value/255.0
                new_value = int_value
            print 'check abs notm value :', norm_value
            #まとめてデータ反映
            for cell_id in self.selected_items:
                self.color_model.setData(cell_id, new_value)
                #焼き込みようリストを更新しておく
                row = cell_id.row()
                column = cell_id.column() 
                rgba = column - 1
                #print 'check row datas :', row, self.vtx_row_dict.keys()
                vf_name, node, vf_id, skip_count = self.get_row_vf_node_data(row)
                c_id = self.model_id_dict[(row, column)]
                mesh_count = (skip_count / 6 - 1)*2
                v_id = c_id - skip_count - 2 * row + 1 + mesh_count
                n_value = new_value
                self.vnrgba_list[v_id] = round(norm_value, 3)#選択頂点の情報を更新
                self.vrgba_list[v_id] = int_value#選択頂点の情報を更新
                #print 'check dict keys :', node, vf_id, rgba, norm_value
                self.mesh_color_dict[node][vf_id][rgba] = norm_value#全ての頂点の情報更新
            #print 'check vnrgba_list', self.vrgba_list
            after_value = new_value
        else:
            #最大最小を設定しておく
            min_value = 0.0
            max_n_value = 1.0
            max_value = 255
            #print 'check source value list :', self.norm_value_list
            if self.add_5_but.isChecked():
                add5_value = 0.5
            else:
                add5_value = 0.0
            #加算の時の処理
            sub_value = add_value - self.pre_add_value
            print 'check sub_value', sub_value
            ratio = add_value/100
            for cell_id in self.selected_items:
                #焼き込みようリストを更新しておく
                row = cell_id.row()
                column = cell_id.column() 
                rgba = column - 1
                vf_name, node, vf_id, skip_count = self.get_row_vf_node_data(row)
                c_id = self.model_id_dict[(row, column)]
                mesh_count = (skip_count / 6 - 1)*2
                v_id = c_id - skip_count - 2 * row + 1 + mesh_count
                
                if self.add_mode == 1:#add
                    if self.norm_but.isChecked():
                        n_value = self.vnrgba_list[v_id] + sub_value
                        v_value = int(n_value*255)
                    else:#誤差補正のため一旦255に戻して計算する
                        v_value = int(self.vrgba_list[v_id] + sub_value)
                        n_value = (v_value + add5_value) / 255.0
                    
                if self.add_mode == 2:#add%
                    if self.norm_but.isChecked():
                        n_value = self.vnrgba_list[v_id] * (1.0 + ratio)
                        v_value = int(n_value*255)
                    else:#誤差補正のため一旦255に戻して計算する
                        v_value = int(round(self.vrgba_list[v_id] * (1.0 + ratio), 0))
                        n_value = (v_value + add5_value) / 255.0
                    
                if n_value > 1.0:
                    n_value = 1.0
                elif n_value < 0.0:
                    n_value = 0.0
                if v_value > 255:
                    v_value = 255
                elif v_value < 0:
                    v_value = 0
                    
                if self.norm_but.isChecked():
                    self.color_model.setData(cell_id, round(n_value, 3))
                else:
                    self.color_model.setData(cell_id,  v_value)
                self.vnrgba_list[v_id] = round(n_value, 3)#選択頂点の情報を更新
                self.vrgba_list[v_id] = v_value#選択頂点の情報を更新
                self.mesh_color_dict[node][vf_id][rgba] = n_value#全ての頂点の情報更新
            print 'check abs notm value :', n_value
                
            #処理後のスピンボックスの値を設定
            if from_spinbox:
                after_value = 0.0
                self.pre_add_value = 0.0
            else:
                self.pre_add_value = add_value
                after_value = add_value
            
        self.weight_input.setValue(after_value)#UIのスピンボックスに数値反映
        
        for row in self.sel_rows:#色を塗る
            skip_count = self.vtx_row_dict[row][3]
            skip = skip_count/6
            color = self.vrgba_list[(row-skip)*4:(row-skip)*4+3]
            #print 'check row color :', row, color
            #self.color_model.set_color(row, 5, color)
        #APIでのアンドゥ制御は別みたい、これから対応→カスタムコマンド作成して対応済み
        print 'bake_color_at :', self.channel_but_group.checkedId() 
        if self.channel_but_group.checkedId() == 0:
            self.bake_vertex_color(realbake=True, ignoreundo=self.change_flag)#焼き付け実行
        else:
            self.bake_vertex_color(realbake=False, ignoreundo=self.change_flag)#アンドゥ履歴だけ残しにいく。実際のベイクはしない。
            self.change_view_channel()
        #print self.all_vtx_rgbas
        
    #ノーマルモードを切り替える
    @timer
    def change_normal_mode(self):
        self.color_model.norm = self.norm_but.isChecked()
        self.pre_add_value = 0.0#加算量を初期化
        if not self.vrgba_list:
            return
        i = 0
        for index in self.model_index:
            if index[0] in self.mesh_rows:
                continue
            if index[1] in [0, 5]:
                continue
            #print 'check_model_index', self.model_index
            #print 'get new value :', index, new_value
            if self.norm_but.isChecked():
                new_text = self.vnrgba_list[i]
            else:
                new_text = self.vrgba_list[i]
            self.color_model.setData(index, new_text)
            i += 1
            if i > len(self.vrgba_list)-1:
                break
            
    #表示されるチャンネルを変更する,MayaCommand版
    all_vertices = []
    @timer
    def change_view_channel_old(self, id=None, change_node=None, reset=False):
        print 'node in selection change:', change_node
        if id is None:
            id = self.channel_but_group.checkedId()
        if not reset:#UIからの変更処理と新規選択チャンネル変更時
            if change_node:#新規変更時もRGBA表示だったら抜ける
                if self.channel_but_group.checkedId() == 0:
                    print 'not need reset return :'
                    return
            vertices = self.all_vertices
            target_vertices = self.all_vertices
            target_rgbs = self.all_vtx_rgbs
            target_alpha = self.all_vtx_alpha
        else:#選択が変わったときの変更処理
            if self.channel_but_group.checkedId() == 0:
                print 'not need reset return :'
                return
            vertices = common.conv_comp(change_node, mode='vf')
            target_vertices = self.pre_all_vertices
            target_rgbs = self.pre_rgbs
            target_alpha = self.pre_alpha
        print 'chanege color channel :', id
        #print 'check target vert :', target_vertices
        for vtx in vertices:
            #print vtx
            temp_index = target_vertices.index(vtx)
            rgb = target_rgbs[temp_index]
            alpha = target_alpha[temp_index]
            if id == 2:
                rgb = [rgb[0]]*3
            elif id == 3:
                rgb = [rgb[1]]*3
            elif id == 4:
                rgb = [rgb[2]]*3
            elif id == 5:
                rgb = [alpha]*3
            if id >= 1:
                alpha =1.0
            cmds.polyColorPerVertex(vtx, rgb = rgb)
            cmds.polyColorPerVertex(vtx, a = alpha)
        #mfnMesh = om2.MFnMesh('')
            
    #チャンネル表示変更、API版
    @timer
    def change_view_channel(self, id=None, change_node=None, reset=False):
        self.cc_counter = prof.LapCounter()
        self.cc_counter.reset()
        print 'node in selection change:', change_node
        if id is None:
            id = self.channel_but_group.checkedId()
        if change_node:#選択が変わったときの変更処理
            target_nodes = [change_node]
            if self.channel_but_group.checkedId() == 0:
                print 'not need reset return :'
                return
            #vertices = common.conv_comp(change_node, mode='vf')
            if reset:#リセットの時は前回選択情報を引っ張ってくる
                mesh_color_dict = self.pre_mesh_color_dict
                #print 'get channel change node data :', vertices
            else:#セットの時は現在の時の情報を使う
                mesh_color_dict = self.mesh_color_dict
        else:#UIからの変更処理
            target_nodes = self.hl_nodes
            #vertices = self.all_vertices
            mesh_color_dict = self.mesh_color_dict
        print 'chanege color channel :', id, change_node
        for node in target_nodes:
            shape = cmds.listRelatives(node, s=True, fullPath=True)
            vertices = common.conv_comp(shape, mode='vf')
            self.cc_counter.count(string='get vtx color data :')
            #print 'check target vert :', target_vertices
            if vertices is None:
                return
            temp_rgba_list = mesh_color_dict[node][:]#OM2のMColorArray
            if id == 0:
                pass
            elif id == 1:
                for color in temp_rgba_list:
                    color[3] = 1.0
            else:
                cid = id - 2
                alpha = [1.0]
                for color in temp_rgba_list:
                    color[0] = color[cid]
                    color[1] = color[cid]
                    color[2] = color[cid]
                    color[3] = 1.0
            self.cc_counter.count(string='culc vtx rgba data:')
            
            #mDagPathを名前から取得してくる
            sList = om2.MSelectionList()
            sList.add(node)
            mDagPath = sList.getDagPath(0)
            #self.targetObj  = om2.MFnTransform(mDagPath)
            self.targetObjMesh = om2.MFnMesh(mDagPath)
            #print 'channel change in om2 :', mDagPath, temp_rgba_list, temp_vf_face_list, temp_vf_vtx_list
            #print 'check change len :', len(temp_rgba_list), len(temp_vf_face_list), len(temp_vf_vtx_list)
            #print len(temp_rgba_list),  len(self.temp_vf_face_dict[node]), len(self.temp_vf_vtx_dict[node])
            self.targetObjMesh.setFaceVertexColors(temp_rgba_list,  self.temp_vf_face_dict[node], self.temp_vf_vtx_dict[node])
                
        self.cc_counter.count(string='change color channel:')
            
        self.cc_counter.lap_print()
        
    #選択変更時に解除されたメッシュのチャンネル表示を元に戻す
    def reset_color_channel(self):
        print 'reset color'
        target_nodes = list(set(self.pre_hl_nodes)-set(self.hl_nodes))
        for pre_node in target_nodes:
            print 'selection node changed in previous selection :', pre_node
            qt.Callback(self.change_view_channel(id=0, change_node=pre_node, reset=True))
        #self.pre_selection_node = self.current_selection_node
        
    #選択変更時に新たに選択されたメッシュのチャンネルを変更する
    def set_color_channel(self):
        print 'set color channel job :'
        channel_id = self.channel_but_group.checkedId()
        if channel_id == 0:
            print 'not need channel change return :'
            return
        target_nodes = list(set(self.hl_nodes)-set(self.pre_hl_nodes))
        print 'channel change target nodes :', target_nodes
        for pre_node in target_nodes:
            print 'selection node changed in new selection:', pre_node
            qt.Callback(self.change_view_channel(id=channel_id, change_node=pre_node))
        #self.pre_selection_node = self.current_selection_node
        
    #ウィンドウ閉じたら全部チャンネル初期化する
    def reset_channel_as_close(self):
        channel_id = self.channel_but_group.checkedId()
        if channel_id == 0:
            print 'not need channel change return :'
            return
        if self.lock_but.isChecked():
            target_nodes = self.hl_nodes
        else:
            if cmds.selectMode(q=True, co=True):
                target_nodes = cmds.ls(hl=True, l=True)
            else:
                target_nodes = cmds.ls(sl=True, l=True, tr=True)
        for pre_node in target_nodes:
            print 'reset channel with close :', pre_node
            qt.Callback(self.change_view_channel(id=0, change_node=pre_node, reset=False))
            
    #変更されたカラーを頂点に焼き付ける,MayaCommand版
    @timer
    def bake_vertex_color_old(self):
        rows = list(set([item.row() for item in self.selected_items]))
        #print 'bake vartex color :', rows
        channel_id = self.channel_but_group.checkedId()
        for row in rows:
            vtx = self.color_model.get_row_vtx(row)
            temp_index = self.all_vertices.index(vtx)
            rgb = self.all_vtx_rgbs[temp_index]
            alpha = self.all_vtx_alpha[temp_index]
            #RGBAの時はそのまま焼き付け
            if channel_id == 0:
                cmds.polyColorPerVertex(vtx, rgb = rgb)
                cmds.polyColorPerVertex(vtx, a = alpha)
        if channel_id != 0:
            if cmds.selectMode(q=True, co=True):
                target_nodes = cmds.ls(hl=True, l=True)
            else:
                target_nodes = cmds.ls(sl=True, l=True, tr=True)
            for node in target_nodes:
                print 'bake temp channel color :', node
                qt.Callback(self.change_view_channel(id=channel_id, change_node=node))
                
    @timer
    def bake_vertex_color(self, realbake=True, ignoreundo=False):
        #APIでアンドゥ実装したカスタムコマンドのためにグローバル空間に値を保持しておく
        set_current_data(self.hl_nodes, self.mesh_color_dict, self.org_mesh_color_dict, self.temp_vf_face_dict, self.temp_vf_vtx_dict)
        #カスタムコマンドを実行
        cmds.bakeVertexColor(rb=realbake, iu=ignoreundo)
        #アンドゥ履歴用カラーを更新しておく
        self.org_mesh_color_dict = {}
        for mesh, color_list in self.mesh_color_dict.items():
            self.org_mesh_color_dict[mesh] = color_list[:]
        
    #パーセントの時の特殊処理、元の値を保持する
    change_flag = False
    def sld_pressed(self):
        cmds.undoInfo(openChunk=True)
        #マウスプレス直後に履歴を残す焼き込みする。実際のベイクはしない。
        self.bake_vertex_color(realbake=False, ignoreundo=False)
        self.change_flag = True#スライダー操作中のみ値の変更を許可するフラグ
        print 'sld mouse pressed'
            
    #パーセントの特殊処理、値をリリースして初期値に戻る
    def sld_released(self):
        self.culc_cell_value()
        print 'sld mouse released'
        self.change_flag = False
        if self.add_mode == 1 or self.add_mode == 2:
            self.weight_input.setValue(0.0)
            self.change_from_spinbox()
            self.pre_add_value = 0.0
        cmds.undoInfo(closeChunk=True)
                
    def create_job(self):
        global select_job
        if 'select_job' in globals():
            if select_job is not None:
                cmds.scriptJob(k=select_job)
        select_job = cmds.scriptJob(cu=True, e=("SelectionChanged", self.get_set_vertex_color))
        #self.set_color_job = cmds.scriptJob(cu=True, e=("SelectionChanged", self.set_color_channel))
        #self.reset_color_job = cmds.scriptJob(cu=True, e=("SelectionChanged", self.reset_color_channel))
        
    def remove_job(self):
        global select_job
        print 'remove job :', select_job
        cmds.scriptJob(k=select_job)
        select_job = None
        #cmds.scriptJob(k=self.set_color_job)
        #cmds.scriptJob(k=self.reset_color_job)
    '''
    def closeEvent(self):
        print 'window close :'
        self.remove_job()
        self.reset_channel_as_close()
    '''
    def dockCloseEventTriggered(self):
        print 'window close :'
        self.remove_job()
        self.reset_channel_as_close()
        self.save_window_data()
        #ちゃんと消さないと莫大なUIデータがメモリに残り続けるので注意
        try:
            self.color_model.deleteLater()
            self.sel_model.deleteLater()
        except:
            pass
        self.deleteLater()
        
#アンドゥ時に辞書を更新しておく。
def update_dict(color_dict):
    window.mesh_color_dict = color_dict
    #print color_dict.values()[0]
    
#アンドゥの時に読み直す
def refresh_window():
    global window
    window.get_set_vertex_color(cycle=True)
        
#焼き込みコマンドに渡すためにグローバルに要素を展開
def set_current_data(nodes, color, org_color, face, vtx):
    global hl_nodes
    global color_dict
    global org_color_dict
    global face_dict
    global vtx_dict
    hl_nodes = nodes
    color_dict = color
    org_color_dict = org_color
    face_dict = face
    vtx_dict = vtx
    #print hl_nodes, color_dict, pre_color_dict, face_dict, vtx_dict

def get_current_data():
    global hl_nodes
    global color_dict
    global org_color_dict
    global face_dict
    global vtx_dict
    return hl_nodes, color_dict, org_color_dict, face_dict, vtx_dict
    
class Lang(object):
    def __init__(self, en='', jp=''):
        self.jp = jp
        self.en = en
    def output(self):
        lang = 'en'
        env = re.sub('_.+', '', os.environ.get('MAYA_UI_LANGUAGE', ''))
        loc = re.sub('_.+', '', locale.getdefaultlocale()[0])
        if loc != '':
            lang = loc
        if env != '':
            lang = env
        if lang == 'ja':
            return self.jp
        if lang == 'en':
            return self.en
        
#右クリックボタンクラスの作成
class RightClickButton(QPushButton):
    rightClicked = Signal()
    def mouseReleaseEvent(self, e):
        if e.button() == Qt.RightButton:
            self.rightClicked.emit()
        else:
            super(self.__class__, self).mouseReleaseEvent(e)
            
#フラットボタンを作って返す
def make_flat_btton(icon=None, name='', text=200, bg=[54, 51, 51], ui_color=68, border_col=160, checkable=True, w_max=None, w_min=None, push_col=120, 
                                h_max=None, h_min=None, policy=None, icon_size=None, tip=None, flat=True, hover=True, destroy_flag=False, context=None):
    button = RightClickButton()
    button.setText(name)
    if checkable:
        button.setCheckable(True)#チェックボタンに
    if icon:
        button.setIcon(QIcon(icon))
    if flat:
        button.setFlat(True)#ボタンをフラットに
        change_button_color(button, textColor=text, bgColor=ui_color, hiColor=bg, mode='button', hover=hover, destroy=destroy_flag, dsColor=border_col)
        button.toggled.connect(lambda : change_button_color(button, textColor=text, bgColor=ui_color, hiColor=bg, mode='button', toggle=True, hover=hover, destroy=destroy_flag, dsColor=border_col))
    else:
        button.setFlat(False)
        change_button_color(button, textColor=text, bgColor=bg, hiColor=push_col, mode='button', hover=hover, destroy=destroy_flag, dsColor=border_col)
    if w_max:
        button.setMaximumWidth(w_max)
    if w_min:
        button.setMinimumWidth(w_min)
    if h_max:
        button.setMaximumHeight(h_max)
    if h_min:
        button.setMinimumHeight(h_min)
    if icon_size:
        button.setIconSize(QSize(*icon_size))
    if policy:#拡大縮小するようにポリシー設定
        button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
    if tip:
        button.setToolTip(tip)
    if context:#コンテキストメニュー設定
        button.setContextMenuPolicy(CustomContextMenu)
        button.customContextMenuRequested.connect(context)
    return button
    
#ボタンカラーを変更する関数
def change_button_color(button, textColor=200, bgColor=68, hiColor=68, hiText=255, hiBg=[97, 132, 167], dsColor=200,
                                        mode='common', toggle=False, hover=True, destroy=False, dsWidth=1):
    '''引数
    button 色を変えたいウィジェットオブジェクト
    textColor ボタンのテキストカラーをRGBのリストか0～255のグレースケールで指定、省略可能。
    bgColor 背景色をRGBのリストか0～255のグレースケールで指定、省略可能。
    '''
    #リスト型でなかったらリスト変換、一ケタでグレー指定ができるように。
    textColor = to_3_list(textColor)
    bgColor = to_3_list(bgColor)
    hiColor = to_3_list(hiColor)
    hiText = to_3_list(hiText)
    hiBg = to_3_list(hiBg)
    dsColor = to_3_list(dsColor)
    #ボタンをハイライトカラーにする
    if toggle and button.isChecked():
        bgColor = hiColor
    #ホバー設定なら明るめの色を作る
    if hover:
        hvColor = map(lambda a:a+20, bgColor)
    else:
        hvColor = bgColor
    #RGBをスタイルシートの16進数表記に変換
    textHex =  convert_2_hex(textColor)
    bgHex = convert_2_hex(bgColor)
    hvHex = convert_2_hex(hvColor)
    hiHex = convert_2_hex(hiColor)
    htHex = convert_2_hex(hiText)
    hbHex = convert_2_hex(hiBg)
    dsHex = convert_2_hex(dsColor)
    
    #destroy=True
    #ボタンはスタイルシートで色変更、色は16進数かスタイルシートの色名で設定するので注意
    if mode == 'common':
        button.setStyleSheet('color: '+textHex+' ; background-color: '+bgHex)
    if mode == 'button':
        if not destroy:
            button. setStyleSheet('QPushButton{background-color: '+bgHex+'; color:  '+textHex+' ; border: black 0px}' +\
                                            'QPushButton:hover{background-color: '+hvHex+'; color:  '+textHex+' ; border: black 0px}'+\
                                            'QPushButton:pressed{background-color: '+hiHex+'; color: '+textHex+'; border: black 2px}')
        if destroy:
            button. setStyleSheet('QPushButton{background-color: '+bgHex+'; color:  '+textHex+'; border-style:solid; border-width: '+str(dsWidth)+'px; border-color:'+dsHex+'; border-weight_input: 0px;}' +\
                                            'QPushButton:hover{background-color: '+hvHex+'; color:  '+textHex+'; border-style:solid; border-width: '+str(dsWidth)+'px; border-color:'+dsHex+'; border-weight_input: 0px;}'+\
                                            'QPushButton:pressed{background-color: '+hiHex+'; color: '+textHex+'; border-style:solid; border-width: '+str(dsWidth)+'px; border-color:'+dsHex+'; border-weight_input: 0px;}')
    if mode == 'window':
        button. setStyleSheet('color: '+textHex+';'+\
                        'background-color: '+bgHex+';'+\
                        'selection-color: '+htHex+';'+\
                        'selection-background-color: '+hbHex+';')
                        
def to_3_list(item):
    if not isinstance(item, list):
        item = [item]*3
    return item
    
#16真数に変換する
def convert_2_hex(color):
    hex = '#'
    for var in color:
        #format(10進数, 'x')で16進数変換
        var = format(var, 'x')
        if  len(var) == 1:
            #桁数合わせのため文字列置換
            hex = hex+'0'+str(var)
        else:
            hex = hex+str(var)
    return hex
    
# index :Noneの場合全列処理
def set_header_width(view, model, index=None, space=10):
    '''
    ヘッダーの幅を表示内容に合わせた上で幅の変更が可能になるようにする
    :param view:
    :param model:
    :param index: Noneの場合全列処理
    :param space:
    :return:
    '''
    if hasattr(view.horizontalHeader(), 'setResizeMode'):
        resize_mode = view.horizontalHeader().setResizeMode  # PySide
    else:
        resize_mode = view.horizontalHeader().setSectionResizeMode # PySide2

    def __resize_main(index):
        resize_mode(index, QHeaderView.ResizeToContents)
        width = view.columnWidth(index) + space
        view.setColumnWidth(index, width)
        resize_mode(index, QHeaderView.Interactive)

    if index is None:
        count = model.columnCount()
        for i in range(count):
            __resize_main(i)
    else:
        __resize_main(index)
        