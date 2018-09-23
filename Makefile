

.PHONY: format
format:
	isort -rc synctogit *.py

.PHONY: lint
lint:
	flake8 && isort --check-only -rc synctogit *.py

.PHONY: test
test:
	coverage run -m py.test
	coverage report

.PHONY: clean
clean:
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	rm -Rf dist
	rm -Rf *.egg-info