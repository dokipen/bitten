@echo off
python -c "import sys; from bitten import slave; sys.argv[0] = r'%0'; slave.main()" %*
