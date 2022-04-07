"""
Написать функцию host_range_ping() для перебора ip-адресов из заданного диапазона.
Меняться должен только последний октет каждого адреса.
По результатам проверки должно выводиться соответствующее сообщение.
"""
from task1 import host_ping
from ipaddress import ip_address


def host_range_ping():
    while True:
        first_ip = input('Введите стартовый ip-адрес:')
        try:
            ip_val = int(first_ip.split('.')[3])
            break
        except:
            print('Вероятно вы ввели некорректный ip-адрес')

    while True:
        cnt = input('Введите длину диапазона ip-адресов:')
        if not cnt.isnumeric():  # списал проверку
            print('Введено не целое число, или вообще не число. Необходимо целое число.')
        else:
            if (ip_val + int(cnt)) > 254:
                print('Слишком большой диапазон.')
            else:
                break

    addresses = []
    [addresses.append(str(ip_address(first_ip)+i)) for i in range(int(cnt))]
    return host_ping(addresses)


if __name__ == '__main__':
    host_range_ping()
