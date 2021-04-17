FROM python:3.8-slim-buster

WORKDIR /kraken

COPY requirements.txt /kraken

RUN pip install -r requirements.txt

COPY . /kraken

CMD ["python", "./main/bot.py"]