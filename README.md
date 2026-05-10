# VSDL-to-KYPO
This repository holds the VSDL-to-KYPO or V2K for short. The V2K is tool for designing cyber-security exercises in VSDL based language to be deployed on KYPO platforms, such as KYPO CSC or KYPO CRP.

# Technical documentation
The technical documentation is in form of pdf in the repository.

# Fast installation
The program can be easily installed and launched by following these steps:
1. download repository
2. extract VSDL-to-KYPO-main
3. install python 3.xx preferably 3.12 and add it to Path
4. using console write:          pip install venv
5. create virtual environment:   python -m venv /path/to/venv
6. activate venv:                /path/to/venv/Scripts/activate
7. move to extracted repo
8. install dependencies:         pip install -r requirements.txt
9. launch program and test it:   main.py
10. deactivate venv:             /path/to/venv/Scripts/deactivate

steps 3 and 4 can be skipped if they are already installed
step 5,6 and 10 can be ignored if you do not wish to run the program in virtual environment

# Deployment platforms
The generated sandbox definition can be deployed on KYPO CSC or CRP.
We do not cover the installation process of the deployment platforms.

For KYPO CSC see: https://gitlab.ics.muni.cz/muni-kypo-csc/cyber-sandbox-creator/-/tree/2e6fc89b815b0daa423355369e1fb7e9eaf8bdad/

For KYPO CRP see: https://gitlab.ics.muni.cz/muni-kypo-crp/kypo-crp-docs/-/blob/f7aadccb2c9cfdfbe75652bcd79d07bbf82621b5/README.md
