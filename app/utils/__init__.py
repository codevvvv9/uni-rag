from time import tzset
# 根据系统环境变量 TZ 重新设置本地时区信息
tzset()

# 从当前文件夹的 get_logger.py 文件里，导入 get_logger 函数。
from .get_logger import get_logger
logger = get_logger()