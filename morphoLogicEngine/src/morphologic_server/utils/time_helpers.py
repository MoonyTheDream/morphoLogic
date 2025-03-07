"""Various helpers for time managament"""
from time import gmtime, strftime

def get_gmt_time():
    """Wrapper to get strigified GMT time"""
    return strftime("%Y-%m-%d %H:%M:%S", gmtime())