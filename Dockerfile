FROM python:3.6-alpine

RUN mkdir -p /prometheus-apache-exporter

COPY requirements.txt /prometheus-apache-exporter/requirements.txt
COPY src/prometheus-apache-exporter/*.py /prometheus-apache-exporter/

WORKDIR /prometheus-apache-exporter

RUN apk add --no-cache py-lxml
RUN pip install -r requirements.txt

EXPOSE 9345/tcp

CMD ["python", "application.py"]
