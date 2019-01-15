FROM python:3.6-alpine

# install lxml
RUN apk add --no-cache libxml2 libxslt libxml2-dev libxslt-dev python-dev py-lxml py3-lxml

# copy python code
RUN mkdir -p /prometheus-apache-exporter
COPY requirements.txt /prometheus-apache-exporter/requirements.txt
COPY src/prometheus-apache-exporter/*.py /prometheus-apache-exporter/

# install python packages
WORKDIR /prometheus-apache-exporter
RUN pip install -r requirements.txt

EXPOSE 9345/tcp
CMD ["python", "application.py"]
