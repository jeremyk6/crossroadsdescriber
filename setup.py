import pathlib
from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="crossroads-description",
    version="0.1.1",
    description="Crossroads description is a python tool that produces automatic description of data from OpenStreetMap.",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://gitlab.limos.fr/jeremyk6/crossroads-description/",
    author="Jérémy Kalsron",
    author_email="jeremy.kalsron@gmail.com  ",
    license="AGPL-3.0",
    classifiers=[
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    install_requires=[
        "osmnx",
        "argparse",
        "geojson",
        "toolz",
        "crossroads-segmentation==0.1.1"
    ],
    packages=["crdesc"],
    include_package_data=True,
)
