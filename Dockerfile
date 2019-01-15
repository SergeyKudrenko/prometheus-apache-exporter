FROM python:3.6-alpine

# install lxml
#RUN wget http://nl.alpinelinux.org/alpine/edge/main/x86_64/py-lxml-4.2.5-r0.apk -O /var/cache/apk/py-lxml.apk
#RUN apk add --allow-untrusted /var/cache/apk/py-lxml.apk
RUN apk add --no-cache libxml2 libxslt py-lxml py3-lxml

# copy python code
RUN mkdir -p /prometheus-apache-exporter
COPY requirements.txt /prometheus-apache-exporter/requirements.txt
COPY src/prometheus-apache-exporter/*.py /prometheus-apache-exporter/
WORKDIR /prometheus-apache-exporter

# install python packages
RUN pip install -r requirements.txt

EXPOSE 9345/tcp
CMD ["python", "application.py"]
