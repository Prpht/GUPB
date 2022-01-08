import collections
import json


def aggregate_scores(log: str, max_games_no: int) -> dict[str, int]:
    i = 0
    scores = collections.defaultdict(int)
    with open(f"../../results/together/{log}.json") as file:
        for line in file.readlines():
            data = json.loads(line)
            if data['type'] == 'GameStartReport':
                i += 1
                if i > max_games_no:
                    break
            elif data['type'] == 'ControllerScoreReport':
                scores[data['value']['controller_name']] += data['value']['score']
    return dict(sorted(scores.items(), key=lambda x: x[1]))


def main() -> None:
    result = aggregate_scores("gupb__2022_01_02_15_58_34", 500)
    print(result)


if __name__ == '__main__':
    main()
