
## Profiling

### Zbieranie czasów wykonań danej funkcji
```python
import gupb.model.profiling.profile

class RandomController:

    @profile
    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        return random.choice(POSSIBLE_ACTIONS)
```

Kolejne czasy wykonania funkcji zbierane są w globalnym dictionary `gupb.model.profiling.PROFILE_RESULTS`,
z defaulta jest to `__qualname__` danej funkcji, czyli w tym przypadku `RandomController.decide`.
Można natomiast podać własną nazwę w dekoratorze `@profile(name="MyFunction"))`.
Należy zwrócić uwagę na to, że w przypadku wystąpienia tych samych nazw czasy będą zapisywane pod tą samą nazwą.


### Konfiguracja wypisywanych metryk
Brak wartości w konfiguracji lub pusta lista spowoduje niewypisanie metryk na koniec gry.
Możemy podać które metryki chcemy wypisać na koniec, np. pomijając osobne czasy każdego wykonania.
```python
CONFIGURATION = {
    'profiling_metrics': ['total', 'avg'],  # possible metrics ['all', 'total', 'avg']
}
```
Metryk wypisywane są na koniec wszystkich gier w metodzie `print_scores` w klasie `Runner`

```python
    def print_scores(self) -> None:
        ...
        if self.profiling_metrics:
            for func in PROFILE_RESULTS.keys():
                print_stats(func, **{m: True for m in self.profiling_metrics})
```


### Przykład zebranych metryk
```text
Stats for function: 'RandomController.decide'
  run times: ['1.31 ms', '0.75 ms', '0.78 ms', '0.71 ms', '4.20 ms', '1.34 ms', '1.01 ms', '0.45 ms', '0.45 ms', '3.07 ms', '0.57 ms', '0.44 ms', '18.73 ms', '0.46 ms', '3.55 ms', '0.47 ms', '0.44 ms', '0.69 ms', '1.23 ms', '8.26 ms', '1.10 ms', '0.90 ms', '0.67 ms', '0.78 ms', '4.21 ms', '1.16 ms', '0.92 ms', '0.75 ms', '0.74 ms', '3.17 ms', '0.55 ms', '0.53 ms', '0.75 ms', '0.74 ms', '4.04 ms', '0.85 ms', '1.03 ms', '1.12 ms', '1.04 ms', '6.56 ms', '1.22 ms', '0.77 ms', '0.78 ms', '0.72 ms', '3.39 ms', '0.80 ms', '0.76 ms', '0.69 ms', '0.63 ms', '3.63 ms', '0.76 ms', '0.70 ms', '0.61 ms', '0.88 ms', '3.66 ms', '0.71 ms', '0.59 ms', '0.77 ms', '0.76 ms', '3.53 ms', '0.70 ms', '1.17 ms', '0.97 ms', '0.75 ms', '3.33 ms', '0.88 ms', '0.75 ms', '0.67 ms', '0.63 ms', '3.64 ms', '0.90 ms', '0.88 ms', '0.91 ms', '1.50 ms', '11.34 ms', '3.13 ms', '2.71 ms', '3.45 ms', '1.46 ms', '4.20 ms', '0.64 ms', '0.79 ms', '0.78 ms', '0.70 ms', '3.32 ms', '0.84 ms', '0.87 ms', '0.77 ms', '0.70 ms', '4.24 ms', '0.98 ms', '1.03 ms', '0.99 ms', '1.46 ms', '6.82 ms', '1.36 ms', '1.20 ms', '1.51 ms', '1.64 ms', '8.38 ms', '1.39 ms', '1.75 ms', '1.80 ms', '1.84 ms', '10.01 ms', '3.68 ms', '3.35 ms', '2.20 ms', '1.93 ms', '12.29 ms', '2.49 ms', '2.23 ms', '2.68 ms', '3.27 ms', '10.14 ms', '1.01 ms', '0.77 ms', '0.96 ms', '0.89 ms', '4.01 ms', '0.76 ms', '1.01 ms', '0.80 ms', '0.82 ms', '3.42 ms', '0.69 ms', '0.68 ms', '0.72 ms', '0.61 ms', '3.80 ms', '0.95 ms', '0.79 ms', '0.74 ms', '0.91 ms', '3.99 ms', '0.74 ms', '0.69 ms', '0.92 ms', '0.88 ms', '3.67 ms', '0.62 ms', '0.79 ms', '0.72 ms', '0.68 ms', '3.31 ms', '0.86 ms', '0.72 ms', '0.70 ms', '0.63 ms', '3.60 ms', '0.76 ms', '0.69 ms', '0.59 ms', '0.76 ms', '3.45 ms', '0.68 ms', '0.54 ms', '0.74 ms', '0.67 ms', '3.26 ms', '0.53 ms', '0.71 ms', '0.70 ms', '0.66 ms', '3.26 ms', '0.74 ms', '0.67 ms', '0.65 ms', '0.54 ms', '3.32 ms', '0.64 ms', '0.64 ms', '0.60 ms', '0.68 ms', '3.32 ms', '0.74 ms', '0.57 ms', '0.75 ms', '0.70 ms', '3.32 ms', '0.61 ms', '0.76 ms', '0.69 ms', '0.59 ms', '3.23 ms', '0.76 ms', '0.64 ms', '0.61 ms', '0.58 ms', '3.35 ms', '0.70 ms', '0.59 ms', '0.56 ms', '0.75 ms', '3.32 ms', '0.60 ms', '0.58 ms', '0.73 ms', '0.67 ms', '3.37 ms', '0.55 ms', '0.76 ms', '0.67 ms', '0.60 ms', '3.28 ms', '0.80 ms', '0.96 ms', '0.70 ms', '0.63 ms', '3.53 ms', '0.76 ms', '0.79 ms', '0.57 ms', '0.79 ms', '3.47 ms', '0.71 ms', '0.62 ms', '0.85 ms', '0.79 ms', '3.37 ms', '0.58 ms', '0.83 ms', '0.81 ms', '0.68 ms', '3.37 ms', '0.78 ms', '0.72 ms', '0.59 ms', '0.59 ms', '3.40 ms', '0.75 ms', '0.64 ms', '0.58 ms', '0.77 ms', '3.31 ms', '0.58 ms', '0.60 ms', '0.75 ms', '0.75 ms', '3.27 ms', '0.55 ms', '0.78 ms', '0.68 ms', '0.67 ms', '3.43 ms', '0.82 ms', '0.67 ms', '0.68 ms', '0.61 ms', '3.39 ms', '0.72 ms', '0.68 ms', '0.69 ms', '0.71 ms', '3.35 ms', '18.92 ms']
  total run time: 445.20 ms
  average run time: 1.74 ms
```
