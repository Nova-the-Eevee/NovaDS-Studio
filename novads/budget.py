"""Static ROM & hardware budget estimates; does not claim live hardware metrics."""
def estimate_budget(p,images,backgrounds,sounds,programs):
    out=['NovaDS v1.1 — static hardware budget (estimates; NOT live profiler)','']
    if p['mode']=='dual3d':out+=['DUAL3D: VRAM C+D reserved for captured 256x192 frames (96 KiB each).', 'Dual 3D video uses no 2D text, sprites or tilemaps; rendering target 30 Hz/screen.','']
    for screen in ('top','bottom'):
        used={o['asset'] for o in p['objects'] if o['type']=='Sprite2D' and o['screen']==screen}
        objbytes=sum(sum(((im.width*im.height//2+127)//128)*128 for im in images[key]) for key in used)
        count=sum(o['type']=='Sprite2D' and o['screen']==screen for o in p['objects'])
        bgbytes=sum(len(bg.tiles)+2*len(bg.tilemap) for key,bg in backgrounds.items() if key.startswith(screen))
        out.append(f'{screen.upper()} — {count}/64 sprite OAM slots; OBJ graphics {objbytes}/131072 bytes; BG graphics+maps {bgbytes} bytes')
    wavbytes=sum(len(pcm) for pcm,_,_ in sounds.values())
    out.append(f'Audio samples (signed PCM8): {wavbytes}/131072 bytes budget')
    out.append(f'Embedded Lua source: {sum(len(script.encode("utf-8")) for script in programs.values())} bytes (VM heap separate)')
    out.append(f'Objects: {len(p["objects"])} / 192; scenes: {len(p["scenes"])}/8')
    out += ['', 'VRAM bank conflicts and actual ARM9 RAM, CPU time, audio playback require real-hardware profiling.']
    return '\n'.join(out)+'\n'
