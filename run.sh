#!/bin/bash

source venv/Scripts/activate
python spike.py &
deactivate

source venv/Scripts/activate
python wingman.py &
deactivate

wait
