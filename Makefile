coverage:
	pytest --cov-report term-missing --cov=skmine --cov-config=.coveragerc skmine

setup:
	python setup.py install

clean: clean_doc
	$(RM) *.cpp
	$(RM) *.so
	$(RM) **/*.cpp
	$(RM) **/*.so
	find . -name "*.pyc" -exec rm -f {} \;
	$(RM) -rf dist/ build/ *.egg-info
	$(RM) -rf **/__pycache__/
	$(RM) -rf __pycache__/
	$(RM) -rf htmlcov/
	$(RM) -rf .ipynb*
	$(RM) -rf .pytest_cache/
	


clean_doc:
	$(RM) -f docs/skmine.rst docs/modules.rst


docs: setup clean_doc
	sphinx-apidoc -o docs/ skmine/ tests/*
	$(MAKE) -C docs clean
	$(MAKE) -C docs html

sort_python:
	isort -sl -rc -y   # single line imports for cleaner versionning via git
