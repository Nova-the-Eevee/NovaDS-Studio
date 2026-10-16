"""NDS banner configuration and indexed icon conversion."""
from pathlib import Path
from PIL import Image

def write_icon_bmp(png_path,output):
    im=Image.open(png_path).convert('RGBA')
    if im.size!=(32,32):raise ValueError('NDS icon PNG must be exactly 32x32')
    # Background color for transparent pixels; DS banner uses indexed 16-color BMP.
    opaque=Image.new('RGB',(32,32),(255,0,255))
    opaque.paste(im,mask=im.getchannel('A'))
    palette=opaque.quantize(colors=16,method=Image.Quantize.FASTOCTREE)
    palette.save(output,format='BMP')

def make_banner_makefile(path,metadata,has_icon):
    # All fields already checked by clean_project(). No make/shell metacharacters.
    lines=['# Generated NDS banner configuration (NovaDS Studio v1.1)',
           'GAME_TITLE := '+metadata['banner_title'],
           'GAME_SUBTITLE1 := '+metadata['banner_subtitle'],
           'GAME_SUBTITLE2 := '+metadata['banner_creator']]
    # The NDS packaging rule runs in build/, not the exported project root.
    # Resolve relative to the actual Makefile, in both recursive and top-level make.
    if has_icon:
        lines.extend(('ifneq ($(notdir $(CURDIR)),build)',
                      'export GAME_ICON := $(CURDIR)/icon.bmp',
                      'endif'))
    source=Path(path).read_text(encoding='utf-8')
    anchor='include $(DEVKITARM)/ds_rules'
    if anchor not in source:raise ValueError('Unsupported NovaDS Makefile layout')
    source=source.replace(anchor,'\n'.join(lines)+'\n\n'+anchor,1)
    Path(path).write_text(source,encoding='utf-8')
