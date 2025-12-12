import os
import json
import glob
import traceback
from fontTools.ttLib import TTFont
from fontTools import subset
from core.utils import ensure_ttf
from core.history_manager import get_history_manager


def build_font(conf, log_signal, prog_signal):
    src = conf['src']
    fallback = conf.get('fallback', '')
    json_path = conf['json']
    file_name = conf['file_name']
    internal_name = conf['internal_name']
    mode = conf['mode']
    output_dir = conf.get('output_dir', '')

    if mode == 0:
        log_signal("⚠️ 未选择任何模式，操作取消。")
        return None

    if not os.path.exists(src):
        log_signal("❌ <font color='red'>错误：未找到源字体文件</font>")
        return None

    if mode not in [3, 4, 5] and not os.path.exists(json_path):
        log_signal("❌ <font color='red'>错误：未找到映射 JSON 文件</font>")
        return None

    out_name = file_name if file_name.lower().endswith('.ttf') else f"{file_name}.ttf"

    mode_desc = {
        1: "日繁映射 (CN -> JP)", 2: "逆向映射 (JP -> CN)",
        3: "仅伪装", 4: "繁转简", 5: "简转繁"
    }.get(mode, "未知")

    log_signal(f"<b>🔨 开始字体处理...</b><br>模式: {mode_desc}<br>输入: {os.path.basename(src)}<br>输出: {out_name}")
    prog_signal(10)

    try:
        font = TTFont(src)
        ensure_ttf(font, log_signal, "主字体")
    except Exception as e:
        log_signal(f"❌ 字体读取失败: {str(e)}")
        return None

    if mode in [1, 2] and fallback and os.path.exists(fallback):
        log_signal(f"🔧 检测到补全字体: {os.path.basename(fallback)}")
        try:
            fb_font = TTFont(fallback)
            ensure_ttf(fb_font, log_signal, "补全字体")

            upm_main = font['head'].unitsPerEm
            upm_fb = fb_font['head'].unitsPerEm
            scale_factor = upm_main / upm_fb

            need_scale = abs(scale_factor - 1.0) > 0.01
            if need_scale:
                log_signal(f"⚖️ 检测到UPM差异 (主:{upm_main} vs 补:{upm_fb})，缩放倍率: {scale_factor:.2f}")

            target_chars_needed = set()
            with open(json_path, 'r', encoding='utf-8') as f:
                raw_json = json.load(f)
                if mode == 1:
                    target_chars_needed = set(raw_json.keys())
                elif mode == 2:
                    target_chars_needed = set(raw_json.values())

            main_cmap = font.getBestCmap()
            fb_cmap = fb_font.getBestCmap()
            injected_count = 0

            if 'glyf' not in font or 'glyf' not in fb_font:
                log_signal("⚠️ 补全警告：非 TrueType 格式，跳过。")
            else:
                for char in target_chars_needed:
                    code = ord(char)
                    if code not in main_cmap and code in fb_cmap:
                        fb_glyph_name = fb_cmap[code]
                        fb_glyph = fb_font['glyf'][fb_glyph_name]

                        if need_scale:
                            if fb_glyph.isComposite():
                                for comp in fb_glyph.components:
                                    comp.x = int(comp.x * scale_factor)
                                    comp.y = int(comp.y * scale_factor)
                            elif hasattr(fb_glyph, 'coordinates'):
                                coords = fb_glyph.coordinates
                                for i in range(len(coords)):
                                    x, y = coords[i]
                                    coords[i] = (int(x * scale_factor), int(y * scale_factor))
                                try:
                                    fb_glyph.recalcBounds(fb_font['glyf'])
                                except:
                                    pass

                            width, lsb = fb_font['hmtx'][fb_glyph_name]
                            if need_scale:
                                width = int(width * scale_factor)
                                lsb = int(lsb * scale_factor)
                        else:
                            width, lsb = fb_font['hmtx'][fb_glyph_name]

                        new_glyph_name = f"uni{code:04X}_fb"
                        font['glyf'][new_glyph_name] = fb_glyph
                        font['hmtx'][new_glyph_name] = (width, lsb)

                        for t in font['cmap'].tables:
                            if t.platformID == 3:
                                t.cmap[code] = new_glyph_name

                        injected_count += 1

                log_signal(f"💉 <b>自动补全:</b> 注入 {injected_count} 个汉字 (已修正大小)")

        except Exception as e:
            log_signal(f"⚠️ 补全出错: {str(e)}")
            traceback.print_exc()

    ok_count = 0
    missing_list = []

    if mode == 3:
        log_signal("⏩ 伪装模式：跳过字符修改...")
        prog_signal(30)

    elif mode in [4, 5]:
        try:
            import opencc
        except ImportError:
            log_signal("❌ 未安装 OpenCC，请运行: pip install opencc-python-reimplemented")
            return None
        
        config_file = 't2s' if mode == 4 else 's2t'
        log_signal(f"🔄 字形转换 ({config_file})...")
        try:
            cc = opencc.OpenCC(config_file)
            mapped_count = 0
            cmap_tables = [t for t in font['cmap'].tables if t.platformID == 3]
            for table in cmap_tables:
                existing = list(table.cmap.keys())
                for code in existing:
                    try:
                        s_char = cc.convert(chr(code))
                        if s_char != chr(code):
                            s_code = ord(s_char)
                            if s_code in table.cmap:
                                table.cmap[code] = table.cmap[s_code]
                                mapped_count += 1
                    except:
                        pass
            ok_count = mapped_count
        except Exception as e:
            log_signal(f"❌ OpenCC 失败: {e}")
            return None

    else:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
                mapping = {v: k for k, v in raw.items()} if mode == 1 else raw
        except Exception as e:
            log_signal(f"❌ JSON 读取失败: {e}")
            return None

        prog_signal(30)
        log_signal("🔍 执行映射...")

        missing_set = set()
        target_tables = [t for t in font['cmap'].tables if t.platformID == 3]

        for table in target_tables:
            for target_char, source_char in mapping.items():
                if target_char == source_char:
                    continue
                target_code, source_code = ord(target_char), ord(source_char)

                if source_code in table.cmap:
                    table.cmap[target_code] = table.cmap[source_code]
                    ok_count += 1
                else:
                    missing_set.add(source_char)

        if target_tables:
            ok_count //= len(target_tables)
        missing_list = list(missing_set)

    prog_signal(60)
    log_signal("✏️ 修改元数据...")

    font['name'].names = [r for r in font['name'].names if r.nameID not in [1, 4, 6, 16, 17]]
    style = "Regular"
    full_name = f"{internal_name} {style}"
    ps_name = f"{internal_name}-{style}".replace(" ", "")

    for nameID, string in [(1, internal_name), (4, full_name), (6, ps_name)]:
        try:
            font['name'].setName(string, nameID, 3, 1, 1033)
        except:
            pass

    log_signal("🇯🇵 注入日文伪装...")
    try:
        font['OS/2'].ulCodePageRange1 |= (1 << 17)
        font['OS/2'].ulCodePageRange1 |= (1 << 0)
    except:
        pass

    if output_dir and os.path.isdir(output_dir):
        out_path = os.path.join(output_dir, out_name)
    else:
        out_path = os.path.join(os.path.dirname(src), out_name)

    history = get_history_manager()
    file_existed = os.path.exists(out_path)
    if file_existed:
        history.record_before_overwrite("生成字体", out_path, f"模式{mode}")

    try:
        font.save(out_path)
        prog_signal(100)

        msg = f"<br><b style='color:#4CAF50'>✅ 成功: {out_path}</b><br>"
        if mode in [1, 2]:
            msg += f"&nbsp;&nbsp;-> 成功映射: {ok_count} 个<br>"
            msg += f"&nbsp;&nbsp;-> 缺失汉字: {len(missing_list)} 个<br>"

        if missing_list:
            msg += f"<br><b style='color:#FF9800'>⚠️ 严重警告：以下字符在补全字体中也未找到：</b><br>"
            msg += "".join(missing_list[:100])
            if len(missing_list) > 100:
                msg += f"... (共 {len(missing_list)} 个)"
            msg += "<br><span style='color:gray'>建议更换一个字符集更大的补全字体。</span><br>"

        log_signal(msg)
        
        if not file_existed and os.path.exists(out_path):
            history.record_new_file("生成字体", out_path, f"模式{mode}")
        
        return out_path
        
    except Exception as e:
        log_signal(f"❌ 保存失败: {e}")
        traceback.print_exc()
        return None


