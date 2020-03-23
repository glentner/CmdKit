# Makefile for development.

install:
	@pipenv install --dev

test:
	@pipenv run pytest

dist:
	@pipenv run setup.py sdist bdist_wheel

upload:
	@twine upload dist/*
