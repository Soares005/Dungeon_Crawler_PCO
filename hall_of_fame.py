import csv
import logging
from pathlib import Path


class HallOfFame:
    def __init__(self, ficheiro="scores.txt"):
        self.ficheiro = Path(ficheiro)

    def guardar_score(self, nome: str, pontuacao: int) -> bool:
        nome = nome.strip()
        if not nome:
            raise ValueError("O nome não pode estar vazio.")
        if pontuacao < 0:
            raise ValueError("A pontuação não pode ser negativa.")

        try:
            with self.ficheiro.open("a", encoding="utf-8", newline="") as arquivo:
                csv.writer(arquivo, delimiter="\t").writerow([nome, pontuacao])
        except (OSError, UnicodeError) as erro:
            logging.warning("Não foi possível guardar a pontuação: %s", erro)
            return False
        return True

    def carregar_scores(self, limite: int = 5) -> list[tuple[str, int]]:
        if limite < 0:
            raise ValueError("O limite não pode ser negativo.")

        scores = []
        try:
            with self.ficheiro.open("r", encoding="utf-8", newline="") as arquivo:
                for linha, campos in enumerate(
                    csv.reader(arquivo, delimiter="\t"), start=1
                ):
                    if not campos:
                        continue
                    if len(campos) != 2:
                        logging.warning("Pontuação inválida na linha %s.", linha)
                        continue
                    try:
                        nome, valor = campos
                        valor = int(valor)
                        if not nome.strip() or valor < 0:
                            raise ValueError
                    except ValueError:
                        logging.warning("Pontuação inválida na linha %s.", linha)
                        continue
                    scores.append((nome, valor))
        except FileNotFoundError:
            return []
        except (OSError, UnicodeError) as erro:
            logging.warning("Não foi possível ler as pontuações: %s", erro)
            return []

        scores.sort(key=lambda score: score[1], reverse=True)
        return scores[:limite]
