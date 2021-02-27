import datetime


def current_time():
    return datetime.datetime.now().time()


def in_time_range(start, now, end):
    if start < end:
        return now >= start and now <= end
    else:  # time interval crosses midnight
        return now >= start or now <= end
