"""
Написать функцию host_ping(), в которой с помощью утилиты ping будет проверяться доступность сетевых узлов.
Аргументом функции является список, в котором каждый сетевой узел должен быть представлен именем хоста или ip-адресом.
В функции необходимо перебирать ip-адреса и проверять их доступность с выводом соответствующего сообщения
(«Узел доступен», «Узел недоступен»). При этом ip-адрес сетевого узла должен создаваться с помощью функции ip_address().
"""

from subprocess import Popen, PIPE
from ipaddress import ip_address


def host_ping(adresses: list, tout=500, rq=1):
    res = {'Доступные узлы': "",
           'Недоступные узлы': ""}

    for address in adresses:
        try:
            address = ip_address(address)
        except:
            pass
        process = Popen(['ping', f'{address}', '-w', f'{tout}', '-n', f'{rq}'], shell=False, stdout=PIPE)
        process.wait()

        if process.returncode:
            res['Недоступные узлы'] += f"{str(address)}\n"
            r_str = f'{address} - Узел недоступен'
        else:
            res['Доступные узлы'] += f"{str(address)}\n"
            r_str = f'{address} - Узел доступен'
        print(r_str)
    return res


if __name__ == '__main__':
    ips = ['www.google.com', '8.8.8.8', '192.168.0.1', '192.168.0.30', '192.168.0.40']
    host_ping(ips)
