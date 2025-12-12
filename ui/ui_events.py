import os
from PyQt6.QtCore import Qt, QPoint, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QColor, QLinearGradient

def paintEvent(main_window, event):
    painter = QPainter(main_window)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad_colors = main_window.theme["bg_grad"]
    gradient = QLinearGradient(0, 0, main_window.width(), main_window.height())
    gradient.setColorAt(0.0, QColor(grad_colors[0]))
    gradient.setColorAt(0.6, QColor(grad_colors[1]))
    gradient.setColorAt(1.0, QColor(grad_colors[2]))
    path = QPainterPath()
    path.addRoundedRect(QRectF(main_window.rect()), 24, 24)
    painter.fillPath(path, gradient)
    pen = QPen(QColor(0, 0, 0, 20))
    pen.setWidth(1)
    painter.strokePath(path, pen)

def closeEvent(main_window, event):
    main_window.settings.setValue("in_src", main_window.in_src.text())
    main_window.settings.setValue("in_fallback", main_window.in_fallback.text())
    main_window.settings.setValue("in_json", main_window.in_json.text())
    main_window.settings.setValue("in_file_name", main_window.in_file_name.text())
    main_window.settings.setValue("in_font_name", main_window.in_font_name.text())
    main_window.settings.setValue("lock_file_name", main_window.chk_lock_file_name.isChecked())
    main_window.settings.setValue("lock_font_name", main_window.chk_lock_font_name.isChecked())
    main_window.settings.setValue("theme", main_window.current_theme_name)
    if hasattr(main_window, 'in_output_dir'):
        main_window.settings.setValue("output_dir", main_window.in_output_dir.text())
    if hasattr(main_window, 'recent_files'):
        main_window.settings.setValue("recent_files", main_window.recent_files)
    event.accept()

def _calc_cursor_pos(main_window, p):
    r = main_window.rect()
    m = main_window.EDGE_MARGIN
    edge = main_window.EDGE_NONE
    if p.x() <= m: edge |= main_window.EDGE_LEFT
    if p.x() >= r.width() - m: edge |= main_window.EDGE_RIGHT
    if p.y() <= m: edge |= main_window.EDGE_TOP
    if p.y() >= r.height() - m: edge |= main_window.EDGE_BOTTOM
    return edge

def _set_cursor_shape(main_window, edge):
    if edge == main_window.EDGE_LEFT | main_window.EDGE_TOP or edge == main_window.EDGE_RIGHT | main_window.EDGE_BOTTOM:
        main_window.setCursor(Qt.CursorShape.SizeFDiagCursor)
    elif edge == main_window.EDGE_RIGHT | main_window.EDGE_TOP or edge == main_window.EDGE_LEFT | main_window.EDGE_BOTTOM:
        main_window.setCursor(Qt.CursorShape.SizeBDiagCursor)
    elif edge & main_window.EDGE_LEFT or edge & main_window.EDGE_RIGHT:
        main_window.setCursor(Qt.CursorShape.SizeHorCursor)
    elif edge & main_window.EDGE_TOP or edge & main_window.EDGE_BOTTOM:
        main_window.setCursor(Qt.CursorShape.SizeVerCursor)
    else:
        main_window.setCursor(Qt.CursorShape.ArrowCursor)

def mousePressEvent(main_window, e):
    if e.button() == Qt.MouseButton.LeftButton:
        edge = _calc_cursor_pos(main_window, e.position().toPoint())
        if edge != main_window.EDGE_NONE:
            main_window.is_resizing = True
            main_window.resize_edge = edge
            main_window.drag_start_pos = e.globalPosition().toPoint()
            main_window.old_geometry = QRectF(main_window.geometry())
        else:
            main_window.is_dragging = True
            main_window.drag_start_pos = e.globalPosition().toPoint() - main_window.frameGeometry().topLeft()
        e.accept()

def mouseMoveEvent(main_window, e):
    if main_window.is_resizing:
        delta = e.globalPosition().toPoint() - main_window.drag_start_pos
        new_geo = main_window.old_geometry.toRect()
        if main_window.resize_edge & main_window.EDGE_LEFT: new_geo.setLeft(new_geo.left() + delta.x())
        if main_window.resize_edge & main_window.EDGE_RIGHT: new_geo.setRight(new_geo.right() + delta.x())
        if main_window.resize_edge & main_window.EDGE_TOP: new_geo.setTop(new_geo.top() + delta.y())
        if main_window.resize_edge & main_window.EDGE_BOTTOM: new_geo.setBottom(new_geo.bottom() + delta.y())
        if new_geo.width() < main_window.minimumWidth():
            if main_window.resize_edge & main_window.EDGE_LEFT:
                new_geo.setLeft(new_geo.right() - main_window.minimumWidth())
            else:
                new_geo.setRight(new_geo.left() + main_window.minimumWidth())
        if new_geo.height() < main_window.minimumHeight():
            if main_window.resize_edge & main_window.EDGE_TOP:
                new_geo.setTop(new_geo.bottom() - main_window.minimumHeight())
            else:
                new_geo.setBottom(new_geo.top() + main_window.minimumHeight())
        main_window.setGeometry(new_geo)
        e.accept()
    elif main_window.is_dragging:
        main_window.move(e.globalPosition().toPoint() - main_window.drag_start_pos)
        e.accept()
    else:
        _set_cursor_shape(main_window, _calc_cursor_pos(main_window, e.position().toPoint()))

