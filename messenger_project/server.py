import os.path
import socket
import argparse
import dis
import threading
import select
import configparser
import logs.config_server_log as clog
from common.utils import *
from common.decos import log
from server_db import ServerStorage
# from server_db import ServerDB
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QTimer
# from PyQt5.QtGui import QStandardItemModel, QStandardItem
from server_gui import MainWindow, gui_create_model, HistoryWindow, ConfigWindow

# Инициализация логирования сервера.
logger = clog.logger
conflag_lock = threading.Lock()
new_connection = False

# Мне просто надоело каждый раз писать имена параметров, поэтому ниже 2 класса делают это за меня
# Если на ваш взгляд этот способ некорректный - буду рад подсказке!
class Settings:
    def __init__(self):
        self.database_path = 'Database_path'
        self.database_file = 'Database_file'
        self.default_port = 'Default_port'
        self.listen_address = 'Listen_address'


class CCONFIG:
    def __init__(self):
        self.settings = 'SETTINGS'
        self.SETTINGS = Settings()


SET_CONF = CCONFIG()


class ServerVerifier(type):
    def __init__(cls, m_classes, m_parents, m_attrs):
        super(ServerVerifier, cls).__init__(m_classes, m_parents, m_attrs)
        m_dis = {
            'LOAD_GLOBAL': [],
            'LOAD_METHOD': [],
            'LOAD_ATTR': []
        }
        # pprint(m_attrs)
        for method in m_attrs:
            try:
                instruction = dis.get_instructions(m_attrs[method])
            except TypeError:
                pass
            else:
                # print(method)
                for n in instruction:
                    # print(n) #if n.opname in m_dis.keys() else None
                    if n.opname in m_dis.keys():
                        if n.argval not in m_dis[n.opname]:
                            # print(n.argval)
                            m_dis[n.opname].append(n.argval)
        # pprint(m_dis.items())
        # простым способом a in b[] не получается узнать, возможно потому что я создал словарь, поэтому пошел перебором
        # словаря
        if [True for i in m_dis.items() if i == 'connect']:
            raise TypeError('Использование метода connect недопустимо в серверном классе')
        # а здесь я (по крайней мере надеюсь на это) думаю что проверяю именно метод, ведь в методе у меня
        # используется создание сокета, другие области мне не важны
        if 'socket' not in m_dis['LOAD_METHOD']:
            raise TypeError('Не обнаружено использования сокета для работы по TCP')
            # print('Не обнаружено использования сокета для работы по TCP')


class CheckServer:
    """
    Дескриптор.
    Проверяет значение порта (>=0) и если значение пусто, то устанавливает 7777
    """

    def __set_name__(self, owner, name):
        self.attr = name

    def __set__(self, instance, value):
        if value < 0:
            ValueError('Значение порта не может быть отрицательным!')
        elif value is None:
            value = 7777

        instance.__dict__[self.attr] = value


