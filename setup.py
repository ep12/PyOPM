import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='pyopm',
    version='0.0.4',
    author='Rodney Meredith McKay',
    # author_email='',
    description='Object Pattern Matching for Python 3',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/ep12/PyOPM',
    packages=setuptools.find_packages(),
    license='GNU LGPL v3',
    keywords=[
        'object patterns',
        'object pattern matching',
        'case statement',
        'match statement',
        'case', 'match',
        'object destructuring',
        # 'overloading',
    ],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        # 'Development Status :: 3 - Alpha',
        # 'Development Status :: 4 - Beta',
        # 'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 6 - Mature',
        'Intended Audience :: Developers',
        'License :: OSI Approved',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries',
        'Topic :: Utilities',
        # 'Typing :: Typed',
        # 'Programming Language :: Python :: Implementation :: CPython',
    ],
    python_requires='>=3.6',
)
