import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="arc_arena",
    version="2.0.0",
    description="Local multiplayer for a crowd (2-14 players) party game. Modern take on the classic \"snake.\"",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SirGnip/arc_arena",

    # Code is in "src/", an un-importable directory (at least not easily or accidentally)
    # Helps reduce confusion around whether code from repo or site-packages is being used.
    # https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure
    # https://hynek.me/articles/testing-packaging/
    # https://hynek.me/articles/sharing-your-labor-of-love-pypi-quick-and-dirty/
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],

    package_data={
        "arc_arena": ["resources/images/*", "resources/sounds/*", "resources/fonts/*"],
    },

    python_requires='>=3.7',
    install_requires=[
        # 3rd party dependencies
        "gnp_pygame @ http://github.com/SirGnip/gnp_pygame/tarball/v2.1.0#egg=package-1.0",
    ],
)