class Server(threading.Thread, metaclass=ServerVerifier):
    port = CheckServer()

    def __init__(self, listen_address, listen_port, data_base):
        super().__init__()
        # Параметры подключения
        self.sock = None
        self.addr = listen_address
        self.port = listen_port
        self.data_base = data_base

        # Список подключённых клиентов.
        self.clients = []

        # Список сообщений на отправку.
        self.messages = []

        # Словарь содержащий сопоставленные имена и соответствующие им сокеты.
        self.names = dict()

    def init_socket(self):
        logger.info(
            f'Запущен сервер, порт для подключений: {self.port}, '
            f'адрес с которого принимаются подключения: {self.addr}. '
            f'Если адрес не указан, принимаются соединения с любых адресов.')
        # Готовим сокет
        transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        transport.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        transport.bind((self.addr, self.port))
        transport.settimeout(0.5)

        # Начинаем слушать сокет.
        self.sock = transport
        self.sock.listen()

    def run(self):
        # Инициализация сокета
        global new_connection

        self.init_socket()

        # Основной цикл программы сервера
        while True:
            # Ждём подключения, если таймаут вышел, ловим исключение.
            try:
                client, client_address = self.sock.accept()
            except OSError:
                pass
            else:
                logger.info(f'Установлено соединение с ПК {client_address}')
                self.clients.append(client)

            recv_data_lst = []
            send_data_lst = []
            err_lst = []
            # Проверяем на наличие ждущих клиентов
            try:
                if self.clients:
                    recv_data_lst, send_data_lst, err_lst = select.select(self.clients, self.clients, [], 0)
            except OSError as err:
                logger.error(f'Ошибка работы с сокетами: {err}')

            # принимаем сообщения и если ошибка, исключаем клиента.
            if recv_data_lst:
                for client_with_message in recv_data_lst:
                    try:
                        self.process_client_message(get_message(client_with_message), client_with_message)
                    except:
                        logger.info(f'Клиент {client_with_message.getpeername()} отключился от сервера.')
                        for name in self.names:
                            if self.names[name] == client_with_message:
                                self.data_base.user_logout(name)
                                del self.names[name]
                                break
                        self.clients.remove(client_with_message)
                        with conflag_lock:
                            new_connection = True

            # Если есть сообщения, обрабатываем каждое.
            for message in self.messages:
                try:
                    self.process_message(message, send_data_lst)
                except (ConnectionAbortedError, ConnectionError,
                        ConnectionResetError, ConnectionRefusedError):
                    logger.info(f'Связь с клиентом с именем {message[DESTINATION]} была потеряна')
                    self.clients.remove(self.names[message[DESTINATION]])
                    self.data_base.user_logout(message[DESTINATION])
                    del self.names[message[DESTINATION]]
                    with conflag_lock:
                        new_connection = True
            self.messages.clear()

    @log
    # Функция адресной отправки сообщения определённому клиенту. Принимает словарь сообщение, список зарегистрированных
    # пользователей и слушающие сокеты. Ничего не возвращает.
    def process_message(self, message, listen_socks):
        if message[DESTINATION] in self.names and self.names[message[DESTINATION]] in listen_socks:
            send_message(self.names[message[DESTINATION]], message)
            logger.info(f'Отправлено сообщение пользователю {message[DESTINATION]} от пользователя {message[SENDER]}.')
        elif message[DESTINATION] in self.names and self.names[message[DESTINATION]] not in listen_socks:
            raise ConnectionError
        else:
            logger.error(
                f'Пользователь {message[DESTINATION]} не зарегистрирован на сервере, отправка сообщения невозможна.')

    # Обработчик сообщений от клиентов, принимает словарь - сообщение от клиента, проверяет корректность, отправляет
    #     словарь-ответ в случае необходимости.
    @log
    def process_client_message(self, message, client):
        global new_connection
        logger.debug(f'Разбор сообщения от клиента : {message}')

        # Если это сообщение о присутствии, принимаем и отвечаем
        if ACTION in message and message[ACTION] == PRESENCE \
                and TIME in message and USER in message:
            # Если такой пользователь ещё не зарегистрирован, регистрируем, иначе отправляем ответ и завершаем
            # соединение.
            if message[USER][ACCOUNT_NAME] not in self.names.keys():
                self.names[message[USER][ACCOUNT_NAME]] = client
                client_ip, client_port = client.getpeername()
                self.data_base.user_login(message[USER][ACCOUNT_NAME], client_ip, client_port)
                send_message(client, RESPONSE_200)
                with conflag_lock:
                    new_connection = True
            else:
                response = RESPONSE_400
                response[ERROR] = 'Имя пользователя уже занято.'
                send_message(client, response)
                self.clients.remove(client)
                client.close()
            return
        # Если это сообщение, то добавляем его в очередь сообщений. Ответ не требуется.
        elif ACTION in message \
                and message[ACTION] == MESSAGE \
                and DESTINATION in message \
                and TIME in message \
                and SENDER in message \
                and MESSAGE_TEXT in message \
                and self.names[message[SENDER]] == client:
            if message[DESTINATION] in self.names:
                self.messages.append(message)
                self.data_base.process_message(message[SENDER], message[DESTINATION])
                send_message(client, RESPONSE_200)
            else:
                response = RESPONSE_400
                response[ERROR] = 'Пользователь не зарегистрирован на сервере.'
                send_message(client, response)
            return
        # Если клиент выходит
        elif ACTION in message \
                and message[ACTION] == EXIT \
                and ACCOUNT_NAME in message \
                and self.names[message[ACCOUNT_NAME]] == client:
            self.data_base.user_logout(message[ACCOUNT_NAME])
            self.clients.remove(self.names[message[ACCOUNT_NAME]])
            self.names[message[ACCOUNT_NAME]].close()
            del self.names[message[ACCOUNT_NAME]]
            with conflag_lock:
                new_connection = True
            return
        elif ACTION in message \
                and message[ACTION] == GET_CONTACTS \
                and USER in message and \
                self.names[message[USER]] == client:
            response = RESPONSE_202
            response[LIST_INFO] = self.data_base.get_contacts(message[USER])
            send_message(client, response)
        elif ACTION in message \
                and message[ACTION] == ADD_CONTACT \
                and ACCOUNT_NAME in message \
                and USER in message \
                and self.names[message[USER]] == client:
            self.data_base.add_contact(message[USER], message[ACCOUNT_NAME])
            send_message(client, RESPONSE_200)
        elif ACTION in message \
                and message[ACTION] == REMOVE_CONTACT \
                and ACCOUNT_NAME in message \
                and USER in message \
                and self.names[message[USER]] == client:
            self.data_base.remove_contact(message[USER], message[ACCOUNT_NAME])
            send_message(client, RESPONSE_200)
        elif ACTION in message \
                and message[ACTION] == USERS_REQUEST \
                and ACCOUNT_NAME in message \
                and self.names[message[ACCOUNT_NAME]] == client:
            response = RESPONSE_202
            response[LIST_INFO] = [user[0] for user in self.data_base.users_list()]
            send_message(client, response)
        # Иначе отдаём Bad request
        else:
            response = RESPONSE_400
            response[ERROR] = 'Запрос некорректен.'
            send_message(client, response)
            return


