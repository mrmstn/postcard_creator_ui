#!/bin/bash

source ${VIRTUAL_ENV}/bin/activate
exec ${VIRTUAL_ENV}/bin/fastapi run --proxy-headers "${HOME}/app/api.py"