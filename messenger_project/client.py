# import sys
# import json
import socket
import time
import argparse
import dis
from pprint import pprint
# import logging
import threading
import logs.config_client_log as clog
from common.variables import *
from common.utils import *
from errors import IncorrectDataRecivedError, ReqFieldMissingError, ServerError
from decos import log

# Инициализация клиентского логера
logger = clog.logger
sock_lock = threading.Lock()
database_lock = threading.Lock()

# Задание 1: Реализовать мета класс ClientVerifier, выполняющий базовую проверку класса «Клиент» (для некоторых
# проверок уместно использовать модуль dis): отсутствие вызовов accept и listen для сокетов; использование сокетов
# для работы по TCP;
class ClientVerifier(type):
    def __init__(cls, m_classes, m_parents, m_attrs):
        super(ClientVerifier, cls).__init__(m_classes, m_parents, m_attrs)
        m_dis = {
            'LOAD_GLOBAL': [],
            'LOAD_METHOD': [],
            'LOAD_ATTR': []
        }
        # pprint(m_attrs)
        # for attr, v in m_attrs.items():
        #     print(attr)
        #     print(v)
        #     print('#'*50)
        for method in m_attrs:
            try:
                instruction = dis.get_instructions(m_attrs[method])
            except TypeError:
                pass
            else:
                # print(method)
                for n in instruction:
                    print(n) #if n.opname in m_dis.keys() else None
                    if n.opname in m_dis.keys():
                        if n.argval not in m_dis[n.opname]:
                            m_dis[n.opname].append(n.argval)

        if [True for i in m_dis.items() if i in ['accept', 'listen']]:
            raise TypeError('Использование методов accept и listen недопустимо в клиентском классе')
        if [True for i in m_dis.items() if i in ['socket', 'Receiver']]:
            raise TypeError('Не обнаружено использования сокета для работы по TCP')


class Sender(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, account_name, sock, database):
        self.account_name = account_name
        self.sock = sock
        self.database = database
        super().__init__()

    # Функция создаёт словарь с сообщением о выходе.
    # @log
    def create_exit_message(self):
        return {
            ACTION: EXIT,
            TIME: time.time(),
            ACCOUNT_NAME: self.account_name
        }

    # @log
    # Функция запрашивает кому отправить сообщение и само сообщение, и отправляет полученные данные на сервер.
    def create_message(self):
        to = input('Введите получателя сообщения: ')
        message = input('Введите сообщение для отправки: ')
        with database_lock:
            if not self.database.check_user(to):
                logger.error(f'Попытка отправить сообщение '
                             f'незарегистрированому получателю: {to}')
                return
        message_dict = {
            ACTION: MESSAGE,
            SENDER: self.account_name,
            DESTINATION: to,
            TIME: time.time(),
            MESSAGE_TEXT: message
        }
        logger.debug(f'Сформирован словарь сообщения: {message_dict}')
        with database_lock:
            self.database.save_message(self.account_name, to, message)

        with sock_lock:
            try:
                send_message(self.sock, message_dict)
                logger.info(f'Отправлено сообщение для пользователя {to}')
            except OSError as err:
                if err.errno:
                    logger.critical('Потеряно соединение с сервером.')
                    exit(1)
                else:
                    logger.error('Не удалось передать сообщение. Таймаут соединения')

    # @log
    # Функция взаимодействия с пользователем, запрашивает команды, отправляет сообщения
    # долго доходило что для того чтобы работал метод is_alive нужно переименовать этот метод в run
    def run(self):
        self.print_help()
        while True:
            command = input('Введите команду: ')
            if command == 'm':
                self.create_message()
            elif command == 'h':
                self.print_help()
            elif command == 'e':
                with sock_lock:
                    try:
                        send_message(self.sock, self.create_exit_message())
                    except Exception as e:
                        print(e)
                        pass
                    print('Завершение соединения.')
                    logger.info('Завершение работы по команде пользователя.')
                # Задержка неоходима, чтобы успело уйти сообщение о выходе
                time.sleep(0.5)
                break
            elif command == 'contacts':
                with database_lock:
                    contacts_list = self.database.get_contacts()
                for contact in contacts_list:
                    print(contact)

            elif command == 'edit':
                self.edit_contacts()

            elif command == 'history':
                self.print_history()

            else:
                print('Команда не распознана, попробойте снова. '
                      'help - вывести поддерживаемые команды.')

    # Функция выводящая справку по использованию.
    @staticmethod
    def print_help():
        print('Поддерживаемые команды:')
        print('m - отправить сообщение. Кому и текст будет запрошены отдельно.')
        print('h - вывести подсказки по командам')
        print('e - выход из программы')

    # Функция выводящяя историю сообщений
    def print_history(self):
        ask = input('Показать входящие сообщения - in, исходящие - out, все - просто Enter: ')
        with database_lock:
            if ask == 'in':
                history_list = self.database.get_history(to_who=self.account_name)
                for message in history_list:
                    print(f'\nСообщение от пользователя: {message[0]} '
                          f'от {message[3]}:\n{message[2]}')
            elif ask == 'out':
                history_list = self.database.get_history(from_who=self.account_name)
                for message in history_list:
                    print(f'\nСообщение пользователю: {message[1]} '
                          f'от {message[3]}:\n{message[2]}')
            else:
                history_list = self.database.get_history()
                for message in history_list:
                    print(f'\nСообщение от пользователя: {message[0]},'
                          f' пользователю {message[1]} '
                          f'от {message[3]}\n{message[2]}')

    # Функция изменеия контактов
    def edit_contacts(self):
        ans = input('Для удаления введите del, для добавления add: ')
        if ans == 'del':
            edit = input('Введите имя удаляемного контакта: ')
            with database_lock:
                if self.database.check_contact(edit):
                    self.database.del_contact(edit)
                else:
                    logger.error('Попытка удаления несуществующего контакта.')
        elif ans == 'add':
            # Проверка на возможность такого контакта
            edit = input('Введите имя создаваемого контакта: ')
            if self.database.check_user(edit):
                with database_lock:
                    self.database.add_contact(edit)
                with sock_lock:
                    try:
                        add_contact(self.sock, self.account_name, edit)
                    except ServerError:
                        logger.error('Не удалось отправить информацию на сервер.')


