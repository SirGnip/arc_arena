"""
Code for the different rounds
"""
import math
import random
import functools
import copy
import pygame
from gnp_pygame import gnipMath
from gnp_pygame import gnppygame
from gnp_pygame import gnpactor
from gnp_pygame import gnpparticle
from arc_arena import settings
from arc_arena import utils
from arc_arena import arc_core

CFG = settings  # quick alias


class MainGameState(gnppygame.GameState):
    _LABEL = None
    _SUB_LABEL = None

    def __init__(self, game_obj):
        super(MainGameState, self).__init__(game_obj)
        self.round_over = False
        self.do_wrap = False
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
        start_positions = self.get_snake_starting_positions(len(self.owner()._controllers),
                                                            self.owner().get_screen_rect())
        if CFG.Round.ShuffleStartLocations:
            random.shuffle(start_positions)
        assert len(start_positions) == len(
            self.owner()._controllers), 'Did not get the same number of start positions as controllers'
        for idx, controller in enumerate(self.owner()._controllers):
            start_dir = gnipMath.cVector2(1.0, 0.05) if CFG.Debug.On else center - start_positions[idx]
            snake = arc_core.Snake(controller._color, self.background_color, start_positions[idx], start_dir, rect)
            self.alive_snakes.append(snake)
            controller.possess(snake)

        # setup gameplay surface (visual effects are drawn to main display before game surface is blitted on top of main display)
        self.game_surface = pygame.Surface(pygame.display.get_surface().get_size(), pygame.HWPALETTE, 8)
        self.game_surface.set_palette(self.owner().palette)
        assert isinstance(CFG.Win.BackgroundColorIdx, int)
        self.game_surface.set_colorkey(CFG.Win.BackgroundColorIdx)
        self.game_surface.fill(CFG.Win.BackgroundColorIdx)
        assert isinstance(CFG.Win.BorderColorIdx, int)

        self._paused = True
        self._fps_timer = gnppygame.FrameTimer()

    def enable_wrapping(self):
        self.do_wrap = True
        for snake in self.alive_snakes:
            snake.do_wrap = True

    def _add_round_labels(self):
        game = self.owner()
        if self._LABEL is not None:
            txt = utils.TextActor(
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
            txt_shadow = utils.TextActor(
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
            subtxt = utils.TextActor(
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
        print('start round:', self.__class__.__name__)

        if not self.do_wrap:
            pygame.draw.rect(self.game_surface, CFG.Win.BorderColorIdx, self.owner().get_screen_rect(), 15)

        shrink_time = 0.5 if CFG.Debug.On or CFG.Debug.FastStart else 4.8
        for snake in self.alive_snakes:
            color = utils.darken_color(snake.body_color.rgb, 0.5)
            self.actors.append(gnpactor.GrowingCircle(snake.pos, 40.0, 0.0, color, shrink_time))

        # trigger stutter-start beginning snake animation
        start_delta = 0.1 if CFG.Debug.On or CFG.Debug.FastStart else CFG.Round.StartDelta
        self.on_timer_first_step(play_beep=False)
        arc_core.game.timers.add(1 * start_delta, self.on_timer_first_step)
        arc_core.game.timers.add(2 * start_delta, self.on_timer_first_step)
        arc_core.game.timers.add(3 * start_delta, self.on_timer_first_step_and_start)

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

        # self.do_robot(self.owner()._controllers[0]._snake)
        # self.do_robot(self.owner()._controllers[1]._snake)

    def do_robot(self, snake):
        """Robot doesn't do much. Just ultra-simple wall avoidance, and it doesn't even do that very well."""
        if snake in self.alive_snakes:
            if snake.turning_dir == None:  # only allow robot to take control if there is no key being pressed
                whisk_ctr = snake.get_color_under_robot_whisker(self.game_surface) != CFG.Win.BackgroundColorRGB
                whisk_near_r = snake.get_color_under_near_right_robot_whisker(
                    self.game_surface) != CFG.Win.BackgroundColorRGB
                whisk_near_l = snake.get_color_under_near_left_robot_whisker(
                    self.game_surface) != CFG.Win.BackgroundColorRGB

                if whisk_near_r or whisk_ctr:
                    snake.set_turn_state(Snake.LEFTTURN)
                else:
                    if whisk_near_l:
                        snake.set_turn_state(Snake.RIGHTTURN)
                    else:
                        snake.set_turn_state(Snake.NOTURN)

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
        surface.blit(self.game_surface, (0,
                                         0))  # draw 8-bit gameplay surface onto the base display (snakes are drawn to game_surface in the step() method)
        self._label_actors.draw(surface)

    def draw_below_game(self, surface):
        """Render objects underneath the gameplay surface. Meant to be overridden by subclasses."""
        pass

    def end_round(self):
        print('end round')
        self.round_over = True
        # self.owner().font_mgr.draw(screen, self.fnt, 16, '%s crashed' % ', '.join(whoCrashed), pygame.Rect((0, 280), (self.owner().get_screen_rect().width, 40)), kBlack, 'center', 'center')
        print('Game State FPS: %.4f (time: %.3f ticks: %d)' % (
        self._fps_timer.get_total_fps(), self._fps_timer.get_total_time(), self._fps_timer.get_total_ticks()))
        if CFG.Profiler.On:
            self.owner().request_exit()
        else:
            self.change_state(arc_core.ShowScoreState(self.owner(), self))
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
                                self.owner().scoreboard.change_score(scoringSnake._controller._index,
                                                                     CFG.Score.PointsForSurviving)

                for crashed_snake in crashed:
                    self.alive_snakes.remove(crashed_snake)
                # end round if all but one snake is dead (if a one player game, end round when that one player dies)
                if (len(self.owner()._controllers) > 1 and len(self.alive_snakes) < 2) or (
                        len(self.owner()._controllers) == 1 and not self.alive_snakes):
                    self.end_round()

        pygame.display.update()


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


class BasicRound(MainGameState):
    """Round with no special rules"""
    _LABEL = 'Classic'


class AppleRound(MainGameState):
    """Round that adds an apple pickup for bonus points"""
    _LABEL = 'The Apple'
    _SUB_LABEL = '%+d Points' % CFG.AppleRound.PointsPerApple

    def __init__(self, game_obj):
        super(AppleRound, self).__init__(game_obj)
        self._apple = None
        self.owner().timers.add(random.uniform(CFG.AppleRound.SpawnStartTime, CFG.AppleRound.SpawnEndTime),
                                self._on_timer_spawn_apple)

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
    _SUB_LABEL = '%+d Point(s) Each' % CFG.AppleRushRound.PointsPerApple

    def __init__(self, game_obj):
        super(AppleRushRound, self).__init__(game_obj)
        self._apples = gnppygame.ActorList()
        self.owner().timers.add(3.0, self._on_timer_spawn_apple)
        self.enable_wrapping()

    def _on_timer_spawn_apple(self):
        if self.round_over:
            return
        self.owner().timers.add(0.5, self._on_timer_spawn_apple)
        if len(self._apples) >= CFG.AppleRushRound.MaxApples:
            return
        self.owner().audio_mgr.play('SOUND528')  # CAMERA SOUND43 SOUND53 SOUND528 P735z
        spawn_rect = self.game_surface.get_rect()
        spawn_rect.inflate_ip(-30, -30)  # Keep apple away from edges a bit
        self._apples.append(Apple(gnipMath.cVector2.RandInRect(spawn_rect), CFG.AppleRushRound.AppleRadius,
                                  CFG.AppleRushRound.AppleColor))

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
            snake.body_color = arc_core.ColorIdxAndRGB(CFG.ColorBlindRound.ColorIdx, CFG.ColorBlindRound.ColorRGB)


class DizzyRound(MainGameState):
    """Flip the directional control of snake"""
    _LABEL = 'Dizzy'

    def __init__(self, game_obj):
        super(DizzyRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.turn_rate_left = -snake.turn_rate_left
            snake.turn_rate_right = -snake.turn_rate_right


class JitterRoundBase(MainGameState):
    """Base class for rounds that jitter the snakes movement on a given time interval"""

    def __init__(self, game_obj):
        super(JitterRoundBase, self).__init__(game_obj)
        self.jitter_interval = 1.0
        self.jitter_intensity = 1.0
        self.jitter_amounts = []

    def begin_state(self):
        super(JitterRoundBase, self).begin_state()
        self.jitter_amounts = [
            self.jitter_intensity,
            self.jitter_intensity / 2,
            -self.jitter_intensity,
            -self.jitter_intensity / 2,
        ]
        self.set_timer()

    def set_timer(self):
        game = self.owner()
        game.timers.add(self.jitter_interval, functools.partial(self.on_do_jitter))

    def on_do_jitter(self):
        """Callback to fire when the snake's cooldown has reset"""
        jitter_amount = random.choice(self.jitter_amounts)
        if not self.round_over:
            game = self.owner()
            for snake in self.alive_snakes:
                snake.turn(jitter_amount, 1.0)
            self.set_timer()


class OneTooManyRound(JitterRoundBase):
    _LABEL = 'One Too Many?'

    def __init__(self, game_obj):
        super(OneTooManyRound, self).__init__(game_obj)
        self.jitter_interval = CFG.OneTooManyRound.JitterInterval
        self.jitter_intensity = CFG.OneTooManyRound.JitterIntensity


class WayTooManyRound(JitterRoundBase):
    _LABEL = 'Way Too Many!'

    def __init__(self, game_obj):
        super(WayTooManyRound, self).__init__(game_obj)
        self.jitter_interval = CFG.WayTooManyRound.JitterInterval
        self.jitter_intensity = CFG.WayTooManyRound.JitterIntensity


class JukeRound(MainGameState):
    """Increases the directional control of snake

    Author: Kaelan E."""
    _LABEL = 'Juke'

    def __init__(self, game_obj):
        super(JukeRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.set_initial_speed(CFG.JukeRound.Speed)
            snake.turn_rate_left -= CFG.JukeRound.IncreasedTurnRate
            snake.turn_rate_right += CFG.JukeRound.IncreasedTurnRate


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


class GoliathRound(MainGameState):
    """Increase width of snake as round progresses

    Author: Kaelan E."""
    _LABEL = 'Goliath'

    def __init__(self, game_obj):
        super(GoliathRound, self).__init__(game_obj)
        self._elapsed = 0.0
        for snake in self.alive_snakes:
            snake.set_initial_speed(CFG.GoliathRound.Speed)
            snake.gap_size = CFG.GoliathRound.GapSize

    def step(self, time_delta):
        super(GoliathRound, self).step(time_delta)
        self._elapsed += time_delta
        size = max(1, int(self._elapsed) * 2)
        for snake in self.alive_snakes:
            snake.draw_size = size
            snake.whisker_length = max(4, size + 2)  # collision seemed flaky mostly at small widths, not sure why


class SpeedCyclesRound(MainGameState):
    """Change speed of snake as round progresses

    Author: Kaelan E."""
    _LABEL = 'Speed Cycles'

    def __init__(self, game_obj):
        super(SpeedCyclesRound, self).__init__(game_obj)
        self._elapsed = 0.0
        # phaseShift is so sine wave starts at minimum value
        self._wave = gnipMath.cSineWave(CFG.SpeedCyclesRound.CycleInSeconds, gnipMath.cRange(2.0, 8.0), phaseShift=.75)
        for snake in self.alive_snakes:
            snake.set_initial_speed(CFG.SpeedCyclesRound.Speed)
            snake.gap_size = CFG.SpeedCyclesRound.GapSize

    def step(self, time_delta):
        super(SpeedCyclesRound, self).step(time_delta)
        self._elapsed += time_delta
        speed = int(self._wave.Get(self._elapsed))
        for snake in self.alive_snakes:
            snake.set_speed(CFG.SpeedCyclesRound.Speed * speed)


class LeadFootRound(MainGameState):
    """Increase speed of snake as round progresses

    Author: Kaelan E."""
    _LABEL = 'Lead Foot'

    def __init__(self, game_obj):
        super(LeadFootRound, self).__init__(game_obj)
        self._elapsed = 0.0
        for snake in self.alive_snakes:
            snake.set_initial_speed(CFG.LeadFootRound.Speed)
            snake.gap_size = CFG.LeadFootRound.GapSize

    def step(self, time_delta):
        super(LeadFootRound, self).step(time_delta)
        self._elapsed += time_delta
        speed = int(self._elapsed) * 5
        for snake in self.alive_snakes:
            snake.set_speed(CFG.LeadFootRound.Speed + speed)


class ReadyAimRound(MainGameState):
    """Snakes fire projectiles to break through walls"""
    _LABEL = 'Ready, Aim... Fire!'
    _SUB_LABEL = 'Press both buttons to fire!'

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
                print('Bullet went off-screen at ' + str(self.pos.AsIntTuple()) + ' Exception: ' + str(e))
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
            game.timers.add(CFG.ReadyAimRound.FiringCooldown,
                            functools.partial(ReadyAimRound.on_timer_reset_firing, snake))

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
                pygame.draw.circle(game_surface, CFG.Win.BackgroundColorIdx, bullet.pos.AsIntTuple(),
                                   CFG.ReadyAimRound.ExplosionRadius)
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
        self._center_point_jitter = (game_rect.centerx + 1, game_rect.centery)
        self._radius = gnipMath.cVector2(self._center_point[0], self._center_point[1]).Magnitude()  # rectangle diagonal
        self._radius = int(self._radius * CFG.SqueezeRound.StartDelayMultiplier)  # delay start of squeeze for a bit
        self._total_time = CFG.SqueezeRound.SqueezeDuration
        self._elapsed = 0.0

    def step(self, time_delta):
        super(SqueezeRound, self).step(time_delta)
        radius = int(
            gnipMath.Lerp(self._radius, CFG.SqueezeRound.MinCircleRadius, min(self._elapsed / self._total_time, 1.0)))
        # Pygame bug: circles with width > 1 have missing pixels (moire pattern artifacts on concentric circles): Fixed in Pygame 1.9.4: https://stackoverflow.com/a/48720206
        # Put in a hacky fix that draws two circles with a one pixel offset to get rid of circle drawing artifacts
        pygame.draw.circle(self.game_surface, CFG.Win.BorderColorIdx, self._center_point, radius, 3)
        pygame.draw.circle(self.game_surface, CFG.Win.BorderColorIdx, self._center_point_jitter, radius, 3)
        self._elapsed += time_delta
        # Maybe slow down shrink rate as it gets smaller?


class TreasureChamberRound(MainGameState):
    """Draw a chamber with treasures in it"""
    _LABEL = 'Treasure Chamber'
    _SUB_LABEL = '%+d Points Each' % CFG.TreasureChamberRound.PointsPerApple

    def __init__(self, game_obj):
        super(TreasureChamberRound, self).__init__(game_obj)
        game_surface = self.game_surface
        game_rect = game_surface.get_rect()
        center_point = (game_rect.centerx, game_rect.centery)
        self._apples = gnppygame.ActorList()
        for a in range(CFG.TreasureChamberRound.AppleCount):
            pos = gnipMath.cVector2.RandInCircle(center_point,
                                                 CFG.TreasureChamberRound.ChamberInnerRadius - 10)  # -10 is buffer
            apple = Apple(pos, CFG.TreasureChamberRound.AppleRadius, CFG.TreasureChamberRound.AppleColor)
            self._apples.append(apple)

        outer_width = 2 * CFG.TreasureChamberRound.ChamberOuterRadius
        outer_rect = pygame.Rect(0, 0, outer_width, outer_width)
        outer_rect.center = game_rect.center
        inner_width = 2 * CFG.TreasureChamberRound.ChamberInnerRadius
        inner_rect = pygame.Rect(0, 0, inner_width, inner_width)
        inner_rect.center = game_rect.center

        arc_count = 8
        delta = (2 * math.pi) / arc_count
        for i in range(arc_count):
            pygame.draw.arc(game_surface, CFG.Win.BorderColorIdx, inner_rect, i * delta, (i * delta) + (delta * .7), 5)
            pygame.draw.arc(game_surface, CFG.Win.BorderColorIdx, outer_rect, i * delta + 0.3,
                            (i * delta) + (delta * .7) + 0.3, 5)

    def step(self, time_delta):
        super(TreasureChamberRound, self).step(time_delta)
        self._apples.step(time_delta)
        for apple in self._apples:
            for snake in self.alive_snakes:
                if apple.is_touching(snake.pos):
                    apple.reap()
                    self.owner().audio_mgr.play('SOUND53')  # CAMERA SOUND43 SOUND53 SOUND528 P735
                    self.owner().scoreboard.change_score(snake._controller._index,
                                                         CFG.TreasureChamberRound.PointsPerApple)

    def draw_below_game(self, surface):
        super(TreasureChamberRound, self).draw_below_game(surface)
        self._apples.draw(surface)


class ToInfinityRound(MainGameState):
    _LABEL = 'To Infinity...'
    _SUB_LABEL = "...and beyond!"

    def __init__(self, game_obj):
        super(ToInfinityRound, self).__init__(game_obj)
        self.enable_wrapping()


class ScatterRound(MainGameState):
    """Each player starts in a random place"""
    _LABEL = 'Scatter'

    def __init__(self, game_obj):
        super(ScatterRound, self).__init__(game_obj)
        # The algorithm for randomly placing the snakes makes sure no two snakes
        # randomly get placed right next to each other where a crash is unavoidable.
        rect = self.game_surface.get_rect()
        pts = utils.make_grid_points(rect, 140)
        # [self.actors.append(gnpactor.Circle(p, 3, gnppygame.WHITE, 10.0)) for p in pts]  # for visualizing the grid
        pts = [p + utils.get_jitter_vect(15, 15) for p in pts]
        # [self.actors.append(gnpactor.Circle(p, 3, gnppygame.DARKGRAY, 10.0)) for p in pts]  # for visualizing the grid with jitter
        assert len(pts) >= len(
            self.alive_snakes), 'Can not shuffle positions for %d snakes from %d possible positions' % (
        len(self.alive_snakes), len(pts))
        random.shuffle(pts)
        for snake in self.alive_snakes:
            snake.pos = pts.pop()
            snake._start_direction = gnipMath.cVector2.RandomDirection()
            snake.set_initial_speed(CFG.Snake.Speed)


class ScatterThroughInfinityRound(ScatterRound):
    _LABEL = 'Scatter'
    _SUB_LABEL = "Through Infinity"

    def __init__(self, game_obj):
        super(ScatterThroughInfinityRound, self).__init__(game_obj)
        self.enable_wrapping()


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
    _SUB_LABEL = 'Harmless but hungry...'

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
            self._controllers.append(
                FollowerRound.FollowerController(enemy, self.alive_snakes, self.game_surface.get_rect()))

    def step(self, time_delta):
        super(FollowerRound, self).step(time_delta)
        if self._paused:
            return
        game_surface = self.game_surface
        self._controllers.step(time_delta)
        self._enemies.step(time_delta)
        for enemy in self._enemies:
            if enemy.is_touching_something(game_surface):
                pygame.draw.circle(game_surface, CFG.Win.BackgroundColorIdx, enemy.pos.AsIntTuple(),
                                   CFG.FollowerRound.FollowerClearRadius)

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


class LeftTurnOnlyRound(MainGameState):
    """Snake can only turn to the left

    Author: Kaelan E."""
    _LABEL = 'Left Turn Only'

    def __init__(self, game_obj):
        super(LeftTurnOnlyRound, self).__init__(game_obj)
        for snake in self.alive_snakes:
            snake.turn_rate_right = 0.0


class AlternateTurnsRound(MainGameState):
    """Each snake only allowed to turn in alternating directions"""
    _LABEL = 'Alternate Directions'
    _SUB_LABEL = 'Left, then right... left, right...'

    class CallbackShim(object):
        """An object constructed to hold state for each Snake's callback"""

        def __init__(self):
            self.last_turn = None
            self.blocked_state = arc_core.InputConfig.TURN_RIGHT

        def turn_state_callback(self, snake, cur_turn):
            """Check staet and return True if standard turn logic should be skipped"""
            if cur_turn == self.blocked_state:
                return True
            if cur_turn != self.last_turn and self.last_turn in (arc_core.InputConfig.TURN_LEFT, arc_core.InputConfig.TURN_RIGHT):
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
    _SUB_LABEL = 'Press both buttons to boost!'

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
            game.audio_mgr.play('SOUND28')  # newemail, PUSH
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


class BeamMeUpRound(MainGameState):
    """Teleport your snake. Do you want to take the risk?"""
    _LABEL = 'Beam me up'
    _SUB_LABEL = 'Press both buttons to teleport'

    def __init__(self, game_obj):
        super(BeamMeUpRound, self).__init__(game_obj)
        self.enable_wrapping()
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
            game.audio_mgr.play('SOUND28')  # newemail, PUSH
            snake.set_head_dim(True)
            snake.pos = gnipMath.cVector2.RandInRect(snake.wrap_boundary)
            game.timers.add(CFG.BeamMeUpRound.TeleportCooldown,
                            functools.partial(BeamMeUpRound.on_teleport_timer_reset, snake))

    @staticmethod
    def on_teleport_timer_reset(snake):
        """Callback to fire when the snake's cooldown has reset"""
        snake.set_head_dim(False)


class SqueezeReadyAimComboRound(MainGameState):
    """Have the playfield slowly shrink & snakes fire projectiles to break through walls

    Author: Kaelan E."""
    _LABEL = 'Ready, Aim... Squeeze!'
    _SUB_LABEL = 'Press both buttons to fire!'

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
        super(SqueezeReadyAimComboRound, self).__init__(game_obj)
        game_rect = self.game_surface.get_rect()
        self._center_point = (game_rect.centerx, game_rect.centery)
        self._center_point_jitter = (game_rect.centerx + 1, game_rect.centery)
        self._radius = gnipMath.cVector2(self._center_point[0], self._center_point[1]).Magnitude()  # rectangle diagonal
        self._radius = int(
            self._radius * CFG.SqueezeReadyAimComboRound.StartDelayMultiplier)  # delay start of squeeze for a bit
        self._total_time = CFG.SqueezeReadyAimComboRound.SqueezeDuration
        self._elapsed = 0.0

        self._bullets = gnppygame.ActorList()
        self._vfx_actors = gnppygame.ActorList()
        for snake in self.alive_snakes:
            snake.head_color_dim = CFG.SqueezeReadyAimComboRound.HeadColorDimIdx
            snake.wall_size = CFG.SqueezeReadyAimComboRound.WallSize
        self._bullet_clip_rect = self.game_surface.get_rect().inflate(-20, -20)

    def on_gameplay_begins(self):
        for snake in self.alive_snakes:
            snake.register_both_turn_callback(self.both_turn_callback)

    def both_turn_callback(self, snake):
        """callback for when a player presses both buttons simultaneously"""
        is_alive = snake in self.alive_snakes
        if is_alive and not snake.is_head_dimmed:
            game = self.owner()
            game.audio_mgr.play('SOUND999')
            self._bullets.append(self.Bullet(snake.pos, snake.vel, snake.body_color))
            snake.set_head_dim(True)
            game.timers.add(CFG.SqueezeReadyAimComboRound.FiringCooldown,
                            functools.partial(SqueezeReadyAimComboRound.on_timer_reset_firing, snake))

    @staticmethod
    def on_timer_reset_firing(snake):
        """Callback to fire when the snake's cooldown has reset"""
        snake.set_head_dim(False)

    def draw(self, surface):
        super(SqueezeReadyAimComboRound, self).draw(surface)
        self._vfx_actors.draw(surface)
        self._bullets.draw(surface)

    def step(self, time_delta):
        super(SqueezeReadyAimComboRound, self).step(time_delta)
        radius = int(
            gnipMath.Lerp(self._radius, CFG.SqueezeRound.MinCircleRadius, min(self._elapsed / self._total_time, 1.0)))
        # Pygame bug: circles with width > 1 have missing pixels (moire pattern artifacts on concentric circles): Fixed in Pygame 1.9.4: https://stackoverflow.com/a/48720206
        # Put in a hacky fix that draws two circles with a one pixel offset to get rid of circle drawing artifacts
        pygame.draw.circle(self.game_surface, CFG.Win.BorderColorIdx, self._center_point, radius, 3)
        pygame.draw.circle(self.game_surface, CFG.Win.BorderColorIdx, self._center_point_jitter, radius, 3)
        self._elapsed += time_delta
        # Maybe slow down shrink rate as it gets smaller?

        self._bullets.step(time_delta)
        self._vfx_actors.step(time_delta)
        game_surface = self.game_surface
        for bullet in self._bullets:
            if not self._bullet_clip_rect.collidepoint(bullet.pos.AsIntTuple()):
                self.owner().audio_mgr.play('SOUND105')
                bullet.reap()
            if bullet.is_touching_wall(game_surface):
                self.owner().audio_mgr.play('SOUND49D')
                pygame.draw.circle(game_surface, CFG.Win.BackgroundColorIdx, bullet.pos.AsIntTuple(),
                                   CFG.SqueezeReadyAimComboRound.ExplosionRadius)
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
