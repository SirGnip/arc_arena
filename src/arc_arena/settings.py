from gnp_pygame.gnppygame import *


class Player:
    Filename = 'ArcArena.lastPlayers'

    Names = (
        'Aladdin',
        'Aragorn',
        'Ariel',
        'Athena',
        'Bard',
        'Burt',
        'Batgirl',
        'Batman',
        'Belle',
        'Bouregard',
        'Catwoman',
        'Copland',
        'daVinci',
        'Elmo',
        'Elsa',
        'Ender',
        'Eowyn',
        'Ernie',
        'Gandalf',
        'Guinevere',
        'Hermes',
        'Jedi',
        'Joker',
        'Katniss',
        'Kennedy',
        'Lincoln',
        'Mr. Big',
        'Mufasa',
        'Olaf',
        'Picasso',
        'Princess',
        'Satchmo',
        'Snuffles',
        'Sparkles',
        'Spiderman',
        'Superman',
        'Tinkerbell',
        'Van Gogh',
        'Wonder Woman',
        'Yoda',
        'Zeus',
    )

    _orig_colors = (
        (255, 91, 173),  # pink
        (228, 0, 19),  # red
        (255, 127, 0),  # orange
        (252, 246, 81),  # yellow
        (0, 188, 56),  # green
        (0, 157, 248),  # blue
        (148, 0, 211),  # violet
        (75, 0, 130),  # indigo
        (80, 80, 80),    # dark gray
        (255, 255, 255),  # white
    )
    _extended_colors = (
        (255, 91, 173),  # pink
        (228, 0, 19),  # red
        (255, 127, 0),  # orange
        (252, 246, 81),  # yellow
        (0, 188, 56),  # green
        (0, 255, 255),  # cyan
        (0, 157, 248),  # blue
        (0, 0, 210),  # dark blue
        (148, 0, 211),  # violet
        (75, 0, 130),  # indigo
        (139, 69, 19),  # brown
        (80, 80, 80),    # dark gray
        (170, 170, 170),  # light gray
        (255, 255, 255),  # white
    )
    _neon_colors = ( # Reference: http://www.colourlovers.com/palette/55400/Neon_Virus
        (255, 0, 146),  # neon pink
        (255, 202, 27), # neon orange
        (255, 255, 0),  # yellow
        (182, 255, 0),  # neon lime
        (34, 141, 255), # neon blue
        (186, 1, 255),  # neon purple
    )
    Colors = _extended_colors

    RequireUniqueColors = True

class Score:
    PointsForSurviving = 10

class Snake:
    Speed = 70
    TurnRateDegPerSec = 180
    WallSize = 60
    GapSize = 25
    DrawSize = 3
    HeadColorIdx = 102
    HeadColorRGB = WHITE
    
class Win:
    # HD resolution
    ResolutionX = 1280
    ResolutionY = 720
    Fullscreen = True
    BackgroundColorIdx = 100
    BackgroundColorRGB = (0, 0, 0)
    FirstColorIdx = 105
    BorderColorIdx = 101
    BorderColorRGB = (100, 100, 100)

class Background:
    Visible = True
    RandomizeOrder = True
    GridColor = (4, 0, 4)
    GridAccentColor = (4, 4, 0)
    CirclesAlpha = 3
    BlueCirclesAlpha = 6
    ConcentricArcsBaseColor = (0, 0, 13)  # dark blue
    ConcentricArcsHighlightColor = (13, 2, 6)  # dark scarlet
    GeometricSceneAlpha = 3
    RandomPolysAlpha = 3
    PlayerNamesAlpha = 3
    SoftCirclesAlpha = 2
    WaveCirclesIntensity = 7
    WaveCirclesDarken = 0.04
    HorizLinesClr1 = (0, 8, 0)
    HorizLinesClr2 = (0, 4, 0)
    HorizLinesClr3 = (4, 8, 4)

class BackgroundOrig:
    Visible = True
    RandomizeOrder = True
    GridColor = (25, 0, 25)
    GridAccentColor = (25, 25, 0)
    CirclesAlpha = 4
    BlueCirclesAlpha = 12
    ConcentricArcsBaseColor = (0, 0, 25)  # dark blue
    ConcentricArcsHighlightColor = (25, 3, 12)  # dark scarlet
    GeometricSceneAlpha = 8
    RandomPolysAlpha = 8
    PlayerNamesAlpha = 15
    SoftCirclesAlpha = 4
    WaveCirclesIntensity = 25
    WaveCirclesDarken = 0.15
    HorizLinesClr1 = (0, 36, 0)
    HorizLinesClr2 = (0, 18, 0)
    HorizLinesClr3 = (18, 36, 18)
# Background = BackgroundOrig  # uncomment to use Original, brighter settings


class Input:
    JoyCountMax = 8
    JoyDeadzone = 0.6
    OnePlayerPerJoy = True
    
class Sound:
    EnableSFX = True

class Debug:
    On = False
    FastStart = False

class Profiler:
    On = False


########## Round-specific config
class Round:
    # RoundSet = 'basic_only'
    RoundSet = 'all'
    # RoundSet = 'favorite'
    RandomRoundSelection = False
    ShuffleStartLocations = True
    LabelVisibilityTime = 4.0
    StartDelta = 1.4

class AppleRound:
    PointsPerApple = Score.PointsForSurviving
    SpawnStartTime = 9.0
    SpawnEndTime = 15.0
    AppleRadius = 10
    AppleColor = GREEN

class AppleRushRound:
    MaxApples = 50
    PointsPerApple = 1
    AppleRadius = AppleRound.AppleRadius
    AppleColor = AppleRound.AppleColor

class TurboArcRound:
    Speed = 120
    GapSize = Snake.GapSize * 2

class BoostRound:
    Speed = 300
    BoostDuration = 0.25
    # Speed = 170
    # BoostDuration = 0.4
    BoostCooldown = 8.0

class ColorBlindRound:
    ColorIdx = 104
    ColorRGB = (128, 128, 128)

class IndigestionRound:
    GapSize = Snake.GapSize * 2
    CycleInSeconds = 40.0

class ReadyAimRound:
    FiringCooldown = 2.0
    ExplosionRadius = 20
    WallSize = 200
    HeadColorDimIdx = 103
    HeadColorDimRGB = (160, 160, 160)

class SqueezeRound:
    StartDelayMultiplier = 1.15
    SqueezeDuration = 45.0
    MinCircleRadius = 150

class TreasureChamberRound:
    ChamberOuterRadius = 120
    ChamberInnerRadius = 80
    PointsPerApple = 5
    AppleCount = 5
    AppleRadius = 6
    AppleColor = GOLD

class FollowerRound:
    FollowerSpeed = 45
    FollowerRadius = 6
    FollowerClearRadius = 15
    FollowerSpawnRadiusPercentage = 0.7
    SnakeWallSize = 300
