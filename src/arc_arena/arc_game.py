import sys
from pathlib import Path
import pygame
import pygame.constants
from gnp_pygame import gnppygame
from gnp_pygame import gnpactor
from gnp_pygame import gnpparticle
import math
import functools
import random
from gnp_pygame import gnipMath
from gnp_pygame import gnpinput
from arc_arena import settings
import inspect
import copy
import pickle
import traceback


CFG = settings  # quick alias
# simplistic color palette
GLOBAL_RED = (175, 0, 0)
GLOBAL_BLUE = (0, 0, 181)


class ColorIdxAndRGB(object):
    """Util class for tracking a color index with associated rgb when working in indexed color mode"""
    def __init__(self, color_idx, color_rgb):
        self.idx = color_idx
        self.rgb = color_rgb

    def __str__(self):
        return '%d %s' % (self.idx, self.rgb)

    def __eq__(self, other):
        """equality operator for when unpickling PlayerControllers from disk and using a Nexter to cycle through them.

        The PlayerRegistrationState Nexter contains ColorIdxAndRGB objects that are different that what is made reading
        from disk, so need to compare by value, not object index."""
        if isinstance(other, ColorIdxAndRGB):
            return self.idx == other.idx and self.rgb == other.rgb
        return NotImplemented

    def __hash__(self):
        """Need because this class is used in a set"""
        return hash((self.idx, self.rgb))


def _withalpha(trg_surface, drawing_callback):
    """Run the drawing_callback (assumed to be a pygame.draw.* function) and blit it to given surface.
    pygame.draw functions don't do alpha blending, but they do preserve alpha in the color. So, if
    you draw something with alpha using pygame.draw*, you need to blit it to get alpha blending."""
    s = pygame.Surface(trg_surface.get_size(), pygame.SRCALPHA)
    drawing_callback(s)
    trg_surface.blit(s, (0, 0))


def _withalphamulti(trg_surface, drawing_callbacks):
    """A multi-callback-function version of _withalpha"""
    s = pygame.Surface(trg_surface.get_size(), pygame.SRCALPHA)
    for cb in drawing_callbacks:
        cb(s)
        trg_surface.blit(s, (0, 0))


def _darken_color(color, darken_pct):
    """Given a 3-tuple representing a color, darken it by the given percentage"""
    return color[0] * darken_pct, color[1] * darken_pct, color[2] * darken_pct


def _alphaize(color, alpha):
    """Take a 3-tuple color and return a color with the given alpha"""
    return (color[0], color[1], color[2], alpha)


def load_player_controllers(joys):
    def persistent_load(persist_id):
        try:
            print('\tUnpickling with persist_id: "%s"' % str(persist_id))
            for joy in joys:
                if joy is not None and (joy._joy.get_id(), joy._joy.get_name()) == persist_id:
                    print('\tUnpickled %s "%s"' % (type(joy).__name__, joy._joy.get_id()))
                    return joy
            raise pickle.UnpicklingError('Unable to find matching gnppygame.Joy object with id: %s' % str(persist_id))
        except Exception as exc:
            raise pickle.UnpicklingError('Unable to use persistent id (%s) to unpickle external object. Exception type:%s %s' % (persist_id, type(exc).__name__, str(exc)))

    print('Attempting to load previous players from %s' % CFG.Player.Filename)
    unpickler = pickle.Unpickler(open(CFG.Player.Filename, 'rb'))
    unpickler.persistent_load = persistent_load
    controllers = unpickler.load()
    print('Loaded %d players from disk at: %s' % (len(controllers), CFG.Player.Filename))
    return controllers


def save_player_controllers(controllers):
    # Need to use a persistent_id as the pygame's Joystick class isn't pickleable.
    def persistent_id(obj):
        if isinstance(obj, gnppygame.Joy):
            # For persist_id combine id *and* name, as id alone would have chance to accidentally mismatch joystick ID's
            # if some joysticks are added/unplugged when game is restarted. Too easy for simple id's to match up. Added
            # name to the persist_id to make it more likely that if controllers have been added/removed, the (id, name)
            # would not match something, causing the load to fail, which is reasonable when joysticks are added/removed.
            persist_id = (obj._joy.get_id(), obj._joy.get_name())
            print('Pickling %s with custom persist_id: "%s"' % (type(obj), persist_id))
            return persist_id
        return None

    # save player list to disk
    print('Saving %d player controllers to disk at: %s' % (len(controllers), CFG.Player.Filename))
    pickler = pickle.Pickler(open(CFG.Player.Filename, 'wb'), 2)
    pickler.persistent_id = persistent_id
    pickler.dump(controllers)
    print('Player controller save complete')


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


class ScoreboardPlayer(object):
    def __init__(self, name, color, start_score=0):
        self.name = name
        self.color = color
        darken_pct = 0.5
        self._dark_color = _darken_color(self.color, darken_pct)
        self.score = start_score
        self.score_delta = 0
        self._winner_pulse = gnipMath.cPulseWave(0.8, gnipMath.cRange(0, 1), pulseWidth=0.2)
        self.win_streak = 0
        self.is_winner = False

    def draw(self, screen, draw_rect, elapsed):
        _game.font_mgr.draw(screen, _game.fnt, 24, '%s: %d' % (self.name, self.score), draw_rect, self.color, 'center', 'top')
        clr = self.color if not self.is_winner or self._winner_pulse.Get(elapsed) == 1 else self._dark_color
        _game.font_mgr.draw(screen, _game.fnt, 24, '%+d' % self.score_delta, draw_rect.move(0, 30), clr, 'center', 'top')

    def start_round(self):
        self.score_delta = 0

    def __str__(self):
        return '<Player %s %+d/%d>' % (self.name, self.score_delta, self.score)


class Scoreboard(object):
    def __init__(self, display_rect_top, display_rect_bottom, start_score=0):
        self._player_list = []
        self._display_rect_top = display_rect_top
        self._display_rect_bottom = display_rect_bottom
        self._top_bg = gnpactor.AlphaRect(self._display_rect_top, (0, 0, 0, 150))
        self._bottom_bg = gnpactor.AlphaRect(self._display_rect_bottom, (0, 0, 0, 150))
        self.start_score = start_score
        self._elapsed = 0.0
        self._current_win_streak = (0, [])
        self._max_win_streak = (0, [])
        self._last_round_time = 0.0
        self._max_round_time = (0, [])

    def add_player(self, name, color):
        self._player_list.append(ScoreboardPlayer(name, color, self.start_score))

    def start_round(self):
        self._elapsed = 0.0
        for player in self._player_list:
            player.start_round()

    def end_round(self, round_time):
        # identify winner(s)
        max_delta = max([p.score_delta for p in self._player_list])
        winning_players = [p for p in self._player_list if p.score_delta >= max_delta]
        # update max win streak
        for plyr in self._player_list:
            plyr.is_winner = plyr.score_delta >= max_delta
        self._set_win_streaks(winning_players)
        # update longest round time
        self._last_round_time = round_time
        if round_time > self._max_round_time[0]:
            self._max_round_time = (round_time, winning_players)

    def _set_win_streaks(self, winning_players):
        for plyr in self._player_list:
            if plyr in winning_players:
                plyr.win_streak += 1
            else:
                plyr.win_streak = 0

        # current win streak
        current_win_streak_length = max([p.win_streak for p in self._player_list])
        current_win_streak_players = [p for p in self._player_list if p.win_streak >= current_win_streak_length]
        self._current_win_streak = (current_win_streak_length, current_win_streak_players)

        if self._current_win_streak[0] > self._max_win_streak[0]:
            self._max_win_streak = self._current_win_streak

    def change_score(self, player_index, score_delta):
        assert 0 <= player_index < len(self._player_list), 'Passed invalid index (%d) into cScoreboard.change_score. Max valid index: %d' % (player_index, len(self._player_list) - 1)
        self._player_list[player_index].score += score_delta
        self._player_list[player_index].score_delta += score_delta
        
    def step(self, time_delta):
        self._elapsed += time_delta

    def draw(self, screen):
        _game.font_mgr.draw(screen, _game.fnt, 60, 'Round Over', _game.get_screen_rect(), gnppygame.WHITE, 'center', 'center')
        # player scores
        cnt = len(self._player_list)
        if cnt <= 6:
            top_cnt, btm_cnt = cnt, 0
        else:
            top_cnt, btm_cnt = cnt//2 + cnt%2, cnt//2  # divide by 2, always add any remainder to top row
        top_players = self._player_list[:top_cnt]  # "top" represents visual positioning, not score
        bottom_players = self._player_list[top_cnt:]  # "bottom" represents visual positioning, not score
        top_rects = gnppygame.split_rect_horizontally(self._display_rect_top, len(top_players))

        # pygame.draw.rect(screen, (30, 40, 0), self._display_rect_top)
        self._top_bg.draw(screen)
        for idx, player in enumerate(top_players):
            player.draw(screen, top_rects[idx], self._elapsed)

        if len(bottom_players) > 0:
            bottom_rects = gnppygame.split_rect_horizontally(self._display_rect_bottom, len(bottom_players))
            # pygame.draw.rect(screen, (30, 40, 0), self._display_rect_bottom)
            self._bottom_bg.draw(screen)
            for idx, player in enumerate(bottom_players):
                player.draw(screen, bottom_rects[idx], self._elapsed)

        # Micro-achievement drawing setup
        rect = _game.get_screen_rect()
        rect.y = rect.centery + 100
        rect.height = 30
        spacing = 40
        # Current round length
        longest_round_msg = 'Round time: %.1f seconds' % self._last_round_time
        _game.font_mgr.draw(screen, _game.fnt, 24, longest_round_msg, rect, gnppygame.WHITE, 'center', 'center')
        # longest round length
        rect.move_ip(0, spacing)
        longest_round_players = self._max_round_time[1]
        players = ', '.join([p.name for p in longest_round_players])
        longest_round_msg = 'Longest round: %.1f seconds by %s' % (self._max_round_time[0], players)
        _game.font_mgr.draw(screen, _game.fnt, 24, longest_round_msg, rect, gnppygame.WHITE, 'center', 'center')
        # current win streak
        rect.move_ip(0, spacing)
        win_streak = self._current_win_streak
        plyrs = ','.join([p.name for p in win_streak[1]])
        streak_msg = 'Current win streak: %d by %s' % (win_streak[0], plyrs)
        _game.font_mgr.draw(screen, _game.fnt, 24, streak_msg, rect, gnppygame.WHITE, 'center', 'center')
        # longest win streak
        rect.move_ip(0, spacing)
        win_streak = self._max_win_streak
        plyrs = ','.join([p.name for p in win_streak[1]])
        streak_msg = 'Longest win streak: %d by %s' % (win_streak[0], plyrs)
        _game.font_mgr.draw(screen, _game.fnt, 24, streak_msg, rect, gnppygame.WHITE, 'center', 'center')


