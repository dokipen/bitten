PYLINT_MSGS = C0101,E0201,E0213,W0103,W0704,R0921,R0923

all: pylint test

pylint:
	PYTHONPATH=.:../Trac/trunk pylint --parseable=y --disable-msg=$(PYLINT_MSGS) --ignore=tests bitten > build/pylint.txt

#test:
#	find . -name *.pyc | xargs rm
#	PYTHONPATH=. trac/test.py
