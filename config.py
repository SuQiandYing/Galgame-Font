import sys

# 依赖检测
try:
    import opencc
    HAS_OPENCC = True
except ImportError:
    HAS_OPENCC = False

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False

# 主题定义
THEMES = {
    "🌊 深海 (Ocean)": {
        "bg_grad": ["#E3F2FD", "#BBDEFB", "#90CAF9"],
        "accent": "#2196F3",
        "btn_hover": "#1976D2",
        "text_main": "#0D47A1",
        "text_dim": "#1565C0",
        "card_bg": "rgba(255, 255, 255, 0.85)",
        "input_bg": "rgba(255,255,255,0.7)",
        "input_focus": "#FFFFFF",
        "border": "rgba(255, 255, 255, 0.8)"
    },
    "🌸 樱花 (Sakura)": {
        "bg_grad": ["#Fce4ec", "#F3E5F5", "#E1BEE7"],
        "accent": "#ff80ab",
        "btn_hover": "#ff4081",
        "text_main": "#333333",
        "text_dim": "#555555",
        "card_bg": "rgba(255, 255, 255, 0.75)",
        "input_bg": "rgba(255,255,255,0.6)",
        "input_focus": "rgba(255,255,255,0.9)",
        "border": "rgba(255, 255, 255, 0.8)"
    },
    "🍃 薄荷 (Mint)": {
        "bg_grad": ["#E0F2F1", "#B2DFDB", "#80CBC4"],
        "accent": "#009688",
        "btn_hover": "#00796B",
        "text_main": "#004D40",
        "text_dim": "#00695C",
        "card_bg": "rgba(255, 255, 255, 0.8)",
        "input_bg": "rgba(255,255,255,0.6)",
        "input_focus": "#FFFFFF",
        "border": "rgba(255, 255, 255, 0.8)"
    },
    "🌙 暗夜 (Night)": {
        "bg_grad": ["#232526", "#414345", "#232526"],
        "accent": "#BB86FC",
        "btn_hover": "#985EFF",
        "text_main": "#E0E0E0",
        "text_dim": "#B0B0B0",
        "card_bg": "rgba(30, 30, 30, 0.85)",
        "input_bg": "rgba(60, 60, 60, 0.6)",
        "input_focus": "rgba(80, 80, 80, 0.95)",
        "border": "rgba(80, 80, 80, 0.8)"
    },
    "🍊 活力 (Sunset)": {
        "bg_grad": ["#FFF3E0", "#FFE0B2", "#FFCC80"],
        "accent": "#FF9800",
        "btn_hover": "#F57C00",
        "text_main": "#E65100",
        "text_dim": "#EF6C00",
        "card_bg": "rgba(255, 255, 255, 0.8)",
        "input_bg": "rgba(255,255,255,0.6)",
        "input_focus": "#FFFFFF",
        "border": "rgba(255, 255, 255, 0.8)"
    }
}