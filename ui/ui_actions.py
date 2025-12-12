import os
import json
import glob
import traceback
import tempfile
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QTableWidgetItem, QTableWidget, QHeaderView
from PyQt6.QtCore import Qt
from fontTools.ttLib import TTFont
from fontTools import subset
from core.utils import ensure_ttf
from core import font_cache

def read_unified_metrics(main_window):
    src_path = main_window.fix_src.text()
    ref_path = main_window.fix_ref.text()

    if not os.path.exists(src_path) or not os.path.exists(ref_path):
        QMessageBox.warning(main_window, "提示", "请先填入【目标字体】和【参考字体】")
        return

    try:
        src_font = TTFont(src_path)
        ref_font = TTFont(ref_path)

        src_upm = src_font['head'].unitsPerEm
        ref_upm = ref_font['head'].unitsPerEm
        
        ratio = src_upm / ref_upm

        ref_hhea = ref_font['hhea']
        target_asc = int(ref_hhea.ascent * ratio)
        target_desc = int(ref_hhea.descent * ratio)
        target_gap = int(ref_hhea.lineGap * ratio)

        main_window.fix_asc.setText(str(target_asc))
        main_window.fix_desc.setText(str(target_desc))
        main_window.fix_gap.setText(str(target_gap))
        
        main_window.fix_scale_x.setText("1.00") 
        main_window.fix_scale_y.setText("1.00")
        main_window.fix_spacing.setText("0")

        main_window.log("="*40)
        main_window.log("🪄 <b>自动计算完成</b>")
        main_window.log(f"   目标字体 UPM: {src_upm}")
        main_window.log(f"   参考字体 UPM: {ref_upm}")
        main_window.log(f"   计算倍率: {ratio:.4f}x")
        main_window.log("-" * 20)
        main_window.log(f"   原版 Asc: {ref_hhea.ascent} -> 新 Asc: {target_asc}")
        main_window.log(f"   原版 Desc: {ref_hhea.descent} -> 新 Desc: {target_desc}")
        main_window.log("="*40)
        
    except Exception as e:
        QMessageBox.critical(main_window, "错误", f"计算失败: {e}")
        
def do_unified_fix(main_window):
    if not main_window.fix_src.text() or not main_window.fix_out.text():
        QMessageBox.warning(main_window, "提示", "请先填写路径")
        return

    try:
        conf = {
            'src': main_window.fix_src.text(),
            'out_path': main_window.fix_out.text(),
            'scale_x': float(main_window.fix_scale_x.text()),
            'scale_y': float(main_window.fix_scale_y.text()),
            'spacing': int(main_window.fix_spacing.text()),
            'asc': int(main_window.fix_asc.text()),
            'desc': int(main_window.fix_desc.text()),
            'gap': int(main_window.fix_gap.text())
        }
        main_window.run_worker('unified_fix', conf)
        
    except ValueError:
        QMessageBox.warning(main_window, "格式错误", "缩放倍率必须是小数，间距必须是整数。")

def read_font_metrics(main_window):
    path = main_window.met_font_path.text()
    ref = main_window.met_ref_path.text()

    if not os.path.exists(path): return

    try:
        target_font = TTFont(path)
        tgt_upm = target_font['head'].unitsPerEm

        if os.path.exists(ref):
            ref_font = TTFont(ref)
            ref_upm = ref_font['head'].unitsPerEm
            hhea = ref_font['hhea']

            ratio = tgt_upm / ref_upm

            asc = int(hhea.ascent * ratio)
            desc = int(hhea.descent * ratio)
            gap = int(hhea.lineGap * ratio)

            main_window.log(f"📐 <b>智能缩放计算:</b>")
            main_window.log(f"&nbsp;&nbsp;参考UPM: {ref_upm} | 目标UPM: {tgt_upm}")
            main_window.log(f"&nbsp;&nbsp;缩放倍率: {ratio:.2f}")
            main_window.log(f"&nbsp;&nbsp;原始Asc: {hhea.ascent} -> 修正后: {asc}")
        else:
            hhea = target_font['hhea']
            asc = hhea.ascent
            desc = hhea.descent
            gap = hhea.lineGap
            main_window.log(f"⚠️ 未提供参考字体，读取目标原始数值 (UPM: {tgt_upm})")

        main_window.in_ascender.setText(str(asc))
        main_window.in_descender.setText(str(desc))
        main_window.in_linegap.setText(str(gap))

    except Exception as e:
        main_window.log(f"❌ 读取失败: {e}")
        traceback.print_exc()

def apply_font_metrics(main_window):
    path = main_window.met_font_path.text()
    if not os.path.exists(path): main_window.log("❌ 目标字体不存在"); return

    try:
        from core.history_manager import get_history_manager
        history = get_history_manager()
        
        asc = int(main_window.in_ascender.text())
        desc = int(main_window.in_descender.text())
        gap = int(main_window.in_linegap.text())

        font = TTFont(path)

        font['hhea'].ascent = asc
        font['hhea'].descent = desc
        font['hhea'].lineGap = gap

        font['OS/2'].sTypoAscender = asc
        font['OS/2'].sTypoDescender = desc
        font['OS/2'].sTypoLineGap = gap
        font['OS/2'].usWinAscent = asc
        font['OS/2'].usWinDescent = abs(desc)

        removed_bitmap = False
        for tag in ['EBDT', 'EBLC', 'EBSC', 'CBDT', 'CBLC']:
            if tag in font:
                del font[tag]
                removed_bitmap = True

        if removed_bitmap:
            main_window.log("🧹 已清除内嵌点阵表 (防止渲染撕裂)")

        save_path = path.replace(".ttf", "_fix.ttf")
        file_existed = os.path.exists(save_path)
        if file_existed:
            history.record_before_overwrite("应用度量", save_path, f"Asc{asc} Desc{desc}")
        
        font.save(save_path)
        
        if not file_existed and os.path.exists(save_path):
            history.record_new_file("应用度量", save_path, f"Asc{asc} Desc{desc}")
        elif os.path.exists(save_path):
            history.record("应用度量", save_path, f"Asc{asc} Desc{desc}")
        
        update_history_buttons(main_window)
        
        main_window.log(f"✅ <b>修复完成!</b><br>Asc: {asc}, Desc: {desc}, Gap: {gap}<br>已保存: {os.path.basename(save_path)}")
        QMessageBox.information(main_window, "成功", f"字体已保存至:\n{save_path}")

    except Exception as e:
        main_window.log(f"❌ 应用失败: {e}")

def load_json_to_table(main_window):
    f, _ = QFileDialog.getOpenFileName(main_window, "选择映射表", "", "JSON (*.json)")
    if not f: return
    try:
        with open(f, 'r', encoding='utf-8') as f_obj:
            data = json.load(f_obj)

        main_window.map_table.setRowCount(0)
        for k, v in data.items():
            row = main_window.map_table.rowCount()
            main_window.map_table.insertRow(row)
            main_window.map_table.setItem(row, 0, QTableWidgetItem(k))
            main_window.map_table.setItem(row, 1, QTableWidgetItem(v))
            main_window.map_table.setItem(row, 2, QTableWidgetItem(""))

        main_window.log(f"✅ 已加载 {len(data)} 条映射记录。")
    except Exception as e:
        main_window.log(f"❌ 加载失败: {e}")

