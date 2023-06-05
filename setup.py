"""Install packages as defined in this file into the Python environment."""
from setuptools import setup


setup(
    name="govqa",
    author="DataMade",
    author_email="info@datamade.us",
    url="https://datamade.us",
    description="Interact with GovQA, a public records request management platform owned by Granicus",
    packages=["govqa"],
    install_requires=[
        "setuptools>=46.4",
        "scrapelib",
        "lxml",
        "jsonschema",
        "python-dateutil",
    ],
    extras_require={
        "dev": ["sphinx", "pytest", "requests-mock", "black", "isort"],
    },
    classifiers=[
        "Development Status :: 1 - Planning",
        "Programming Language :: Python :: 3.0",
        "Topic :: Utilities",
    ],
)
