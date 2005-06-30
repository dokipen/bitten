@echo off
python -c "import sys; from bitten import master; sys.argv[0] = r'%0'; master.main()" %*
