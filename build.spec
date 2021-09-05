# -*- mode: python ; coding: utf-8 -*-
import gooey
gooey_root = os.path.dirname(gooey.__file__)
gooey_languages = Tree(os.path.join(gooey_root, 'languages'), prefix = 'gooey/languages')
gooey_images = Tree(os.path.join(gooey_root, 'images'), prefix = 'gooey/images')

block_cipher = None

a = Analysis(
    ['src/main.py'], 
    pathex=['/home/jesko/projects/rightmove_scraper_gui/'],
    hiddenimports=[],
    hookspath=None,
    runtime_hooks=None
    )

pyz = PYZ(a.pure)

options = [('u', None, 'OPTION')]

exe = EXE(pyz,
       a.scripts,
       a.binaries,
       a.zipfiles,
       a.datas,
       options,
       gooey_languages,
       gooey_images,
       icon="images/Rightmove_scaper_gui.ico",
       name='RightmoveScraper_0.1',
       debug=False,
       strip=None,
       upx=True,
       console=False)
       
