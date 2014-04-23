bumpversion:
	pip install bumpversion

major minor patch: bumpversion
	bumpversion $@
	@echo "push via \`git push origin master --tags\`"

clean:
	find . -name '*.py[co]' -delete
	find . -name '__pycache__' -delete
	find . -name '*.so' -delete
	rm -rf build/ dist/ *.egg *.egg-info/
