from .pudzian import Pudzian

__all__ = [
    "Pudzian",
    "POTENTIAL_CONTROLLERS",
]

# Zarejestrowana instancja tylko GRA (inference), nie trenuje — więc actor/CPU,
# bez bufora 1.5M i bez alokacji na GPU. Inaczej KAŻDY proces-dziecko spawnu
# (14 aktorów) re-importuje ten moduł i buduje pełny learner-brain na CUDA,
# co lokalnie kończy się CUDA OOM + numpy MemoryError. load_from_disk=True
# pozostaje, by w realnych grach wczytać wytrenowany model.
POTENTIAL_CONTROLLERS = [
    Pudzian("Pudzian", brain_mode="actor", device="cpu"),
]
