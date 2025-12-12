import traceback
from PyQt6.QtCore import QThread, pyqtSignal

from core.tasks import image_tasks, font_tasks, text_tasks, modify_tasks


class Worker(QThread):
    log = pyqtSignal(str)
    prog = pyqtSignal(int)
    done = pyqtSignal(object)

    def __init__(self, task_type, config):
        super().__init__()
        self.task = task_type
        self.c = config

    def run(self):
        log_func = self.log.emit
        prog_func = self.prog.emit

        try:
            result = None
            
            if self.task == "font":
                result = font_tasks.build_font(self.c, log_func, prog_func)
            elif self.task == "subset":
                result = font_tasks.subset_font(self.c, log_func, prog_func)
            elif self.task == "woff2":
                result = font_tasks.gen_woff2(self.c, log_func, prog_func)
            
            elif self.task == "pic":
                result = image_tasks.gen_pic(self.c, log_func, prog_func)
            elif self.task == "tga":
                result = image_tasks.gen_tga(self.c, log_func, prog_func)
            elif self.task == "bmp":
                result = image_tasks.gen_bmp(self.c, log_func, prog_func)
            elif self.task == "bmfont":
                result = image_tasks.gen_bmfont(self.c, log_func, prog_func)
            
            elif self.task == "map":
                result = text_tasks.gen_mapping(self.c, log_func, prog_func)
            elif self.task == "smart_fallback":
                result = text_tasks.smart_fallback_scan(self.c, log_func, prog_func)
            
            elif self.task == "tweak_width":
                result = modify_tasks.tweak_font_width(self.c, log_func, prog_func)
            elif self.task == "cleanup":
                result = modify_tasks.clean_font_tables(self.c, log_func, prog_func)
            elif self.task == "unified_fix":
                result = modify_tasks.gen_unified_fix(self.c, log_func, prog_func)
            
            self.done.emit(result)

        except Exception as e:
            self.log.emit(f"❌ <font color='red'>[系统异常] {str(e)}</font>")
            traceback.print_exc()
