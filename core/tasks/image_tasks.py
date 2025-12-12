import os
import struct
from PIL import Image, ImageDraw, ImageFont

def _get_jp_chars():
    fl = list(range(0x81, 0xA0)) + list(range(0xE0, 0xF0)) + list(range(0xFA, 0xFD))
    sl = list(range(0x40, 0x7F)) + list(range(0x80, 0xFD))
    return fl, sl

def gen_pic(conf, log_signal, prog_signal):
    if not os.path.exists(conf['font']): 
        log_signal("❌ 字体文件不存在！")
        return None

    log_signal(f"🚀 开始生成图片字库 ({conf['format']})...")
    if not os.path.exists(conf['folder']): os.makedirs(conf['folder'])

    font = ImageFont.truetype(conf['font'], conf['fsize'])
    fl, sl = _get_jp_chars()
    total_blocks = len(fl)
    seq = 0

    for idx, i in enumerate(fl):
        prog_signal(int((idx / total_blocks) * 100))
        text_buf = ""
        valid = 0
        for j in sl:
            try:
                text_buf += (i * 0x100 + j).to_bytes(2, 'big').decode('cp932')
                valid += 1
            except:
                text_buf += '･'

        if valid == 0: continue

        img = Image.new('RGBA', (conf['img_w'], conf['img_h']))
        draw = ImageDraw.Draw(img)

        start = 0
        py = conf['iy']
        while start < len(text_buf):
            line = text_buf[start: start + conf['count']]
            px = conf['ix']
            for char in line:
                draw.text((px, py), char, font=font, fill=(255, 255, 255))
                px += conf['cw'] + conf['iw']
            py += conf['ch'] + conf['ih']
            start += conf['count']

        seq += 1
        fname = f"fnt_s{conf['fsize']}_n{seq}.{conf['format']}"
        img.save(os.path.join(conf['folder'], fname))
        log_signal(f"   -> 已输出: {fname}")

    prog_signal(100)
    log_signal("✅ 图片字库生成完成。")
    return None

def gen_tga(conf, log_signal, prog_signal):
    if not os.path.exists(conf['font']): 
        log_signal("❌ 字体文件不存在！")
        return None
    log_signal("🚀 开始生成 TGA 引擎字库...")

    out_dir = os.path.join(conf['folder'], 'new')
    if not os.path.exists(out_dir): os.makedirs(out_dir)

    text_items = []
    for code in range(0x20, 0x7F): text_items.append((chr(code), code))

    fl = list(range(0x81, 0xA0)) + list(range(0xE0, 0xEB)) + list(range(0xFA, 0xFD))
    sl = list(range(0x40, 0x80)) + list(range(0x80, 0x100))
    for i in fl:
        for j in sl:
            code = i * 0x100 + j
            try:
                text_items.append(((code).to_bytes(2, 'big').decode('cp932'), code))
            except:
                pass

    img = Image.new('RGBA', (conf['img_w'], conf['img_h']))
    font = ImageFont.truetype(conf['font'], conf['fsize'])
    draw = ImageDraw.Draw(img)

    px, py = 0, 0
    info_map = {}
    total = len(text_items)

    for idx, (char, code) in enumerate(text_items):
        if idx % 500 == 0: prog_signal(int((idx / total) * 100))

        bbox = font.getbbox(char)
        cw = bbox[2]
        ch = bbox[3]

        if px + cw > conf['img_w']:
            px = 0
            py += conf['ch'] + conf['ih']
            if py + conf['ch'] > conf['img_h']:
                log_signal("⚠️ 警告：图片空间不足，截断！")
                break

        draw.text((px, py), char, font=font, fill=(255, 255, 255))
        info_map[code] = {'box': (px, py, px + cw, py + ch), 'code': code}
        px += cw + conf['iw']

    tga_path = os.path.join(out_dir, f"{conf['dat']}.tga")
    img.save(tga_path)

    dat = bytearray()
    fname_b = conf['eng_name'].encode('cp932')
    fpath_b = conf['eng_path'].encode('cp932')
    dat.extend(struct.pack(f'<I{len(fname_b)}s', len(fname_b), fname_b))
    dat.extend(struct.pack('<II', conf['cw'], conf['ch']))
    dat.extend(struct.pack(f'<I{len(fpath_b)}s', len(fpath_b), fpath_b))
    dat.extend(struct.pack('<I', len(info_map)))

    for _, info in info_map.items():
        x0, y0, x1, y1 = info['box']
        dat.extend(struct.pack('<HBBIIIIII', info['code'], x1 - x0, 0x1E, x0, y0, x1, y1, 0xFFFFFFFF, 0))

    with open(os.path.join(out_dir, f"{conf['dat']}.txt"), 'wb') as f: f.write(dat)
    prog_signal(100)
    log_signal(f"✅ TGA 字库完成，索引: {conf['dat']}.txt")
    return None

