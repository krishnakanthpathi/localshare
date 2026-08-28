from setuptools import setup, find_packages

setup(
    name="localshare",
    version="2.0.0",
    packages=find_packages(),
    py_modules=["main"],
    install_requires=[
        "cryptography>=42.0.0",
        "mcp>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "localshare=main:main",
        ],
    },
)
