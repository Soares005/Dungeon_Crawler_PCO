from entidade import Entidade


class Player(Entidade):
    def __init__(self, nome: str, hp: int, ataque: int, x: int, y: int):
        super().__init__(nome, hp, ataque, x, y)
        self.inventario: list[str] = []
        self.inimigos_derrotados = 0

    def mover(self, dx: int, dy: int, nivel) -> bool:
        return super().mover(dx, dy, nivel)