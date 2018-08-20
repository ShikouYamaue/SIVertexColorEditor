# -*- coding: utf-8 -*-
import sys
import maya.api.OpenMaya as om2
#import maya.api.OpenMayaUI as omui
 
kPluginCmdName = "bakeVertexColor" # MELコマンド名
 
kShortFlagName = "-ts"         # 引数のショートネーム
kLongFlagName = "-test"   # 引数のロングネーム
 
def maya_useNewAPI():
    pass
    
class BakeVertexColorClass( om2.MPxCommand ):
    
    def __init__(self):
        global sivertexcoloreditor
        from sivertexcoloreditor import sivertexcoloreditor
        #reload(sivertexcoloreditor)
        ''' Constructor. '''
        om2.MPxCommand.__init__(self)
    
    def doIt(self, args):
        realbake, ignore_undo= self.parseArguments( args )
        #print 'ignore undo :', ignore_undo
        self.ignore_undo = ignore_undo
        self.nodes, self.bake_color_dict, self.color_dict, self.org_color_dict, self.face_dict, self.vtx_dict = sivertexcoloreditor.get_current_data()
        if realbake:
            self.redoIt(flash=False)
        
    def parseArguments(self, args):
        argData = om2.MArgParser(self.syntax(), args)
        
        if argData.isFlagSet( '-rb' ):
            flagValue = argData.flagArgumentBool( '-rb', 0)
        if argData.isFlagSet( '-iu' ):
            ignore_undo = argData.flagArgumentBool( '-iu', 0)
        return flagValue, ignore_undo
        
    def redoIt(self, flash=True):
        for node in self.nodes:
            sList = om2.MSelectionList()
            sList.add(node)
            mDagPath = sList.getDagPath(0)
            targetObjMesh = om2.MFnMesh(mDagPath)
            targetObjMesh.setFaceVertexColors(self.bake_color_dict[node],  self.face_dict[node], self.vtx_dict[node])
        sivertexcoloreditor.update_dict(self.color_dict)
        if flash:
            if self.ignore_undo:#スライダー制御中のアンドゥ履歴は全無視する
                return
            sivertexcoloreditor.refresh_window()
            
    
    def undoIt(self):
        sivertexcoloreditor.update_dict(self.org_color_dict)
        #sivertexcoloreditor.set_current_data(self.nodes, self.org_color_dict,  self.org_color_dict, self.face_dict, self.vtx_dict)
        if self.ignore_undo:#スライダー制御中のアンドゥ履歴は全無視する
            return
        for node in self.nodes:
            sList = om2.MSelectionList()
            sList.add(node)
            mDagPath = sList.getDagPath(0)
            targetObjMesh = om2.MFnMesh(mDagPath)
            targetObjMesh.setFaceVertexColors(self.org_color_dict[node],  self.face_dict[node], self.vtx_dict[node])
        sivertexcoloreditor.refresh_window()
 
    def isUndoable(self):
        return True
 
def cmdCreator():
    return BakeVertexColorClass() 
    
def syntaxCreator():
    syntax = om2.MSyntax()
    syntax.addFlag( '-rb', '-realbake', om2.MSyntax.kBoolean )
    syntax.addFlag( '-iu', '-ignoreundo', om2.MSyntax.kBoolean )
    return syntax

def initializePlugin( mobject ):
    mplugin = om2.MFnPlugin( mobject )
    try:
        mplugin.registerCommand( kPluginCmdName, cmdCreator, syntaxCreator )
        #引数持たせないバージョン
        #mplugin.registerCommand( kPluginCmdName, cmdCreator)
    except:
        sys.stderr.write( 'Failed to register command: ' + kPluginCmdName )
 
def uninitializePlugin( mobject ):
    mplugin = om2.MFnPlugin( mobject )
    try:
        mplugin.deregisterCommand( kPluginCmdName )
    except:
        sys.stderr.write( 'Failed to unregister command: ' + kPluginCmdName ) 