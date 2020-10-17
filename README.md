# Arc Arena

*Can you survive longer than your foes in the Arena?*

Arc Arena is a "hotseat for a crowd" video game that supports a large number of players (1-10+) on one screen.  Players
are able to use a mix of keyboard, mouse, and gamepads to allow a crowd to compete against each other.

Good reflexes and an ability to handle the pressure will help you show those on the couch next to you who is king of the Arena! 


# Installation

    pip install git+https://github.com/SirGnip/arc_arena.git
    python -m arc_arena.Snake
    
## ...for local development

    # Open a GitBash shell
    git clone https://github.com/SirGnip/arc_arena.git
    cd arc_arena
    py -3.7 -m venv venv
    source venv/Scripts/activate
    pip install -e .
    python -m arc_arena.Snake


# Revision History

- 2.0.0 (10/2020): migrated to Python 3, partially to be able to use [PyInstaller](https://www.pyinstaller.org/).
- 1.0.0 (8/2020): migrated code to GitHub, added ability to package with setup.py, extracted shared code into `gnp_pygame`, no attempts at cleanup.
- pre-GitHub (2006, probably even earlier): a big, messy uber-repo-ish kinda thing with tons of random Python code, which included this game. I creatively called the game "Snake".

[![HitCount](http://hits.dwyl.com/SirGnip/arc_arena.svg)](http://hits.dwyl.com/SirGnip/arc_arena)
