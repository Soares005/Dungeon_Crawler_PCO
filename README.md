# Dungeon Crawler

Projeto académico de Programação Orientada a Objetos, desenvolvido em Python
com Pygame.

## Executar

Requer Python 3.10 ou superior.

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Controlos

- `Enter` ou `Espaço`: começar / voltar ao menu
- `W`, `A`, `S`, `D` ou setas: mover
- `Espaço`: atacar um inimigo adjacente

O jogo usa formas desenhadas pelo Pygame, pelo que não precisa de sprites para
arrancar. As pontuações (inimigos derrotados) são guardadas em `scores.txt`.
