import tempfile
import unittest
from pathlib import Path

from hall_of_fame import HallOfFame
from inimigos import Esqueleto, Goblin
from jogador import Player
from nivel import Nivel


class LogicaJogoTests(unittest.TestCase):
    def test_jogador_nao_atravessa_parede_ou_inimigo(self):
        nivel = Nivel(5, 5, paredes={(2, 1)})
        jogador = Player("Herói", 10, 3, 1, 1)
        goblin = Goblin(1, 2)
        nivel.adicionar_inimigo(goblin)

        self.assertFalse(jogador.mover(1, 0, nivel))
        self.assertFalse(jogador.mover(0, 1, nivel))
        self.assertEqual((jogador.x, jogador.y), (1, 1))

    def test_inimigo_persegue_e_ataca_com_dano_polimorfico(self):
        nivel = Nivel(7, 7)
        jogador = Player("Herói", 10, 3, 2, 2)
        goblin = Goblin(4, 2)
        esqueleto = Esqueleto(2, 4)
        nivel.adicionar_inimigo(goblin)
        nivel.adicionar_inimigo(esqueleto)

        nivel.atualizar_inimigos(jogador)
        self.assertEqual((goblin.x, goblin.y), (3, 2))
        self.assertEqual((esqueleto.x, esqueleto.y), (2, 3))
        nivel.atualizar_inimigos(jogador)
        self.assertEqual(jogador.hp, 6)

    def test_dano_nao_reduz_hp_abaixo_de_zero(self):
        jogador = Player("Herói", 2, 3, 1, 1)

        self.assertEqual(jogador.receber_dano(5), 2)
        self.assertEqual(jogador.hp, 0)
        self.assertFalse(jogador.vivo)

    def test_hall_of_fame_guarda_e_ordena_scores(self):
        with tempfile.TemporaryDirectory() as pasta:
            ficheiro = Path(pasta) / "scores.txt"
            hall = HallOfFame(ficheiro)
            hall.guardar_score("Ana", 2)
            hall.guardar_score("Rui", 4)
            hall.guardar_score("Inês", 1)

            self.assertEqual(
                hall.carregar_scores(limite=2), [("Rui", 4), ("Ana", 2)]
            )

    def test_ficheiro_em_falta_nao_interrompe_o_jogo(self):
        with tempfile.TemporaryDirectory() as pasta:
            hall = HallOfFame(Path(pasta) / "inexistente.txt")

            self.assertEqual(hall.carregar_scores(), [])


if __name__ == "__main__":
    unittest.main()