class Receiver(threading.Thread, metaclass=ClientVerifier):
    def __init__(self, account_name, sock, database):
        self.account_name = account_name
        self.sock = sock
        self.database = database
        super().__init__()

    # @log
    # Функция - обработчик сообщений других пользователей, поступающих с сервера.
    # долго доходило что для того чтобы работал метод is_alive нужно переименовать этот метод в run
    def run(self):
        while True:
            time.sleep(1)
            try:
                message = get_message(self.sock)

            # Принято некорректное сообщение
            except IncorrectDataRecivedError:
                logger.error(f'Не удалось декодировать полученное сообщение.')
            # Вышел таймаут соединения если errno = None, иначе обрыв соединения.
            except OSError as err:
                if err.errno:
                    logger.critical(f'Потеряно соединение с сервером.')
                    break
            # Проблемы с соединением
            except (ConnectionError,
                    ConnectionAbortedError,
                    ConnectionResetError,
                    json.JSONDecodeError):
                logger.critical(f'Потеряно соединение с сервером.')
                break
            # Если пакет корретно получен выводим в консоль и записываем в базу.
            else:
                if ACTION in message and message[ACTION] == MESSAGE \
                        and SENDER in message \
                        and DESTINATION in message \
                        and MESSAGE_TEXT in message \
                        and message[DESTINATION] == self.account_name:
                    print(f'\n Получено сообщение от пользователя '
                          f'{message[SENDER]}:\n{message[MESSAGE_TEXT]}')
                    # Захватываем работу с базой данных и сохраняем в неё сообщение
                    with database_lock:
                        try:
                            self.database.save_message(message[SENDER],
                                                       self.account_name,
                                                       message[MESSAGE_TEXT])
                        except Exception as e:
                            print(e)
                            logger.error('Ошибка взаимодействия с базой данных')

                    logger.info(f'Получено сообщение от пользователя '
                                f'{message[SENDER]}:\n{message[MESSAGE_TEXT]}')
                else:
                    logger.error(f'Получено некорректное сообщение с сервера: {message}')

    @staticmethod
    def main():
        # Сообщаем о запуске
        print('Консольный мессенджер. Клиентский модуль.')

        # Загружаем параметры командной строки
        server_address, server_port, client_name = arg_parser()

        # Если имя пользователя не было задано, необходимо запросить пользователя.
        if not client_name:
            client_name = input('Введите имя пользователя: ')

        logger.info(
            f'Запущен клиент с параметрами: адрес сервера: {server_address} , порт: {server_port}, '
            f'имя пользователя: {client_name}')

        # Инициализация сокета и сообщение серверу о нашем появлении
        try:
            transport = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            transport.connect((server_address, server_port))
            send_message(transport, create_presence(client_name))
            answer = process_response_ans(get_message(transport))
            logger.info(f'Установлено соединение с сервером. Ответ сервера: {answer}')
            print(f'Установлено соединение с сервером для пользователя: {client_name}')
        except json.JSONDecodeError:
            logger.error('Не удалось декодировать полученную Json строку.')
            exit(1)
        except ServerError as error:
            logger.error(f'При установке соединения сервер вернул ошибку: {error.text}')
            exit(1)
        except ReqFieldMissingError as missing_error:
            logger.error(f'В ответе сервера отсутствует необходимое поле {missing_error.missing_field}')
            exit(1)
        except (ConnectionRefusedError, ConnectionError):
            logger.critical(
                f'Не удалось подключиться к серверу {server_address}:{server_port}, '
                f'конечный компьютер отверг запрос на подключение.')
            exit(1)
        else:
            # Если соединение с сервером установлено корректно, запускаем клиентский процесс приёма сообщений
            mod_receiver = Receiver(client_name, transport)
            mod_receiver.daemon = True
            mod_receiver.start()

            # затем запускаем отправку сообщений и взаимодействие с пользователем.
            user_interface = Sender(client_name, transport)
            user_interface.daemon = True
            user_interface.start()
            logger.debug('Запущены процессы')

            # Watchdog основной цикл, если один из потоков завершён, то значит или потеряно соединение, или пользователь
            # ввёл exit. Поскольку все события обрабатываются в потоках, достаточно просто завершить цикл.
            while True:
                time.sleep(1)
                if mod_receiver.is_alive() and user_interface.is_alive():
                    continue
                break