def save_table_to_json(main_window):
    data = {}
    for row in range(main_window.map_table.rowCount()):
        k_item = main_window.map_table.item(row, 0)
        v_item = main_window.map_table.item(row, 1)
        if k_item and v_item:
            data[k_item.text()] = v_item.text()

    f, _ = QFileDialog.getSaveFileName(main_window, "保存映射表", "edited_map.json", "JSON (*.json)")
    if f:
        try:
            with open(f, 'w', encoding='utf-8') as f_obj:
                json.dump(data, f_obj, ensure_ascii=False, indent=2)
            main_window.log(f"💾 已保存 {len(data)} 条记录至 {f}")
        except Exception as e:
            main_window.log(f"❌ 保存失败: {e}")

def add_mapping_row(main_window):
    k = main_window.in_new_key.text()
    v = main_window.in_new_val.text()
    if not k or not v: return

    row = main_window.map_table.rowCount()
    main_window.map_table.insertRow(row)
    main_window.map_table.setItem(row, 0, QTableWidgetItem(k))
    main_window.map_table.setItem(row, 1, QTableWidgetItem(v))
    main_window.in_new_key.clear()
    main_window.in_new_val.clear()

def remove_mapping_row(main_window):
    rows = sorted(set(index.row() for index in main_window.map_table.selectedIndexes()), reverse=True)
    for row in rows:
        main_window.map_table.removeRow(row)

def do_subset(main_window):
    conf = {
        'font_path': main_window.sub_font.text(),
        'txt_dir': main_window.sub_txt.text(),
        'json_path': main_window.sub_json.text(),
        'out_path': main_window.sub_out.text(),
        'exts': ".txt;.json"
    }
    main_window.run_worker('subset', conf)

def do_coverage_analysis(main_window):
    font_path = main_window.cov_font.text()
    if not os.path.exists(font_path):
        QMessageBox.warning(main_window, "路径无效", "请先指定字体文件！")
        return

    try:
        cmap = font_cache.get_cmap(font_path)
        font_chars = set(cmap.keys())

        charsets = {
            "ASCII (基础拉丁)": (0x0020, 0x007E),
            "日文平假名": (0x3040, 0x309F),
            "日文片假名": (0x30A0, 0x30FF),
            "CJK 基本 (常用汉字)": (0x4E00, 0x9FFF),
            "全角ASCII": (0xFF01, 0xFF5E),
            "CJK 标点符号": (0x3000, 0x303F),
        }

        results = []
        results.append(f"📂 字体: {os.path.basename(font_path)}")
        results.append(f"📊 总字符数: {len(font_chars)}\n")
        results.append("=" * 50)

        for name, (start, end) in charsets.items():
            total = end - start + 1
            covered = sum(1 for c in range(start, end + 1) if c in font_chars)
            percent = (covered / total) * 100

            bar_len = 20
            filled = int(bar_len * percent / 100)
            bar = "█" * filled + "░" * (bar_len - filled)

            results.append(f"{name}")
            results.append(f"  [{bar}] {percent:.1f}% ({covered}/{total})")
            results.append("")

        main_window.cov_result.setPlainText("\n".join(results))
        main_window.log(f"📊 覆盖率分析完成: {os.path.basename(font_path)}")

    except Exception as e:
        main_window.log(f"❌ 分析失败: {e}")
        QMessageBox.critical(main_window, "分析失败", f"无法分析字体: {e}")

def do_merge_fonts(main_window):
    base_path = main_window.merge_base.text()
    add_path = main_window.merge_add.text()
    out_path = main_window.merge_out.text()

    if not os.path.exists(base_path):
        QMessageBox.warning(main_window, "路径无效", "基础字体不存在！")
        return
    if not os.path.exists(add_path):
        QMessageBox.warning(main_window, "路径无效", "来源字体不存在！")
        return

    try:
        from core.history_manager import get_history_manager
        history = get_history_manager()
        
        main_window.log("🔗 <b>开始合并字体...</b>")

        base_font = TTFont(base_path)
        ensure_ttf(base_font, main_window.log, "基础字体")
        base_upm = base_font['head'].unitsPerEm
        
        fd_base, temp_base_path = tempfile.mkstemp(suffix='.ttf')
        os.close(fd_base)
        base_font.save(temp_base_path)
        base_font.close()
        
        add_font = TTFont(add_path)
        ensure_ttf(add_font, main_window.log, "来源字体")
        add_upm = add_font['head'].unitsPerEm
        
        fd_add, temp_add_path = tempfile.mkstemp(suffix='.ttf')
        os.close(fd_add)
        add_font.save(temp_add_path)
        add_font.close()
        
        base_path = temp_base_path
        add_path = temp_add_path

        main_window.log(f"   基础 UPM: {base_upm}, 来源 UPM: {add_upm}")
        
        if base_upm != add_upm:
            main_window.log(f"   ⚠️ UPM 不一致，正在缩放来源字体...")
            temp_fd, temp_add_path = tempfile.mkstemp(suffix='.ttf')
            os.close(temp_fd)

            add_font = TTFont(add_path)
            scale = base_upm / add_upm 
            add_font['head'].unitsPerEm = base_upm
            
            if 'hhea' in add_font:
                hhea = add_font['hhea']
                hhea.ascent = int(hhea.ascent * scale)
                hhea.descent = int(hhea.descent * scale)
                hhea.lineGap = int(hhea.lineGap * scale)

            if 'OS/2' in add_font:
                os2 = add_font['OS/2']
                if hasattr(os2, 'sTypoAscender'): os2.sTypoAscender = int(os2.sTypoAscender * scale)
                if hasattr(os2, 'sTypoDescender'): os2.sTypoDescender = int(os2.sTypoDescender * scale)
                if hasattr(os2, 'sTypoLineGap'): os2.sTypoLineGap = int(os2.sTypoLineGap * scale)
                if hasattr(os2, 'usWinAscent'): os2.usWinAscent = int(os2.usWinAscent * scale)
                if hasattr(os2, 'usWinDescent'): os2.usWinDescent = int(os2.usWinDescent * scale)
                if hasattr(os2, 'sxHeight') and os2.sxHeight: os2.sxHeight = int(os2.sxHeight * scale)
                if hasattr(os2, 'sCapHeight') and os2.sCapHeight: os2.sCapHeight = int(os2.sCapHeight * scale)

            hmtx = add_font['hmtx']
            for name in hmtx.metrics:
                w, lsb = hmtx.metrics[name]
                hmtx.metrics[name] = (int(w * scale), int(lsb * scale))

            if 'glyf' in add_font:
                from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
                glyf = add_font['glyf']
                for glyphName in glyf.keys():
                    glyph = glyf[glyphName]
                    if glyph.numberOfContours > 0:
                        if hasattr(glyph, 'coordinates') and glyph.coordinates:
                            coords = glyph.coordinates
                            new_coords = GlyphCoordinates([(int(x * scale), int(y * scale)) for x, y in coords])
                            glyph.coordinates = new_coords
                    elif glyph.numberOfContours == -1:
                        if hasattr(glyph, 'components'):
                            for comp in glyph.components:
                                comp.x = int(comp.x * scale)
                                comp.y = int(comp.y * scale)

            add_font.save(temp_add_path)
            add_font.close()
            main_window.log("   ✓ UPM 转换完成")

        filter_text = main_window.merge_filter.text()
        if filter_text:
            main_window.log(f"✂️ <b>正在提取指定字符...</b>")
            main_window.log(f"   目标字符: {filter_text}")
            try:
                tmp_font = TTFont(temp_add_path)
                options = subset.Options()
                options.name_IDs = []
                options.drop_tables = [] 
                options.recalc_bounds = True
                options.notdef_glyph = False
                
                subsetter = subset.Subsetter(options=options)
                subsetter.populate(text=filter_text)
                subsetter.subset(tmp_font)
                
                fd_sub, subset_path = tempfile.mkstemp(suffix='.ttf')
                os.close(fd_sub)
                tmp_font.save(subset_path)
                tmp_font.close()
                
                if temp_add_path != add_path and os.path.exists(temp_add_path):
                    os.remove(temp_add_path)
                    
                temp_add_path = subset_path
                main_window.log("   ✓ 已生成仅包含指定字符的子集")
            except Exception as e:
                main_window.log(f"   ⚠️ 提取字符失败: {e}，将尝试合并全部...")

        main_window.log("   正在执行合并...")

        if os.path.exists(out_path):
            history.record_before_overwrite("合并字体", out_path, "覆盖")

        from fontTools.merge import Merger
        merger = Merger()
        merged_font = merger.merge([base_path, temp_add_path])
        merged_font.save(out_path)
        merged_font.close()

        if temp_add_path != add_path and os.path.exists(temp_add_path):
            os.remove(temp_add_path)

        if not os.path.exists(out_path):
            return
        history.record("合并字体", out_path, "合并完成")
        update_history_buttons(main_window)
        
        main_window.log(f"✅ <b>合并完成!</b>")
        main_window.log(f"   输出: {out_path}")
        QMessageBox.information(main_window, "合并成功", f"合并完成！\n输出: {out_path}")

    except FileNotFoundError:
        main_window.log("❌ 缺少组件，请确保安装了 fonttools")
    except Exception as e:
        main_window.log(f"❌ 合并失败: {e}")
        traceback.print_exc()
        QMessageBox.critical(main_window, "合并失败", f"合并出错: {e}")

