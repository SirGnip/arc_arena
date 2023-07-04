"""
Functions that draw background images for the playfield
"""
import random
import math
import pygame
from gnp_pygame import gnppygame
from gnp_pygame import gnipMath
from arc_arena import utils
from arc_arena import settings

CFG = settings  # quick alias


def draw_grid(surf, gameobj):
    x_count = 8
    y_count = 5
    size = 140
    margin = 15
    hide_color_count = 4
    accent_color_count = 2
    idxs = list(range(x_count * y_count))
    random.shuffle(idxs)
    hide_idxs = idxs[:hide_color_count]
    accent_idxs = idxs[-accent_color_count:]
    # extend grid as I need to draw grid larger than surface because I rotate it
    grid_rect = pygame.Rect(0, 0, surf.get_size()[0]+200, surf.get_size()[1]+200)
    grid_surf = pygame.Surface(grid_rect.size, pygame.SRCALPHA)
    cur_idx = 0
    for x in range(0, x_count * (size+margin), size+margin):
        for y in range(0, y_count * (size+margin), size+margin):
            if cur_idx not in hide_idxs:
                final_clr = CFG.Background.GridColor if cur_idx not in accent_idxs else CFG.Background.GridAccentColor
                rect = pygame.Rect(x, y, size, size)
                grid_surf.fill(final_clr, rect)
            cur_idx += 1
    grid_surf = pygame.transform.rotate(grid_surf, 5)
    surf.blit(grid_surf, (0, -100))


def draw_circles(surf, gameobj):
    colors = (
        (255, 0, 0, CFG.Background.CirclesAlpha),
        (0, 255, 0, CFG.Background.CirclesAlpha),
        (0, 0, 255, CFG.Background.CirclesAlpha+3),
        (255, 255, 0, CFG.Background.CirclesAlpha),
    )
    for i in range(125):
        utils.withalpha(surf, lambda sf: pygame.draw.circle(
            sf,
            random.choice(colors),
            (random.randint(0, surf.get_rect().width), random.randint(0, surf.get_rect().height)),
            random.randint(75, 200)
        ))


def draw_blue_circles(surf, gameobj):
    for i in range(125):
        utils.withalpha(surf, lambda sf: pygame.draw.circle(
            sf,
            (0, 0, 100, CFG.Background.BlueCirclesAlpha),
            (random.randint(0, surf.get_rect().width), random.randint(0, surf.get_rect().height)),
            random.randint(100, 200)
        ))


def draw_concentric_arcs(surf, gameobj):
    def eighths():
        return math.pi/4
    def quarters():
        return math.pi/2
    def random_angle():
        return random.uniform(0, 2*math.pi)
    def random_quarters():
        return random.choice((0, math.pi/2, math.pi, 3*math.pi/2))
    def random_eighths():
        return random.choice(
            [i * 2 * math.pi / 8 for i in range(8)]
        )
    def random_blue_scarlet_clrs():
        return random.choice(
            (
                CFG.Background.ConcentricArcsBaseColor,
                CFG.Background.ConcentricArcsBaseColor,
                CFG.Background.ConcentricArcsBaseColor,
                CFG.Background.ConcentricArcsBaseColor,
                CFG.Background.ConcentricArcsBaseColor,
                CFG.Background.ConcentricArcsHighlightColor,
            )
        )

    def random_title_screen_clrs():
        base_color = (6, 0, 29)
        accent_color = (30, 0, 0)
        return random.choice(
            (
                base_color,
                base_color,
                base_color,
                base_color,
                accent_color
            )
        )

    def draw_cirs(pos, starting_size, arc_count, step, start_factory, span_factory, line_width):
        rect = pygame.Rect(0, 0, starting_size, starting_size)
        rect.center = pos
        for size in range(arc_count):
            start_angle = start_factory()
            stop_angle = start_angle - span_factory()
            if gameobj is None:
                # gameobj==None tells the class to use different colors, didn't have to change class signature
                color = random_title_screen_clrs()
            else:
                color = random_blue_scarlet_clrs()

            pygame.draw.arc(surf, color, rect, start_angle, stop_angle, line_width)
            pygame.draw.arc(surf, color, rect.move(1, 0), start_angle, stop_angle, line_width)
            rect.inflate_ip(-step, -step)

    win = surf.get_rect()
    win.inflate_ip(150, 150) # since make_grid_points() doesn't create points on the edges, inflate the rect first
    pts = utils.make_grid_points(win, 100)
    pts = [p + utils.get_jitter_vect(15, 15) for p in pts]
    random.shuffle(pts)
    pts = pts[:30]
    for pt in pts:
        setup = random.choice((
            (200, 7, 30),
            (80, 3, 30),
            (80, 3, 30),
        ))
        draw_cirs(pt.AsTuple(), setup[0], setup[1], setup[2], random_quarters, quarters, 7)

    # original samples
    # draw_cirs((0, 20), 400, 4, 75, random_angle, eighths, 5)
    # draw_cirs((300, 20), 200, 3, 25, random_angle, eighths, 3)
    # draw_cirs((500, 20), 150, 4, 35, random_angle, eighths, 4)
    # draw_cirs((700, 20), 150, 4, 40, random_angle, eighths, 6)
    # draw_cirs((850, 20), 150, 4, 40, random_quarters, quarters, 6)
    # draw_cirs((1000, 20), 150, 4, 40, random_eighths, quarters, 6)
    # draw_cirs((400, 300), 300, 6, 50, random_quarters, quarters, 7)   #### THIS ONE