def gen_bmp(conf, log_signal, prog_signal):
    if not os.path.exists(conf['font']): 
        log_signal("❌ 字体文件不存在！")
        return None
    log_signal("🚀 开始生成 BMP 长图字库...")
    if not os.path.exists(conf['folder']): os.makedirs(conf['folder'])

    font = ImageFont.truetype(conf['font'], conf['fsize'])
    fl, sl = _get_jp_chars()

    palette = []
    if conf['depth'] <= 8:
        grad = 256 // (2 ** conf['depth'])
        t = 0
        for i in range(2 ** conf['depth']):
            palette.extend([t, t, t]); t += grad

    text_buf = ""
    count = 0
    seq = 0
    page_limit = 16

    total_fl = len(fl)

    for idx, i in enumerate(fl):
        prog_signal(int((idx / total_fl) * 100))
        for j in sl:
            try:
                text_buf += (i * 0x100 + j).to_bytes(2, 'big').decode('cp932')
            except:
                text_buf += '　'

        count += 1
        if count == page_limit or i == fl[-1]:
            h = count * conf['ch'] * 12
            if conf['depth'] <= 8:
                img = Image.new('P', (conf['img_w'], h))
                img.putpalette(palette)
            else:
                img = Image.new('RGBA', (conf['img_w'], h))

            draw = ImageDraw.Draw(img)
            start = 0
            py = 0
            while start < len(text_buf):
                line = text_buf[start: start + conf['count']]
                px = 0
                for ch in line:
                    draw.text((px, py), ch, font=font, fill=(255, 255, 255))
                    px += conf['cw']
                py += conf['ch']
                start += conf['count']

            if conf['scale'] != 1.0:
                img = img.resize((int(img.width * conf['scale']), int(img.height * conf['scale'])), Image.Resampling.BICUBIC)

            fname = f"ff_0{seq}l.bmp"
            img.save(os.path.join(conf['folder'], fname))
            log_signal(f"   -> 已输出: {fname}")

            seq += 1
            text_buf = ""
            count = 0

    prog_signal(100)
    log_signal("✅ BMP 长图字库生成完成。")
    return None

def gen_bmfont(conf, log_signal, prog_signal):
    font_path = conf['font_path']
    chars = conf['chars']
    tex_size = conf['tex_size']
    font_size = conf['font_size']
    out_fnt = conf['out_fnt']
    out_png = os.path.splitext(out_fnt)[0] + ".png"
    
    if not os.path.exists(font_path):
            log_signal("❌ 字体文件不存在")
            return None

    log_signal(f"🚀 <b>开始生成 BMFont...</b>")
    log_signal(f"   画布尺寸: {tex_size}x{tex_size} | 字号: {font_size}")
    log_signal(f"   字符总数: {len(chars)}")
    prog_signal(5)
    
    try:
        pil_font = ImageFont.truetype(font_path, font_size)
        metrics = [] 
        log_signal("📏 正在测量字形...")
        
        current_x = 0
        current_y = 0
        row_h = 0
        padding = 2 
        
        packed_glyphs = []
        img_map = {} 
        
        ascent, descent = pil_font.getmetrics()
        line_height = ascent + descent
        
        count = 0 
        total_chars = len(chars)
        
        for char in chars:
            adv = pil_font.getlength(char)
            bbox = pil_font.getbbox(char)
            
            if bbox:
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                cw, ch = font_size * 2, font_size * 2
                tmp_img = Image.new('RGBA', (cw, ch), (0,0,0,0))
                draw = ImageDraw.Draw(tmp_img)
                draw.text((0,0), char, font=pil_font, fill=(255,255,255))
                
                crop_box = tmp_img.getbbox()
                if crop_box:
                        glyph_img = tmp_img.crop(crop_box)
                        w, h = glyph_img.size
                        xoff = crop_box[0]
                        yoff = crop_box[1]
                else:
                        glyph_img = None
                        w, h = 0, 0
                        xoff, yoff = 0, 0
            else:
                glyph_img = None
                w, h = 0, 0
                xoff, yoff = 0, 0
                
            img_map[char] = glyph_img

            if current_x + w + padding > tex_size:
                current_x = 0
                current_y += row_h + padding
                row_h = 0
            
            if current_y + h + padding > tex_size:
                log_signal("❌ 画布过小，无法容纳所有字符！请增大画布尺寸。")
                return None

            packed_glyphs.append({
                "id": ord(char),
                "char": char,
                "x": current_x,
                "y": current_y,
                "width": w,
                "height": h,
                "xoffset": xoff,
                "yoffset": yoff,
                "xadvance": int(adv),
                "chnl": 15
            })

            current_x += w + padding
            row_h = max(row_h, h)
            
            count += 1
            if count % 200 == 0:
                prog_signal(int(5 + 80 * count / total_chars))
        
        log_signal("🎨 正在绘制纹理...")
        atlas = Image.new('RGBA', (tex_size, tex_size), (0,0,0,0))
        for g in packed_glyphs:
            char = g['char']
            if img_map[char]:
                atlas.paste(img_map[char], (g['x'], g['y']))
        
        log_signal(f"💾 保存纹理: {out_png}")
        atlas.save(out_png)
        
        log_signal(f"📝 生成描述文件: {out_fnt}")
        
        lines = []
        lines.append(f'info face="{os.path.basename(font_path)}" size={font_size} bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1 outline=0')
        lines.append(f'common lineHeight={line_height} base={ascent} scaleW={tex_size} scaleH={tex_size} pages=1 packed=0 alphaChnl=1 redChnl=0 greenChnl=0 blueChnl=0')
        lines.append(f'page id=0 file="{os.path.basename(out_png)}"')
        lines.append(f'chars count={len(packed_glyphs)}')
        
        for g in packed_glyphs:
            line = f'char id={g["id"]} x={g["x"]} y={g["y"]} width={g["width"]} height={g["height"]} xoffset={g["xoffset"]} yoffset={g["yoffset"]} xadvance={g["xadvance"]} page=0 chnl=15'
            lines.append(line)
        
        with open(out_fnt, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        prog_signal(100)
        log_signal(f"✅ <b>BMFont 生成完毕!</b>")
        return out_fnt

    except Exception as e:
        log_signal(f"❌ 生成失败: {e}")
        traceback.print_exc()
        return None