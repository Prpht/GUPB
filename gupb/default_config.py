from gupb.controller import bandyta, keyboard

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        keyboard.KeyboardController(),
        bandyta.Bandyta("1.0")
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
