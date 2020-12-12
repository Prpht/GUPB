import time

PROFILE_RESULTS = {}


def profile(method):
    """ Profiling decorator. """

    def wrapper(*args, **kw):
        start_time = time.time()

        result = method(*args, **kw)

        elapsed_time = time.time() - start_time
        PROFILE_RESULTS.setdefault(method.__name__, []).append(elapsed_time)
        return result

    return wrapper  # Decorated method (need to return this).


def print_stats(method_name, all=False, total=True, avg=True):
    if method_name not in PROFILE_RESULTS:
        print("{!r} wasn't profiled, nothing to display.".format(method_name))
    else:
        runtimes = PROFILE_RESULTS[method_name]
        total_runtime = sum(runtimes)
        average = total_runtime / len(runtimes)
        print('Stats for method: {!r}'.format(method_name))
        if all:
            print('  run times: {}'.format(runtimes))
        if total:
            print('  total run time: {}'.format(total_runtime))
        if avg:
            print('  average run time: {}'.format(average))

