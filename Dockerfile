FROM python:3.6-alpine

# install lxml dependencies
RUN apk add --no-cache g++ gcc libxml2 libxslt

# copy python code
RUN mkdir -p /prometheus-apache-exporter
COPY src/prometheus-apache-exporter/*.py /prometheus-apache-exporter/
COPY requirements.txt /prometheus-apache-exporter/requirements.txt

# install python packages
WORKDIR /prometheus-apache-exporter
RUN pip install -r requirements.txt

EXPOSE 9345/tcp
CMD ["python", "application.py"]