def draw_geometric_scene(surf, gameobj):
    win = surf.get_rect()
    w = win.width
    h = win.height
    alpha = CFG.Background.GeometricSceneAlpha

    utils.withalpha(surf, lambda sf: pygame.draw.polygon(
        sf,
        (0, 0, 255, alpha*2),
        [
            (w*.7 , 0.0),
            (w*.8 , 0.0),
            (w*.78, h),
            (w*.4 , h),
        ]
    ))
    utils.withalpha(surf, lambda sf: pygame.draw.polygon(
        sf,
        (255, 0, 0, alpha*2),
        [
            (0.0, h * .8),
            (w, h * .2),
            (w, h * .7),
            (0.0, h * .9),
        ]
    ))

    pt = [int(w*.5), int(h*.5)]
    for radius in range(100, 251, 75):
        utils.withalpha(surf, lambda sf: pygame.draw.circle(
            sf,
            (255, 255, 0, alpha),
            pt,
            radius
        ))
        pt[0] += 20
        pt[1] += 10

    utils.withalpha(surf, lambda sf: pygame.draw.polygon(
        sf,
        (255, 0, 255, alpha*2),
        [
            (w*.2, h*.1),
            (w*.5, h*.4),
            (w*.3, h*.9),
            (w*.1, h*.7),
        ]
    ))


def draw_random_polys(surf, gameobj):
    win = surf.get_rect()
    alpha = CFG.Background.RandomPolysAlpha
    colors = (
        (255, 0, 0, alpha),
        (0, 255, 0, alpha),
        (0, 0, 255, alpha),
        (255, 255, 0, alpha),
        (255, 0, 255, alpha),
        (0, 255, 255, alpha),
        (255, 255, 255, alpha),
    )
    for _ in range(100):
        pt = gnipMath.cVector2.RandInRect(win)
        jitter = 600
        utils.withalpha(surf, lambda sf: pygame.draw.polygon(
            sf,
            random.choice(colors),
            (
                (pt + gnipMath.cVector2().Rand(jitter, jitter)).AsIntTuple(),
                (pt + gnipMath.cVector2().Rand(jitter, jitter)).AsIntTuple(),
                (pt + gnipMath.cVector2().Rand(jitter, jitter)).AsIntTuple(),
                (pt + gnipMath.cVector2().Rand(jitter, jitter)).AsIntTuple(),
            )
        ))


def draw_player_names(surf, gameobj):
    win = surf.get_rect()
    alpha = CFG.Background.PlayerNamesAlpha
    count = 0
    while count < 25:
        count += 1
        ctrl = gameobj._controllers[count % len(gameobj._controllers)]
        sf = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        sf.set_alpha(alpha)
        sf.set_colorkey((0, 0, 0)) # surface with text doesn't have alpha, just a black background
        sf = sf.convert()
        point = gnipMath.cVector2.RandInRect(win)
        gameobj.font_mgr.draw(sf, gameobj.fnt, 160, ctrl._name, (point+gnipMath.cVector2(-300, -50)).AsIntTuple(), (255, 255, 255), antialias=True)
        sf = pygame.transform.rotate(sf, 3)
        surf.blit(sf, (0, 0))