def do_run_pipeline(main_window):
    steps = []
    if main_window.pipe_step1.isChecked(): steps.append(('map', '动态映射'))
    if main_window.pipe_step2.isChecked(): steps.append(('font', '字体生成'))
    if main_window.pipe_step3.isChecked(): steps.append(('subset', '字体精简'))
    if main_window.pipe_step4.isChecked(): steps.append(('checkup', '体检'))

    if not steps:
        QMessageBox.warning(main_window, "未选择步骤", "请至少勾选一个执行步骤！")
        return

    main_window.log("🚀 <b>开始执行工作流...</b>")
    main_window.pipe_status.setText(f"⏳ 准备执行 {len(steps)} 个步骤...")

    main_window._pipeline_steps = steps
    main_window._pipeline_idx = 0
    main_window._run_next_pipeline_step()

def _run_next_pipeline_step(main_window):
    from PyQt6.QtCore import QTimer
    if main_window._pipeline_idx >= len(main_window._pipeline_steps):
        main_window.pipe_status.setText("✅ 工作流全部完成！")
        main_window.log("✅ <b>工作流执行完毕！</b>")
        QMessageBox.information(main_window, "完成", "工作流已全部执行完毕！")
        return

    step_type, step_name = main_window._pipeline_steps[main_window._pipeline_idx]
    main_window.pipe_status.setText(f"⏳ [{main_window._pipeline_idx + 1}/{len(main_window._pipeline_steps)}] 正在执行: {step_name}...")
    main_window.log(f"📌 步骤 {main_window._pipeline_idx + 1}: {step_name}")

    try:
        if step_type == 'map':
            main_window.do_gen_map()
        elif step_type == 'font':
            main_window.do_gen_font()
        elif step_type == 'subset':
            main_window.do_subset()
        elif step_type == 'checkup':
            main_window.do_checkup('subset')
            main_window._pipeline_idx += 1
            _run_next_pipeline_step(main_window)
            return

        if hasattr(main_window, 'worker') and main_window.worker:
            main_window.worker.done.disconnect()
            main_window.worker.done.connect(main_window._on_pipeline_step_done)
    except Exception as e:
        main_window.log(f"❌ 步骤失败: {e}")
        main_window.pipe_status.setText(f"❌ 失败于步骤: {step_name}")

def _on_pipeline_step_done(main_window, result):
    from PyQt6.QtCore import QTimer
    main_window._pipeline_idx += 1
    QTimer.singleShot(500, lambda: _run_next_pipeline_step(main_window))

def do_read_font_info(main_window):
    from PyQt6.QtCore import Qt
    font_path = main_window.info_font.text()
    if not os.path.exists(font_path):
        QMessageBox.warning(main_window, "文件不存在", "请先选择有效的字体文件")
        return

    try:
        font = TTFont(font_path)
        name_table = font['name']
        
        name_map = {
            0: "Copyright (版权)", 1: "Family Name (族名)", 2: "Subfamily (子族)",
            3: "Unique ID (唯一ID)", 4: "Full Name (完整名)", 5: "Version (版本)",
            6: "PostScript Name", 7: "Trademark (商标)", 8: "Manufacturer (厂商)",
            9: "Designer (设计师)", 10: "Description (描述)", 11: "Vendor URL (厂商链接)",
            12: "Designer URL (设计师链接)", 13: "License (许可证)", 14: "License URL",
            16: "Typographic Family", 17: "Typographic Subfamily"
        }

        main_window.info_table.setRowCount(0)
        
        records = []
        for record in name_table.names:
            if record.platformID == 3:
                records.append(record)
        
        records.sort(key=lambda x: x.nameID)

        main_window.info_table.setRowCount(len(records))
        
        for row, record in enumerate(records):
            id_item = QTableWidgetItem(str(record.nameID))
            id_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            desc = name_map.get(record.nameID, f"Unknown ID {record.nameID}")
            if record.langID == 1041: desc += " [🇯🇵 JP]"
            elif record.langID == 2052: desc += " [🇨🇳 CN]"
            elif record.langID == 1033: desc += " [🇺🇸 EN]"
            
            name_item = QTableWidgetItem(desc)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            
            try:
                value = record.toUnicode()
            except:
                value = "<无法解码的数据>"
            
            val_item = QTableWidgetItem(value)
            
            main_window.info_table.setItem(row, 0, id_item)
            main_window.info_table.setItem(row, 1, name_item)
            main_window.info_table.setItem(row, 2, val_item)

        main_window.log(f"📖 成功读取 {len(records)} 条元数据。")

    except Exception as e:
        QMessageBox.critical(main_window, "读取失败", f"无法读取字体: {e}")
        traceback.print_exc()