# Функция запрос контакт листа
def contacts_list_request(sock, name):
    logger.debug(f'Запрос контакт листа для пользователя {name}')
    req = {
        ACTION: GET_CONTACTS,
        TIME: time.time(),
        USER: name
    }
    logger.debug(f'Сформирован запрос {req}')
    send_message(sock, req)
    ans = get_message(sock)
    logger.debug(f'Получен ответ {ans}')
    if RESPONSE in ans and ans[RESPONSE] == 202:
        return ans[LIST_INFO]
    else:
        raise ServerError


# Функция добавления пользователя в контакт лист
def add_contact(sock, username, contact):
    logger.debug(f'Создание контакта {contact}')
    req = {
        ACTION: ADD_CONTACT,
        TIME: time.time(),
        USER: username,
        ACCOUNT_NAME: contact
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 200:
        pass
    else:
        raise ServerError('Ошибка создания контакта')
    print('Удачное создание контакта.')


# Функция запроса списка известных пользователей
def user_list_request(sock, username):
    logger.debug(f'Запрос списка известных пользователей {username}')
    req = {
        ACTION: USERS_REQUEST,
        TIME: time.time(),
        ACCOUNT_NAME: username
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 202:
        return ans[LIST_INFO]
    else:
        raise ServerError


# Функция удаления пользователя из списка контактов
def remove_contact(sock, username, contact):
    logger.debug(f'Создание контакта {contact}')
    req = {
        ACTION: REMOVE_CONTACT,
        TIME: time.time(),
        USER: username,
        ACCOUNT_NAME: contact
    }
    send_message(sock, req)
    ans = get_message(sock)
    if RESPONSE in ans and ans[RESPONSE] == 200:
        pass
    else:
        raise ServerError('Ошибка удаления клиента')
    print('Удачное удаление')


# Функция инициализатор базы данных.
# Запускается при запуске, загружает данные в базу с сервера.
def database_load(sock, database, username):
    # Загружаем список известных пользователей
    try:
        users_list = user_list_request(sock, username)
    except ServerError:
        logger.error('Ошибка запроса списка известных пользователей.')
    else:
        database.add_users(users_list)

    # Загружаем список контактов
    try:
        contacts_list = contacts_list_request(sock, username)
    except ServerError:
        logger.error('Ошибка запроса списка контактов.')
    else:
        for contact in contacts_list:
            database.add_contact(contact)

# Функция генерирует запрос о присутствии клиента
# @log
def create_presence(account_name):
    out = {
        ACTION: PRESENCE,
        TIME: time.time(),
        USER: {
            ACCOUNT_NAME: account_name
        }
    }
    logger.debug(f'Сформировано {PRESENCE} сообщение для пользователя {account_name}')
    return out


# Функция разбирает ответ сервера на сообщение о присутствии, возвращает 200 если все ОК или генерирует
# исключение при ошибке.
# @log
def process_response_ans(message):
    logger.debug(f'Разбор приветственного сообщения от сервера: {message}')
    if RESPONSE in message:
        if message[RESPONSE] == 200:
            return '200 : OK'
        elif message[RESPONSE] == 400:
            raise ServerError(f'400 : {message[ERROR]}')
    raise ReqFieldMissingError(RESPONSE)


# Парсер аргументов командной строки
# @log
def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('addr', default=DEFAULT_IP_ADDRESS, nargs='?')
    parser.add_argument('port', default=DEFAULT_PORT, type=int, nargs='?')
    parser.add_argument('-n', '--name', default=None, nargs='?')
    namespace = parser.parse_args(sys.argv[1:])
    server_address = namespace.addr
    server_port = namespace.port
    client_name = namespace.name

    # проверим подходящий номер порта
    if not 1023 < server_port < 65536:
        logger.critical(
            f'Попытка запуска клиента с неподходящим номером порта: {server_port}. Допустимы адреса с 1024 до '
            f'65535. Клиент завершается.')
        exit(1)

    return server_address, server_port, client_name




if __name__ == '__main__':
    client = Receiver
    client.main()
