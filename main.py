import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

from ui.main_window import GalFontTool

if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    w = GalFontTool()
    w.show()
    sys.exit(app.exec())