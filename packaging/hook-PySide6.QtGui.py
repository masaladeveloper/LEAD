"""Keep Qt's standard dependency discovery, without unused PDF/virtual keyboard plugins."""
from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

# This widgets app neither renders PDF images nor provides a touch keyboard.
# Filter before binary dependency analysis so their Qt libraries are omitted too.
unused_plugins = {'qpdf', 'libqpdf', 'qtvirtualkeyboardplugin', 'libqtvirtualkeyboardplugin'}
binaries = [(source, target) for source, target in binaries
            if Path(source).stem not in unused_plugins]
