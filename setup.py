#
# Copyright (c) 2025 broomd0g <broomd0g@wreckinglabs.org>
#
# This software is released under the MIT License.
# See the LICENSE file for more details.

import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


def load_requirements(filename="requirements.txt"):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


setuptools.setup(
    name="dragonkick",
    version="0.1.0",
    author="broomd0g",
    author_email="broomd0g@wreckinglabs.org",
    description="A simple colorful tool to kickstart Ghidra projects from the command line",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wreckinglabs/dragonkick",
    packages=setuptools.find_packages(),

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],

    python_requires=">=3.8",

    install_requires=load_requirements(),

    entry_points={
        "console_scripts": [
            "dragonkick = dragonkick.main:main",
        ],
    },
)
