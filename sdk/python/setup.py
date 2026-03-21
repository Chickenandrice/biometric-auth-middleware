from setuptools import setup, find_packages

setup(
    name="bioauth",
    version="0.1.0",
    description="Python SDK for BioAuth Gateway",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=["requests>=2.31.0"],
)
