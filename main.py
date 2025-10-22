import json
import sys
import logging.config

from PySide6.QtWidgets import QApplication

from musicsync.gui.main_window import MainWindow

if __name__ == "__main__":
    with open('logging_config.json', 'r') as f:
        logging_config = json.load(f)
    logging.config.dictConfig(logging_config)

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