def draw_soft_circles(surf, gameobj):
    win = surf.get_rect()
    alpha = CFG.Background.SoftCirclesAlpha   # alpha of 3 and step in range of 4 below was nice, but slow
    colors = (
        (255, 0, 0, alpha),
        (0, 255, 0, alpha),
        (0, 0, 255, alpha),
        (255, 255, 0, alpha),
        (255, 0, 255, alpha),
        (0, 255, 255, alpha),
        (255, 255, 255, alpha),
    )

    for _ in range(16):
        pt = gnipMath.cVector2.RandInRect(win)
        clr = random.choice(colors)
        start_radius = random.randint(70, 100)
        for radius in range(start_radius, start_radius+50, 7):
            utils.withalpha(surf, lambda sf: pygame.draw.circle(
                sf,
                clr,
                pt.AsIntTuple(),
                radius
            ))


def draw_wave_circles(surf, gameobj):
    win = surf.get_rect()
    center = gnipMath.cVector2(win.center)
    offset = gnipMath.cVector2(0, 1)
    max_radius = center.Magnitude()
    choice = random.randint(0, 2)
    if choice == 0:
        clr = CFG.Background.WaveCirclesIntensity  # color intensity
        clr_line = (0, 0, int(clr * 1.5))
        clr_cir1 = (clr, clr, int(clr*2.0))
        clr_cir2 = (clr, clr, clr)
    elif choice == 1:
        clr_line = utils.darken_color(gnppygame.YELLOW, CFG.Background.WaveCirclesDarken)
        clr_cir1 = utils.darken_color(gnppygame.BLUE, CFG.Background.WaveCirclesDarken)
        clr_cir2 = utils.darken_color(gnppygame.RED, CFG.Background.WaveCirclesDarken)
    elif choice == 2:
        clr_line = utils.darken_color(gnppygame.YELLOW, CFG.Background.WaveCirclesDarken)
        clr_cir1 = utils.darken_color(gnppygame.WHITE, CFG.Background.WaveCirclesDarken)
        clr_cir2 = utils.darken_color(gnppygame.PURPLE, CFG.Background.WaveCirclesDarken)

    # radial spikes
    for _ in range(30):
        pt = gnipMath.cVector2()
        pt.SetFromPolar(random.uniform(0.0, math.pi * 2), random.randint(150, 700))
        pt = pt + center
        pygame.draw.line(surf, clr_line, center.AsIntTuple(), pt.AsIntTuple(), 5)

    # centered circles
    sf1 = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    wave1 = gnipMath.cSineWave(50.0, gnipMath.cRange(0, 300))
    radius = 1
    while radius <= max_radius:
        alpha = min(wave1.Get(radius), 255)
        pygame.draw.circle(sf1, utils.alphaize(clr_cir1, alpha), center.AsIntTuple(), radius, 1)
        pygame.draw.circle(sf1, utils.alphaize(clr_cir1, alpha), (center+offset).AsIntTuple(), radius, 1)
        radius += 1
    surf.blit(sf1, (0, 0))

    # offset circles on top
    sf2 = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    wave2 = gnipMath.cSineWave(55.0, gnipMath.cRange(0, 300))
    center = center + gnipMath.cVector2(-50, 25)
    radius = 1
    while radius <= max_radius:
        alpha = min(wave2.Get(radius), 255)
        pygame.draw.circle(sf2, utils.alphaize(clr_cir2, alpha), center.AsIntTuple(), radius, 1)
        pygame.draw.circle(sf2, utils.alphaize(clr_cir2, alpha), (center+offset).AsIntTuple(), radius, 1)
        radius += 1
    surf.blit(sf2, (0, 0))


def draw_horiz_lines(surf, gameobj):
    win = surf.get_rect()
    colors = (
        CFG.Background.HorizLinesClr1,
        CFG.Background.HorizLinesClr2,
        CFG.Background.HorizLinesClr3,
    )
    y_mid = win.centery + 75
    max_length = 500
    for _ in range(500):
        length = max(0, random.normalvariate(100, 100))
        x = random.randint(0-max_length, win.right)
        y = random.normalvariate(y_mid, 90)
        thickness = random.randint(1, 6)
        pygame.draw.line(surf, random.choice(colors), (x, y), (x+length, y), thickness)
