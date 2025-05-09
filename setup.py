from setuptools import setup, find_packages
import os

# Read requirements.txt
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

# Read README for long description
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="GitSentry",
    version="0.1.0",
    description="A security tool that detects exposed tokens and secrets in GitHub repositories",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="GitSentry Contributors",
    author_email="ritikrkcr7@gmail.com",
    url="https://github.com/Rkcr7/GitSentry",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Security",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "gitsentry=app:main",
        ],
    },
) 