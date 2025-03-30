import neat

from gupb import runner
from gupb.controller import random
from gupb.controller.neat.kim_dzong_neat_jr import KimDzongNeatJuniorController
from gupb.controller.neat.neat_training.neat_evaluator import NeatEvaluatorV1, NeatEvaluator


def default_game_configuration(controller: KimDzongNeatJuniorController):
    return {
        'arenas': [
            'ordinary_chaos'
        ],
        'controllers': [
            controller,
            random.RandomController("Alice"),
            random.RandomController("Bob"),
            random.RandomController("Cecilia"),
            random.RandomController("Darius"),
        ],
        'start_balancing': False,
        'visualise': False,
        'show_sight': controller,
        'runs_no': 1,
        'profiling_metrics': [],
    }


def get_evaluator(name, neat_controller, game_runner) -> NeatEvaluator:
    if name == "eval_v1":
        return NeatEvaluatorV1(
            controller=neat_controller,
            runner=game_runner
        )
    else:
        raise ValueError(f"{name} evaluator doesn't exist")


def eval_genomes_with_evaluator(evaluator_name, genomes, config):
    for genome_id, genome in genomes:
        genome.fitness = 0
        net = neat.nn.FeedForwardNetwork.create(genome, config)
        neat_controller = KimDzongNeatJuniorController(net=net)

        game_config = default_game_configuration(neat_controller)
        game_runner = runner.Runner(game_config)
        game_runner.run()

        evaluator = get_evaluator(evaluator_name, neat_controller, game_runner)

        genome.fitness += evaluator.calculate_score()


def run_neat_training(config: neat.Config, n: int, evaluator_name: str):
    population = neat.Population(config)
    population.add_reporter(neat.StdOutReporter(True))
    population.add_reporter(neat.StatisticsReporter())

    eval_genomes = lambda genomes, neat_config: eval_genomes_with_evaluator(evaluator_name, genomes, neat_config)
    winner = population.run(eval_genomes, n)
    return winner
