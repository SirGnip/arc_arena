import random

import pygame
from gnp_pygame import gnipMath
from gnp_pygame import gnpactor


class TextActor(gnpactor.LifetimeActor):
    def __init__(self, font_mgr, font, font_size, text, rect, color, align_horiz, align_vert, lifetime):
        super(TextActor, self).__init__(lifetime)
        self._font_mgr = font_mgr
        self._font = font
        self._font_size = font_size
        self._text = text
        self._rect = rect
        self._color = color
        self._align_horiz = align_horiz
        self._align_vert = align_vert

    def draw(self, surface):
        self._font_mgr.draw(
            surface,
            self._font,
            self._font_size,
            self._text,
            self._rect,
            self._color,
            self._align_horiz,
            self._align_vert
        )


def make_grid_points(rect, spacing):
    """given a rect, return a list of points in a grid (not on the edges) with given spacing"""
    pts = []
    y = rect.top + spacing
    while y <= rect.bottom - spacing:
        x = rect.left + spacing
        while x <= rect.right - spacing:
            pts.append(gnipMath.cVector2(x, y))
            x += spacing
        y += spacing
    assert len(pts) > 0, '_make_grid_points generated 0 points from rect %s with spacing=%s' % (str(rect), spacing)
    return pts


def get_jitter_vect(xdelta, ydelta):
    """Return random vector which can be added to other vectors to jitter them slightly"""
    return gnipMath.cVector2(
        random.randint(-xdelta, xdelta),
        random.randint(-ydelta, ydelta)
    )


def withalpha(trg_surface, drawing_callback):
    """Run the drawing_callback (assumed to be a pygame.draw.* function) and blit it to given surface.
    pygame.draw functions don't do alpha blending, but they do preserve alpha in the color. So, if
    you draw something with alpha using pygame.draw*, you need to blit it to get alpha blending."""
    s = pygame.Surface(trg_surface.get_size(), pygame.SRCALPHA)
    drawing_callback(s)
    trg_surface.blit(s, (0, 0))


def withalphamulti(trg_surface, drawing_callbacks):
    """A multi-callback-function version of withalpha"""
    s = pygame.Surface(trg_surface.get_size(), pygame.SRCALPHA)
    for cb in drawing_callbacks:
        cb(s)
        trg_surface.blit(s, (0, 0))


def darken_color(color, darken_pct):
    """Given a 3-tuple representing a color, darken it by the given percentage"""
    return color[0] * darken_pct, color[1] * darken_pct, color[2] * darken_pct


def alphaize(color, alpha):
    """Take a 3-tuple color and return a color with the given alpha"""
    return (color[0], color[1], color[2], alpha)
