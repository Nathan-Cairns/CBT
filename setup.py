#!/usr/bin/env python3

from setuptools import setup

setup(name='cbt',
      description='Generating code using machine learning',
      author='Buster & Nathan',
      packages=['cbt'],
      install_requires=[
            'comment-filter'
      ],
      dependency_links=[
            'https://github.com/codeauroraforum/comment-filter/tarball/master#egg=comment-filter-v1.0.0'
      ])
