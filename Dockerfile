FROM python:3.6-alpine

# install lxml
#RUN wget http://nl.alpinelinux.org/alpine/edge/main/x86_64/py-lxml-4.2.5-r0.apk -O /var/cache/apk/py-lxml.apk
#RUN apk add --allow-untrusted /var/cache/apk/py-lxml.apk
#RUN apk add --no-cache libxml2 libxslt py-lxml py3-lxml

RUN wget https://files.pythonhosted.org/packages/5d/d4/e81be10be160a6323cf5f29f1eabc9693080cb16780a2e19c96091ee37ee/lxml-4.3.0-cp36-cp36m-manylinux1_x86_64.whl -O /var/cache/lxml.whl

# copy python code
RUN mkdir -p /prometheus-apache-exporter
COPY requirements.txt /prometheus-apache-exporter/requirements.txt
COPY src/prometheus-apache-exporter/*.py /prometheus-apache-exporter/

# install python packages
WORKDIR /prometheus-apache-exporter
RUN pip install wheel
RUN pip install /var/cache/lxml.whl
RUN pip install -r requirements.txt

EXPOSE 9345/tcp
CMD ["python", "application.py"]