# Парсер аргументов командной строки.
@log
def arg_parser(default_port, default_address):
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', default=default_port, type=int, nargs='?')
    parser.add_argument('-a', default=default_address, nargs='?')
    namespace = parser.parse_args(sys.argv[1:])
    listen_address = namespace.a
    listen_port = namespace.p
    # проверка получения корректного номера порта для работы сервера.
    if not 1023 < listen_port < 65536:
        logger.critical(
            f'Попытка запуска сервера с указанием неподходящего порта {listen_port}. Допустимы адреса с 1024 до 65535.')
        exit(1)

    return listen_address, listen_port


def config_load():
    config = configparser.ConfigParser()
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config.read(f"{dir_path}/{'server.ini'}")
    # Если конфиг файл загружен правильно, запускаемся, иначе конфиг по умолчанию.
    if SET_CONF.settings in config:
        return config
    else:
        config.add_section(SET_CONF.settings)
        config.set(SET_CONF.settings, SET_CONF.SETTINGS.default_port, str(DEFAULT_PORT))
        config.set(SET_CONF.settings, SET_CONF.SETTINGS.listen_address, '')
        config.set(SET_CONF.settings, SET_CONF.SETTINGS.database_path, '')
        config.set(SET_CONF.settings, SET_CONF.SETTINGS.database_file, 'server_db.db3')
        return config


def main():
    config = config_load()
    # Загрузка параметров командной строки, если нет параметров,
    # то задаём значения по умолчанию.
    listen_address, listen_port = arg_parser(
        config[SET_CONF.settings][SET_CONF.SETTINGS.default_port],
        config[SET_CONF.settings][SET_CONF.SETTINGS.listen_address]
    )

    db = ServerStorage(
        os.path.join(
            config[SET_CONF.settings][SET_CONF.SETTINGS.database_path],
            config[SET_CONF.settings][SET_CONF.SETTINGS.database_file]
        )
    )

    # Создание экземпляра класса - сервера.
    server = Server(listen_address, listen_port, db)
    server.daemon = True
    server.start()

    server_app = QApplication(sys.argv)
    main_window = MainWindow()

    main_window.statusBar().showMessage('Сервер работает')
    main_window.active_clients_table.setModel(gui_create_model(db))
    main_window.active_clients_table.resizeColumnsToContents()
    main_window.active_clients_table.resizeRowsToContents()

    def list_update():
        global new_connection
        if new_connection:
            main_window.active_clients_table.setModel(gui_create_model(db))
            main_window.active_clients_table.resizeColumnsToContents()
            main_window.active_clients_table.resizeRowsToContents()
            with conflag_lock:
                new_connection = False

    def show_statistics():
        global stat_window
        stat_window = HistoryWindow()
        stat_window.history_table.setModel(gui_create_model(db))
        stat_window.history_table.resizeColumnsToContents()
        stat_window.history_table.resizeRowsToContents()
        stat_window.show()

    def server_config():
        global config_window
        config_window = ConfigWindow()
        config_window.db_path.insert(config[SET_CONF.settings][SET_CONF.SETTINGS.database_path])
        config_window.db_file.insert(config[SET_CONF.settings][SET_CONF.SETTINGS.database_file])
        config_window.port.insert(config[SET_CONF.settings][SET_CONF.SETTINGS.default_port])
        config_window.ip.insert(config[SET_CONF.settings][SET_CONF.SETTINGS.listen_address])
        config_window.save_btn.clicked.connect(save_server_config)

    def save_server_config():
        global config_window
        message = QMessageBox()
        config[SET_CONF.settings][SET_CONF.SETTINGS.database_path] = config_window.db_path.text()
        config[SET_CONF.settings][SET_CONF.SETTINGS.database_file] = config_window.db_file.text()
        try:
            port = int(config_window.port.text())
        except ValueError:
            message.warning(config_window, 'Ошибка', 'Порт должен быть числом')
        else:
            config[SET_CONF.settings][SET_CONF.SETTINGS.listen_address] = config_window.ip.text()
            if 1023 < port < 65536:
                config[SET_CONF.settings][SET_CONF.SETTINGS.default_port] = str(port)
                print(port)
                with open('server.ini', 'w') as conf:
                    config.write(conf)
                    message.information(config_window, 'ОК', 'Настройки успешно сохранены')
            else:
                message.warning(config_window, 'Ошибка', 'Порт должен быть от 1024 до 65535')

    timer = QTimer()
    timer.timeout.connect(list_update)
    timer.start(1000)

    main_window.refresh_button.triggered.connect(list_update)
    main_window.show_history_button.triggered.connect(show_statistics)
    main_window.config_btn.triggered.connect(server_config)

    server_app.exec_()


if __name__ == '__main__':
    main()