class Apple(object):
    def __init__(self, pos, radius, color):
        self.pos = pos
        self._radius = radius
        self._color = color
        self._alive = True

    def draw(self, surface):
        pygame.draw.circle(surface, self._color, self.pos.AsIntTuple(), self._radius)

    def step(self, time_delta):
        pass

    def can_reap(self):
        return not self._alive

    def reap(self):
        self._alive = False

    def is_touching(self, pos):
        return (self.pos - pos).Magnitude() < self._radius


class Snake(object):
    """Object representing the arc that the player controls
    NOTE:
    If the snake velocity is high and the frame rate is slow, you'll see
    unintentional gaps in the snake.
    """
    NOTURN = 0
    LEFTTURN = 1
    RIGHTTURN = 2
    BOTHTURN = 3
    
    def __init__(self, body_color, background_color, start_pos, start_direction):
        assert isinstance(start_pos, gnipMath.cVector2), 'cSnake starting position must be a gnipMath.cVector2'
        assert isinstance(start_direction, gnipMath.cVector2), 'cSnake starting direction must be a gnipMath.cVector2'
        self._start_direction = start_direction
        self.head_color = CFG.Snake.HeadColorIdx
        self.head_color_dim = None
        self.head_color_dim = CFG.ReadyAimRound.HeadColorDimIdx
        self.is_head_dimmed = False
        assert isinstance(body_color, ColorIdxAndRGB)
        self.body_color = body_color
        assert isinstance(background_color, int)
        self.background_color = background_color
        self.pos = start_pos
        self.last_pos = None
        self.set_initial_speed(CFG.Snake.Speed)
        self.turn_rate_left = -math.radians(CFG.Snake.TurnRateDegPerSec)  # radians per second
        self.turn_rate_right = math.radians(CFG.Snake.TurnRateDegPerSec)  # radians per second
        self.turning_dir = self.NOTURN
        self.draw_size = CFG.Snake.DrawSize
        self.whisker_length = self.draw_size + 2
        self.robot_whisker_length = 50
        self.gap_size = CFG.Snake.GapSize  # how big are the gaps?
        self.wall_size = CFG.Snake.WallSize  # how long are the walls inbetween gaps?
        self._drawing_gap = False
        self._cur_length = 0.0
        self._controller = None
        self._both_turn_callback = None
        self._turn_state_callback = None

    def set_initial_speed(self, speed):
        self.vel = self._start_direction.Normalize() * speed

    def set_speed(self, speed):
        """Set speed of snake after it has been created"""
        self.vel = self.vel.Normalize() * speed

    def possessed_by(self, controller):
        assert self._controller is None, 'Trying to set the controller for a snake that already has one'
        self._controller = controller

    def set_head_dim(self, is_dimmed):
        self.is_head_dimmed = is_dimmed

    def draw(self, game_surface):
        if self._drawing_gap:
            pygame.draw.circle(game_surface, self.background_color, self.last_pos.AsIntTuple(), self.draw_size)
        else:
            pygame.draw.circle(game_surface, self.body_color.idx, self.last_pos.AsIntTuple(), self.draw_size)
        # draw head if alive
        if not self.is_dead(game_surface):
            # Draw head one pixel smaller than body as I would see occasional times where the head wouldn't
            # be completely covered by the body, leaving intermittent white slivers. This was noticed in
            # the Indigestion game mode.
            head_color = self.head_color_dim if self.is_head_dimmed else self.head_color
            pygame.draw.circle(game_surface, head_color, self.pos.AsIntTuple(), self.draw_size - 1)

    def make_explosion(self):
        return gnpparticle.Emitter(
            self.pos,
            gnpparticle.EmitterRate_DelayRangeWithLifetime(0.001, 0.001, 0.075),
            gnpparticle.EmitterSpeed_Range(50.0, 100.0),
            gnpparticle.EmitterDirection_360(),
            gnpparticle.EmitterLifetime_Range(0.1, 0.4),
            gnpparticle.EmitterColor_Choice((self._controller._color.rgb, gnppygame.WHITE)),
            2
        )

    def step(self, time_delta):
        movement_vect = self.vel * time_delta
        movement_dist = movement_vect.Magnitude()
        self._cur_length += movement_dist
        
        if self._drawing_gap:
            if self._cur_length > self.gap_size:
                self._drawing_gap = False
                self._cur_length = 0.0
        else:
            if self._cur_length > self.wall_size and self.gap_size > 0:
                self._drawing_gap = True
                self._cur_length = 0.0

        if self.turning_dir == self.LEFTTURN:
            self.turn_left(time_delta)
        if self.turning_dir == self.RIGHTTURN:
            self.turn_right(time_delta)
        self.last_pos = self.pos
        self.pos = self.pos + (self.vel * time_delta)

    def set_turn_state(self, turn):
        if self._turn_state_callback:
            result = self._turn_state_callback(self, turn)
            if result:  # if callback returns True, skip any further processing
                return

        if self.turning_dir != turn:
            self.turning_dir = turn
            if self._both_turn_callback is not None and self.turning_dir == self.BOTHTURN:
                self._both_turn_callback(self)
        
    def turn_left(self, time_delta):
        self.turn(self.turn_rate_left, time_delta)
    
    def turn_right(self, time_delta):
        self.turn(self.turn_rate_right, time_delta)
        
    def turn(self, turn_amount_per_sec, time_delta):
        turn = turn_amount_per_sec * time_delta
        self.vel.Rotate(turn)

    def register_both_turn_callback(self, callback):
        self._both_turn_callback = callback

    def get_color_under_whisker(self, screen):
        whisker_pos = self.pos + (self.vel.Normalize() * self.whisker_length)
        # TODO: OPTIMIZE: Run performance test to see if get_at_mapped is faster. right now I'm getting and comparing RGB values.
        return screen.get_at(whisker_pos.AsIntTuple())

    def get_color_under_robot_whisker(self, screen):
        whisker_pos = self.pos + (self.vel.Normalize() * self.robot_whisker_length)
        whisker_pos = gnppygame.clamp_point_to_rect(whisker_pos.AsIntTuple(), _game.get_screen_rect())
        return screen.get_at(whisker_pos)
        
    def is_dead(self, game_surface):
        try:
            return self.get_color_under_whisker(game_surface) != CFG.Win.BackgroundColorRGB
        except IndexError as e:
            print('WARNING: Killing snake "%s" because its whisker went off screen with snake at position=%s. Exception: %s' % (self._controller, self.pos, e))
            return True


class InputConfig(object):
    """for player checkin screen, watches different types of input and generates generic actions"""
    TURN_LEFT = 1
    TURN_RIGHT = 2
    BOTH_TURN = 3
    REMOVE_PLAYER = 4

    def __init__(self):
        raise NotImplementedError

    def input(self):
        """Input routine for game. Polls state of input each frame of the game."""
        raise NotImplementedError

    def parse_event(self, event):
        """Input routine for player registration UI. Processes input queue for events."""
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError


class KeyboardInputConfig(InputConfig):
    def __init__(self, name, key_left, key_right):
        self.name = name
        self._key_left = key_left
        self._key_right = key_right

    def input(self):
        """Reads pygame input system and returns left, right, None"""
        left_pressed = pygame.key.get_pressed()[self._key_left]
        right_pressed = pygame.key.get_pressed()[self._key_right]
        if left_pressed and right_pressed:
            return self.BOTH_TURN
        elif left_pressed:
            return self.TURN_LEFT
        elif right_pressed:
            return self.TURN_RIGHT
        else:
            return None

    def parse_event(self, event):
        """Given a pygame event, return whether this input config handles it. If this event doesn't apply, return None."""
        if event.type == gnpinput.HOLD and event.origtype == pygame.KEYDOWN and (event.key == self._key_left or event.key == self._key_right):
            return self.REMOVE_PLAYER

        if event.type != pygame.KEYDOWN:
            return None

        if event.key == self._key_left:
            return self.TURN_LEFT
        elif event.key == self._key_right:
            return self.TURN_RIGHT
        return None


class MouseInputConfig(InputConfig):
    _LEFT_BTN = 1
    _MIDDLE_BTN = 2
    _RIGHT_BTN = 3
    _WHEEL_UP = 4
    _WHEEL_DOWN = 5

    def __init__(self, name):
        self.name = name

    def input(self):
        btn_left, btn_ctr, btn_right = pygame.mouse.get_pressed()
        if btn_left and btn_right:
            return self.BOTH_TURN
        elif btn_left:
            return self.TURN_LEFT
        elif btn_right:
            return self.TURN_RIGHT
        return None

    def parse_event(self, event):
        """Given a pygame event, return whether this input config handles it. If this event doesn't apply, return None."""
        if event.type == gnpinput.HOLD and event.origtype == pygame.MOUSEBUTTONDOWN and (event.button == self._LEFT_BTN or event.button == self._RIGHT_BTN):
            return self.REMOVE_PLAYER
        if event.type != pygame.MOUSEBUTTONDOWN:
            return None

        if event.button == self._LEFT_BTN:
            return self.TURN_LEFT
        elif event.button == self._RIGHT_BTN:
            return self.TURN_RIGHT
        return None