def do_save_font_info(main_window):
    font_path = main_window.info_font.text()
    if not os.path.exists(font_path): return

    try:
        from core.history_manager import get_history_manager
        history = get_history_manager()
        
        font = TTFont(font_path)
        name_table = font['name']
        
        updated_count = 0
        
        for row in range(main_window.info_table.rowCount()):
            id_item = main_window.info_table.item(row, 0)
            val_item = main_window.info_table.item(row, 2)
            
            if not id_item or not val_item: continue
            
            nid = int(id_item.text())
            new_string = val_item.text()
            
            for record in name_table.names:
                if record.platformID == 3 and record.nameID == nid:
                    try:
                        old_str = record.toUnicode()
                        if old_str != new_string:
                            record.string = new_string.encode('utf-16-be')
                            updated_count += 1
                    except:
                        pass

        out_path = font_path.replace('.ttf', '_mod.ttf').replace('.otf', '_mod.otf')
        file_existed = os.path.exists(out_path)
        
        if file_existed:
            history.record_before_overwrite("修改元数据", out_path, f"更新{updated_count}条")
        
        font.save(out_path)
        
        if not file_existed and os.path.exists(out_path):
            history.record_new_file("修改元数据", out_path, f"更新{updated_count}条")
        elif os.path.exists(out_path):
            history.record("修改元数据", out_path, f"更新{updated_count}条")
        
        update_history_buttons(main_window)
        
        main_window.log(f"💾 已保存修改！更新了相关记录。")
        main_window.log(f"   输出文件: {out_path}")
        QMessageBox.information(main_window, "成功", f"字体元数据已更新！\n保存在: {os.path.basename(out_path)}")

    except Exception as e:
        main_window.log(f"❌ 保存失败: {e}")
        QMessageBox.critical(main_window, "保存失败", str(e))

def do_compare_fonts(main_window):
    path1 = main_window.cmp_font1.text()
    path2 = main_window.cmp_font2.text()

    if not os.path.exists(path1) or not os.path.exists(path2):
        QMessageBox.warning(main_window, "文件不存在", "请确保两个字体文件都存在")
        return

    try:
        chars1 = set(font_cache.get_cmap(path1).keys())
        chars2 = set(font_cache.get_cmap(path2).keys())

        common = chars1 & chars2
        only_a = chars1 - chars2
        only_b = chars2 - chars1

        lines = []
        lines.append(f"📊 字符集对比结果")
        lines.append(f"{'=' * 40}")
        lines.append(f"字体 A: {os.path.basename(path1)} ({len(chars1)} 字符)")
        lines.append(f"字体 B: {os.path.basename(path2)} ({len(chars2)} 字符)")
        lines.append(f"{'=' * 40}")
        lines.append(f"✅ 共有字符: {len(common)}")
        lines.append(f"🅰️ A 独有: {len(only_a)}")
        lines.append(f"🅱️ B 独有: {len(only_b)}")
        lines.append("")

        if only_a:
            lines.append("─── A 独有的字符 (前100个) ───")
            sample_a = sorted(only_a)[:100]
            lines.append(''.join(chr(c) for c in sample_a if c < 0x10000))
            lines.append("")

        if only_b:
            lines.append("─── B 独有的字符 (前100个) ───")
            sample_b = sorted(only_b)[:100]
            lines.append(''.join(chr(c) for c in sample_b if c < 0x10000))

        main_window.cmp_result.setPlainText("\n".join(lines))
        main_window._compare_result = {'only_a': only_a, 'only_b': only_b, 'common': common}

        main_window.log(f"🔍 对比完成: A独有 {len(only_a)}, B独有 {len(only_b)}, 共有 {len(common)}")

    except Exception as e:
        QMessageBox.critical(main_window, "对比失败", f"无法对比字体: {e}")

def do_export_diff(main_window):
    if not main_window._compare_result:
        QMessageBox.warning(main_window, "无数据", "请先执行对比")
        return

    path, _ = QFileDialog.getSaveFileName(main_window, "保存差异报告", "diff_report.txt", "文本文件 (*.txt)")
    if not path:
        return

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("字体字符集对比报告\n")
            f.write("=" * 50 + "\n\n")

            only_a = main_window._compare_result.get('only_a', set())
            only_b = main_window._compare_result.get('only_b', set())

            f.write(f"A 独有字符 ({len(only_a)} 个):\n")
            f.write(''.join(chr(c) for c in sorted(only_a) if c < 0x10000))
            f.write("\n\n")

            f.write(f"B 独有字符 ({len(only_b)} 个):\n")
            f.write(''.join(chr(c) for c in sorted(only_b) if c < 0x10000))

        main_window.log(f"📥 已导出差异报告: {path}")
        QMessageBox.information(main_window, "导出成功", f"已保存到:\n{path}")

    except Exception as e:
        QMessageBox.critical(main_window, "导出失败", str(e))

