import datetime


def current_datetime():
    return datetime.datetime.now()


def current_time():
    return datetime.datetime.now().time()


def is_a_weekend(date):
    return date.weekday() > 5


def in_time_range(start, now, end):
    if start < end:
        return now >= start and now <= end
    else:  # time interval crosses midnight
        return now >= start or now <= end
