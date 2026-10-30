from setuptools import setup, find_packages

setup(
    name="localshare",
    version="2.1.0",
    packages=find_packages(),
    py_modules=["main"],
    install_requires=[
        "cryptography>=42.0.0",
        "mcp>=1.0.0",
        "customtkinter>=6.0.0",
        "darkdetect>=0.8.0",
        "pillow>=10.0.0",
        "pynput>=1.7.6",
    ],
    entry_points={
        "console_scripts": [
            "localshare=main:main",
        ],
    },
)
