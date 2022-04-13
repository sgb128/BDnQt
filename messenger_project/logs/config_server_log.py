import sys
import logging as log
import logging.handlers
import os
from common.variables import LOGGING_LEVEL
sys.path.append('../')

# создаём формировщик логов (formatter):
server_formatter = log.Formatter('%(asctime)s %(levelname)s %(filename)s %(message)s')

# Подготовка имени файла для логирования
path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, 'server.log')

# создаём потоки вывода логов
steam = log.StreamHandler(sys.stderr)
steam.setFormatter(server_formatter)
steam.setLevel(log.DEBUG)
log_file = log.handlers.TimedRotatingFileHandler(path, encoding='utf8', interval=1, when='D')
log_file.setFormatter(server_formatter)

# создаём регистратор и настраиваем его
logger = log.getLogger('server_dist')
logger.addHandler(steam)
logger.addHandler(log_file)
logger.setLevel(log.INFO)

# отладка
if __name__ == '__main__':
    logger.critical('Test critical event')
    logger.error('Test error event')
    logger.debug('Test debug event')
    logger.info('Test info event')