def do_checkup(main_window, source):
    if source == 'map':
        txt_dir = main_window.map_src.text()
        exts = main_window.map_ext.text().split(';')
        font_path = main_window.in_src.text()
        json_path = main_window.in_json.text()
    else:
        txt_dir = main_window.sub_txt.text()
        exts = ".txt;.json".split(';')
        font_path = main_window.sub_font.text()
        json_path = main_window.sub_json.text()

    has_txt_dir = os.path.exists(txt_dir)
    has_json = os.path.exists(json_path)

    if not has_txt_dir and not has_json:
        QMessageBox.warning(main_window, "路径无效", "文本目录和映射表都不存在！\n请至少提供其中一个。")
        return
    if not os.path.exists(font_path):
        QMessageBox.warning(main_window, "路径无效", "请先指定字体文件！")
        return

    main_window.log("🩺 <b>开始体检...</b>")

    all_chars = set()

    if has_txt_dir:
        all_files = []
        for ext in exts:
            ext = ext.strip()
            if not ext: continue
            if not ext.startswith('.'): ext = '.' + ext
            all_files.extend(glob.glob(os.path.join(txt_dir, '**', f'*{ext}'), recursive=True))

        main_window.log(f"   扫描文本目录: {len(all_files)} 个文件")

        for fpath in all_files:
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    all_chars.update(f.read())
            except:
                pass
    else:
        main_window.log("   ⚠️ 文本目录不存在，跳过")

    if has_json:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_chars.update(data.keys())
                all_chars.update(data.values())
                main_window.log(f"   读取映射表: {len(data)} 条映射")
        except Exception as e:
            main_window.log(f"   ⚠️ 映射表读取失败: {e}")
    else:
        main_window.log("   ⚠️ 映射表不存在，跳过")

    try:
        cmap = font_cache.get_cmap(font_path)
        font_chars = set(chr(c) for c in cmap.keys())
        main_window.log(f"   字体包含 {len(font_chars)} 个字符")
    except Exception as e:
        QMessageBox.critical(main_window, "字体读取失败", f"无法读取字体: {e}")
        return

    text_chars = {c for c in all_chars if c.isprintable() and not c.isspace()}
    missing = text_chars - font_chars

    main_window.log(f"   需要检查的可见字符: {len(text_chars)}")
    main_window.log(f"   缺失字符: <b style='color:#F44336'>{len(missing)}</b>")

    if not missing:
        QMessageBox.information(main_window, "✅ 体检通过",
                                f"恭喜！文本和映射表中的 {len(text_chars)} 个可见字符在字体中全部存在。")
        main_window.log("✅ <b>体检通过！所有字符均存在于字体中。</b>")
    else:
        missing_sorted = sorted(missing, key=lambda x: ord(x))
        display_list = missing_sorted[:50]
        display_str = '】【'.join(display_list)
        extra_msg = f"\n\n... 以及其他 {len(missing_sorted) - 50} 个字符" if len(missing_sorted) > 50 else ""

        msg = f"警告：你的文本中包含以下 {len(missing_sorted)} 个字，但字体文件中不存在：\n\n【{display_str}】{extra_msg}"

        dialog = QMessageBox(main_window)
        dialog.setWindowTitle("⚠️ 发现缺失字符")
        dialog.setText(msg)
        dialog.setIcon(QMessageBox.Icon.Warning)

        btn_ok = dialog.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
        btn_export = dialog.addButton("📄 导出列表", QMessageBox.ButtonRole.ActionRole)

        dialog.exec()

        if dialog.clickedButton() == btn_export:
            save_path, _ = QFileDialog.getSaveFileName(main_window, "保存缺失字符列表", "missing_chars.txt", "Text (*.txt)")
            if save_path:
                try:
                    with open(save_path, 'w', encoding='utf-8') as f:
                        f.write(f"# 缺失字符列表 (共 {len(missing_sorted)} 个)\n")
                        f.write(f"# 字体: {font_path}\n\n")
                        for char in missing_sorted:
                            f.write(f"{char}\tU+{ord(char):04X}\n")
                    main_window.log(f"💾 已导出缺失字符列表: {save_path}")
                    QMessageBox.information(main_window, "导出成功", f"已保存 {len(missing_sorted)} 个缺失字符到：\n{save_path}")
                except Exception as e:
                    main_window.log(f"❌ 导出失败: {e}")

        log_display = ''.join(missing_sorted[:100])
        main_window.log(f"⚠️ 缺失字符预览: {log_display}")

def do_smart_fallback_scan(main_window):
    conf = {
        'primary': main_window.sf_primary.text(),
        'txt_dir': main_window.sf_txt.text(),
        'fb_dir': main_window.sf_lib.text()
    }
    main_window.sf_table.setRowCount(0)
    if hasattr(main_window, 'worker') and main_window.worker.isRunning():
        QMessageBox.warning(main_window, "忙碌", "后台任务正在运行中...")
        return
        
    main_window.run_worker('smart_fallback', conf)
    main_window.worker.done.disconnect()
    main_window.worker.done.connect(main_window.on_smart_scan_done)

def on_smart_scan_done(main_window, result):
    if not isinstance(result, dict): return
    
    main_window.sf_table.setRowCount(0)
    main_window.sf_table.setSortingEnabled(False)
    
    for char, font_name in result.items():
        row = main_window.sf_table.rowCount()
        main_window.sf_table.insertRow(row)
        main_window.sf_table.setItem(row, 0, QTableWidgetItem(char))
        main_window.sf_table.setItem(row, 1, QTableWidgetItem(f"U+{ord(char):04X}"))
        main_window.sf_table.setItem(row, 2, QTableWidgetItem(font_name))
        
    main_window.sf_table.setSortingEnabled(True)
    main_window.lbl_status.setText(f"分析完成，找到 {len(result)} 个补全建议")
    main_window.set_ui_busy(False)
    
    if len(result) > 0:
        QMessageBox.information(main_window, "完成", f"分析结束！\n成功为 {len(result)} 个缺失字符找到了来源字体。")

def export_smart_result(main_window):
    if main_window.sf_table.rowCount() == 0:
        QMessageBox.warning(main_window, "无数据", "表格为空，请先运行分析。")
        return
        
    path, _ = QFileDialog.getSaveFileName(main_window, "保存清单", "fallback_plan.json", "JSON (*.json)")
    if path:
        data = {}
        for row in range(main_window.sf_table.rowCount()):
            char = main_window.sf_table.item(row, 0).text()
            font = main_window.sf_table.item(row, 2).text()
            if font not in data: data[font] = ""
            data[font] += char
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            main_window.log(f"💾 补全清单已保存: {path}")
            main_window.log("💡 您可以根据这个清单，使用【字体合并】功能进行定向补全。")
        except Exception as e:
            main_window.log(f"❌ 保存失败: {e}")

def do_gen_woff2(main_window):
    src = main_window.woff2_src.text()
    if not os.path.exists(src):
        QMessageBox.warning(main_window, "错误", "请先选择字体文件")
        return
    
    conf = { 'src': src, 'out_path': main_window.woff2_out.text() }
    main_window.run_worker('woff2', conf)

def do_cleanup(main_window):
    src = main_window.clean_src.text()
    if not os.path.exists(src):
        QMessageBox.warning(main_window, "错误", "请先选择字体文件")
        return
    
    tables = []
    if main_window.chk_gsub.isChecked(): tables.append('GSUB')
    if main_window.chk_gpos.isChecked(): tables.append('GPOS')
    if main_window.chk_hdmx.isChecked(): tables.append('hdmx')
    if main_window.chk_vdmx.isChecked(): tables.append('VDMX')
    if main_window.chk_hint.isChecked(): tables.append('HINTING')
    if main_window.chk_name.isChecked(): tables.append('NAME_DETAILED')
    
    if not tables:
        QMessageBox.warning(main_window, "提示", "请至少选择一项要清理的内容")
        return

    conf = {
        'src': src,
        'out_path': main_window.clean_out.text(),
        'tables': tables
    }
    main_window.run_worker('cleanup', conf)

def do_gen_bmfont(main_window):
    font_path = main_window.bm_font.text()
    txt_path = main_window.bm_char_txt.text()
    
    if not os.path.exists(font_path):
        QMessageBox.warning(main_window, "错误", "字体文件不存在")
        return
    if not os.path.exists(txt_path):
        QMessageBox.warning(main_window, "错误", "字符来源文件或目录不存在")
        return

    try:
        content = ""
        if os.path.isdir(txt_path):
            exts = ('.txt', '.json', '.c', '.cpp', '.h', '.hpp', '.py', '.md', '.ini')
            for root, dirs, files in os.walk(txt_path):
                for file in files:
                    if file.lower().endswith(exts):
                        try:
                            with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                                content += f.read()
                        except: pass
        else:
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        
        chars = sorted(list(set([c for c in content if c >= ' '])))
        
        if not chars:
            QMessageBox.warning(main_window, "错误", "未能找到有效可显示字符")
            return
            
        conf = {
            'font_path': font_path,
            'chars': chars,
            'tex_size': int(main_window.bm_tex_size.currentText()),
            'font_size': int(main_window.bm_size.text()),
            'out_fnt': main_window.bm_out.text()
        }
        main_window.run_worker('bmfont', conf)
        
    except Exception as e:
        QMessageBox.critical(main_window, "错误", f"读取字符文件失败: {e}")

