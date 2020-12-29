import time

PROFILE_RESULTS = {}


def profile(_func=None, name=None):
    """ Profiling decorator. """

    def decorator(func):
        def wrapper(*args, **kw):
            start_time = time.time()

            result = func(*args, **kw)

            elapsed_time = time.time() - start_time
            key = name if name else func.__qualname__
            PROFILE_RESULTS.setdefault(key, []).append(elapsed_time)
            return result

        return wrapper

    return decorator(_func) if _func else decorator


def humanize_time(time_diff_secs):
    intervals = [('s', 1000), ('m', 60), ('h', 60)]

    unit, number = 'ms', abs(time_diff_secs) * 1000
    for new_unit, ratio in intervals:
        new_number = float(number) / ratio
        if new_number < 2:
            break
        unit, number = new_unit, new_number
    shown_num = number
    return '{:.2f} {}'.format(shown_num, unit)


def print_stats(function_name, all=False, total=True, avg=True):
    if function_name not in PROFILE_RESULTS:
        print("{!r} wasn't profiled, nothing to display.".format(function_name))
    else:
        runtimes = PROFILE_RESULTS[function_name]
        total_runtime = sum(runtimes)
        average = total_runtime / len(runtimes)
        print('Stats for function: {!r}'.format(function_name))
        if all:
            print('  run times: {}'.format([humanize_time(time) for time in runtimes]))
        if total:
            print('  total run time: {}'.format(humanize_time(total_runtime)))
        if avg:
            print('  average run time: {}'.format(humanize_time(average)))

