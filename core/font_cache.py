import os
import time
from fontTools.ttLib import TTFont
from functools import lru_cache

_font_cache = {}
_cmap_cache = {}
_cache_times = {}
_MAX_CACHE_AGE = 300
_MAX_CACHE_SIZE = 10

def get_font(path, readonly=True):
    path = os.path.abspath(path)
    mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    
    cache_key = (path, mtime)
    
    if cache_key in _font_cache:
        _cache_times[cache_key] = time.time()
        return _font_cache[cache_key]
    
    _cleanup_old_cache()
    
    font = TTFont(path)
    if readonly:
        _font_cache[cache_key] = font
        _cache_times[cache_key] = time.time()
    
    return font

def get_cmap(path):
    path = os.path.abspath(path)
    mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    
    cache_key = (path, mtime)
    
    if cache_key in _cmap_cache:
        return _cmap_cache[cache_key]
    
    font = get_font(path, readonly=True)
    cmap = font.getBestCmap()
    _cmap_cache[cache_key] = cmap
    
    return cmap

def get_charset(path):
    cmap = get_cmap(path)
    return set(chr(c) for c in cmap.keys() if c < 0x110000)

def invalidate_cache(path=None):
    global _font_cache, _cmap_cache, _cache_times
    
    if path is None:
        for font in _font_cache.values():
            try:
                font.close()
            except:
                pass
        _font_cache.clear()
        _cmap_cache.clear()
        _cache_times.clear()
    else:
        path = os.path.abspath(path)
        keys_to_remove = [k for k in _font_cache.keys() if k[0] == path]
        for key in keys_to_remove:
            try:
                _font_cache[key].close()
            except:
                pass
            del _font_cache[key]
            if key in _cache_times:
                del _cache_times[key]
        
        keys_to_remove = [k for k in _cmap_cache.keys() if k[0] == path]
        for key in keys_to_remove:
            del _cmap_cache[key]

def _cleanup_old_cache():
    now = time.time()
    keys_to_remove = []
    
    for key, cache_time in list(_cache_times.items()):
        if now - cache_time > _MAX_CACHE_AGE:
            keys_to_remove.append(key)
    
    while len(_font_cache) - len(keys_to_remove) >= _MAX_CACHE_SIZE:
        oldest_key = min(_cache_times.keys(), key=lambda k: _cache_times[k])
        if oldest_key not in keys_to_remove:
            keys_to_remove.append(oldest_key)
    
    for key in keys_to_remove:
        if key in _font_cache:
            try:
                _font_cache[key].close()
            except:
                pass
            del _font_cache[key]
        if key in _cmap_cache:
            del _cmap_cache[key]
        if key in _cache_times:
            del _cache_times[key]

@lru_cache(maxsize=32)
def get_font_info(path):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return None
    
    mtime = os.path.getmtime(path)
    return _get_font_info_impl(path, mtime)

def _get_font_info_impl(path, mtime):
    try:
        font = get_font(path, readonly=True)
        name_table = font.get('name')
        
        info = {
            'path': path,
            'size': os.path.getsize(path),
            'glyph_count': len(font.getGlyphOrder()),
            'names': {}
        }
        
        if name_table:
            for record in name_table.names:
                try:
                    value = record.toUnicode()
                    if record.nameID not in info['names']:
                        info['names'][record.nameID] = value
                except:
                    pass
        
        return info
    except:
        return None
