"""Various helpers for time managament"""
import datetime
from time import gmtime, strftime

def get_gmt_time_as_string():
    """Wrapper to get strigified GMT time"""
    return strftime("%Y-%m-%d %H:%M:%S", gmtime())

def get_gmt_time() -> datetime.datetime:
    """Wrapper to get GMT time"""
    return datetime.datetime.now(datetime.UTC)