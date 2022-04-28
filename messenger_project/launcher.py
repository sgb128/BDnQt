import subprocess

process = []

while True:
    action = input('Выберите действие: q - выход , s - запустить сервер, k - запустить клиенты, x - закрыть все окна:')

    if action == 'q':
        break
    elif action == 's':
        process.append(
            subprocess.Popen(
                'python server.py',
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        )
    elif action == 'k':
        clients_count = int(input('Введите количество тестовых клиентов для запуска: '))
        # Запускаем клиентов:
        for i in range(clients_count):
            process.append(
                subprocess.Popen(f'python client.py -n sgb{i + 1}', creationflags=subprocess.CREATE_NEW_CONSOLE))
    elif action == 'x':
        while process:
            victim = process.pop()
            victim.kill()
