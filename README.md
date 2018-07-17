# SIVertexColorEditor
Softimageにあったバーテックスカラーエディット機能をリスペク(ry

![image](https://user-images.githubusercontent.com/28256498/42760899-e4e0ed9c-8946-11e8-81cf-5e47f29bdaba.png)

Clone or download > Download ZIP もしくは  
release > Source code (zip) からZIPファイルをダウンロードしてください。  

解凍したSiWeightEditorフォルダを C:\Program Files\Autodesk\ApplicationPlugins へコピーしてください。  
ディレクトリ構成などは変更せず解凍フォルダごとそのまま設置します。  

![image](https://user-images.githubusercontent.com/28256498/42760977-237f2758-8947-11e8-9338-6462028ed5a9.png)

MayaをCドライブ以外にインストールしている場合でも  
C:\Program Files\Autodesk\ApplicationPlugins  
に置く必要があるようです。  

ApplicationPluginsフォルダが存在しない場合は作成してください。  

動作確認はMaya2015～2018で行っています。  

インストールに成功するとウィンドウ以下に項目が追加されます。  

![image](https://user-images.githubusercontent.com/28256498/42761037-4bf12fb0-8947-11e8-9dbc-05aa10db0dce.png)

## 主な機能・UI

### 基本UI表示1
![image](https://user-images.githubusercontent.com/28256498/42761765-678b087a-8949-11e8-8f9e-8ac9b626d7b5.png)

・Show → 選択したテーブルセルに表示をフォーカスする。  
・Show All → オブジェクトのウェイトを全表示する  
・Highlite → セル選択されたフェース頂点をビューポート上でハイライトする  

## 主な機能・入力

### 入力方法4種類  
・スピンボックス　→　ボックス入力、ホイール可能  
・スライダーバー → スライダーバーで値を指定  
・右クリック入力　→　セルを右クリックして小窓に入力、絶対値の場合はクリックしたセルの値を拾います。  
・直接入力　→　セル選択した状態で数値入力を始めるとそのまま小窓入力できます。  

### 入力モード3種類と正規化設定

![image](https://user-images.githubusercontent.com/28256498/42762235-b952520c-894a-11e8-9a5b-122904f00c1d.png)

・Abs　→　絶対値入力、指定した値がそのまま入ります。  
・Add　→　加算入力、現在の値に入力値を加算（減算）します。  
・Add%　→　率加算、現在の値に対して指定比率加算します。例)50に50を指定すると50%の25が加算されて75になります。  
・1<>255　→　 RGBA表示の0-1と0-255表示を切り替えます

### チャンネル切替機能

RGBのみ表示とRGBA各チャンネルのグレースケール表示を切り替えることができます。  
表示を切り替えたままエディット可能です。  
 
### ペイント機能とチャンネル切替の併用

Mayaのバーテックスカラーペイント機能とチャンネル切替で連携した塗りができます。  
アルファチャンネル非表示状態でRGBチャンネルのみペイント。  
RGBAチャンネル各独立してグレースケールでペイントするなど。  

![vetexcoloreditor](https://user-images.githubusercontent.com/28256498/42763047-e75f3e2e-894c-11e8-8b21-f0004283065b.gif)