def subset_font(conf, log_signal, prog_signal):
    font_path = conf['font_path']
    txt_dir = conf.get('txt_dir', '')
    json_path = conf.get('json_path', '')
    out_path = conf['out_path']
    exts = conf.get('exts', '.txt;.json').split(';')
    history = get_history_manager()
    file_existed = os.path.exists(out_path)

    if not os.path.exists(font_path):
        log_signal("❌ 字体文件不存在！")
        return None

    log_signal(f"✂️ <b>开始精简字体...</b>")
    log_signal(f"   源字体: {os.path.basename(font_path)}")
    prog_signal(5)

    all_chars = set()

    if txt_dir and os.path.exists(txt_dir):
        all_files = []
        for ext in exts:
            ext = ext.strip()
            if not ext: continue
            if not ext.startswith('.'): ext = '.' + ext
            all_files.extend(glob.glob(os.path.join(txt_dir, '**', f'*{ext}'), recursive=True))
        
        log_signal(f"   扫描文本: {len(all_files)} 个文件")
        
        for fpath in all_files:
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    all_chars.update(f.read())
            except:
                pass

    if json_path and os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
                all_chars.update(mapping.keys())
                all_chars.update(mapping.values())
            log_signal(f"   映射表: {len(mapping)} 条")
        except:
            pass

    all_chars = {c for c in all_chars if c.isprintable() or c in ['\n', '\r', '\t']}
    log_signal(f"   需要保留: {len(all_chars)} 个字符")
    
    prog_signal(30)

    if not all_chars:
        log_signal("⚠️ 未找到任何字符，无法精简！")
        return None

    try:
        font = TTFont(font_path)
        ensure_ttf(font, log_signal, "源字体")
        
        options = subset.Options()
        options.name_IDs = ['*']
        options.name_legacy = True
        options.name_languages = ['*']
        options.glyph_names = True
        options.notdef_glyph = True
        options.notdef_outline = True
        options.recalc_bounds = True
        options.drop_tables = ['EBDT', 'EBLC', 'EBSC', 'CBDT', 'CBLC']
        
        prog_signal(50)
        
        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=''.join(all_chars))
        subsetter.subset(font)
        
        prog_signal(80)
        
        if file_existed:
            history.record_before_overwrite("精简字体", out_path, f"保留{len(all_chars)}字符")

        font.save(out_path)
        font.close()
        
        original_size = os.path.getsize(font_path) / 1024
        new_size = os.path.getsize(out_path) / 1024
        reduction = (1 - new_size / original_size) * 100
        
        if not file_existed and os.path.exists(out_path):
            history.record_new_file("精简字体", out_path, f"保留{len(all_chars)}字符")
        elif os.path.exists(out_path):
            history.record("精简字体", out_path, f"保留{len(all_chars)}字符")
        
        prog_signal(100)
        log_signal(f"✅ <b>精简完成！</b>")
        log_signal(f"   原始大小: {original_size:.1f} KB")
        log_signal(f"   精简后: {new_size:.1f} KB")
        log_signal(f"   体积减少: {reduction:.1f}%")
        log_signal(f"   输出: {out_path}")
        return out_path

    except Exception as e:
        log_signal(f"❌ 精简失败: {e}")
        traceback.print_exc()
        return None


