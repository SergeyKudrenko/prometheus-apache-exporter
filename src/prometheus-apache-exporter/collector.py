import os
import time
import json
import logging
import requests
import tornado.web
from lxml import html
from prometheus_client import generate_latest
from prometheus_client.core import REGISTRY, GaugeMetricFamily, CounterMetricFamily

class MetricHandler(tornado.web.RequestHandler):
    """ Tornado Handler for /metrics endpoint """
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.logger = logging.getLogger(type(self).__name__)
        self.logger.setLevel(logging.DEBUG)

    def initialize(self, ref_object):
        self.obj = ref_object

    def get(self):
        start = time.clock()
        self.obj.collect()
        value = self.obj.generate_latest_scrape()
        self.write(value)
        end = time.clock()
        self.logger.info("Scraped in %.2gs" % (end-start))        

    def on_finish(self):
        self.obj = None

class Collector(object):
    """ Apache exporter. 
    Provides information about current workers, status of requests balancing within preconfigured clusters """
    def __init__(self):
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(type(self).__name__)

        try:
            self.url = os.environ['APACHE_EXPORTER_URL']
        except Exception as e:
            self.logger.error("ENV variable APACHE_EXPORTER_URL is not set. Exception: %s" % e)

    def generate_latest_scrape(self):
        """ Return a content of Prometheus registry """
        return generate_latest(REGISTRY)

    def ping(self):
        """ Check Apache availability """
        try:
            ping = requests.get(self.url, verify=False)
            if ping.status_code == requests.codes.ok:
                return 1
            else:
                return 0
        except Exception as e:
            self.logger.error("Cannot ping Apache status page. Exception: %s" % e)
            return 0

    def collect(self):
        """ Scrape /server-status url and collect metrics """      
        # Exposed metrics
        balancer_acc = CounterMetricFamily('apache_balancer_requests_total', 'Total requests count', 
                                           labels=['cluster', 'host', 'route', 'exporter_name'])                                        
        balancer_wr = CounterMetricFamily('apache_balancer_write_bytes_total', 'Total bytes written', 
                                          labels=['cluster', 'host', 'route', 'exporter_name'])
        balancer_rd = CounterMetricFamily('apache_balancer_read_bytes_total', 'Total bytes read', 
                                          labels=['cluster', 'host', 'route', 'exporter_name'])
        route_ok = GaugeMetricFamily('apache_balancer_route_ok', 'Balancing status of the route is OK', 
                                     labels=['cluster', 'host', 'route', 'exporter_name'])
        route_dis = GaugeMetricFamily('apache_balancer_route_disabled', 'Balancing status of the route is DISABLED', 
                                      labels=['cluster', 'host', 'route', 'exporter_name'])
        route_err = GaugeMetricFamily('apache_balancer_route_error', 'Balancing status of the route is ERROR', 
                                      labels=['cluster', 'host', 'route', 'exporter_name'])
        route_unk = GaugeMetricFamily('apache_balancer_route_unknown', 'Balancing status of the route is UNKNOWN', 
                                           labels=['cluster', 'host', 'route', 'exporter_name'])
        scoreboard = GaugeMetricFamily('apache_scoreboard_current', 'Count of workers grouped by status', 
                                       labels=['status', 'exporter_name'])
        try:
            exporter_name = os.environ['APACHE_EXPORTER_NAME']
        except:
            exporter_name = 'none'

        try:
            page = requests.get(self.url, verify=False)
            page.raise_for_status()
        except Exception as e:
            self.logger.error("Cannot load Apache status page. Exception: %s" % e)            
        
        try:
            root = html.fromstring(page.content)
        except Exception as e:
            self.logger.error("Cannot parse status page as html. Exception: %s" % e)                        

        # Get workers statuses
        workers_map = {}
        workers = root.xpath('/html/body/pre')[0].text.strip()
        for symbol in range (0,len(workers)):
            if workers[symbol] in workers_map:
                workers_map[workers[symbol]] += 1
            else:
                workers_map[workers[symbol]] = 1            
        # Update metrics 
        for worker_status in workers_map:
            if worker_status == ".":
                status = "Open slot"
            elif worker_status == "_":
                status = "Waiting for Connection"
            elif worker_status == "S":
                status = "Starting up"
            elif worker_status == "R":
                status = "Reading Request"
            elif worker_status == "W":
                status = "Sending Reply"
            elif worker_status == "K":
                status = "Keepalive"
            elif worker_status == "D":
                status = "DNS Lookup"
            elif worker_status == "C":
                status = "Closing connection"
            elif worker_status == "L":
                status = "Logging"
            elif worker_status == "G":
                status = "Gracefully finishing"
            elif worker_status == "I":
                status = "Idle cleanup of worker"                                
            else:
                status = "Unknown"
            if worker_status != "\n":
                scoreboard.add_metric([status, exporter_name], int(workers_map[worker_status]))

        # Get balancing and routes status
        try:
            cluster_xpaths = json.loads(os.environ['APACHE_EXPORTER_CLUSTERS'])
        except Exception as e:
            self.logger.error("Cannot load ENV variable APACHE_EXPORTER_CLUSTERS. Exception: %s" % e)
            cluster_xpaths = None

        for cluster in cluster_xpaths:
            h = 0
            for row in root.xpath(cluster_xpaths[cluster]):
                if h == 0:
                    h += 1
                    continue
                else:                    
                    host = "%s" % row[1].text
                    route = "%s" % row[3].text
                    status = row[2].text
                    acc = row[7].text
                    wr = row[8].text
                    rd =  row[9].text

                # Convert to bytes
                if wr.find('K') > 0:
                    wr = float(wr.replace('K','')) * 2**10
                elif wr.find('M') > 0:
                    wr = float(wr.replace('M','')) * 2**20
                elif wr.find('G') > 0:
                    wr = float(wr.replace('G','')) * 2**30

                if rd.find('K') > 0:
                    rd = float(rd.replace('K','')) * 2**10
                elif rd.find('M') > 0:
                    rd = float(rd.replace('M','')) * 2**20
                elif rd.find('G') > 0:
                    rd = float(rd.replace('G','')) * 2**30

                # Update nodes statuses
                ok, dis, err, unk = 0, 0, 0, 0                
                if status == "Ok":
                    ok = 1                    
                elif status == "Dis":
                    dis = 1
                elif status == "Err":
                    err = 1
                else:
                    unk = 1
                route_ok.add_metric([cluster,host,route,exporter_name], ok)
                route_dis.add_metric([cluster,host,route,exporter_name], dis)
                route_err.add_metric([cluster,host,route,exporter_name], err)
                route_unk.add_metric([cluster,host,route,exporter_name], unk)
                # Update requests, wr, rd counters
                balancer_acc.add_metric([cluster,host,route,exporter_name], int(acc))
                balancer_wr.add_metric([cluster,host,route,exporter_name], int(wr))
                balancer_rd.add_metric([cluster,host,route,exporter_name], int(rd))
       
        yield scoreboard
        yield balancer_acc
        yield balancer_wr        
        yield balancer_rd                
        yield route_ok
        yield route_dis
        yield route_err
        yield route_unk
