from enum import Enum, auto

import pygame

from config import (
    ALTURA_JANELA,
    COR_DESTAQUE,
    COR_ESQUELETO,
    COR_FUNDO,
    COR_GOBLIN,
    COR_JOGADOR,
    COR_PAREDE,
    COR_TEXTO,
    COR_CHAO,
    FPS,
    LARGURA_JANELA,
    TAMANHO_TILE,
)
from hall_of_fame import HallOfFame
from inimigos import Esqueleto, Goblin
from jogador import Player
from nivel import Nivel


class EstadoJogo(Enum):
    MENU = auto()
    A_JOGAR = auto()
    GAME_OVER = auto()
    VITORIA = auto()


class Jogo:
    def __init__(self):
        self.estado = EstadoJogo.MENU
        self.ecra_pygame = None
        self.relogio = None
        self.nivel = None
        self.jogador = None
        self.hall_of_fame = HallOfFame()
        self._score_guardado = False

    def iniciar(self) -> None:
        pygame.init()
        self.ecra_pygame = pygame.display.set_mode(
            (LARGURA_JANELA, ALTURA_JANELA)
        )
        pygame.display.set_caption("Dungeon Crawler")
        self.relogio = pygame.time.Clock()
        self._loop_principal()
        pygame.quit()

    def _novo_jogo(self) -> None:
        largura = LARGURA_JANELA // TAMANHO_TILE
        altura = ALTURA_JANELA // TAMANHO_TILE
        paredes = {
            *((x, 0) for x in range(largura)),
            *((x, altura - 1) for x in range(largura)),
            *((0, y) for y in range(altura)),
            *((largura - 1, y) for y in range(altura)),
            (7, 4), (7, 5), (7, 6), (12, 8), (13, 8), (14, 8),
        }
        self.nivel = Nivel(largura, altura, paredes)
        self.jogador = Player("Jogador", hp=10, ataque=3, x=1, y=1)
        self.nivel.adicionar_inimigo(Goblin(largura - 3, 3))
        self.nivel.adicionar_inimigo(Esqueleto(largura - 3, altura - 3))
        self.estado = EstadoJogo.A_JOGAR
        self._score_guardado = False

    def _loop_principal(self) -> None:
        em_execucao = True
        while em_execucao:
            self.relogio.tick(FPS)
            for evento in pygame.event.get():
                if evento.type == pygame.QUIT:
                    em_execucao = False
                elif evento.type == pygame.KEYDOWN:
                    self._processar_tecla(evento.key)
            self._desenhar()
            pygame.display.flip()

    def _processar_tecla(self, tecla: int) -> None:
        if self.estado == EstadoJogo.MENU:
            if tecla in (pygame.K_RETURN, pygame.K_SPACE):
                self._novo_jogo()
            return
        if self.estado in (EstadoJogo.GAME_OVER, EstadoJogo.VITORIA):
            if tecla in (pygame.K_RETURN, pygame.K_SPACE):
                self.estado = EstadoJogo.MENU
            return

        movimentos = {
            pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
            pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
            pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
            pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
        }
        if tecla in movimentos:
            if self.jogador.mover(*movimentos[tecla], self.nivel):
                self.nivel.atualizar_inimigos(self.jogador)
        elif tecla == pygame.K_SPACE:
            self._atacar()
            self.nivel.atualizar_inimigos(self.jogador)

        if not self.jogador.vivo:
            self.estado = EstadoJogo.GAME_OVER
        elif not self.nivel.inimigos:
            self.estado = EstadoJogo.VITORIA
        if self.estado in (EstadoJogo.GAME_OVER, EstadoJogo.VITORIA):
            self._guardar_score()

    def _atacar(self) -> None:
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            inimigo = self.nivel.inimigo_em(
                self.jogador.x + dx, self.jogador.y + dy
            )
            if inimigo is not None:
                self.jogador.atacar(inimigo)
                self.jogador.inimigos_derrotados += self.nivel.remover_inimigos_derrotados()
                return

    def _guardar_score(self) -> None:
        if self._score_guardado:
            return
        self.hall_of_fame.guardar_score(
            "Jogador", self.jogador.inimigos_derrotados
        )
        self._score_guardado = True

    def _desenhar(self) -> None:
        self.ecra_pygame.fill(COR_FUNDO)
        fonte = pygame.font.Font(None, 30)

        if self.estado == EstadoJogo.MENU:
            self._texto(fonte, "DUNGEON CRAWLER", COR_DESTAQUE, 190, 150)
            self._texto(fonte, "ENTER ou ESPACO para começar", COR_TEXTO, 145, 210)
        elif self.estado == EstadoJogo.A_JOGAR:
            self._desenhar_nivel()
            self._texto(
                fonte,
                f"HP: {self.jogador.hp}   Inimigos derrotados: "
                f"{self.jogador.inimigos_derrotados}",
                COR_TEXTO,
                12,
                8,
            )
        else:
            titulo = "VITORIA!" if self.estado == EstadoJogo.VITORIA else "GAME OVER"
            self._texto(fonte, titulo, COR_DESTAQUE, 250, 165)
            self._texto(fonte, "ENTER para voltar ao menu", COR_TEXTO, 180, 215)

    def _desenhar_nivel(self) -> None:
        for y in range(self.nivel.altura):
            for x in range(self.nivel.largura):
                cor = COR_PAREDE if (x, y) in self.nivel.paredes else COR_CHAO
                pygame.draw.rect(
                    self.ecra_pygame,
                    cor,
                    (x * TAMANHO_TILE, y * TAMANHO_TILE,
                     TAMANHO_TILE - 1, TAMANHO_TILE - 1),
                )
        for inimigo in self.nivel.inimigos:
            cor = COR_GOBLIN if isinstance(inimigo, Goblin) else COR_ESQUELETO
            self._desenhar_entidade(inimigo.x, inimigo.y, cor)
        self._desenhar_entidade(self.jogador.x, self.jogador.y, COR_JOGADOR)

    def _desenhar_entidade(self, x: int, y: int, cor) -> None:
        margem = 5
        pygame.draw.rect(
            self.ecra_pygame,
            cor,
            (x * TAMANHO_TILE + margem, y * TAMANHO_TILE + margem,
             TAMANHO_TILE - margem * 2, TAMANHO_TILE - margem * 2),
        )

    def _texto(self, fonte, texto: str, cor, x: int, y: int) -> None:
        superficie = fonte.render(texto, True, cor)
        self.ecra_pygame.blit(superficie, (x, y))
