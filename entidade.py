class Entidade:
    def __init__(self, nome: str, hp: int, ataque: int, x: int, y: int):
        if hp <= 0:
            raise ValueError("O HP inicial tem de ser positivo.")
        if ataque < 0:
            raise ValueError("O ataque não pode ser negativo.")
        self.nome = nome
        self._hp = hp
        self._ataque = ataque
        self.x = x
        self.y = y

    @property
    def hp(self) -> int:
        return self._hp

    @property
    def ataque(self) -> int:
        return self._ataque

    @property
    def vivo(self) -> bool:
        return self._hp > 0

    def mover(self, dx: int, dy: int, nivel) -> bool:
        if abs(dx) + abs(dy) != 1:
            raise ValueError("A entidade só pode mover-se uma posição de cada vez.")

        novo_x = self.x + dx
        novo_y = self.y + dy
        if not nivel.e_posicao_valida(novo_x, novo_y):
            return False
        if nivel.posicao_ocupada(novo_x, novo_y, ignorar=self):
            return False

        self.x = novo_x
        self.y = novo_y
        return True

    def receber_dano(self, dano: int) -> int:
        if dano < 0:
            raise ValueError("O dano não pode ser negativo.")
        dano_aplicado = min(dano, self._hp)
        self._hp -= dano_aplicado
        return dano_aplicado

    def atacar(self, alvo: "Entidade") -> int:
        return alvo.receber_dano(self._ataque)