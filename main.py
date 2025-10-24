import json
import sys
import logging.config
import os

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow

if __name__ == "__main__":
    if not os.path.isdir('logs'):
        os.mkdir('logs')
    with open('logging_config.json', 'r') as f:
        logging_config = json.load(f)
    logging.config.dictConfig(logging_config)

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
