from setuptools import setup, find_namespace_packages

VERSION = "1.1.1"

# Runtime dependencies. See requirements.txt for development dependencies.
DEPENDENCIES = [
    'bitfinex-v2',
]

setup(
    name='xtobtc',
    version=VERSION,
    description='Job to buy btc',
    author='Iulian Moraru',
    author_email='iulian.moraru@pm.me',
    url='https://gitlab.com/iulian-moraru/xtobtc.git',
    packages=find_namespace_packages(),
    install_requires=DEPENDENCIES,
    include_package_data=True,
    keywords=[],
    classifiers=[],
    zip_safe=True,
    entry_points={
        "console_scripts": [
            "xtobtc = xtobtc.__main__:main",
        ],
    }
)