def do_gen_font(main_window):
    mode_idx = main_window.combo_mode.currentIndex()
    if mode_idx == 0:
        QMessageBox.warning(main_window, "未选择模式", "请先在下拉菜单中选择一个处理模式！")
        return

    output_dir = ""
    if hasattr(main_window, 'in_output_dir') and main_window.in_output_dir.text().strip():
        output_dir = main_window.in_output_dir.text().strip()

    conf = {
        'src': main_window.in_src.text(),
        'fallback': main_window.in_fallback.text(),
        'json': main_window.in_json.text(),
        'file_name': main_window.in_file_name.text(),
        'internal_name': main_window.in_font_name.text(),
        'mode': mode_idx,
        'output_dir': output_dir
    }
    main_window.run_worker('font', conf)

def do_gen_pic(main_window):
    conf = {
        'font': main_window.pic_font.text(), 'folder': main_window.pic_folder.text(), 'format': main_window.pic_fmt.text(),
        'fsize': int(main_window.pic_fs.text()), 'count': int(main_window.pic_cnt.text()),
        'cw': int(main_window.pic_cw.text()), 'ch': int(main_window.pic_ch.text()),
        'iw': int(main_window.pic_iw.text()), 'ih': int(main_window.pic_ih.text()),
        'img_w': int(main_window.pic_imw.text()), 'img_h': int(main_window.pic_imh.text()),
        'ix': int(main_window.pic_ix.text()), 'iy': int(main_window.pic_iy.text())
    }
    main_window.run_worker('pic', conf)

def do_gen_tga(main_window):
    conf = {
        'font': main_window.tga_font.text(), 'folder': 'tga_output', 'dat': main_window.tga_dat.text(),
        'eng_name': main_window.tga_eng_n.text(), 'eng_path': main_window.tga_eng_p.text(),
        'fsize': int(main_window.tga_fs.text()),
        'cw': int(main_window.tga_cw.text()), 'ch': int(main_window.tga_ch.text()),
        'iw': int(main_window.tga_iw.text()), 'ih': int(main_window.tga_ih.text()),
        'img_w': int(main_window.tga_w.text()), 'img_h': int(main_window.tga_h.text())
    }
    main_window.run_worker('tga', conf)

def do_gen_bmp(main_window):
    sz = int(main_window.bmp_sz.text())
    conf = {
        'font': main_window.bmp_font.text(), 'folder': 'bmp_output',
        'fsize': int(main_window.bmp_fs.text()), 'cw': sz, 'ch': sz,
        'count': int(main_window.bmp_cnt.text()), 'img_w': int(main_window.bmp_w.text()),
        'scale': float(main_window.bmp_scale.text()), 'depth': int(main_window.bmp_depth.text())
    }
    main_window.run_worker('bmp', conf)

def do_gen_imgfont(main_window):
    mode = main_window.imgfont_mode.currentIndex()
    if mode == 0:
        do_gen_pic(main_window)
    elif mode == 1:
        do_gen_tga(main_window)
    elif mode == 2:
        do_gen_bmp(main_window)
    elif mode == 3:
        do_gen_bmfont(main_window)

def do_gen_map(main_window):
    conf = {
        'src_dir': main_window.map_src.text(),
        'out_dir': main_window.map_out.text(),
        'out_json': main_window.map_json.text(),
        'exts': main_window.map_ext.text(),
        'limit_font': getattr(main_window, 'map_limit_font', None).text() if hasattr(main_window, 'map_limit_font') else ""
    }
    main_window.run_worker('map', conf)

def do_preview_mapping(main_window):
    json_path = main_window.in_json.text()
    txt_dir = main_window.map_src.text()

    mapping = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
        except:
            pass

    if not mapping:
        QMessageBox.warning(main_window, "无法预览", "请先指定有效的映射表JSON文件！")
        return

    sample_text = ""
    sample_file = ""
    if os.path.exists(txt_dir):
        exts = main_window.map_ext.text().split(';')
        for ext in exts:
            ext = ext.strip()
            if not ext: continue
            if not ext.startswith('.'): ext = '.' + ext
            files = glob.glob(os.path.join(txt_dir, '**', f'*{ext}'), recursive=True)
            if files:
                sample_file = files[0]
                try:
                    with open(sample_file, 'r', encoding='utf-8') as f:
                        sample_text = f.read()[:2000]
                    break
                except:
                    continue

    if not sample_text:
        sample_text = "这是一个测试文本。\n它包含了一些需要映射的汉字。\n请确保文本目录中有可读取的文件。"

    replaced_text = list(sample_text)
    replaced_count = 0
    for i, char in enumerate(replaced_text):
        if char in mapping:
            replaced_text[i] = mapping[char]
            replaced_count += 1
    replaced_text = ''.join(replaced_text)

    dialog = QDialog(main_window)
    dialog.setWindowTitle("👁️ 映射预览")
    dialog.setMinimumSize(700, 500)

    layout = QVBoxLayout(dialog)

    info = QLabel(f"📄 示例文件: {os.path.basename(sample_file) if sample_file else '内置示例'}\n"
                  f"🔄 映射表: {len(mapping)} 条 | 替换字符: {replaced_count} 个")
    info.setStyleSheet("font-weight: bold; padding: 10px;")
    layout.addWidget(info)

    compare_layout = QHBoxLayout()

    left_box = QVBoxLayout()
    left_lbl = QLabel("📝 替换前 (原文)")
    left_lbl.setStyleSheet("font-weight: bold;")
    left_box.addWidget(left_lbl)
    left_text = QTextEdit()
    left_text.setPlainText(sample_text)
    left_text.setReadOnly(True)
    left_box.addWidget(left_text)
    compare_layout.addLayout(left_box)

    right_box = QVBoxLayout()
    right_lbl = QLabel("✨ 替换后 (应用映射)")
    right_lbl.setStyleSheet("font-weight: bold;")
    right_box.addWidget(right_lbl)
    right_text = QTextEdit()
    right_text.setPlainText(replaced_text)
    right_text.setReadOnly(True)
    right_box.addWidget(right_text)
    compare_layout.addLayout(right_box)

    layout.addLayout(compare_layout)

    btn_close = QPushButton("关闭")
    btn_close.clicked.connect(dialog.close)
    layout.addWidget(btn_close)

    dialog.exec()

