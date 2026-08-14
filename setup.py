from setuptools import setup, find_packages

setup(
    name="localshare",
    version="2.0.0",
    packages=find_packages(),
    py_modules=["main"],
    install_requires=[
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "pymongo>=4.6.0",
        "cryptography>=42.0.0",
        "qrcode>=8.0",
        "mcp>=1.0.0",
        "python-multipart>=0.0.6",
    ],
    entry_points={
        "console_scripts": [
            "localshare=main:main",
        ],
    },
)
