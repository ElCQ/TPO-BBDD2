FROM python:3.12

COPY ./requirements.txt /requirements.txt

RUN pip install --no-cache-dir -r /requirements.txt

COPY ./app /app
WORKDIR /app/

EXPOSE 80
