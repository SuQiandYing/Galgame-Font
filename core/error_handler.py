import traceback
from PyQt6.QtWidgets import QMessageBox

class FontToolError(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details

class FileNotFoundError(FontToolError):
    pass

class FontReadError(FontToolError):
    pass

class FontWriteError(FontToolError):
    pass

class ConfigError(FontToolError):
    pass

def show_error(parent, title, message, details=None):
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    if details:
        msg_box.setDetailedText(details)
    msg_box.exec()

def show_warning(parent, title, message):
    QMessageBox.warning(parent, title, message)

def show_info(parent, title, message):
    QMessageBox.information(parent, title, message)

def handle_exception(parent, e, log_func=None, context=""):
    error_type = type(e).__name__
    error_msg = str(e)
    
    if log_func:
        log_func(f"❌ {context}: {error_msg}")
    
    if isinstance(e, FileNotFoundError):
        show_warning(parent, "文件不存在", error_msg)
    elif isinstance(e, FontReadError):
        show_error(parent, "字体读取失败", error_msg, traceback.format_exc())
    elif isinstance(e, FontWriteError):
        show_error(parent, "字体保存失败", error_msg, traceback.format_exc())
    elif isinstance(e, ConfigError):
        show_warning(parent, "配置错误", error_msg)
    else:
        show_error(parent, f"发生错误 ({error_type})", error_msg, traceback.format_exc())

def validate_paths(**paths):
    import os
    missing = []
    for name, path in paths.items():
        if path and not os.path.exists(path):
            missing.append(f"- {name}: {path}")
    
    if missing:
        raise FileNotFoundError(
            "以下路径不存在:\n" + "\n".join(missing),
            details="\n".join(missing)
        )
    return True

def validate_config(required_fields, config):
    missing = []
    for field in required_fields:
        if field not in config or not config[field]:
            missing.append(field)
    
    if missing:
        raise ConfigError(f"缺少必填项: {', '.join(missing)}")
    return True

def safe_execute(func, parent, log_func=None, context="", on_success=None, on_error=None):
    try:
        result = func()
        if on_success:
            on_success(result)
        return result
    except Exception as e:
        handle_exception(parent, e, log_func, context)
        if on_error:
            on_error(e)
        return None
