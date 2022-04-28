from PyQt5.QtWidgets import QDialog, QPushButton, QLineEdit, QApplication, QLabel, qApp
from PyQt5.QtCore import QEvent


class GreetingsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.ok_pressed = False
        self.setWindowTitle('Приветствую!')
        self.setFixedSize(250, 93)

        self.label = QLabel('Введите имя пользователя:', self)
        self.label.move(20, 10)
        self.label.setFixedSize(180, 10)

        self.client_name = QLineEdit(self)
        self.client_name.setFixedSize(212, 20)
        self.client_name.move(20, 30)

        self.button_ok = QPushButton('Начать', self)
        self.button_ok.move(20, 60)
        self.button_ok.clicked.connect(self.click)

        self.button_cancel = QPushButton('Выход', self)
        self.button_cancel.move(140, 60)
        self.button_cancel.clicked.connect(qApp.exit)

        self.show()

    def click(self):
        if self.client_name.text():
            self.ok_pressed = True
            qApp.exit()


if __name__ == '__main__':
    app = QApplication([])
    dial = GreetingsDialog()
    app.exec_()
