from pathlib import Path
from setuptools import find_packages, setup

ROOT_DIR = Path(__file__).parent

with open(ROOT_DIR / "README.md") as f:
    long_description = f.read()

with open(ROOT_DIR / "requirements.txt") as f:
    requirements = f.read().splitlines()

link_to_package_name = {
    "github.com/zurk/pretty_logging": "pretty_logging",
}

for i, requirement in enumerate(requirements):
    if not requirement.startswith("git+"):
        continue
    link = requirement.split("//")[1].split("@")[0]
    requirements[i] = f"{link_to_package_name[link]} @ {requirement}"

setup(
    name="doc-search",
    description="Package for searching and summarizing documents.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version="0.1.0",
    url="https://github.com/constantine7cd/doc-search",
    download_url="https://github.com/constantine7cd/doc-search",
    packages=find_packages(),
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 3.11",
    ],
    include_package_data=True,
)
