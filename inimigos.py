from abc import ABC, abstractmethod

from entidade import Entidade


class Enemy(Entidade, ABC):
    def __init__(
        self, nome: str, hp: int, ataque: int, x: int, y: int, raio_visao: int = 5
    ):
        super().__init__(nome, hp, ataque, x, y)
        if raio_visao < 1:
            raise ValueError("O raio de visão tem de ser positivo.")
        self.raio_visao = raio_visao

    @abstractmethod
    def atacar(self, alvo: Entidade) -> int:
        raise NotImplementedError

    def atualizar(self, jogador, nivel) -> None:
        distancia = abs(jogador.x - self.x) + abs(jogador.y - self.y)
        if distancia == 1:
            self.atacar(jogador)
            return
        if distancia > self.raio_visao:
            return

        passos = []
        if jogador.x != self.x:
            passos.append((1 if jogador.x > self.x else -1, 0))
        if jogador.y != self.y:
            passos.append((0, 1 if jogador.y > self.y else -1))

        for dx, dy in passos:
            if self.mover(dx, dy, nivel):
                break


class Goblin(Enemy):
    def __init__(self, x: int, y: int):
        super().__init__("Goblin", hp=5, ataque=1, x=x, y=y, raio_visao=5)

    def atacar(self, alvo: Entidade) -> int:
        return alvo.receber_dano(self.ataque)


class Esqueleto(Enemy):
    def __init__(self, x: int, y: int):
        super().__init__("Esqueleto", hp=8, ataque=2, x=x, y=y, raio_visao=6)

    def atacar(self, alvo: Entidade) -> int:
        return alvo.receber_dano(self.ataque + 1)
