from setuptools import setup, find_packages

setup(
    name='amproxy',
    version='1.0.36',  # bisa kamu update sesuai versi release
    description='Manageable load balancer for Docker containers',
    author='Aris',
    url='https://github.com/areesmoon/amproxy',
    packages=find_packages(),
    install_requires=[
        'pyinstaller',
        'pyyaml',
    ],
    entry_points={
        'console_scripts': [
            'amproxy=amproxy.cli:main',  # contoh kalau kamu punya CLI di amproxy/cli.py, fungsi main()
        ],
    },
)