def mouseReleaseEvent(main_window, e):
    main_window.is_dragging = False
    main_window.is_resizing = False
    main_window.resize_edge = main_window.EDGE_NONE
    main_window.setCursor(Qt.CursorShape.ArrowCursor)

def dragEnterEvent(main_window, e):
    if e.mimeData().hasUrls(): e.acceptProposedAction()

def dropEvent(main_window, e):
    urls = e.mimeData().urls()
    current_idx = main_window.stack.currentIndex()
    
    if current_idx == 2:
         for u in urls:
            p = u.toLocalFile()
            if os.path.isdir(p):
                main_window.sub_txt.setText(p)
                main_window.log_area.append(f"📂 [精简] 已设定文本目录: {p}")
            elif p.lower().endswith(('.ttf', '.otf')):
                main_window.sub_font.setText(p)
                main_window.log_area.append(f"📥 [精简] 已载入源字体: {os.path.basename(p)}")
                if hasattr(main_window, 'add_to_recent_files'):
                    main_window.add_to_recent_files(p)
            elif p.lower().endswith('.json'):
                main_window.sub_json.setText(p)
                main_window.log_area.append(f"📥 [精简] 已载入映射表: {os.path.basename(p)}")
         return

    if current_idx == 3:
        for u in urls:
            p = u.toLocalFile()
            if p.lower().endswith(('.ttf', '.otf')):
                if not main_window.merge_base.text() or main_window.merge_base.text() == "base.ttf":
                    main_window.merge_base.setText(p)
                    main_window.log_area.append(f"📥 [合并] 已载入基础字体: {os.path.basename(p)}")
                elif not main_window.merge_add.text() or main_window.merge_add.text() == "supplement.ttf":
                    main_window.merge_add.setText(p)
                    main_window.log_area.append(f"📥 [合并] 已载入补充字体: {os.path.basename(p)}")
                else:
                    main_window.merge_add.setText(p)
                    main_window.log_area.append(f"📥 [合并] 已更新补充字体: {os.path.basename(p)}")
                if hasattr(main_window, 'add_to_recent_files'):
                    main_window.add_to_recent_files(p)
        return

    if current_idx == 4:
        for u in urls:
            p = u.toLocalFile()
            if p.lower().endswith(('.ttf', '.otf')):
                if not main_window.cmp_font1.text() or main_window.cmp_font1.text() == "fontA.ttf":
                    main_window.cmp_font1.setText(p)
                    main_window.log_area.append(f"📥 [分析] 已载入字体A: {os.path.basename(p)}")
                elif not main_window.cmp_font2.text() or main_window.cmp_font2.text() == "fontB.ttf":
                    main_window.cmp_font2.setText(p)
                    main_window.log_area.append(f"📥 [分析] 已载入字体B: {os.path.basename(p)}")
                else:
                    main_window.cov_font.setText(p)
                    main_window.log_area.append(f"📥 [分析] 已载入覆盖率字体: {os.path.basename(p)}")
                if hasattr(main_window, 'add_to_recent_files'):
                    main_window.add_to_recent_files(p)
        return

    if current_idx == 0:
        for u in urls:
            p = u.toLocalFile()
            if p.lower().endswith(('.ttf', '.otf')):
                main_window.info_font.setText(p)
                main_window.log_area.append(f"📥 [信息] 已载入字体: {os.path.basename(p)}")
                main_window.do_read_font_info()
                if hasattr(main_window, 'add_to_recent_files'):
                    main_window.add_to_recent_files(p)
        return

    if current_idx == 10:
        for u in urls:
            p = u.toLocalFile()
            if os.path.isdir(p):
                if not main_window.sf_txt.text() or main_window.sf_txt.text() == "cn_text":
                    main_window.sf_txt.setText(p)
                    main_window.log_area.append(f"📂 [智能补全] 已设定文本目录: {p}")
                else:
                    main_window.sf_lib.setText(p)
                    main_window.log_area.append(f"📂 [智能补全] 已设定补全库目录: {p}")
            elif p.lower().endswith(('.ttf', '.otf')):
                main_window.sf_primary.setText(p)
                main_window.log_area.append(f"📥 [智能补全] 已载入主字体: {os.path.basename(p)}")
                if hasattr(main_window, 'add_to_recent_files'):
                    main_window.add_to_recent_files(p)
        return

    for u in urls:
        p = u.toLocalFile()
        if os.path.isdir(p):
            main_window.map_src.setText(p)
            main_window.log_area.append(f"📂 已设定文本目录: {p}")
            main_window.switch_tab(1)
        elif p.lower().endswith(('.ttf', '.otf')):
            if not main_window.in_src.text() or main_window.in_src.text() == "Font.ttf":
                main_window.in_src.setText(p)
                main_window.log_area.append(f"📥 已载入主字体: {os.path.basename(p)}")
                main_window.on_source_font_changed()
                if hasattr(main_window, 'add_to_recent_files'):
                    main_window.add_to_recent_files(p)
            else:
                main_window.in_fallback.setText(p)
                main_window.log_area.append(f"🔧 已载入补全字体: {os.path.basename(p)}")
                if hasattr(main_window, 'add_to_recent_files'):
                    main_window.add_to_recent_files(p)
        elif p.lower().endswith('.json'):
            main_window.in_json.setText(p)
            main_window.log_area.append(f"📥 已载入码表: {os.path.basename(p)}")