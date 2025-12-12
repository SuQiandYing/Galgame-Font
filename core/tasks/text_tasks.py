import os
import glob
import json
import unicodedata
from fontTools.ttLib import TTFont


def gen_mapping(conf, log_signal, prog_signal):
    src_dir = conf['src_dir']
    out_dir = conf['out_dir']
    out_json = conf['out_json']
    exts = conf['exts'].split(';')
    limit_font_path = conf.get('limit_font', '')

    if not os.path.exists(src_dir):
        log_signal("❌ 输入目录不存在！")
        return None

    log_signal(f"🔍 开始扫描文本: {src_dir}")
    prog_signal(5)

    all_files = []
    for ext in exts:
        ext = ext.strip()
        if not ext: continue
        if not ext.startswith('.'): ext = '.' + ext
        all_files.extend(glob.glob(os.path.join(src_dir, '**', f'*{ext}'), recursive=True))

    if not all_files:
        log_signal("⚠️ 未找到任何匹配的文件。")
        return None

    unique_chars = set()
    total_files = len(all_files)

    def extract_chars_from_obj(obj, char_set):
        if isinstance(obj, str):
            for char in obj:
                char_set.add(char)
        elif isinstance(obj, list):
            for item in obj:
                extract_chars_from_obj(item, char_set)
        elif isinstance(obj, dict):
            for value in obj.values():
                extract_chars_from_obj(value, char_set)

    for idx, fpath in enumerate(all_files):
        try:
            if fpath.lower().endswith('.json'):
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    extract_chars_from_obj(data, unique_chars)
            else:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for char in content:
                        unique_chars.add(char)
        except Exception as e:
            log_signal(f"⚠️ 读取失败 {os.path.basename(fpath)}: {e}")
        
        if idx % 10 == 0:
            prog_signal(5 + int(15 * idx / total_files))

    log_signal(f"📊 扫描完成，共发现 {len(unique_chars)} 个唯一字符。")
    prog_signal(20)

    limit_font_chars = None
    if limit_font_path and os.path.exists(limit_font_path):
        try:
            tmp_font = TTFont(limit_font_path)
            tmp_cmap = tmp_font.getBestCmap()
            limit_font_chars = set(chr(c) for c in tmp_cmap.keys())
            tmp_font.close()
        except:
            pass

    chars_to_map = []
    chars_safe = 0

    for char in unique_chars:
        if char in ['\n', '\r', '\t', '\b', '\f', '\v']:
            chars_safe += 1
            continue
        
        category = unicodedata.category(char)
        if category.startswith('C') or category.startswith('Z'):
            chars_safe += 1
            continue

        is_cp932 = False
        try:
            char.encode('cp932')
            is_cp932 = True
        except UnicodeEncodeError:
            is_cp932 = False

        should_map = False
        
        if not is_cp932:
            should_map = True
        elif limit_font_chars is not None and char not in limit_font_chars:
            should_map = True
            
        if should_map:
            chars_to_map.append(char)
        else:
            chars_safe += 1

    chars_to_map.sort()
    log_signal(f"   -> 原生 CP932 且存在: {chars_safe} (保持不变)")
    log_signal(f"   -> 需映射字符: {len(chars_to_map)} (含非CP932或缺失字符)")

    if len(chars_to_map) == 0:
        log_signal("✅ 所有字符均支持 CP932 且存在于字体中，无需映射！")
        prog_signal(100)
        return None

    available_proxies = []
    
    if limit_font_path and os.path.exists(limit_font_path):
        log_signal(f"🔒 <b>启用字体限制模式</b>: {os.path.basename(limit_font_path)}")
        try:
            font = TTFont(limit_font_path)
            cmap = font.getBestCmap()
            font_chars = set(chr(c) for c in cmap.keys())
            font.close()
            
            for char in font_chars:
                if char in unique_chars: continue
                if char in ['\n', '\r', '\t']: continue
                
                try:
                    b = char.encode('cp932')
                    if len(b) == 2:
                        available_proxies.append(char)
                except UnicodeEncodeError:
                    pass
            
            log_signal(f"   可用空位(Slot): {len(available_proxies)} 个")

        except Exception as e:
            log_signal(f"⚠️ 读取限制字体失败: {e}，将回退到全量模式。")
            limit_font_path = None

    if not limit_font_path:
        log_signal("🌍 使用标准全量 CP932 空间")
        def sjis_generator():
            ranges = [(0x89, 0x9F), (0xE0, 0xEA)]
            for h in range(ranges[0][0], ranges[0][1] + 1):
                for l in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
                    yield bytes([h, l])
            for h in range(ranges[1][0], ranges[1][1] + 1):
                for l in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
                    yield bytes([h, l])

        for proxy_bytes in sjis_generator():
            try:
                proxy_char = proxy_bytes.decode('cp932')
                category = unicodedata.category(proxy_char)
                if proxy_char not in unique_chars and not (category.startswith('C') or category.startswith('Z')):
                    available_proxies.append(proxy_char)
            except UnicodeDecodeError:
                continue

    if len(available_proxies) < len(chars_to_map):
        log_signal(f"❌ <font color='red'><b>致命错误：可用空位不足！</b></font>")
        log_signal(f"   需要映射: {len(chars_to_map)} 个 | 实际可用: {len(available_proxies)} 个")
        return None

    mapping_dict = {}
    available_proxies.sort()
    
    for i, cn_char in enumerate(chars_to_map):
        proxy_char = available_proxies[i]
        mapping_dict[cn_char] = proxy_char

    prog_signal(40)

    try:
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(mapping_dict, f, ensure_ascii=False, indent=2)
        log_signal(f"💾 映射表已保存: {out_json}")
    except Exception as e:
        log_signal(f"❌ JSON 保存失败: {e}")
        return None

    prog_signal(50)
    log_signal("📝 正在替换并输出文本文件...")
    if not os.path.exists(out_dir): os.makedirs(out_dir)

    def recursive_replace(obj, mapper):
        if isinstance(obj, str):
            return "".join([mapper.get(c, c) for c in obj])
        elif isinstance(obj, list):
            return [recursive_replace(i, mapper) for i in obj]
        elif isinstance(obj, dict):
            return {k: recursive_replace(v, mapper) for k, v in obj.items()}
        else:
            return obj

    processed_count = 0
    for idx, fpath in enumerate(all_files):
        try:
            rel_path = os.path.relpath(fpath, src_dir)
            target_path = os.path.join(out_dir, rel_path)
            target_folder = os.path.dirname(target_path)

            if not os.path.exists(target_folder):
                os.makedirs(target_folder)

            if fpath.lower().endswith('.json'):
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    new_data = recursive_replace(data, mapping_dict)
                    
                    with open(target_path, 'w', encoding='utf-8') as f:
                        json.dump(new_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    log_signal(f"⚠️ JSON解析失败 ({os.path.basename(fpath)})，尝试作为纯文本处理。")
                    with open(fpath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    new_content = "".join([mapping_dict.get(c, c) for c in content])
                    with open(target_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
            else:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                new_content = "".join([mapping_dict.get(c, c) for c in content])
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

            processed_count += 1

        except Exception as e:
            log_signal(f"⚠️ 处理失败 {os.path.basename(fpath)}: {e}")

        if idx % 50 == 0:
            prog_signal(50 + int(50 * idx / total_files))

    prog_signal(100)
    mode_str = f"字体限制 ({os.path.basename(limit_font_path)})" if limit_font_path else "全量"
    log_signal(f"✅ 任务完成！ (模式: {mode_str})<br>已处理文件: {processed_count}<br>映射字符数: {len(mapping_dict)}<br>生成的 JSON 可直接用于字体处理。")
    return out_json


def smart_fallback_scan(conf, log_signal, prog_signal):
    primary = conf['primary']
    fallback_dir = conf['fb_dir']
    txt_dir = conf['txt_dir']
    
    if not os.path.exists(primary):
        log_signal("❌ 主字体不存在")
        return None
    if not os.path.exists(fallback_dir):
        log_signal("❌ 补全库目录不存在")
        return None

    log_signal(f"🔍 <b>开始智能缺字分析...</b>")
    prog_signal(5)

    needed_chars = set()
    if os.path.exists(txt_dir):
        files = glob.glob(os.path.join(txt_dir, '**', '*.txt'), recursive=True)
        files += glob.glob(os.path.join(txt_dir, '**', '*.json'), recursive=True)
        total_f = len(files)
        for i, fpath in enumerate(files):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    needed_chars.update(f.read())
            except: pass
            if i % 10 == 0: prog_signal(5 + int(10 * i / total_f))
    
    needed_chars = {c for c in needed_chars if c.isprintable() and not c.isspace()}
    log_signal(f"📝 文本需求字符数: {len(needed_chars)}")

    try:
        font = TTFont(primary)
        cmap = font.getBestCmap()
        existing_chars = set(chr(c) for c in cmap.keys())
        missing_chars = needed_chars - existing_chars
        font.close()
    except Exception as e:
        log_signal(f"❌ 主字体读取错误: {e}")
        return None

    if not missing_chars:
        log_signal("✅ 完美！主字体包含所有所需字符。")
        prog_signal(100)
        return {}

    log_signal(f"⚠️ <b>缺失字符: {len(missing_chars)} 个</b>")
    log_signal(f"🚀 正在扫描所有补全字体，请稍候...")
    prog_signal(20)

    fb_fonts = glob.glob(os.path.join(fallback_dir, "*.ttf")) + glob.glob(os.path.join(fallback_dir, "*.otf"))
    
    font_stats = []
    
    total_fb = len(fb_fonts)
    for idx, fb_path in enumerate(fb_fonts):
        fb_name = os.path.basename(fb_path)
        try:
            fb_font = TTFont(fb_path, fontNumber=0)
            fb_cmap = fb_font.getBestCmap()
            
            covered_in_this = set()
            for char in missing_chars:
                if ord(char) in fb_cmap:
                    covered_in_this.add(char)
            
            if covered_in_this:
                font_stats.append({
                    'name': fb_name,
                    'covered': covered_in_this,
                    'count': len(covered_in_this)
                })
            
            fb_font.close()
        except:
            pass
        
        prog_signal(20 + int(40 * idx / total_fb))

    font_stats.sort(key=lambda x: x['count'], reverse=True)
    
    log_signal(f"📊 <b>字体适配度排名 (共 {len(font_stats)} 个):</b>")
    for i, stats in enumerate(font_stats):
        log_signal(f"   #{i+1} {stats['name']} (覆盖 {stats['count']} 个缺字)")

    log_signal("🚀 正在分配最佳来源...")

    final_map = {}
    unfound_chars = missing_chars.copy()
    
    for stats in font_stats:
        if not unfound_chars: break
        
        actually_contributed = stats['covered'] & unfound_chars
        
        if actually_contributed:
            for char in actually_contributed:
                final_map[char] = stats['name']
            
            unfound_chars -= actually_contributed

    prog_signal(100)
    
    log_signal(f"🏁 <b>分析结束</b>")
    log_signal(f"   ✅ 已解决: {len(final_map)} 个")
    log_signal(f"   ❌ 仍缺失: {len(unfound_chars)} 个")
    
    return final_map