def do_convert_format(main_window):
    src_path = main_window.conv_src.text()
    out_path = main_window.conv_out.text()
    
    if not os.path.exists(src_path):
        QMessageBox.warning(main_window, "文件不存在", "请选择有效的字体文件")
        return
    
    src_ext = os.path.splitext(src_path)[1].lower()
    out_ext = os.path.splitext(out_path)[1].lower()
    
    if src_ext not in ['.ttf', '.otf'] or out_ext not in ['.ttf', '.otf']:
        QMessageBox.warning(main_window, "格式错误", "仅支持 TTF 和 OTF 格式互转")
        return
    
    try:
        from core.history_manager import get_history_manager
        history = get_history_manager()
        
        main_window.log("🔄 <b>开始格式转换...</b>")
        main_window.log(f"   源文件: {os.path.basename(src_path)} ({src_ext.upper()})")
        main_window.log(f"   目标: {os.path.basename(out_path)} ({out_ext.upper()})")
        
        font = TTFont(src_path)
        
        if src_ext == '.otf' and out_ext == '.ttf':
            if 'CFF ' in font:
                main_window.log("   ⚠️ CFF 轮廓字体，正在转换为 TrueType 轮廓...")
                try:
                    from fontTools.pens.cu2quPen import Cu2QuPen
                    from fontTools.pens.ttGlyphPen import TTGlyphPen
                    from fontTools.ttLib.tables._g_l_y_f import Glyph
                    from fontTools.ttLib.tables import _g_l_y_f
                    
                    glyph_order = font.getGlyphOrder()
                    glyph_set = font.getGlyphSet()
                    
                    glyphs = {}
                    widths = {}
                    failed_glyphs = []
                    
                    max_err = 1.0
                    
                    for glyph_name in glyph_order:
                        try:
                            tt_pen = TTGlyphPen(None)
                            cu2qu_pen = Cu2QuPen(tt_pen, max_err, reverse_direction=True)
                            glyph_set[glyph_name].draw(cu2qu_pen)
                            glyphs[glyph_name] = tt_pen.glyph()
                            widths[glyph_name] = glyph_set[glyph_name].width
                        except Exception as glyph_err:
                            failed_glyphs.append(glyph_name)
                            glyphs[glyph_name] = Glyph()
                            widths[glyph_name] = glyph_set[glyph_name].width if glyph_name in glyph_set else 0
                    
                    if failed_glyphs:
                        main_window.log(f"   ⚠️ {len(failed_glyphs)} 个字形转换失败: {', '.join(failed_glyphs[:5])}{'...' if len(failed_glyphs) > 5 else ''}")
                    
                    del font['CFF ']
                    if 'CFF2' in font:
                        del font['CFF2']
                    
                    glyf_table = _g_l_y_f.table__g_l_y_f()
                    glyf_table.glyphs = glyphs
                    font['glyf'] = glyf_table
                    
                    from fontTools.ttLib.tables import _l_o_c_a
                    font['loca'] = _l_o_c_a.table__l_o_c_a()
                    
                    font['maxp'].tableTag = 'maxp'
                    font['maxp'].version = 0x00010000
                    
                    font['head'].glyphDataFormat = 0
                    
                    main_window.log(f"   ✓ 轮廓转换完成 ({len(glyph_order) - len(failed_glyphs)}/{len(glyph_order)} 成功)")
                    
                except ImportError:
                    main_window.log("   ❌ 缺少 cu2qu 库，请运行: pip install cu2qu")
                    QMessageBox.warning(main_window, "缺少依赖", "请先安装 cu2qu 库：\npip install cu2qu")
                    font.close()
                    return
                except Exception as conv_err:
                    main_window.log(f"   ❌ 轮廓转换失败: {conv_err}")
                    traceback.print_exc()
                    QMessageBox.critical(main_window, "转换失败", f"CFF 轮廓转换失败：\n{conv_err}")
                    font.close()
                    return
        
        elif src_ext == '.ttf' and out_ext == '.otf':
            main_window.log("   TTF -> OTF: 保持 TrueType 轮廓 (仅改变容器格式)")
        
        file_existed = os.path.exists(out_path)
        if file_existed:
            history.record_before_overwrite("格式转换", out_path, f"{src_ext} -> {out_ext}")
        
        font.save(out_path)
        font.close()
        
        if not file_existed and os.path.exists(out_path):
            history.record_new_file("格式转换", out_path, f"{src_ext} -> {out_ext}")
        elif os.path.exists(out_path):
            history.record("格式转换", out_path, f"{src_ext} -> {out_ext}")
        
        update_history_buttons(main_window)
        
        main_window.log(f"✅ <b>转换完成!</b>")
        main_window.log(f"   输出: {out_path}")
        QMessageBox.information(main_window, "转换成功", f"格式转换完成！\n输出: {out_path}")
        
    except Exception as e:
        main_window.log(f"❌ 转换失败: {e}")
        traceback.print_exc()
        QMessageBox.critical(main_window, "转换失败", f"转换出错: {e}")

def do_export_config(main_window):
    config = {
        'version': '1.1',
        'basic': {
            'src': main_window.in_src.text(),
            'fallback': main_window.in_fallback.text(),
            'json': main_window.in_json.text(),
            'file_name': main_window.in_file_name.text(),
            'font_name': main_window.in_font_name.text(),
            'output_dir': main_window.in_output_dir.text() if hasattr(main_window, 'in_output_dir') else '',
            'mode': main_window.combo_mode.currentIndex(),
        },
        'theme': main_window.current_theme_name,
        'recent_files': main_window.recent_files if hasattr(main_window, 'recent_files') else [],
        'mapping': {
            'src': main_window.map_src.text(),
            'out': main_window.map_out.text(),
            'json': main_window.map_json.text(),
            'ext': main_window.map_ext.text(),
        },
        'subset': {
            'font': main_window.sub_font.text(),
            'txt': main_window.sub_txt.text(),
            'json': main_window.sub_json.text(),
            'out': main_window.sub_out.text(),
        },
        'merge': {
            'base': main_window.merge_base.text(),
            'add': main_window.merge_add.text(),
            'out': main_window.merge_out.text(),
            'filter': main_window.merge_filter.text(),
        },
        'pic': {
            'font': main_window.pic_font.text(),
            'folder': main_window.pic_folder.text(),
            'fmt': main_window.pic_fmt.text(),
            'fs': main_window.pic_fs.text(),
            'cnt': main_window.pic_cnt.text(),
        },
        'tga': {
            'font': main_window.tga_font.text(),
            'dat': main_window.tga_dat.text(),
        },
        'bmp': {
            'font': main_window.bmp_font.text(),
            'fs': main_window.bmp_fs.text(),
        },
        'woff2': {
            'src': main_window.woff2_src.text() if hasattr(main_window, 'woff2_src') else '',
            'out': main_window.woff2_out.text() if hasattr(main_window, 'woff2_out') else '',
        },
        'fix': {
            'src': main_window.fix_src.text() if hasattr(main_window, 'fix_src') else '',
            'ref': main_window.fix_ref.text() if hasattr(main_window, 'fix_ref') else '',
            'out': main_window.fix_out.text() if hasattr(main_window, 'fix_out') else '',
        },
    }
    
    save_path, _ = QFileDialog.getSaveFileName(
        main_window, "导出配置", "gal_font_config.gft", "项目配置 (*.gft);;JSON (*.json)"
    )
    
    if save_path:
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            main_window.log(f"💾 配置已导出: {os.path.basename(save_path)}")
            QMessageBox.information(main_window, "导出成功", f"完整配置已保存到：\n{save_path}")
        except Exception as e:
            main_window.log(f"❌ 导出失败: {e}")
            QMessageBox.critical(main_window, "导出失败", str(e))

