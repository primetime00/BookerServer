FROM python:3.12-alpine

RUN mkdir /app
ADD requirements.txt main.py /app/
RUN pip install -r /app/requirements.txt
RUN mkdir /app/books
VOLUME /app/books
EXPOSE 8080
WORKDIR "/app"
CMD [ "python", "main.py" ]
