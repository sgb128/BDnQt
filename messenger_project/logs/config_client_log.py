import sys
import os
import logging as log
from common.variables import LOGGING_LEVEL
sys.path.append('../')

# создаём формировщик логов (formatter):
client_formatter = log.Formatter('%(asctime)s %(levelname)s %(filename)s %(message)s')

# Подготовка имени файла для логирования
path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, 'client.log')

# создаём потоки вывода логов
steam = log.StreamHandler(sys.stderr)
steam.setFormatter(client_formatter)
steam.setLevel(log.ERROR)
log_file = log.FileHandler(path, encoding='utf8')
log_file.setFormatter(client_formatter)

# создаём регистратор и настраиваем его
logger = log.getLogger('client_dist')
logger.addHandler(steam)
logger.addHandler(log_file)
logger.setLevel(log.INFO)

# отладка
if __name__ == '__main__':
    logger.critical('Test critical event')
    logger.error('Test error event')
    logger.debug('Test debug event')
    logger.info('Test info event')
