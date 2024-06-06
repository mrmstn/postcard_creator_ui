FROM python:3.12-slim AS builder
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes pipx
ENV PATH="/root/.local/bin:${PATH}"
RUN pipx install poetry
RUN pipx inject poetry poetry-plugin-bundle
WORKDIR /src
COPY . .
RUN poetry bundle venv --python=/usr/bin/python3 /venv

FROM python:3.12-slim

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 -ms /bin/bash appuser

RUN pip3 install --no-cache-dir --upgrade \
    pip \
    virtualenv

RUN apt-get update && apt-get install -y \
    build-essential \
    software-properties-common \
    git

USER appuser
WORKDIR /home/appuser

COPY --from=builder /venv /venv
ENV VIRTUAL_ENV=/venv

WORKDIR /home/appuser/app

COPY streamlit_app.py   ./streamlit_app.py
COPY api.py             ./api.py
COPY pages              ./pages

EXPOSE 8501

COPY docker/run.sh /home/appuser
COPY docker/run-api.sh /home/appuser
CMD ["/home/appuser/run.sh"]