"""
Написать функцию host_range_ping_tab(), возможности которой основаны на функции из примера 2.
Но в данном случае результат должен быть итоговым по всем ip-адресам, представленным в табличном формате
(использовать модуль tabulate).
"""
from tabulate import tabulate
from task2 import host_range_ping


def host_range_ping_tab():
    result = host_range_ping()
    print(tabulate([result], headers='keys', tablefmt='pipe', stralign='left'))


if __name__ == '__main__':
    host_range_ping_tab()
