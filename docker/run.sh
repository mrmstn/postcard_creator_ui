#!/bin/bash

source ${VIRTUAL_ENV}/bin/activate
exec ${VIRTUAL_ENV}/bin/streamlit run ${HOME}/app/streamlit_app.py