class JoystickInputConfig(InputConfig):
    def __init__(self, name, joy, button_idx_pair):
        self.name = name
        self._joy = joy
        self._button_idx_pair = button_idx_pair

    def get_pickle_persist_id(self):
        """Generate ID used for pickling"""
        return '%s - %s' % (self.name, self._joy._joy.get_name())

    def input(self):
        btn_left, btn_right = self._button_idx_pair
        if self._joy.get_button(btn_left) and self._joy.get_button(btn_right):
            return self.BOTH_TURN
        elif self._joy.get_button(btn_left):
            return self.TURN_LEFT
        elif self._joy.get_button(btn_right):
            return self.TURN_RIGHT
        return None

    def parse_event(self, event):
        """Given pygame event, return action to take. If this input config doesn't handle event, return None."""
        joyid = self._joy._joy.get_id()
        if event.type == gnpinput.HOLD and event.origtype == pygame.JOYBUTTONDOWN and event.joyid == joyid and event.button in self._button_idx_pair:
            return self.REMOVE_PLAYER

        if event.type == pygame.JOYBUTTONDOWN and event.joy == joyid:
            btn_left, btn_right = self._button_idx_pair
            if event.button == btn_left:
                return self.TURN_LEFT
            elif event.button == btn_right:
                return self.TURN_RIGHT

        return None


class Controller(object):
    def __init__(self, name, color, index):
        self._name = name
        assert isinstance(color, ColorIdxAndRGB)
        self._color = color
        self._is_human = True
        self._index = index

    def __str__(self):
        return '%s (#%s)' % (self._name, str(self._index))


class PlayerController(Controller):
    def __init__(self, name, color, index, input_map):
        Controller.__init__(self, name, color, index)
        self._input_config = input_map

    def possess(self, snake):
        self._snake = snake
        self._snake.possessed_by(self)

    def input(self):
        input_result = self._input_config.input()
        self._snake.set_turn_state(input_result)


### Drawing Backgrounds
def draw_background_grid(surf, gameobj):
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


def draw_background_circles(surf, gameobj):
    colors = (
        (255, 0, 0, CFG.Background.CirclesAlpha),
        (0, 255, 0, CFG.Background.CirclesAlpha),
        (0, 0, 255, CFG.Background.CirclesAlpha+3),
        (255, 255, 0, CFG.Background.CirclesAlpha),
    )
    for i in range(125):
        _withalpha(surf, lambda sf: pygame.draw.circle(
            sf,
            random.choice(colors),
            (random.randint(0, surf.get_rect().width), random.randint(0, surf.get_rect().height)),
            random.randint(75, 200)
        ))


def draw_background_blue_circles(surf, gameobj):
    for i in range(125):
        _withalpha(surf, lambda sf: pygame.draw.circle(
            sf,
            (0, 0, 100, CFG.Background.BlueCirclesAlpha),
            (random.randint(0, surf.get_rect().width), random.randint(0, surf.get_rect().height)),
            random.randint(100, 200)
        ))


def draw_background_concentric_arcs(surf, gameobj):
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
    win.inflate_ip(150, 150) # since ScatterRound._make_grid_points() doesn't create points o nthe edges, inflate the rect first
    pts = ScatterRound._make_grid_points(win, 100)
    pts = [p + ScatterRound._get_jitter_vect(15, 15) for p in pts]
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