def gen_woff2(conf, log_signal, prog_signal):
    src = conf['src']
    out_path = conf['out_path']
    history = get_history_manager()
    file_existed = os.path.exists(out_path)

    if not os.path.exists(src):
        log_signal("❌ 源字体不存在！")
        return None

    log_signal(f"🌐 <b>开始转换 WOFF2...</b>")
    log_signal(f"   源文件: {os.path.basename(src)}")
    prog_signal(10)

    try:
        font = TTFont(src)
        ensure_ttf(font, log_signal, "源字体")
        
        prog_signal(50)
        
        if file_existed:
            history.record_before_overwrite("WOFF2转换", out_path, os.path.basename(src))
        
        font.flavor = 'woff2'
        font.save(out_path)
        font.close()
        
        original_size = os.path.getsize(src) / 1024
        new_size = os.path.getsize(out_path) / 1024
        reduction = (1 - new_size / original_size) * 100
        
        if not file_existed and os.path.exists(out_path):
            history.record_new_file("WOFF2转换", out_path, os.path.basename(src))
        elif os.path.exists(out_path):
            history.record("WOFF2转换", out_path, os.path.basename(src))
        
        prog_signal(100)
        log_signal(f"✅ <b>WOFF2 转换完成！</b>")
        log_signal(f"   原始大小: {original_size:.1f} KB")
        log_signal(f"   WOFF2: {new_size:.1f} KB")
        log_signal(f"   压缩率: {reduction:.1f}%")
        log_signal(f"   输出: {out_path}")
        return out_path

    except Exception as e:
        log_signal(f"❌ 转换失败: {e}")
        traceback.print_exc()
        return None