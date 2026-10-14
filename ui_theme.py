"""Shared Qt styling: warm workspace, ink navigation, and terracotta accents."""
STYLE = '''
QWidget { font-family: "Segoe UI", "Inter", sans-serif; font-size: 13px; color: #27333c; }
QMainWindow, QDialog { background: #f5f5f1; }
QWidget#sidebar { background: #182d31; }
QWidget#sidebar QLabel { color: #a6bbba; background: transparent; }
QLabel#brand { color: #ffffff; font-size: 24px; font-weight: 700; }
QLabel#brandSub { color: #91aaa8; font-size: 11px; }
QLabel#eyebrow { color: #728580; font-size: 11px; font-weight: 700; }
QLabel#title { font-size: 30px; font-weight: 700; color: #173237; }
QLabel#subtitle { color: #72817e; font-size: 13px; }
QLabel#sectionTitle { font-size: 18px; font-weight: 600; }
QLabel#metric { font-size: 32px; font-weight: 600; color: #183c3d; }
QLabel#detailTitle { font-size: 21px; font-weight: 600; }
QFrame#card, QFrame#panel { background: #ffffff; border: 1px solid #e3e8e3; border-radius: 12px; }
QLabel#badge { color: #227569; background: #e9f3ee; border-radius: 6px; padding: 5px 9px; }
QLabel#notice { background: #edf1e9; color: #456454; border-radius: 8px; padding: 12px; }
QPushButton { background: #ffffff; border: 1px solid #dce3dc; border-radius: 7px; padding: 10px 15px; font-weight: 600; }
QPushButton:hover { background: #edf2ec; border-color: #b7c7bb; }
QPushButton:disabled { color: #9aa5a1; background: #edf0ec; }
QPushButton#primary { color: white; background: #bf623f; border-color: #bf623f; }
QPushButton#primary:hover { background: #a64f30; }
QPushButton#primary:disabled { background: #c9a28f; border-color: #c9a28f; }
QPushButton#nav { text-align: left; background: transparent; color: #b8cbc7; border: 0; padding: 13px 16px; }
QPushButton#nav:hover { background: #263f42; color: white; }
QPushButton#nav:checked { background: #334c4c; color: white; border-left: 3px solid #e6a179; }
QLineEdit, QComboBox, QSpinBox, QDateEdit, QPlainTextEdit, QTextEdit { background: #ffffff; border: 1px solid #dce3dc; border-radius: 6px; padding: 8px; selection-background-color: #dcebe4; selection-color: #183c3d; }
QLineEdit:focus, QPlainTextEdit:focus { border-color: #709487; }
QComboBox::drop-down { border: 0; width: 24px; }
QTableWidget { background: white; border: 0; gridline-color: #edf0eb; selection-background-color: #edf4ef; selection-color: #163d36; }
QTableWidget::item { padding: 10px; border-bottom: 1px solid #edf0eb; }
QHeaderView::section { background: #fafbf8; color: #75847c; border: 0; border-bottom: 1px solid #e3e8e3; padding: 12px 8px; font-size: 11px; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #cbd6ce; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTabWidget::pane { border: 1px solid #dce3dc; background: white; border-radius: 8px; }
QTabBar::tab { padding: 12px 20px; color: #6d8177; }
QTabBar::tab:selected { color: #244f41; border-bottom: 2px solid #bf623f; }
QSplitter::handle { background: transparent; width: 14px; }
QToolTip { background: #183237; color: white; padding: 8px; border: 0; }
'''
