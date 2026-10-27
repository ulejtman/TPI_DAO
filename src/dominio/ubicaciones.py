from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Ubicacion(ABC):
    id: int
    nombre: str
    direccion: str
    telefono: str = ""
    activo: bool = True

    @property
    @abstractmethod
    def tipo(self) -> str: ...


@dataclass(frozen=True)
class CentroDistribucion(Ubicacion):
    @property
    def tipo(self):
        return "CD"


@dataclass(frozen=True)
class LocalMinorista(Ubicacion):
    @property
    def tipo(self):
        return "LOCAL"
