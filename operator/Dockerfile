ARG GOLANG_VERSION=latest

FROM quay.io/blueshoe/python3.9-slim AS builder

# python
ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=1.1.7 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    PATH="$PATH:/root/.poetry/bin" \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    \
    # paths
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/venv"


ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        # deps for installing poetry
        curl \
        # deps for building python deps
        build-essential

# install poetry - respects $POETRY_VERSION & $POETRY_HOME
RUN curl -sSL https://install.python-poetry.org | python -

RUN python -m venv $VENV_PATH

# copy project requirement files here to ensure they will be cached.
WORKDIR $PYSETUP_PATH
COPY poetry.lock pyproject.toml ./

# install runtime deps - uses $POETRY_VIRTUALENVS_IN_PROJECT internally
RUN bash -c 'source $VENV_PATH/bin/activate && poetry install --no-dev'

FROM golang:${GOLANG_VERSION} as certstrap
WORKDIR /certstrap
RUN  apt update && apt install -y --no-install-recommends git
RUN git clone https://github.com/square/certstrap && \
    cd certstrap && go build


FROM gcr.io/distroless/python3
COPY --from=builder /opt/pysetup/venv/lib/python3.9/site-packages /usr/lib/python3.9/
COPY . /app/
WORKDIR /app
CMD ["-m", "kopf", "run", "-A", "main.py"]