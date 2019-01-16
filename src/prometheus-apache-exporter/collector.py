import os
import json
import requests
import tornado.web
from lxml import html, etree
from prometheus_client import generate_latest
from prometheus_client.core import REGISTRY, GaugeMetricFamily, CounterMetricFamily

class MetricHandler(tornado.web.RequestHandler):
    """ Tornado Handler for /metrics endpoint """
    def initialize(self, ref_object):
        self.obj = ref_object

    def get(self):
        self.obj.collect()
        value = self.obj.generate_latest_scrape()
        self.write(value)

    def on_finish(self):
        self.obj = None

class Collector(object):
    """ Apache exporter. Provides information about current workers, status of requests balancing within preconfigured clusters 
        Exporter is configured via environment variables:
          APACHE_EXPORTER_URL - Apache /server-status url. Example: "https://some-host.com/server-status"
          APACHE_EXPORTER_CLUSTERS - Hash (JSON) Clusters and XPath to <TR> element. Example: '{"cluster1": "/html/body/table[5]/tr"}'
        
        Metrics:
          Counter: apache_balancer_acc_total - Total requests count
          Counter: apache_balancer_wr_total - Total bytes written
          Counter: apache_balancer_rd_total - Total bytes read
          Gauge: apache_balancer_route_ok - Balancing status of the route is OK
          Gauge: apache_balancer_route_dis - Balancing status of the route is DISABLED
          Gauge: apache_balancer_route_err - Balancing status of the route is ERROR
          Gauge: apache_balancer_route_unk - Balancing status of the route is UNKNOWN          
          Gauge: apache_scoreboard_current - Count of workers grouped by status
    """
    def __init__(self):
        self.url = os.environ['APACHE_EXPORTER_URL']

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
        except:
            return 0

    def collect(self):
        """ Scrape /server-status url and collect metrics """      
        # Exposed metrics
        balancer_acc = CounterMetricFamily('apache_balancer_acc_total', 'Total requests count', 
                                           labels=['cluster', 'host', 'route'])                                        
        balancer_wr = CounterMetricFamily('apache_balancer_wr_total', 'Total bytes written', 
                                          labels=['cluster', 'host', 'route'])
        balancer_rd = CounterMetricFamily('apache_balancer_rd_total', 'Total bytes read', 
                                          labels=['cluster', 'host', 'route'])
        route_ok = GaugeMetricFamily('apache_balancer_route_ok', 'Balancing status of the route is OK', 
                                     labels=['cluster', 'host', 'route'])
        route_dis = GaugeMetricFamily('apache_balancer_route_dis', 'Balancing status of the route is DISABLED', 
                                      labels=['cluster', 'host', 'route'])
        route_err = GaugeMetricFamily('apache_balancer_route_err', 'Balancing status of the route is ERROR', 
                                      labels=['cluster', 'host', 'route'])
        route_unk = GaugeMetricFamily('apache_balancer_route_unk', 'Balancing status of the route is UNKNOWN', 
                                           labels=['cluster', 'host', 'route'])
        scoreboard = GaugeMetricFamily('apache_scoreboard_current', 'Count of workers grouped by status', 
                                       labels=['status'])

        page = requests.get(self.url, verify=False)       
        root = html.fromstring(page.content)

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
            scoreboard.add_metric([worker_status], int(workers_map[worker_status]))

        # Get balancing and routes status
        try:
            cluster_xpaths = json.loads(os.environ['APACHE_EXPORTER_CLUSTERS'])
        except:
            cluster_xpaths = None

        for cluster in cluster_xpaths:
            h = 0
            for row in root.xpath(cluster_xpaths[cluster]):
                if h == 0:
                    h += 1
                    continue
                else:                    
                    host = row[1].text
                    route = row[3].text
                    status = row[2].text
                    acc = row[7].text
                    wr = row[8].text.replace('K','000').replace('M','000000').replace('G','000000000').replace('.','').strip()
                    rd =  row[9].text.replace('K','000').replace('M','000000').replace('G','000000000').replace('.','').strip()

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
                route_ok.add_metric([cluster,host,route], ok)
                route_dis.add_metric([cluster,host,route], dis)
                route_err.add_metric([cluster,host,route], err)
                route_unk.add_metric([cluster,host,route], unk)
                # Update requests, wr, rd counters
                balancer_acc.add_metric([cluster,host,route], int(acc))
                balancer_wr.add_metric([cluster,host,route], int(wr))
                balancer_rd.add_metric([cluster,host,route], int(rd))
       
        yield scoreboard
        yield balancer_acc
        yield balancer_wr        
        yield balancer_rd                
        yield route_ok
        yield route_dis
        yield route_err
        yield route_unk
