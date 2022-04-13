import socket
import sys
import argparse
import dis
from pprint import pprint
import json
import logging
import select
import time
import logs.config_server_log as clog
from errors import IncorrectDataRecivedError
from common.variables import *
from common.utils import *
from decos import log
from server_db import ServerStorage

# Инициализация логирования сервера.
logger = clog.logger


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


class Server(metaclass=ServerVerifier):
    port = CheckServer()

    def __init__(self, listen_address, listen_port, data_base):
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
        transport.bind((self.addr, self.port))
        transport.settimeout(0.5)

        # Начинаем слушать сокет.
        self.sock = transport
        self.sock.listen()

    # Обработчик сообщений от клиентов, принимает словарь - сообщение от клиента, проверяет корректность, отправляет
    #     словарь-ответ в случае необходимости.
    @log
    def process_client_message(self, message, client):
        # logger.debug(f'Разбор сообщения от клиента : {message}')
        # Если это сообщение о присутствии, принимаем и отвечаем
        if ACTION in message and message[ACTION] == PRESENCE and TIME in message and USER in message:
            # Если такой пользователь ещё не зарегистрирован, регистрируем, иначе отправляем ответ и завершаем
            # соединение.
            if message[USER][ACCOUNT_NAME] not in self.names.keys():
                self.names[message[USER][ACCOUNT_NAME]] = client
                client_ip, client_port = client.getpeername()
                self.database.user_login(message[USER][ACCOUNT_NAME], client_ip, client_port)
                send_message(client, RESPONSE_200)
            else:
                response = RESPONSE_400
                response[ERROR] = 'Имя пользователя уже занято.'
                send_message(client, response)
                self.clients.remove(client)
                client.close()
            return
        # Если это сообщение, то добавляем его в очередь сообщений. Ответ не требуется.
        elif ACTION in message and message[ACTION] == MESSAGE and DESTINATION in message and TIME in message \
                and SENDER in message and MESSAGE_TEXT in message:
            self.messages.append(message)
            return
        # Если клиент выходит
        elif ACTION in message and message[ACTION] == EXIT and ACCOUNT_NAME in message:
            self.data_base.user_logout(message[ACCOUNT_NAME])
            self.clients.remove(self.names[ACCOUNT_NAME])
            self.names[ACCOUNT_NAME].close()
            del self.names[ACCOUNT_NAME]
            return
        # Иначе отдаём Bad request
        else:
            response = RESPONSE_400
            response[ERROR] = 'Запрос некорректен.'
            send_message(client, response)
            return

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

    def main_loop(self):
        # Инициализация сокета
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
            except OSError:
                pass

            # принимаем сообщения и если ошибка, исключаем клиента.
            if recv_data_lst:
                for client_with_message in recv_data_lst:
                    try:
                        self.process_client_message(get_message(client_with_message), client_with_message)
                    except:
                        logger.info(f'Клиент {client_with_message.getpeername()} отключился от сервера.')
                        self.clients.remove(client_with_message)

            # Если есть сообщения, обрабатываем каждое.
            for message in self.messages:
                try:
                    self.process_message(message, send_data_lst)
                except Exception as e:
                    logger.info(f'Связь с клиентом с именем {message[DESTINATION]} была потеряна')
                    self.clients.remove(self.names[message[DESTINATION]])
                    del self.names[message[DESTINATION]]
            self.messages.clear()


# Парсер аргументов командной строки.
@log
def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', default=DEFAULT_PORT, type=int, nargs='?')
    parser.add_argument('-a', default='', nargs='?')
    namespace = parser.parse_args(sys.argv[1:])
    listen_address = namespace.a
    listen_port = namespace.p

    # проверка получения корректного номера порта для работы сервера.
    if not 1023 < listen_port < 65536:
        logger.critical(
            f'Попытка запуска сервера с указанием неподходящего порта {listen_port}. Допустимы адреса с 1024 до 65535.')
        exit(1)

    return listen_address, listen_port


def main():
    # Загрузка параметров командной строки, если нет параметров,
    # то задаём значения по умолчанию.
    listen_address, listen_port = arg_parser()

    db = ServerStorage()

    # Создание экземпляра класса - сервера.
    server = Server(listen_address, listen_port, db)
    server.daemon = True
    server.main_loop()

if __name__ == '__main__':
    main()
