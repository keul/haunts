#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "setuptools",
    "Click>=7.0",
    "colorama",
    "python-dateutil",
    "google-api-python-client",
    "google-auth-httplib2",
    "google-auth-oauthlib",
    "google-auth<2dev",
]

test_requirements = []

setup(
    author="Luca Fabbri",
    author_email="l.fabbri@bopen.eu",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Fill and sync Google Calendars with events taken from a Google spreadsheet",
    entry_points={
        "console_scripts": [
            "haunts=haunts.cli:main",
        ],
    },
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="google-calendar spreadsheet reports",
    name="haunts",
    packages=find_packages(include=["haunts", "haunts.*"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/bopen/haunts",
    version="0.3.1",
    zip_safe=False,
)
