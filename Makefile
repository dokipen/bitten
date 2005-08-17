PYLINT_MSGS = C0101,E0201,E0213,W0103,W0704,R0921,R0923
PYTHONPATH = .

all: pylint

pylint:
	PYTHONPATH=$(PYTHONPATH) pylint --parseable=yes --include-ids=yes \
	--disable-msg=$(PYLINT_MSGS) --ignore=tests \
	bitten > build/pylint-results.txt
