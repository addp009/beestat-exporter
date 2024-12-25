FROM python:3-slim-buster

WORKDIR /usr/src/app



COPY ./server.py ./server.py
COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 9123

CMD [ "python","-u","/usr/src/app/server.py" ]