def do_import_config(main_window):
    load_path, _ = QFileDialog.getOpenFileName(
        main_window, "导入配置", "", "项目配置 (*.gft);;JSON (*.json);;所有文件 (*.*)"
    )
    
    if not load_path:
        return
    
    try:
        with open(load_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        if 'basic' in config:
            b = config['basic']
            if 'src' in b: main_window.in_src.setText(b['src'])
            if 'fallback' in b: main_window.in_fallback.setText(b['fallback'])
            if 'json' in b: main_window.in_json.setText(b['json'])
            if 'file_name' in b: main_window.in_file_name.setText(b['file_name'])
            if 'font_name' in b: main_window.in_font_name.setText(b['font_name'])
            if 'output_dir' in b and hasattr(main_window, 'in_output_dir'):
                main_window.in_output_dir.setText(b['output_dir'])
            if 'mode' in b: main_window.combo_mode.setCurrentIndex(b['mode'])
        
        if 'theme' in config:
            idx = main_window.combo_theme.findText(config['theme'])
            if idx >= 0: main_window.combo_theme.setCurrentIndex(idx)
        
        if 'recent_files' in config and hasattr(main_window, 'recent_files'):
            main_window.recent_files = [f for f in config['recent_files'] if os.path.exists(f)]
        
        if 'mapping' in config:
            m = config['mapping']
            if 'src' in m: main_window.map_src.setText(m['src'])
            if 'out' in m: main_window.map_out.setText(m['out'])
            if 'json' in m: main_window.map_json.setText(m['json'])
            if 'ext' in m: main_window.map_ext.setText(m['ext'])
        
        if 'subset' in config:
            s = config['subset']
            if 'font' in s: main_window.sub_font.setText(s['font'])
            if 'txt' in s: main_window.sub_txt.setText(s['txt'])
            if 'json' in s: main_window.sub_json.setText(s['json'])
            if 'out' in s: main_window.sub_out.setText(s['out'])
        
        if 'merge' in config:
            mg = config['merge']
            if 'base' in mg: main_window.merge_base.setText(mg['base'])
            if 'add' in mg: main_window.merge_add.setText(mg['add'])
            if 'out' in mg: main_window.merge_out.setText(mg['out'])
            if 'filter' in mg: main_window.merge_filter.setText(mg['filter'])
        
        if 'pic' in config:
            p = config['pic']
            if 'font' in p: main_window.pic_font.setText(p['font'])
            if 'folder' in p: main_window.pic_folder.setText(p['folder'])
            if 'fmt' in p: main_window.pic_fmt.setText(p['fmt'])
            if 'fs' in p: main_window.pic_fs.setText(p['fs'])
            if 'cnt' in p: main_window.pic_cnt.setText(p['cnt'])
        
        if 'tga' in config:
            tg = config['tga']
            if 'font' in tg: main_window.tga_font.setText(tg['font'])
            if 'dat' in tg: main_window.tga_dat.setText(tg['dat'])
        
        if 'bmp' in config:
            bm = config['bmp']
            if 'font' in bm: main_window.bmp_font.setText(bm['font'])
            if 'fs' in bm: main_window.bmp_fs.setText(bm['fs'])
        
        if 'woff2' in config and hasattr(main_window, 'woff2_src'):
            w = config['woff2']
            if 'src' in w: main_window.woff2_src.setText(w['src'])
            if 'out' in w: main_window.woff2_out.setText(w['out'])
        
        if 'fix' in config and hasattr(main_window, 'fix_src'):
            fx = config['fix']
            if 'src' in fx: main_window.fix_src.setText(fx['src'])
            if 'ref' in fx: main_window.fix_ref.setText(fx['ref'])
            if 'out' in fx: main_window.fix_out.setText(fx['out'])
        
        main_window.log(f"📂 配置已导入: {os.path.basename(load_path)}")
        QMessageBox.information(main_window, "导入成功", f"已从配置文件恢复设置：\n{os.path.basename(load_path)}")
        
    except Exception as e:
        main_window.log(f"❌ 导入失败: {e}")
        QMessageBox.warning(main_window, "导入失败", f"无法导入配置：\n{e}")

def do_undo(main_window):
    from core.history_manager import get_history_manager
    history = get_history_manager()
    
    record, msg = history.undo()
    
    if record:
        main_window.log(f"↩️ {msg}")
        main_window.log(f"   已恢复文件: {os.path.basename(record['original_path'])}")
        update_history_buttons(main_window)
    else:
        main_window.log(f"⚠️ {msg}")
        QMessageBox.information(main_window, "撤销", msg)

def do_redo(main_window):
    from core.history_manager import get_history_manager
    history = get_history_manager()
    
    record, msg = history.redo()
    
    if record:
        main_window.log(f"↪️ {msg}")
        main_window.log(f"   已恢复文件: {os.path.basename(record['original_path'])}")
        update_history_buttons(main_window)
    else:
        main_window.log(f"⚠️ {msg}")
        QMessageBox.information(main_window, "重做", msg)

def update_history_buttons(main_window):
    from core.history_manager import get_history_manager
    history = get_history_manager()
    
    if hasattr(main_window, 'btn_undo'):
        main_window.btn_undo.setEnabled(history.can_undo())
    if hasattr(main_window, 'btn_redo'):
        main_window.btn_redo.setEnabled(history.can_redo())

def show_history_dialog(main_window):
    from core.history_manager import get_history_manager
    history = get_history_manager()
    
    history_list = history.get_history_list()
    
    dialog = QDialog(main_window)
    dialog.setWindowTitle("📜 操作历史")
    dialog.setMinimumSize(500, 400)
    
    layout = QVBoxLayout(dialog)
    
    if not history_list:
        lbl = QLabel("暂无操作历史记录")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: gray; font-size: 14px; padding: 50px;")
        layout.addWidget(lbl)
    else:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["时间", "操作", "文件", "描述"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(history_list))
        
        for row, item in enumerate(history_list):
            table.setItem(row, 0, QTableWidgetItem(item['time']))
            table.setItem(row, 1, QTableWidgetItem(item['action']))
            table.setItem(row, 2, QTableWidgetItem(item['file']))
            table.setItem(row, 3, QTableWidgetItem(item['description']))
        
        layout.addWidget(table)
    
    btn_layout = QHBoxLayout()
    
    def clear_and_update():
        history.clear_history()
        update_history_buttons(main_window)
        main_window.log("🗑️ 历史记录已清空")
        dialog.accept()
    
    btn_clear = QPushButton("🗑️ 清空历史")
    btn_clear.clicked.connect(clear_and_update)
    
    btn_close = QPushButton("关闭")
    btn_close.clicked.connect(dialog.close)
    
    btn_layout.addWidget(btn_clear)
    btn_layout.addStretch()
    btn_layout.addWidget(btn_close)
    
    layout.addLayout(btn_layout)
    
    dialog.exec()