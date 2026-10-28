class Nivel:
    def __init__(self, largura: int, altura: int, paredes=None):
        if largura < 3 or altura < 3:
            raise ValueError("O nível tem de ter pelo menos 3 posições em cada dimensão.")
        self.largura = largura
        self.altura = altura
        self.paredes = set(paredes or ())
        self.inimigos = []

    def e_posicao_valida(self, x: int, y: int) -> bool:
        return (
            0 <= x < self.largura
            and 0 <= y < self.altura
            and (x, y) not in self.paredes
        )

    def adicionar_inimigo(self, inimigo) -> None:
        if not self.e_posicao_valida(inimigo.x, inimigo.y):
            raise ValueError("O inimigo tem de começar numa posição válida.")
        if self.posicao_ocupada(inimigo.x, inimigo.y):
            raise ValueError("Já existe uma entidade nessa posição.")
        self.inimigos.append(inimigo)

    def posicao_ocupada(self, x: int, y: int, ignorar=None) -> bool:
        return any(
            inimigo is not ignorar and inimigo.vivo
            and inimigo.x == x and inimigo.y == y
            for inimigo in self.inimigos
        )

    def inimigo_em(self, x: int, y: int):
        return next(
            (
                inimigo for inimigo in self.inimigos
                if inimigo.vivo and inimigo.x == x and inimigo.y == y
            ),
            None,
        )

    def remover_inimigos_derrotados(self) -> int:
        derrotados = len(self.inimigos) - sum(inimigo.vivo for inimigo in self.inimigos)
        self.inimigos = [inimigo for inimigo in self.inimigos if inimigo.vivo]
        return derrotados

    def atualizar_inimigos(self, jogador) -> None:
        for inimigo in tuple(self.inimigos):
            if inimigo.vivo and jogador.vivo:
                inimigo.atualizar(jogador, self)
        self.remover_inimigos_derrotados()