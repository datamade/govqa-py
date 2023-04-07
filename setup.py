"""Install packages as defined in this file into the Python environment."""
from setuptools import setup, find_namespace_packages


setup(
    name="govqa",
    author="DataMade",
    author_email="info@datamade.us",
    url="https://datamade.us",
    description="Interact with GovQA, a public records request management platform owned by Granicus",
    package_dir={"": "govqa"},
    packages=find_namespace_packages(where="govqa", exclude=["tests"]),
    install_requires=[
        "setuptools>=46.4",
        "scrapelib",
        "lxml",
    ],
    extras_require={
        "dev": [
            "sphinx",
            "pytest",
            "requests-mock"
        ],
    },
    classifiers=[
        "Development Status :: 1 - Planning",
        "Programming Language :: Python :: 3.0",
        "Topic :: Utilities",
    ],
)
