DEBUG = True


def debug_print(*args):
    if not DEBUG:
        return
    print(args)
