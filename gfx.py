"""Small drawing helpers shared by the renderer, the particles and the UI.

Expensive surfaces (glows, translucent circles) are generated once and cached,
so the main loop only blits them.
"""
import math

import pygame

_glow_cache = {}
_circle_cache = {}


def clamp_color(color):
    return tuple(max(0, min(255, int(c))) for c in tuple(color)[:3])


def scale_color(color, factor):
    return clamp_color([c * factor for c in color[:3]])


def lerp_color(a, b, t):
    t = max(0.0, min(1.0, t))
    return clamp_color([a[i] + (b[i] - a[i]) * t for i in range(3)])


def glow(radius, color):
    """A soft radial gradient, meant to be blitted with BLEND_RGB_ADD."""
    radius = max(2, int(radius) // 2 * 2)
    key = (radius, tuple(color[:3]))
    surface = _glow_cache.get(key)
    if surface is None:
        size = radius * 2
        surface = pygame.Surface((size, size))
        surface.fill((0, 0, 0))
        steps = min(radius, 24)
        for i in range(steps, 0, -1):
            t = i / steps
            strength = (1 - t) ** 1.8
            pygame.draw.circle(surface, scale_color(color, strength * 0.9), (radius, radius),
                               max(1, int(radius * t)))
        _glow_cache[key] = surface
        if len(_glow_cache) > 600:
            _glow_cache.clear()
    return surface


def blit_glow(target, pos, radius, color):
    surface = glow(radius, color)
    r = surface.get_width() // 2
    target.blit(surface, (int(pos[0]) - r, int(pos[1]) - r), special_flags=pygame.BLEND_RGB_ADD)


def alpha_circle(radius, color, alpha, width=0):
    """Translucent circle surface (cached; radius rounded to 4 px steps)."""
    radius = max(2, int(radius) // 4 * 4)
    key = (radius, tuple(color[:3]), int(alpha) // 8 * 8, width)
    surface = _circle_cache.get(key)
    if surface is None:
        surface = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surface, (*color[:3], int(alpha) // 8 * 8), (radius + 1, radius + 1), radius, width)
        _circle_cache[key] = surface
        if len(_circle_cache) > 800:
            _circle_cache.clear()
    return surface


def blit_alpha_circle(target, pos, radius, color, alpha, width=0):
    surface = alpha_circle(radius, color, alpha, width)
    half = surface.get_width() // 2
    target.blit(surface, (int(pos[0]) - half, int(pos[1]) - half))


def jagged_line(points, rng, jitter=10, segments=4):
    """Turn a polyline into a jagged lightning bolt."""
    result = [points[0]]
    for a, b in zip(points, points[1:]):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length
        for s in range(1, segments):
            t = s / segments
            offset = rng.uniform(-jitter, jitter)
            result.append((ax + dx * t + nx * offset, ay + dy * t + ny * offset))
        result.append(b)
    return result


def regular_polygon(center, radius, sides, rotation=0.0):
    cx, cy = center
    return [(cx + math.cos(rotation + math.tau * i / sides) * radius,
             cy + math.sin(rotation + math.tau * i / sides) * radius) for i in range(sides)]
