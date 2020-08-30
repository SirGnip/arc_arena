import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="arc_arena",
    version="1.0.0",
    description="Survive longer than your foes in the arena! A hotseat game that supports a large number of players on one screen.",
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
        "Programming Language :: Python :: 2",
        "Operating System :: OS Independent",
    ],

    package_data={
        "arc_arena": ["resources/images/*", "resources/sounds/*"],
    },

    python_requires='>=2.7',
    install_requires=[
        # 3rd party dependencies
        "gnp_pygame @ http://github.com/SirGnip/gnp_pygame/tarball/v1.0.0#egg=package-1.0",
    ],
)