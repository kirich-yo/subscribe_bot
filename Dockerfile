FROM python

ARG BOT_TOKEN

ARG MESSAGE_TIMEOUT=10

ARG LOG_FILE_PATH=logs

RUN mkdir subscribe_bot

WORKDIR subscribe_bot

RUN python -m venv venv

CMD source venv/bin/activate

RUN pip install aiogram redis

RUN mkdir ${LOG_FILE_PATH}

VOLUME /subscribe_bot/${LOG_FILE_PATH}

ENV BOT_TOKEN=${BOT_TOKEN}

ENV MESSAGE_TIMEOUT=${MESSAGE_TIMEOUT}

ENV LOG_FILE_PATH=${LOG_FILE_PATH}

COPY main.py middleware.py ./

CMD python main.py
