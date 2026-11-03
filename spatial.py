"""Spatial hash grid used to keep collision checks fast with hundreds of enemies.

Instead of testing every projectile against every enemy (O(n*m)), enemies are
bucketed by the grid cell their centre is in. A query only looks at the cells
that overlap the search circle.
"""
from settings import GRID_CELL, MAX_ENEMY_RADIUS


class SpatialGrid:
    def __init__(self, cell_size=GRID_CELL):
        self._cell = cell_size
        self._cells = {}

    def rebuild(self, objects):
        """Clear the grid and insert every object (anything with a .pos)."""
        cells = {}
        size = self._cell
        for obj in objects:
            key = (int(obj.pos.x // size), int(obj.pos.y // size))
            bucket = cells.get(key)
            if bucket is None:
                cells[key] = [obj]
            else:
                bucket.append(obj)
        self._cells = cells

    def query(self, pos, radius):
        """Yield objects whose circle *might* touch the circle (pos, radius).

        The caller still performs the exact distance test; this only narrows
        the candidates. The radius is widened by the largest enemy radius so
        big enemies whose centre is in a neighbouring cell are not missed.
        """
        size = self._cell
        reach = radius + MAX_ENEMY_RADIUS
        x0 = int((pos[0] - reach) // size)
        x1 = int((pos[0] + reach) // size)
        y0 = int((pos[1] - reach) // size)
        y1 = int((pos[1] + reach) // size)
        cells = self._cells
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                bucket = cells.get((cx, cy))
                if bucket:
                    yield from bucket
