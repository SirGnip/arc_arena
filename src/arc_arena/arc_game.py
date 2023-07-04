import sys
from pathlib import Path
import pygame
import pygame.constants
from gnp_pygame import gnppygame
import random
from gnp_pygame import gnpinput
from arc_arena import arc_core
from arc_arena import settings
from arc_arena import backgrounds
from arc_arena import round
import traceback


CFG = settings  # quick alias
# simplistic color palette


class ArcGame(gnppygame.GameWithStates):
    def __init__(self, resource_path):
        # call parent ctor
        self.round_idx = 0
        gnppygame.GameWithStates.__init__(
                self,
                'Arc Arena',
                (CFG.Win.ResolutionX, CFG.Win.ResolutionY),
                CFG.Win.Fullscreen)

        self._init_mode_list()
        self.resource_path = resource_path
        self.fnt = str(self.resource_path / 'fonts/Arista2.0.ttf')
        self.font_mgr = gnppygame.FontManager(((self.fnt, 160), (self.fnt, 60), (self.fnt, 24)))
        self.timers = gnppygame.TimerManager()
        event_types = (gnpinput.HOLD, gnpinput.AXISPRESS, gnpinput.AXISRELEASE, pygame.USEREVENT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.KEYUP, pygame.MOUSEBUTTONUP, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP, pygame.JOYAXISMOTION)
        pygame.event.set_allowed(event_types)  # set_allowed is additive

        # graphics
        self.palette = arc_core.make_palette(CFG.Player.Colors)

        # backgrounds
        background_draw_functs = [
            backgrounds.draw_grid,
            backgrounds.draw_circles,
            backgrounds.draw_blue_circles,
            backgrounds.draw_concentric_arcs,
            backgrounds.draw_geometric_scene,
            backgrounds.draw_random_polys,
            backgrounds.draw_player_names,
            backgrounds.draw_soft_circles,
            backgrounds.draw_wave_circles,
            backgrounds.draw_horiz_lines,
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
                self._controllers = arc_core.load_player_controllers(self.joys)
            except Exception as e:
                print('WARNING: Problem loading previous player list from %s. Exception: %s' % (CFG.Player.Filename, type(e)))
                print(traceback.print_exc())
                self._controllers = []
        else:
            self._controllers = []

        # audio manager
        self.audio_mgr = gnppygame.AudioManager(self.resource_path / 'sounds')
        self.audio_mgr.enable_sfx(CFG.Sound.EnableSFX)
        # self.audio_mgr.enable_music(CFG.Sound.EnableMusic)
        # self.audio_mgr.load_music(self.resource_path / '/music/MySong.mp3')
        # self.audio_mgr.play_music(-1)
        # startup sound

        # set initial state
        self.change_state(arc_core.TitleScreenState(self))

    def _init_mode_list(self):
        all_rounds = (
            round.BasicRound,
            round.ScatterRound,
            round.AppleRound,
            round.NoGapRound,
            round.TurboArcRound,
            round.DizzyRound,
            round.IndigestionRound,
            round.ReadyAimRound,
            round.SqueezeRound,
            round.TurboArcRound,
            round.ColorBlindRound,
            round.AppleRushRound,
            round.RightTurnOnlyRound,
            round.ScatterThroughInfinityRound,
            round.LeftTurnOnlyRound,
            round.BoostRound,
            round.TurboArcRound,
            round.OneTooManyRound,
            round.WayTooManyRound,
            round.FollowerRound,
            round.AlternateTurnsRound,
            round.ReadyAimRound,
            round.TreasureChamberRound,
            round.ToInfinityRound,
            round.JukeRound,
            round.GoliathRound,
            round.LeadFootRound,
            round.SpeedCyclesRound,
            round.SqueezeReadyAimComboRound,
            round.BeamMeUpRound,
        )

        basic_only_round = (
            round.BasicRound,
        )

        simple_rounds = (
            round.BasicRound,
            round.BasicRound,
            round.AppleRound,
            round.ScatterRound,
            round.TurboArcRound,
        )

        custom_rounds = (
            round.BasicRound,
            round.BasicRound,
            round.ScatterRound,
            round.BasicRound,
            round.AppleRound,
            round.ScatterRound,
            round.NoGapRound,
            round.BasicRound,
            round.TurboArcRound,
            round.DizzyRound,
            round.ScatterRound,
            round.IndigestionRound,
            round.BasicRound,
            round.ToInfinityRound,
            round.ColorBlindRound,
            round.AppleRushRound,
            round.RightTurnOnlyRound,
            round.SqueezeRound,
            round.ScatterRound,
            round.BoostRound,
            round.FollowerRound,
            round.ReadyAimRound,
            round.ScatterRound,
            round.TreasureChamberRound,
            round.AlternateTurnsRound,
            round.ColorBlindRound,
        )

        favorite_rounds = (
            round.ScatterRound,
            round.IndigestionRound,
            round.AppleRushRound,
            round.BoostRound,
            round.ScatterThroughInfinityRound,
            round.OneTooManyRound,
            round.SqueezeRound,
            round.FollowerRound,
            round.ReadyAimRound,
            round.ToInfinityRound,
            round.JukeRound,
            round.GoliathRound,
            round.WayTooManyRound,
            round.LeadFootRound,
            round.SpeedCyclesRound,
            round.SqueezeReadyAimComboRound,
            round.BeamMeUpRound,
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
        self.scoreboard = arc_core.Scoreboard(scoreboard_rect.move(0, 15), scoreboard_rect.move(0, 85))  # needs to be called after RestartGame
        for controller in self._controllers:
            self.scoreboard.add_player(controller._name, controller._color.rgb)


if __name__ == '__main__':
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        resource_path = Path(sys._MEIPASS, 'resources')  # path relative to root of PyInstaller bundle
        local_path = Path(sys.executable).parent  # directory the bundle exe lives in
    else:
        resource_path = Path(__file__).resolve().parent / 'resources'  # path relative to script file
        # for local checkout: local_path is at top of repo
        # for install from GitHub: local_path is one dir above venv/
        local_path = Path(sys.executable).resolve().parent.parent.parent  # one dir above venv\
    print("resource_path:", resource_path)
    print("local_path:", local_path)
    CFG.Player.Filename = Path(local_path, CFG.Player.Filename)

    arc_core.game = ArcGame(resource_path)  # global variable

    if CFG.Profiler.On:
        import gnpprofile
        profiler = gnpprofile.Profiler(arc_core.game.run_game_loop)
        # print profiler.get_default_report()
        # print profiler.data_as_csv()
        print(profiler.get_summary_report(8))
    else:
        arc_core.game.run_game_loop()
        print('Time: %f' % arc_core.game._frame_timer.get_total_time())
        print('FPS:  %f' % arc_core.game._frame_timer.get_total_fps())

