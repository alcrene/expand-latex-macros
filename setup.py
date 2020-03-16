from setuptools import setup
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(

    name="expand-latex-macros",
    version="2.0.0dev",
    description="A package for replacing latex macros by their definition.",
    long_description=long_description,
    author='Alexandre René',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)'
    ],
    keywords='latex',

    py_modules=["expand_latex_macros"],

    python_requires='>=3.6',

    install_requires=[
        'flap',
        'click'
    ],

    entry_points="""
        [console_scripts]
        expand-latex-macros=expand_latex_macros:main
    """
)
