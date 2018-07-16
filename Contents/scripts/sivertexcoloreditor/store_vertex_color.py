
import maya.api.OpenMaya as om2


def convert_comp_to_fv_list(self, meshFn, component, all_vf_array):
    for meshDag, component in zip(dags, comps):
        trsFn = om2.MFnTransform(meshDag)
        meshFn = om2.MFnMesh(meshDag)
        mesh_name = meshFn.fullPathName()
        #print 'store data :', mesh_name
        
        #全てのコンポーネントも取っておく                    
        all_vf_array = []
        all_facet = []
        all_vertices = []
        vf_id_dict = {}
        polyIter = om2.MItMeshPolygon(meshDag)
        i = 0
        for fid in range(polyIter.count()): 
            vtxArray = polyIter.getVertices()
            #print 'mesh iter :', fid, vtxArray
            for vid in vtxArray:
                if get_org:
                    all_facet.append(fid)
                    all_vertices.append(vid)
                all_vf_array.append((vid, fid))
                vf_id_dict[(vid, fid)] = i
                i += 1
            polyIter.next(1)  
            
            
    fv_array = []
    #現在選択中のコンポーネントを取得
    cmpType = None
    #フェースバーテックスならそのまま取得
    if component.hasFn(om2.MFn.kMeshVtxFaceComponent):
        cmpType = "facevtx"
        compFn = om2.MFnDoubleIndexedComponent(component)
        fv_array = compFn.getElements()
    #頂点なら全フェースバーテックスを捜査して含まれるものを取得
    elif component.hasFn(om2.MFn.kMeshVertComponent):
        cmpType = "vtx"
        compFn = om2.MFnSingleIndexedComponent(component)
        vids = compFn.getElements()
        polyIter = om2.MItMeshPolygon(meshDag)
        for fid in range(polyIter.count()):
            vtxArray = polyIter.getVertices()
            for vid in vtxArray:
                if vid in vids:
                    fv_array.append((vid, fid))
            polyIter.next(1)
    #エッジならいったん重複のない頂点セットに置き換えてフェースバーテックスを走査
    elif component.hasFn(om2.MFn.kMeshEdgeComponent):
        cmpType = "edge"
        compFn = om2.MFnSingleIndexedComponent(component)
        eid = compFn.getElements()
        eSet = []
        for e in eid:
            evid = meshFn.getEdgeVertices(e)
            eSet.extend(evid)
        vids = list(set(eSet))
        polyIter = om2.MItMeshPolygon(meshDag)
        for fid in range(polyIter.count()):
            vtxArray = polyIter.getVertices()
            for vid in vtxArray:
                if vid in vids:
                    fv_array.append((vid, fid))
            polyIter.next(1)
    #フェースなら含まれるバーテックスを取得してID生成
    elif component.hasFn(om2.MFn.kMeshPolygonComponent):
        cmpType = "face"
        compFn = om2.MFnSingleIndexedComponent(component)
        fids = compFn.getElements()
        fSet = []
        for fid in fids:
            vids = meshFn.getPolygonVertices(fid)
            for vid in vids:
                fv_array.append((vid, fid))
    #print 'check_comp_type :', mesh_name, cmpType
    #メッシュなら事前取得分をそのまま適用
    if not cmpType:
        fv_array = all_vf_array[:]
    #print 'cek all vf array :', all_vf_array
    #print 'get sel fv array :', fv_array
    
    return fv_array