def draw_background_geometric_scene(surf, gameobj):
    win = surf.get_rect()
    w = win.width
    h = win.height
    alpha = CFG.Background.GeometricSceneAlpha

    _withalpha(surf, lambda sf: pygame.draw.polygon(
        sf,
        (0, 0, 255, alpha*2),
        [
            (w*.7 , 0.0),
            (w*.8 , 0.0),
            (w*.78, h),
            (w*.4 , h),
        ]
    ))
    _withalpha(surf, lambda sf: pygame.draw.polygon(
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
        _withalpha(surf, lambda sf: pygame.draw.circle(
            sf,
            (255, 255, 0, alpha),
            pt,
            radius
        ))
        pt[0] += 20
        pt[1] += 10

    _withalpha(surf, lambda sf: pygame.draw.polygon(
        sf,
        (255, 0, 255, alpha*2),
        [
            (w*.2, h*.1),
            (w*.5, h*.4),
            (w*.3, h*.9),
            (w*.1, h*.7),
        ]
    ))


def draw_background_random_polys(surf, gameobj):
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
        _withalpha(surf, lambda sf: pygame.draw.polygon(
            sf,
            random.choice(colors),
            (
                (pt + gnipMath.cVector2().Rand(jitter, jitter)).AsIntTuple(),
                (pt + gnipMath.cVector2().Rand(jitter, jitter)).AsIntTuple(),
                (pt + gnipMath.cVector2().Rand(jitter, jitter)).AsIntTuple(),
                (pt + gnipMath.cVector2().Rand(jitter, jitter)).AsIntTuple(),
            )
        ))


def draw_background_player_names(surf, gameobj):
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


def draw_background_soft_circles(surf, gameobj):
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
            _withalpha(surf, lambda sf: pygame.draw.circle(
                sf,
                clr,
                pt.AsIntTuple(),
                radius
            ))


def draw_background_wave_circles(surf, gameobj):
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
        clr_line = _darken_color(gnppygame.YELLOW, CFG.Background.WaveCirclesDarken)
        clr_cir1 = _darken_color(gnppygame.BLUE, CFG.Background.WaveCirclesDarken)
        clr_cir2 = _darken_color(gnppygame.RED, CFG.Background.WaveCirclesDarken)
    elif choice == 2:
        clr_line = _darken_color(gnppygame.YELLOW, CFG.Background.WaveCirclesDarken)
        clr_cir1 = _darken_color(gnppygame.WHITE, CFG.Background.WaveCirclesDarken)
        clr_cir2 = _darken_color(gnppygame.PURPLE, CFG.Background.WaveCirclesDarken)

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
        pygame.draw.circle(sf1, _alphaize(clr_cir1, alpha), center.AsIntTuple(), radius, 1)
        pygame.draw.circle(sf1, _alphaize(clr_cir1, alpha), (center+offset).AsIntTuple(), radius, 1)
        radius += 1
    surf.blit(sf1, (0, 0))

    # offset circles on top
    sf2 = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    wave2 = gnipMath.cSineWave(55.0, gnipMath.cRange(0, 300))
    center = center + gnipMath.cVector2(-50, 25)
    radius = 1
    while radius <= max_radius:
        alpha = min(wave2.Get(radius), 255)
        pygame.draw.circle(sf2, _alphaize(clr_cir2, alpha), center.AsIntTuple(), radius, 1)
        pygame.draw.circle(sf2, _alphaize(clr_cir2, alpha), (center+offset).AsIntTuple(), radius, 1)
        radius += 1
    surf.blit(sf2, (0, 0))


def draw_background_horiz_lines(surf, gameobj):
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


class ArcGame(gnppygame.GameWithStates):
    def __init__(self):
        # call parent ctor
        self.round_idx = 0
        gnppygame.GameWithStates.__init__(
                self,
                'Arc Arena',
                (CFG.Win.ResolutionX, CFG.Win.ResolutionY),
                CFG.Win.Fullscreen)

        self._init_mode_list()
        self.fnt = str(_resource_path / 'fonts/Arista2.0.ttf')
        self.font_mgr = gnppygame.FontManager(((self.fnt, 160), (self.fnt, 60), (self.fnt, 24)))
        self.timers = gnppygame.TimerManager()
        event_types = (gnpinput.HOLD, gnpinput.AXISPRESS, gnpinput.AXISRELEASE, pygame.USEREVENT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.KEYUP, pygame.MOUSEBUTTONUP, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYAXISMOTION)
        pygame.event.set_allowed(event_types)  # set_allowed is additive

        # graphics
        self.palette = make_palette(CFG.Player.Colors)

        # backgrounds
        background_draw_functs = [
            draw_background_grid,
            draw_background_circles,
            draw_background_blue_circles,
            draw_background_concentric_arcs,
            draw_background_geometric_scene,
            draw_background_random_polys,
            draw_background_player_names,
            draw_background_soft_circles,
            draw_background_wave_circles,
            draw_background_horiz_lines,
        ]
        if CFG.Background.RandomizeOrder:
            self.background_chooser = gnppygame.random_no_repeat(background_draw_functs)
        else:
            self.background_chooser = gnppygame.cycle_through_items(background_draw_functs)

        # joysticks
        self.joys = [gnppygame.Joy.joy_factory(i) for i in range(CFG.Input.JoyCountMax)]
        for joy in self.joys:
            if joy:
                joy.set_deadzone(CFG.Input.JoyDeadzone)
        print('Found %d total joystick(s)' % len([j for j in self.joys if j is not None]))

        # player and AI controllers
        if not CFG.Debug.On:
            try:
                self._controllers = load_player_controllers(self.joys)
            except Exception as e:
                print('WARNING: Problem loading previous player list from %s. Exception: %s' % (CFG.Player.Filename, type(e)))
                print(traceback.print_exc())
                self._controllers = []
        else:
            self._controllers = []

        # audio manager
        self.audio_mgr = gnppygame.AudioManager(_resource_path / 'sounds')
        self.audio_mgr.enable_sfx(CFG.Sound.EnableSFX)
        # self.audio_mgr.enable_music(CFG.Sound.EnableMusic)
        # self.audio_mgr.load_music(_resource_path / '/music/MySong.mp3')
        # self.audio_mgr.play_music(-1)
        # startup sound

        # set initial state
        self.change_state(TitleScreenState(self))

    def _init_mode_list(self):
        all_rounds = (
            BasicRound,
            ScatterRound,
            AppleRound,
            NoGapRound,
            TurboArcRound,
            DizzyRoundMode,
            IndigestionRound,
            ReadyAimRound,
            SqueezeRound,
            TurboArcRound,
            ColorBlindRound,
            AppleRushRound,
            RightTurnOnlyRound,
            BoostRound,
            TurboArcRound,
            FollowerRound,
            AlternateTurnsRound,
            ReadyAimRound,
            TreasureChamberRound,
        )

        basic_only_round = (
            BasicRound,
        )

        simple_rounds = (
            BasicRound,
            BasicRound,
            AppleRound,
            ScatterRound,
            TurboArcRound,
        )

        custom_rounds = (
            BasicRound,
            BasicRound,
            ScatterRound,
            BasicRound,
            AppleRound,
            ScatterRound,
            NoGapRound,
            BasicRound,
            TurboArcRound,
            DizzyRoundMode,
            ScatterRound,
            IndigestionRound,
            BasicRound,
            ColorBlindRound,
            AppleRushRound,
            RightTurnOnlyRound,
            SqueezeRound,
            ScatterRound,
            BoostRound,
            FollowerRound,
            ReadyAimRound,
            ScatterRound,
            TreasureChamberRound,
            AlternateTurnsRound,
            ColorBlindRound,
        )

        favorite_rounds = (
            ScatterRound,
            IndigestionRound,
            AppleRushRound,
            BoostRound,
            SqueezeRound,
            FollowerRound,
            ReadyAimRound,
        )

        if CFG.Round.RoundSet == 'all':
            self._mode_sequence = all_rounds
        elif CFG.Round.RoundSet == 'basic_only':
            self._mode_sequence = basic_only_round
        elif CFG.Round.RoundSet == 'simple':
            self._mode_sequence = simple_rounds
        elif CFG.Round.RoundSet == 'custom':
            self._mode_sequence = custom_rounds
        elif CFG.Round.RoundSet == 'favorite':
            self._mode_sequence = favorite_rounds
        else:
            raise Exception('Unknown value for configuration value Round.RoundSet: %s' % CFG.Round.RoundSet)

    def make_next_round(self):
        if CFG.Debug.On:
            return BoostRound(self)

        if CFG.Round.RandomRoundSelection:
            return random.choice(self._mode_sequence)(self)

        return self._mode_sequence[self.round_idx % len(self._mode_sequence)](self)

    def step(self, time_delta):
        self.timers.step(time_delta)
        gnppygame.GameWithStates.step(self, time_delta)  # step the parent game class last because it can trigger a state transition

    def init_scoreboard(self):
        scoreboard_rect = self.get_screen_rect()
        scoreboard_rect.height = 60
        self.scoreboard = Scoreboard(scoreboard_rect.move(0, 15), scoreboard_rect.move(0, 85))  # needs to be called after RestartGame
        for controller in self._controllers:
            self.scoreboard.add_player(controller._name, controller._color.rgb)

def make_palette(colors):
    '''Generate a palette for the 8-bit color game surface'''
    pal = [(0, 255, 0)] * 256 # bright green for unused colors
    idx = 100 # starting index
    # add static colors
    pal[idx] = CFG.Win.BackgroundColorRGB
    idx += 1
    pal[idx] = CFG.Win.BorderColorRGB
    idx += 1
    pal[idx] = CFG.Snake.HeadColorRGB
    idx += 1
    pal[idx] = CFG.ReadyAimRound.HeadColorDimRGB
    idx += 1
    pal[idx] = CFG.ColorBlindRound.ColorRGB
    idx += 1
    # add player colors (dynamic-ish)
    assert idx == CFG.Win.FirstColorIdx
    for color in colors:
        pal[idx] = color
        idx += 1
    # asserts for sanity checks on values in settings.py
    assert pal[CFG.Win.BackgroundColorIdx] == CFG.Win.BackgroundColorRGB
    assert pal[CFG.Win.BorderColorIdx] == CFG.Win.BorderColorRGB
    assert pal[CFG.Snake.HeadColorIdx] == CFG.Snake.HeadColorRGB
    assert pal[CFG.ReadyAimRound.HeadColorDimIdx] == CFG.ReadyAimRound.HeadColorDimRGB
    assert pal[CFG.ColorBlindRound.ColorIdx] == CFG.ColorBlindRound.ColorRGB
    return pal


class MainGameState(gnppygame.GameState):
    _LABEL = None
    _SUB_LABEL = None

    def __init__(self, game_obj):
        super(MainGameState, self).__init__(game_obj)
        self.round_over = False
        self.background_color = CFG.Win.BackgroundColorIdx
        self.alive_snakes = []
        self.owner().scoreboard.start_round()
        self.actors = gnppygame.ActorList()
        self._label_actors = gnppygame.ActorList()
        self._add_round_labels()
        display = pygame.display.get_surface()
        # Optimization: Blitting is faster than filling. So, fill a surface once and blit it each frame.
        self._surface_eraser = pygame.Surface(display.get_size(), 0, display)
        self._surface_eraser.fill(CFG.Win.BackgroundColorRGB)
        if CFG.Background.Visible:
            draw_bg_func = next(self.owner().background_chooser)
            draw_bg_func(self._surface_eraser, self.owner())

        # Reset frame timer because the background drawing could take so long,
        # causing the state's first tick to be seconds long...
        self.owner()._frame_timer.tick()

        # initialize Snakes
        rect = self.owner().get_screen_rect()
        center = gnipMath.cVector2(rect.centerx, rect.centery)
        start_positions = self.get_snake_starting_positions(len(self.owner()._controllers), self.owner().get_screen_rect())
        if CFG.Round.ShuffleStartLocations:
            random.shuffle(start_positions)
        assert len(start_positions) == len(self.owner()._controllers), 'Did not get the same number of start positions as controllers'
        for idx, controller in enumerate(self.owner()._controllers):
            start_dir = gnipMath.cVector2(1.0, 0.05) if CFG.Debug.On else center - start_positions[idx]
            snake = Snake(controller._color, self.background_color, start_positions[idx], start_dir)
            self.alive_snakes.append(snake)
            controller.possess(snake)

        # setup gameplay surface (visual effects are drawn to main display before game surface is blitted on top of main display)
        self.game_surface = pygame.Surface(pygame.display.get_surface().get_size(), pygame.HWPALETTE, 8)
        self.game_surface.set_palette(self.owner().palette)
        assert isinstance(CFG.Win.BackgroundColorIdx, int)
        self.game_surface.set_colorkey(CFG.Win.BackgroundColorIdx)
        self.game_surface.fill(CFG.Win.BackgroundColorIdx)
        assert isinstance(CFG.Win.BorderColorIdx, int)
        pygame.draw.rect(self.game_surface, CFG.Win.BorderColorIdx, self.owner().get_screen_rect(), 15)

        self._paused = True
        self._fps_timer = gnppygame.FrameTimer()

    def _add_round_labels(self):
        game = self.owner()
        if self._LABEL is not None:
            txt = TextActor(
                game.font_mgr,
                game.fnt,
                60,
                self._LABEL,
                game.get_screen_rect(),
                gnppygame.WHITE,
                'center',
                'center',
                CFG.Round.LabelVisibilityTime
            )
            txt_shadow = TextActor(
                game.font_mgr,
                game.fnt,
                60,
                self._LABEL,
                game.get_screen_rect().move(3, 3),
                gnppygame.BLACK,
                'center',
                'center',
                CFG.Round.LabelVisibilityTime
            )
            self._label_actors.append(txt_shadow)
            self._label_actors.append(txt)

        if self._SUB_LABEL is not None:
            subtxt = TextActor(
                game.font_mgr,
                game.fnt,
                24,
                self._SUB_LABEL,
                game.get_screen_rect().move(0, 50),
                gnppygame.WHITE,
                'center',
                'center',
                CFG.Round.LabelVisibilityTime
            )
            self._label_actors.append(subtxt)

    def begin_state(self):
        """Called right as state beings. Meant to be overridden by subclasses."""
        super(MainGameState, self).begin_state()
        print('start round')

        shrink_time = 0.5 if CFG.Debug.On else 4.8
        for snake in self.alive_snakes:
            color = _darken_color(snake.body_color.rgb, 0.5)
            self.actors.append(gnpactor.GrowingCircle(snake.pos, 40.0, 0.0, color, shrink_time))

        # trigger stutter-start beginning snake animation
        start_delta = 0.1 if CFG.Debug.On else CFG.Round.StartDelta
        self.on_timer_first_step(play_beep=False)
        _game.timers.add(1 * start_delta, self.on_timer_first_step)
        _game.timers.add(2 * start_delta, self.on_timer_first_step)
        _game.timers.add(3 * start_delta, self.on_timer_first_step_and_start)

    def get_snake_starting_positions(self, num_players, playfield_rect):
        assert num_players > 0, 'There are zero players. Can not create starting positions for zero players.'
        radius = self.get_playfield_radius(playfield_rect) * .85
        points = []
        center = gnipMath.cVector2(playfield_rect.centerx, playfield_rect.centery)
        if num_players == 1:
            return [center + gnipMath.cVector2(0, radius * 0.5)]
        for idx in range(num_players):
            normalized = idx / float(num_players)  # scale idx between 0.0-1.0
            start = gnipMath.cPolar2(normalized * (2 * math.pi), radius)
            points.append(center + start.AsVector())
        return points

    def get_playfield_radius(self, playfield_rect):
        return (min(playfield_rect.width, playfield_rect.height) / 2)

    def input(self):
        for controller in self.owner()._controllers:
            controller.input()

##      # HACK: player 3 robot
##      if len(self.aliveSnakes) > 2:
##          s = self.aliveSnakes[2]
##          if s.get_color_under_robot_whisker() == self.backgroundColor:
##              s.set_turn_state(cSnake.kNone)
##          else:
##              s.set_turn_state(cSnake.kLeft)

    def on_timer_first_step(self, play_beep=True):
        if play_beep:
            self.owner().audio_mgr.play('SOUND16')
        # draw the snakes once on the screen
        for snake in self.alive_snakes:
            for _ in range(2):
                snake.step(0.025)  # get the snake to have a bit of color showing
                snake.draw(self.game_surface)

    def on_timer_first_step_and_start(self):
        self.owner().audio_mgr.play('SOUND19')
        self._paused = False
        self.round_timer = gnppygame.Stopwatch()
        self.on_gameplay_begins()

    def on_gameplay_begins(self):
        """Meant to be overridden by rounds if needed"""
        pass

    def draw(self, surface):
        # Working with two main surfaces (so that I can do special effects while also preserving the ability to query a surface for snake collisions):
        # - pygame.display: contains effects (particles, starting circle) and round labels, erased every frame
        # - self.game_surface: snakes and border, erase once at the beginning of each round
        surface.blit(self._surface_eraser, (0, 0))  # erase main display
        self.actors.draw(surface)  # draw visual effects actors (explosions, starting circle)
        self.draw_below_game(surface)  # hook for round customization
        surface.blit(self.game_surface, (0, 0))  # draw 8-bit gameplay surface onto the base display (snakes are drawn to game_surface in the step() method)
        self._label_actors.draw(surface)

    def draw_below_game(self, surface):
        """Render objects underneath the gameplay surface. Meant to be overridden by subclasses."""
        pass

    def end_round(self):
        print('end round')
        self.round_over = True
        # self.owner().font_mgr.draw(screen, self.fnt, 16, '%s crashed' % ', '.join(whoCrashed), pygame.Rect((0, 280), (self.owner().get_screen_rect().width, 40)), kBlack, 'center', 'center')
        print('Game State FPS: %.4f (time: %.3f ticks: %d)' % (self._fps_timer.get_total_fps(), self._fps_timer.get_total_time(), self._fps_timer.get_total_ticks()))
        if CFG.Profiler.On:
            self.owner().request_exit()
        else:
            self.change_state(ShowScoreState(self.owner(), self))
            self.owner().scoreboard.end_round(self.round_timer.get_elapsed())
            self.owner().round_idx += 1

    def step(self, time_delta):
        self._fps_timer.tick()
        self.actors.step(time_delta)
        self._label_actors.step(time_delta)
        display = pygame.display.get_surface()
        self.draw(display)
        self.input()

        if not self._paused:
            if not self.round_over:
                crashed = []
                
                for snake in self.alive_snakes:
                    snake.step(time_delta)
                    snake.draw(self.game_surface)
                    
                for idx, snake in enumerate(self.alive_snakes):
                    if snake.is_dead(self.game_surface):
                        print('Snake %s is dead.' % snake._controller._name)
                        self.actors.append(snake.make_explosion())
                        self.owner().audio_mgr.play('EXPLODE')
                        crashed.append(snake)
                        # go thru all snakes still in list and give them points for living
                        for scoringSnake in self.alive_snakes:
                            # if this snake is dead (probably just died), dont give him a point
                            if not scoringSnake.is_dead(self.game_surface):
                                self.owner().scoreboard.change_score(scoringSnake._controller._index, CFG.Score.PointsForSurviving)

                for crashed_snake in crashed:
                    self.alive_snakes.remove(crashed_snake)
                # end round if all but one snake is dead (if a one player game, end round when that one player dies)
                if (len(self.owner()._controllers) > 1 and len(self.alive_snakes) < 2) or (len(self.owner()._controllers) == 1 and not self.alive_snakes):
                    self.end_round()

        pygame.display.update()


class BasicRound(MainGameState):
    """Round with no special rules"""
    pass


class AppleRound(MainGameState):
    """Round that adds an apple pickup for bonus points"""
    _LABEL = 'The Apple'
    _SUB_LABEL = '%+d' % CFG.AppleRound.PointsPerApple

    def __init__(self, game_obj):
        super(AppleRound, self).__init__(game_obj)
        self._apple = None
        self.owner().timers.add(random.uniform(CFG.AppleRound.SpawnStartTime, CFG.AppleRound.SpawnEndTime), self._on_timer_spawn_apple)

    def _on_timer_spawn_apple(self):
        if self.round_over:
            return
        self.owner().audio_mgr.play('SOUND528')  # CAMERA SOUND43 SOUND53 SOUND528 P735z
        spawn_pt = gnipMath.cVector2(self.game_surface.get_rect().center)
        self._apple = Apple(spawn_pt, CFG.AppleRound.AppleRadius, CFG.AppleRound.AppleColor)

    def step(self, time_delta):
        super(AppleRound, self).step(time_delta)
        if self._apple:
            self._apple.step(time_delta)

        for snake in self.alive_snakes:
            if self._apple is not None and self._apple.is_touching(snake.pos):
                self._apple.reap()
                self._apple = None
                self.owner().audio_mgr.play('SOUND53')  # CAMERA SOUND43 SOUND53 SOUND528 P735
                self.owner().scoreboard.change_score(snake._controller._index, CFG.AppleRound.PointsPerApple)

    def draw(self, surface):
        super(AppleRound, self).draw(surface)
        if self._apple:
            self._apple.draw(surface)


class AppleRushRound(MainGameState):
    """Round that adds multiple apple pickups as the round progresses"""
    _LABEL = 'Apple Rush'
    _SUB_LABEL = '%+d each' % CFG.AppleRushRound.PointsPerApple

    def __init__(self, game_obj):
        super(AppleRushRound, self).__init__(game_obj)
        self._apples = gnppygame.ActorList()
        self.owner().timers.add(3.0, self._on_timer_spawn_apple)

    def _on_timer_spawn_apple(self):
        if self.round_over:
            return
        self.owner().timers.add(0.5, self._on_timer_spawn_apple)
        if len(self._apples) >= CFG.AppleRushRound.MaxApples:
            return
        self.owner().audio_mgr.play('SOUND528')  # CAMERA SOUND43 SOUND53 SOUND528 P735z
        spawn_rect = self.game_surface.get_rect()
        spawn_rect.inflate_ip(-30, -30)  # Keep apple away from edges a bit
        self._apples.append(Apple(gnipMath.cVector2.RandInRect(spawn_rect), CFG.AppleRushRound.AppleRadius, CFG.AppleRushRound.AppleColor))

    def step(self, time_delta):
        super(AppleRushRound, self).step(time_delta)
        self._apples.step(time_delta)

        for snake in self.alive_snakes:
            for apple in self._apples:
                if apple.is_touching(snake.pos):
                    self.owner().audio_mgr.play('SOUND53')  # CAMERA SOUND43 SOUND53 SOUND528 P735
                    self.owner().scoreboard.change_score(snake._controller._index, CFG.AppleRushRound.PointsPerApple)
                    apple.reap()

    def draw(self, surface):
        super(AppleRushRound, self).draw(surface)
        self._apples.draw(surface)


class TurboArcRound(MainGameState):
    """Speed up snake and increase gap size"""
    _LABEL = 'Turbo Arc'

    def __init__(self, game_obj):
        super(TurboArcRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.set_initial_speed(CFG.TurboArcRound.Speed)
            snake.gap_size = CFG.TurboArcRound.GapSize


class ColorBlindRound(MainGameState):
    """Remove color from all snakes"""
    _LABEL = 'Color Blind'

    def __init__(self, game_obj):
        super(ColorBlindRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.body_color = ColorIdxAndRGB(CFG.ColorBlindRound.ColorIdx, CFG.ColorBlindRound.ColorRGB)


class DizzyRoundMode(MainGameState):
    """Flip the directional control of snake"""
    _LABEL = 'Dizzy'

    def __init__(self, game_obj):
        super(DizzyRoundMode, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.turn_rate_left = -snake.turn_rate_left
            snake.turn_rate_right = -snake.turn_rate_right


class IndigestionRound(MainGameState):
    """Change width of snake as round progresses"""
    _LABEL = 'Indigestion'

    def __init__(self, game_obj):
        super(IndigestionRound, self).__init__(game_obj)
        self._elapsed = 0.0
        # phaseShift is so sine wave starts at minimum value
        self._wave = gnipMath.cSineWave(CFG.IndigestionRound.CycleInSeconds, gnipMath.cRange(2.0, 8.0), phaseShift=.75)
        for snake in self.alive_snakes:
            snake.gap_size = CFG.TurboArcRound.GapSize

    def step(self, time_delta):
        super(IndigestionRound, self).step(time_delta)
        self._elapsed += time_delta
        size = int(self._wave.Get(self._elapsed))
        for snake in self.alive_snakes:
            snake.draw_size = size
            snake.whisker_length = max(4, size + 2)  # collision seemed flaky mostly at small widths, not sure why


class ReadyAimRound(MainGameState):
    """Snakes fire projectiles to break through walls"""
    _LABEL = 'Ready, aim...'
    _SUB_LABEL = 'press both buttons'

    class Bullet(object):
        def __init__(self, position, velocity, source_color):
            self._vel = copy.copy(velocity) * 2.0
            self.pos = copy.copy(position) + (self._vel.Normalize() * 5)
            self.source_color = source_color
            self._radius = 3
            self._is_alive = True

        def step(self, time_delta):
            self.pos += self._vel * time_delta

        def draw(self, surface):
            pygame.draw.circle(surface, CFG.Snake.HeadColorRGB, self.pos.AsIntTuple(), self._radius)

        def can_reap(self):
            return not self._is_alive

        def reap(self):
            self._is_alive = False

        def is_touching_wall(self, game_surface):
            # TODO: profile to see if doing a get_at_mapped() is faster than get_at
            try:
                clr = game_surface.get_at(self.pos.AsIntTuple())
            except IndexError as e:
                print('Bullet went offscreen at ' + self.pos.AsIntTuple() + ' Exception: ' + e)
                return True
            touching = clr not in (CFG.Win.BackgroundColorRGB, CFG.Win.BorderColorRGB)
            return touching

    def __init__(self, game_obj):
        super(ReadyAimRound, self).__init__(game_obj)
        self._bullets = gnppygame.ActorList()
        self._vfx_actors = gnppygame.ActorList()
        for snake in self.alive_snakes:
            snake.head_color_dim = CFG.ReadyAimRound.HeadColorDimIdx
            snake.wall_size = CFG.ReadyAimRound.WallSize
        self._bullet_clip_rect = self.game_surface.get_rect().inflate(-20, -20)

    def on_gameplay_begins(self):
        for snake in self.alive_snakes:
            snake.register_both_turn_callback(self.both_turn_callback)

    def both_turn_callback(self, snake):
        """callback for when a player presses both buttons simultaneously"""
        is_alive = snake in self.alive_snakes
        if is_alive and not snake.is_head_dimmed:
            game = self.owner()
            game.audio_mgr.play('SOUND999')  # SOUND49 SOUND58 # SOUND12
            self._bullets.append(self.Bullet(snake.pos, snake.vel, snake.body_color))
            snake.set_head_dim(True)
            game.timers.add(CFG.ReadyAimRound.FiringCooldown, functools.partial(ReadyAimRound.on_timer_reset_firing, snake))

    @staticmethod
    def on_timer_reset_firing(snake):
        """Callback to fire when the snake's cooldown has reset"""
        snake.set_head_dim(False)

    def draw(self, surface):
        super(ReadyAimRound, self).draw(surface)
        self._vfx_actors.draw(surface)
        self._bullets.draw(surface)

    def step(self, time_delta):
        super(ReadyAimRound, self).step(time_delta)
        self._bullets.step(time_delta)
        self._vfx_actors.step(time_delta)
        game_surface = self.game_surface
        for bullet in self._bullets:
            if not self._bullet_clip_rect.collidepoint(bullet.pos.AsIntTuple()):
                self.owner().audio_mgr.play('SOUND105')
                bullet.reap()
            if bullet.is_touching_wall(game_surface):
                self.owner().audio_mgr.play('SOUND49D')
                pygame.draw.circle(game_surface, CFG.Win.BackgroundColorIdx, bullet.pos.AsIntTuple(), CFG.ReadyAimRound.ExplosionRadius)
                self._vfx_actors.extend(self._explosion_factory(bullet.pos, bullet.source_color.rgb))
                bullet.reap()

    @staticmethod
    def _explosion_factory(pos, color):
        implode = gnpactor.GrowingCircle(pos, 35.0, 0.0, gnppygame.DARKGRAY, 0.15)
        explode = gnpparticle.Emitter(
            pos,
            gnpparticle.EmitterRate_DelayRangeWithLifetime(0.001, 0.001, 0.075),
            gnpparticle.EmitterSpeed_Range(50.0, 100.0),
            gnpparticle.EmitterDirection_360(),
            gnpparticle.EmitterLifetime_Range(0.1, 0.4),
            gnpparticle.EmitterColor_Constant(color),
            1
        )
        ring = gnpparticle.Emitter(
            pos,
            gnpparticle.EmitterRate_DelayRangeWithLifetime(0.001, 0.001, 0.1),
            gnpparticle.EmitterSpeed_Constant(15.0),
            gnpparticle.EmitterDirection_360(),
            gnpparticle.EmitterLifetime_Range(1.1, 2.0),
            gnpparticle.EmitterColor_Choice((color, color, gnppygame.DARKGRAY)),
            1
        )
        return implode, explode, ring


class SqueezeRound(MainGameState):
    """Have the playfield slowly shrink"""
    _LABEL = 'Squeeze'

    def __init__(self, game_obj):
        super(SqueezeRound, self).__init__(game_obj)
        game_rect = self.game_surface.get_rect()
        self._center_point = (game_rect.centerx, game_rect.centery)
        self._center_point_jitter = (game_rect.centerx+1, game_rect.centery)
        self._radius = gnipMath.cVector2(self._center_point[0], self._center_point[1]).Magnitude()  # rectangle diagonal
        self._radius = int(self._radius * CFG.SqueezeRound.StartDelayMultiplier)  # delay start of squeeze for a bit
        self._total_time = CFG.SqueezeRound.SqueezeDuration
        self._elapsed = 0.0

    def step(self, time_delta):
        super(SqueezeRound, self).step(time_delta)
        radius = int(gnipMath.Lerp(self._radius, CFG.SqueezeRound.MinCircleRadius, min(self._elapsed / self._total_time, 1.0)))
        # Pygame bug: circles with width > 1 have missing pixels (moire pattern artifacts on concentric circles): Fixed in Pygame 1.9.4: https://stackoverflow.com/a/48720206
        # Put in a hacky fix that draws two circles with a one pixel offset to get rid of circle drawing artifacts
        pygame.draw.circle(self.game_surface, CFG.Win.BorderColorIdx, self._center_point, radius, 3)
        pygame.draw.circle(self.game_surface, CFG.Win.BorderColorIdx, self._center_point_jitter, radius, 3)
        self._elapsed += time_delta
        # Maybe slow down shrink rate as it gets smaller?


class TreasureChamberRound(MainGameState):
    """Draw a chamber with treasures in it"""
    _LABEL = 'Treasure Chamber'
    _SUB_LABEL = '%+d each' % CFG.TreasureChamberRound.PointsPerApple

    def __init__(self, game_obj):
        super(TreasureChamberRound, self).__init__(game_obj)
        game_surface = self.game_surface
        game_rect = game_surface.get_rect()
        center_point = (game_rect.centerx, game_rect.centery)
        self._apples = gnppygame.ActorList()
        for a in range(CFG.TreasureChamberRound.AppleCount):
            pos = gnipMath.cVector2.RandInCircle(center_point, CFG.TreasureChamberRound.ChamberInnerRadius - 10) # -10 is buffer
            apple = Apple(pos, CFG.TreasureChamberRound.AppleRadius, CFG.TreasureChamberRound.AppleColor)
            self._apples.append(apple)

        outer_width = 2 * CFG.TreasureChamberRound.ChamberOuterRadius
        outer_rect = pygame.Rect(0, 0, outer_width, outer_width)
        outer_rect.center = game_rect.center
        inner_width = 2 * CFG.TreasureChamberRound.ChamberInnerRadius
        inner_rect = pygame.Rect(0, 0, inner_width, inner_width)
        inner_rect.center = game_rect.center

        arc_count = 8
        delta = (2*math.pi) / arc_count
        for i in range(arc_count):
            pygame.draw.arc(game_surface, CFG.Win.BorderColorIdx, inner_rect, i*delta, (i*delta)+(delta*.7), 5)
            pygame.draw.arc(game_surface, CFG.Win.BorderColorIdx, outer_rect, i*delta+0.3, (i*delta)+(delta*.7)+0.3, 5)

    def step(self, time_delta):
        super(TreasureChamberRound, self).step(time_delta)
        self._apples.step(time_delta)
        for apple in self._apples:
            for snake in self.alive_snakes:
                if apple.is_touching(snake.pos):
                    apple.reap()
                    self.owner().audio_mgr.play('SOUND53')  # CAMERA SOUND43 SOUND53 SOUND528 P735
                    self.owner().scoreboard.change_score(snake._controller._index, CFG.TreasureChamberRound.PointsPerApple)

    def draw_below_game(self, surface):
        super(TreasureChamberRound, self).draw_below_game(surface)
        self._apples.draw(surface)


class ScatterRound(MainGameState):
    """Each player starts in a random place"""
    _LABEL = 'Scatter'

    def __init__(self, game_obj):
        super(ScatterRound, self).__init__(game_obj)
        # The algorithm for randomly placing the snakes makes sure no two snakes
        # randomly get placed right next to each other where a crash is unavoidable.
        rect = self.game_surface.get_rect()
        pts = ScatterRound._make_grid_points(rect, 140)
        # [self.actors.append(gnpactor.Circle(p, 3, gnppygame.WHITE, 10.0)) for p in pts]  # for visualizing the grid
        pts = [p + ScatterRound._get_jitter_vect(15, 15) for p in pts]
        # [self.actors.append(gnpactor.Circle(p, 3, gnppygame.DARKGRAY, 10.0)) for p in pts]  # for visualizing the grid with jitter
        assert len(pts) >= len(self.alive_snakes), 'Can not shuffle positions for %d snakes from %d possible positions' % (len(self.alive_snakes), len(pts))
        random.shuffle(pts)
        for snake in self.alive_snakes:
            snake.pos = pts.pop()
            snake._start_direction = gnipMath.cVector2.RandomDirection()
            snake.set_initial_speed(CFG.Snake.Speed)

    @staticmethod
    def _make_grid_points(rect, spacing):
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

    @staticmethod
    def _get_jitter_vect(xdelta, ydelta):
        """Return random vector which can be added to other vectors to jitter them slightly"""
        return gnipMath.cVector2(
            random.randint(-xdelta, xdelta),
            random.randint(-ydelta, ydelta)
        )


class NoGapRound(MainGameState):
    """Snakes draw no gaps"""
    _LABEL = 'No Gap'

    def __init__(self, game_obj):
        super(NoGapRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.gap_size = 0


class FollowerRound(MainGameState):
    """An enemy that follows closest snake and eats walls"""
    _LABEL = 'Followers'
    _SUB_LABEL = 'harmless but hungry...'

    class FollowerController(object):
        def __init__(self, target_actor, snakes, boundary_rect):
            self._target = target_actor
            self._snakes = snakes
            self._boundary_rect = boundary_rect.inflate(-50, -50)

        def step(self, time_delta):
            if not self._boundary_rect.collidepoint(self._target.pos.AsIntTuple()):
                # safety to keep snake in the bounds of the playfield
                center = self._boundary_rect.center
                center_vect = gnipMath.cVector2(center[0], center[1])
                vect = (center_vect - self._target.pos).Normalize() * 200.0
                self._target.vel = vect
            else:
                closest = [999999999, None]
                for snake in self._snakes:
                    dist = (snake.pos - self._target.pos).Magnitude()
                    if dist < closest[0]:
                        closest = [dist, snake]
                if closest[1]:
                    vect = (closest[1].pos - self._target.pos).Normalize() * CFG.FollowerRound.FollowerSpeed
                    self._target.vel = vect

        def can_reap(self):
            return False

    class Follower(object):
        def __init__(self, position, source_color):
            self.vel = gnipMath.cVector2()
            self.pos = copy.copy(position)
            self._source_color = source_color
            self._radius = CFG.FollowerRound.FollowerRadius

        def step(self, time_delta):
            self.pos += self.vel * time_delta

        def draw(self, surface):
            pygame.draw.circle(surface, self._source_color, self.pos.AsIntTuple(), self._radius)

        def can_reap(self):
            return False

        def reap(self):
            pass

        def is_touching_something(self, game_surface):
            clr = game_surface.get_at(self.pos.AsIntTuple())
            touching = clr not in (CFG.Win.BackgroundColorRGB, CFG.Win.BorderColorRGB)
            return touching

    def __init__(self, game_obj):
        super(FollowerRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            # snake.gap_size = 0
            snake.wall_size = CFG.FollowerRound.SnakeWallSize
        game_rect = self.game_surface.get_rect()
        radius = (self.get_playfield_radius(game_rect)) * CFG.FollowerRound.FollowerSpawnRadiusPercentage
        self._enemies = gnppygame.ActorList()
        self._controllers = gnppygame.ActorList()
        for _ in range(len(self.alive_snakes)):
            pos = gnipMath.cVector2.RandInCircle(game_rect.center, radius)
            self._enemies.append(FollowerRound.Follower(pos, gnppygame.DARKGRAY))
        for enemy in self._enemies:
            self._controllers.append(FollowerRound.FollowerController(enemy, self.alive_snakes, self.game_surface.get_rect()))

    def step(self, time_delta):
        super(FollowerRound, self).step(time_delta)
        if self._paused:
            return
        game_surface = self.game_surface
        self._controllers.step(time_delta)
        self._enemies.step(time_delta)
        for enemy in self._enemies:
            if enemy.is_touching_something(game_surface):
                pygame.draw.circle(game_surface, CFG.Win.BackgroundColorIdx, enemy.pos.AsIntTuple(), CFG.FollowerRound.FollowerClearRadius)

    def draw(self, surface):
        super(FollowerRound, self).draw(surface)
        self._enemies.draw(surface)


class RightTurnOnlyRound(MainGameState):
    """Snake can only turn to the right"""
    _LABEL = 'Right Turn Only'

    def __init__(self, game_obj):
        super(RightTurnOnlyRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.turn_rate_left = 0.0


class AlternateTurnsRound(MainGameState):
    """Each snake only allowed to turn in alternating directions"""
    _LABEL = 'Alternate'
    _SUB_LABEL = 'left, then right... left, right, left, right...'

    class CallbackShim(object):
        """An object constructed to hold state for each Snake's callback"""
        def __init__(self):
            self.last_turn = None
            self.blocked_state = InputConfig.TURN_RIGHT

        def turn_state_callback(self, snake, cur_turn):
            """Check staet and return True if standard turn logic should be skipped"""
            if cur_turn == self.blocked_state:
                return True
            if cur_turn != self.last_turn and self.last_turn in (InputConfig.TURN_LEFT, InputConfig.TURN_RIGHT):
                self.blocked_state = self.last_turn
            self.last_turn = cur_turn
            return False

    def __init__(self, game_obj):
        super(AlternateTurnsRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake._turn_state_callback = self.CallbackShim().turn_state_callback


class BoostRound(MainGameState):
    """Snakes can boost for a short time"""
    _LABEL = 'Boost'
    _SUB_LABEL = 'press both buttons'

    def __init__(self, game_obj):
        super(BoostRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.head_color_dim = CFG.ReadyAimRound.HeadColorDimIdx

    def on_gameplay_begins(self):
        for snake in self.alive_snakes:
            snake.register_both_turn_callback(self.both_turn_callback)

    def both_turn_callback(self, snake):
        """callback for when a player presses both buttons simultaneously"""
        is_alive = snake in self.alive_snakes
        if is_alive and not snake.is_head_dimmed:
            game = self.owner()
            game.audio_mgr.play('SOUND28') # newemail, PUSH
            snake.set_head_dim(True)
            snake.set_speed(CFG.BoostRound.Speed)
            game.timers.add(CFG.BoostRound.BoostDuration, functools.partial(BoostRound.on_boost_complete, snake))
            game.timers.add(CFG.BoostRound.BoostCooldown, functools.partial(BoostRound.on_boost_timer_reset, snake))

    @staticmethod
    def on_boost_complete(snake):
        """Callback to fire when the snake's cooldown has reset"""
        snake.set_speed(CFG.Snake.Speed)

    @staticmethod
    def on_boost_timer_reset(snake):
        """Callback to fire when the snake's cooldown has reset"""
        snake.set_head_dim(False)


class HitSpacebarToContinueState(gnppygame.GameState):
##  def __init__(self, owner):
##      cGameState.__init__(self, owner)

    def draw_hit_spacebar_to_continue_text(self):
        self.owner().font_mgr.draw(pygame.display.get_surface(), self.owner().fnt, 24, '- Hit spacebar to continue -', self.owner().get_screen_rect(), GLOBAL_RED, 'center', 'bottom')

    def goto_next_state(self):
        """meant to be overridden"""
        pass
    
    def input(self):
        if pygame.key.get_pressed()[pygame.K_SPACE]:
            self.goto_next_state()

    def step(self, time_delta):
        self.input()
        self.draw_hit_spacebar_to_continue_text()
        pygame.display.update()


class Nexter(object):
    """Utility class to get next item from a list, given an item at an unknown position in the list.
    Doesn't support duplicate items in a list."""
    def __init__(self, items):
        if len(items) == 0:
            raise Exception('Nexter can not support empty lists')
        self._items = items

    def get_first(self):
        return self._items[0]

    def get_next(self, cur_item):
        if cur_item not in self._items:
            return self._items[0]
        idx = self._items.index(cur_item)
        idx = (idx + 1) % (len(self._items))
        return self._items[idx]

    def get_random(self):
        return random.choice(self._items)


class PlayerRegistrationState(gnppygame.GameState):
    def __init__(self, owner):
        gnppygame.GameState.__init__(self, owner)

        self.names = Nexter(CFG.Player.Names)
        colors = [ColorIdxAndRGB(idx+CFG.Win.FirstColorIdx, color) for idx, color in enumerate(CFG.Player.Colors)]
        self.colors = Nexter(colors)
        self._dark_rect = gnpactor.AlphaRect(self.owner().get_screen_rect().inflate(-200, -20), (0, 0, 0, 220))
        self._actors = gnppygame.ActorList()

        pygame.event.pump()
        pygame.event.clear()

        self.hold_watcher = gnpinput.HoldWatcher()
        axis_counts = [j._joy.get_numaxes() for j in self.owner().joys if j is not None]
        press_threshold = 0.8
        release_threshold = 0.5
        if len(axis_counts) == 0:
            self.joy_watcher = gnpinput.AxisWatcher(0, 0, press_threshold, release_threshold)
        else:
            self.joy_watcher = gnpinput.AxisWatcher(len(axis_counts), max(axis_counts), press_threshold, release_threshold)

        # setup keyboard key id-to-name lookup map
        key_constants = [(name, value) for name, value in inspect.getmembers(pygame.constants) if name.startswith('K_')]
        self.key_name_lookup = {}
        for key_name, key_id in key_constants:
            key_name = key_name[2:]
            self.key_name_lookup[key_id] = key_name

        # start registration "script"
        self.header = ''
        self.event = None
        self.script = self.registration_script()
        next(self.script)  # give script a chance to init itself

        self.enable_input = False
        self.owner().timers.add(4.5, self.set_enable_input)

    def set_enable_input(self):
        self.enable_input = True

    def draw_player_instructions(self):
        if len(self.owner()._controllers) > 0:
            self.owner().font_mgr.draw(pygame.display.get_surface(), self.owner().fnt, 24, 'Press LEFT/RIGHT to change name/color, hold to remove player. F5 to remove bottom player. Press SPACE to start.', self.owner().get_screen_rect(), GLOBAL_RED, 'center', 'bottom')

    def goto_next_state(self):
        """meant to be overridden"""
        pass

    def can_start_game(self):
        if len(self.owner()._controllers) == 0:
            return False

        if self.player_registration_in_flight:
            print('Cant start game while a player registration is in progress')
            self.owner().audio_mgr.play('HAMMER')
            return False

        if CFG.Player.RequireUniqueColors:
            colors = [c._color for c in self.owner()._controllers]
            count = len(colors)
            unique_count = len(set(colors))

            can_start = count == unique_count
            if not can_start:
                err_msg_rect = self.owner().get_screen_rect().inflate(-50, -50)
                msg_duration = 3.0
                msg = TextActor(
                    self.owner().font_mgr,
                    self.owner().fnt,
                    60,
                    'Everyone must have unique colors before starting',
                    err_msg_rect,
                    gnppygame.WHITE,
                    'center',
                    'center',
                    msg_duration
                )
                self._actors.append(gnpactor.Rect(err_msg_rect, gnppygame.BLACK, msg_duration))
                self._actors.append(msg)
            return can_start
        else:
            return True

    def input(self, time_delta):
        """Call each frame to process input"""
        if not self.enable_input:
            return

        dirty = False
        events = self.hold_watcher.get(pygame.event.get(), time_delta)
        events = self.joy_watcher.get(events)
        for e in events:
            if e.type != pygame.JOYAXISMOTION: print('EVENT:', e)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_F5:
                # don't delete player while a new registration is taking place
                if not self.player_registration_in_flight:
                    print('Clearing last player from list')
                    self.owner().audio_mgr.play('HAMMER')
                    ctrls = self.owner()._controllers
                    if len(ctrls) > 0:
                        ctrls.pop(len(ctrls) - 1)
                    continue  # prevent "else" clause below from handling F5 event
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE and self.can_start_game():
                self.start_game()
            else:
                # do not allow SPACE or F5 to be used for player input
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_F5, pygame.K_ESCAPE):
                    self.owner().audio_mgr.play('HAMMER')
                    continue

                # handle input of players who are already registered
                for controller in self.owner()._controllers:
                    input_config = controller._input_config
                    result = input_config.parse_event(e)
                    if result is not None:
                        if result == InputConfig.TURN_LEFT:
                            self.owner().audio_mgr.play('start')
                            controller._name = self.names.get_next(controller._name)
                            dirty = True
                        elif result == InputConfig.TURN_RIGHT:
                            self.owner().audio_mgr.play('start')
                            controller._color = self.colors.get_next(controller._color)
                            dirty = True
                        elif result == InputConfig.REMOVE_PLAYER:
                            self.owner().audio_mgr.play('HAMMER')
                            print('removing %s via %s' % (controller._name, input_config.name))
                            self.owner()._controllers.remove(controller)
                            dirty = True
                        break
                else:  # else clause on for loop is executed when no "break" statement was encountered
                    # advance "register new players" input handler
                    self.event = e  # can i pass an event to the generator script in a different way? coroutine?
                    next(self.script)
                    dirty = True

        if dirty:
            print('-' * 20, 'Press button or move stick that you want to use for input')
            for c in self.owner()._controllers:
                print(c._name, c._color, c._input_config.name)

    def start_game(self):
        save_player_controllers(self.owner()._controllers)
        print('Starting game...')

        # now that the player list is set, set controller indexes
        for idx, c in enumerate(self.owner()._controllers):
            c._index = idx
        pygame.event.set_blocked(pygame.JOYAXISMOTION)
        self.owner().init_scoreboard()
        self.goto_next_state()

    def draw_player_list(self, surface):
        controllers = self.owner()._controllers
        font_mgr = self.owner().font_mgr
        if len(controllers) > 0:
            self._dark_rect.draw(surface)
        x = 225
        if len(controllers) < 7:
            y, y_delta = (50, 80)
        elif len(controllers) < 10:
            y, y_delta = (15, 65)
        elif len(controllers) < 13:
            y, y_delta = (5, 55)
        else:
            y, y_delta = (0, 40)

        for c in controllers:
            font_mgr.draw(surface, self.owner().fnt, 60, c._name, (x, y), c._color.rgb)
            pygame.draw.rect(surface, c._color.rgb, pygame.Rect(x+400, y+10, 200, 50), 0)
            font_mgr.draw(surface, self.owner().fnt, 24, c._input_config.name, (x +650, y+20), c._color.rgb)
            y += y_delta

    def step(self, time_delta):
        self._actors.step(time_delta)
        if CFG.Debug.On:
            config1 = KeyboardInputConfig(f'keys Q / W', pygame.K_q, pygame.K_w)
            config2 = KeyboardInputConfig(f'keys Z / X', pygame.K_z, pygame.K_x)
            config3 = MouseInputConfig('mouse input config')
            self.owner()._controllers.append(PlayerController('FirstSnake', ColorIdxAndRGB(CFG.Win.FirstColorIdx, CFG.Player.Colors[0]), None, config1))
            self.owner()._controllers.append(PlayerController('SecondSnake', ColorIdxAndRGB(CFG.Win.FirstColorIdx+2, CFG.Player.Colors[2]), None, config2))
            self.owner()._controllers.append(PlayerController('ThirdSnake', ColorIdxAndRGB(CFG.Win.FirstColorIdx+4, CFG.Player.Colors[4]), None, config3))
            self.start_game()
        else:
            # advance the logic that handles new player input registration, name and color changes
            self.input(time_delta)

            s = pygame.display.get_surface()
            if self.enable_input:
                self.draw_player_list(s)
                self.draw_player_instructions()
                self._actors.draw(s)
                self.owner().font_mgr.draw(s, self.owner().fnt, 24, self.header, self.owner().get_screen_rect(), GLOBAL_RED, 'center', 'top')
            pygame.display.update()

    def registration_script(self):
        """Generator-based "script" that drives player checkin and input config"""
        # Called for each event that isn't processed by .input()
        self.player_registration_in_flight = False

        while True:
            self.header = 'Add a new player. Start by pressing a button to be their LEFT control.'

            yield from wait_until(lambda: self.event and self.event.type in (
            pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.JOYBUTTONDOWN))
            self.player_registration_in_flight = True
            self.owner().audio_mgr.play('start')
            joy_msg = ''
            device = ''
            if self.event.type == pygame.KEYDOWN:
                device = 'Keyboard'
            elif self.event.type == pygame.MOUSEBUTTONDOWN:
                device = 'Mouse'
            elif self.event.type == pygame.JOYBUTTONDOWN:
                device = 'Gamepad'
                j = self.owner().joys[self.event.joy]
                joy_msg = f'{j._joy.get_name().strip()} #{j._joy.get_id()}'
            left_event = self.event
            self.header = f'Complete addition of new player by pressing a button on the {device} {joy_msg} to be player\'s RIGHT control.'
            yield  # consume the event that was handled above by yielding control

            yield from wait_until(lambda: is_event_on_same_device_and_not_same_button(left_event, self.event))
            right_event = self.event
            self.owner().audio_mgr.play('Blip')
            if device == 'Keyboard':
                # get string representations of keys that don't have a readable .unicode member
                left_str = left_event.unicode.title()
                if len(left_str.strip()) == 0:
                    left_str = self.key_name_lookup.get(left_event.key, '???').title()
                right_str = right_event.unicode.title()
                if len(right_str.strip()) == 0:
                    right_str = self.key_name_lookup.get(right_event.key, '???').title()

                input_cfg = KeyboardInputConfig(f'{device} {left_str} / {right_str}', left_event.key, right_event.key)
            elif device == 'Mouse':
                input_cfg = MouseInputConfig(f'{device} {left_event.button}/{right_event.button}')
            elif device == 'Gamepad':
                cur_joy = self.owner().joys[self.event.joy]
                desc = f'{cur_joy._joy.get_name().strip()} #{cur_joy._joy.get_id()} {left_event.button}/{right_event.button}'
                input_cfg = JoystickInputConfig(desc, cur_joy, (left_event.button, right_event.button))
            else:
                raise Exception(f'Unknown device: {device}')
            self.owner()._controllers.append(
                PlayerController(self.names.get_random(), self.colors.get_random(), None, input_cfg))
            self.player_registration_in_flight = False
            yield  # consume the event that was handled above by yielding control


def is_event_on_same_device_and_not_same_button(orig_event, other_event):
    """Test if other_event is a compatible event for orig_event: same device, not using same button."""
    if orig_event is None or other_event is None:
        return False

    if orig_event.type == other_event.type:
        if orig_event.type == pygame.KEYDOWN:
            return orig_event.key != other_event.key
        elif orig_event.type == pygame.MOUSEBUTTONDOWN:
            return orig_event.button != other_event.button
        elif orig_event.type == pygame.JOYBUTTONDOWN:
            return orig_event.joy == other_event.joy and orig_event.button != other_event.button
        raise Exception(f'Trying to compare events of unexpected types: {orig_event} {other_event}')
    return False


def wait_until(predicate):
    """generator that blocks until the given predicate evaluates to true"""
    while True:
        if predicate():
            break
        yield


class TitleScreenState(PlayerRegistrationState):
    def begin_state(self):
        PlayerRegistrationState.begin_state(self)
        self.__img = pygame.image.load(str(_resource_path / 'images/ArcArena_title.png'))
        self.screen = pygame.display.get_surface()
        fade_start_time = 1.5  # give monitor time to switch video mode, etc. before staring title screen
        fade_length_time = 1.0
        self._screen_fader = gnppygame.ScreenFader(self.screen.get_rect().size, GLOBAL_BLUE, fade_length_time, 255, 0)
        self.enable_fader = False
        self.owner().timers.add(fade_start_time, self.start_fade)

        # background
        self._surface_bg = pygame.Surface(self.screen.get_size(), 0, self.screen)
        draw_background_concentric_arcs(self._surface_bg, None)

    def start_fade(self):
        self.owner().audio_mgr.play('SOUND243')
        self.enable_fader = True

    def goto_next_state(self):
        self.change_state(self.owner().make_next_round())

    def step(self, time_delta):
        PlayerRegistrationState.step(self, time_delta)
        self.screen.fill(gnppygame.BLACK)

        self.screen.blit(self._surface_bg, (0, 0))  # draw background pattern to main display

        new_scaled_surf = pygame.transform.scale(self.__img, self.owner().get_screen_rect().size)
        self.screen.blit(new_scaled_surf, self.__img.get_rect())

        self._screen_fader.draw(pygame.display.get_surface())
        if self.enable_fader:
            self._screen_fader.step(time_delta)
        
        
class ShowScoreState(HitSpacebarToContinueState):
    def __init__(self, owner, prev_state):
        HitSpacebarToContinueState.__init__(self, owner)
        self.prevState = prev_state

    def begin_state(self):
        print('entered ShowScoreState')
        HitSpacebarToContinueState.begin_state(self)

    def step_and_draw_scoreboard(self, time_delta, surface):
        self._screen_fader = gnppygame.ScreenFader(surface.get_rect().size, gnppygame.BLACK, 0, 140, 140)
        self._screen_fader.draw(surface)
        self.owner().scoreboard.step(time_delta)
        self.owner().scoreboard.draw(surface)

    def goto_next_state(self):
        self.change_state(self.owner().make_next_round())

    def step(self, time_delta):
        display = pygame.display.get_surface()
        self.prevState.actors.step(time_delta)  # breach of encapsulation to draw explosion effects after round is over
        self.prevState.draw(display)
        self.step_and_draw_scoreboard(time_delta, display)
        HitSpacebarToContinueState.step(self, time_delta)


if __name__ == '__main__':
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        _resource_path = Path(sys._MEIPASS, 'resources')  # path relative to root of PyInstaller bundle
        _local_path = Path(sys.executable).parent  # directory the bundle exe lives in
    else:
        _resource_path = Path(__file__).resolve().parent / 'resources'  # path relative to script file
        # for local checkout: _local_path is at top of repo
        # for install from GitHub: _local_path is one dir above venv/
        _local_path = Path(sys.executable).resolve().parent.parent.parent  # one dir above venv\
    print("_resource_path:", _resource_path)
    print("_local_path:", _local_path)
    CFG.Player.Filename = Path(_local_path, CFG.Player.Filename)

    _game = ArcGame()  # global variable

    if CFG.Profiler.On:
        import gnpprofile
        profiler = gnpprofile.Profiler(_game.run_game_loop)
        # print profiler.get_default_report()
        # print profiler.data_as_csv()
        print(profiler.get_summary_report(8))
    else:
        _game.run_game_loop()
        print('Time: %f' % _game._frame_timer.get_total_time())
        print('FPS:  %f' % _game._frame_timer.get_total_fps())

