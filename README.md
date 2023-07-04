# Arc Arena

*Can you outlast your foes in the Arena?*

Arc Arena is a "local multiplayer for a crowd" party game for Windows that supports a large number
of players (1-14) on one screen. Extremely simple but competitive gameplay. Good reflexes and an
ability to handle the pressure will help you show those on the couch next to you who is king of
the Arena!

![Arc Arena gameplay](https://sirgnip.github.io/repo/arc_arena/arc_arena_gameplay_15fps_40pct.gif)

There are no fancy 3D graphics here, no soundtrack, no AI players, no single player campaign. Just
lots of competitors sitting shoulder to shoulder, with just two buttons, one screen, and one final
victor!

I'm sure you have played something like the "Snake Game" or "Tron light cycles" before. But have
you ever played it against a large group of your friends, sitting next to you on the couch?

### Features:

- Local multiplayer "for a crowd" (supports 1-14 players)
- Simple controls (only 2 buttons per player)
- Registration screen allows the players to use whatever keyboard, mouse, and gamepads are connected to the computer for their input
- Includes 30 different levels that remix the core gameplay

# Installation

    pip install git+https://github.com/SirGnip/arc_arena.git
    python -m arc_arena.arc_game

# Playing with a large number of players

Screen:

- With lots of players, it helps to have a larger screen. Simply install Arc Arena on a laptop and use an HDMI cable to plug it into a large-screen TV!

Input:

- Strategies for how to play with larger crowds:
    - crowd people around one keyboard (game supports multiple people using one keyboard)
        - When more than 2 or 3 players are sharing the keyboard for their input (which is completely possible and a lot of fun!), you need to be aware of the "[multi-key rollover](https://en.wikipedia.org/wiki/Rollover_(key)#Multi-key_rollover)" limitations of your specific keyboard.
    - plug a second keyboard into your computer
    - plug multiple USB gamepads into a USB hub

# Installation for local development

    # Open a GitBash shell and then enter...
    
    git clone https://github.com/SirGnip/arc_arena.git
    cd arc_arena
    py -3.7 -m venv venv
    source venv/Scripts/activate
    pip install -e .
    python -m arc_arena.arc_game


# Bundle into a self-contained, one-file executable with PyInstaller

    pip install pyinstaller
    pyinstaller src/arc_arena/arc_game.py --name ArcArena --add-data 'src/arc_arena/resources;resources' --onefile
    # .exe generated will be located here: dist/ArcArena.exe

# Revision History

- 2.1.0 (3/2023): rename to Arc Arena, add support for PyInstaller, add custom font, registration screen tweaks, add new rounds (some from Kaelan E).
- 2.0.0 (10/2020): migrated to Python 3, partially to be able to use [PyInstaller](https://www.pyinstaller.org/).
- 1.0.0 (8/2020): migrated code to GitHub, added ability to package with setup.py, extracted shared code into `gnp_pygame`, no attempts at cleanup.
- pre-GitHub (2006, probably even earlier): a big, messy uber-repo-ish kinda thing with tons of random Python code, which included this game. I creatively called the game "Snake".

# History

This game was inspired by my memories of playing "Achtung! Die Kurve" on a friend's Amiga back in the 90's. The experience of having 6 people crammed around one keyboard to battle it out was unforgettable!

![Hits](https://hitcounter.pythonanywhere.com/count/tag.svg?url=https%3A%2F%2Fgithub.com%2FSirGnip%2Farc_arena)

![HitCount](http://hits.dwyl.com/SirGnip/arc_arena.svg)
