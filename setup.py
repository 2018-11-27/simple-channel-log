# coding:utf-8
import sys
import codecs
import setuptools

if sys.version_info.major < 3:
    open = codecs.open

if sys.version_info >= (3, 8):
    exceptionx = 'exceptionx>=4.1.8,<5.0'
    gqylpy_log = 'gqylpy_log>=2.0.2,<3.0'
else:
    exceptionx = 'exceptionx<1.0'
    gqylpy_log = 'gqylpy_log==0.0a1'

setuptools.setup(
    name='simple-channel-log',
    version='1.8',
    author='Nameless Master',
    author_email='<gqylpy@outlook.com>',
    license='MIT',
    project_urls={'Source': 'https://github.com/2018-11-27/simple-channel-log'},
    description='''
        轻量高效的日志库，支持多级别日志记录、日志轮转、流水日志追踪及埋点日志功能，深度集成
        Flask，FastAPI，Requests，Unirest 以及 CTEC-Consumer 框架。
    '''.strip().replace('\n       ', ''),
    long_description=open('README.md', encoding='utf8').read(),
    long_description_content_type='text/markdown',
    packages=['simple_channel_log'],
    python_requires='>=2.7',
    install_requires=[exceptionx, gqylpy_log, 'ipaddress>=1.0.23,<2.0'],
    extras_require={
        'flask': ['Flask>=0.10'],
        'fastapi': ['fastapi>=0.83.0'],
        'requests': ['requests>=2.19'],
        'unirest': ['unirest>=1.0.5'],
        'ctec-consumer': ['ctec-consumer>=0.1']
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Chinese (Simplified)',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Artistic Software',
        'Topic :: Internet :: Log Analysis',
        'Topic :: Text Processing',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13'
    ]
)
