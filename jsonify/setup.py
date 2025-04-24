from setuptools import setup, find_packages

setup(
    name='xmljsonify',
    version='1.0.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},  # 'src' é o diretório raiz dos pacotes
    install_requires=[
        'lxml',
        'setuptools',
    ],
    entry_points={
        'console_scripts': [
            'xmljsonify=main:main',  # O ponto de entrada para o script
        ],
    },
)
