FROM python:3.6.9

WORKDIR /app

ADD ./controlboard-subsystem /app

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python", "CB_Subsystem.py", "Config.ini"]
