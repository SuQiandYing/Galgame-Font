from fontTools.ttLib import newTable
from fontTools.pens.ttGlyphPen import TTGlyphPen


def ensure_ttf(font, logger_func=print, name_desc="字体"):
    if 'CFF ' not in font:
        return font

    if logger_func:
        logger_func(f"⚙️ 检测到 {name_desc} 为 OTF 格式，正在转换为 TTF...")
    
    glyphOrder = font.getGlyphOrder()
    font['maxp'] = newTable('maxp')
    font['maxp'].tableVersion = 0x00010000
    font['maxp'].numGlyphs = len(glyphOrder)
    font['maxp'].maxZones = 1
    font['maxp'].maxTwilightPoints = 0
    font['maxp'].maxStorage = 0
    font['maxp'].maxFunctionDefs = 0
    font['maxp'].maxInstructionDefs = 0
    font['maxp'].maxStackElements = 0
    font['maxp'].maxSizeOfInstructions = 0
    font['maxp'].maxComponentElements = 0

    font['loca'] = newTable('loca')
    font['glyf'] = newTable('glyf')
    font['glyf'].glyphs = {}
    font['glyf'].glyphOrder = glyphOrder

    glyphSet = font.getGlyphSet()
    for glyphName in glyphOrder:
        pen = TTGlyphPen(glyphSet)
        try:
            glyphSet[glyphName].draw(pen)
            font['glyf'][glyphName] = pen.glyph()
        except Exception:
            font['glyf'][glyphName] = TTGlyphPen(None).glyph()

    if 'CFF ' in font: del font['CFF ']
    if 'VORG' in font: del font['VORG']
    font.sfntVersion = "\x00\x01\x00\x00"
    
    if logger_func:
        logger_func(f"✅ {name_desc} 格式转换完成。")
    return font
