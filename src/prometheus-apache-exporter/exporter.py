import os
import json
import requests
from lxml import html, etree
from prometheus_client import CollectorRegistry, Gauge, Counter, generate_latest
from prometheus_client.core import REGISTRY, CounterMetricFamily

class exporter(object):
    """ Apache exporter. Provides information about current workers, status of requests balancing within preconfigured clusters 
        Exporter is configured via environment variables:
          APACHE_EXPORTER_URL - Apache /server-status url. Example: "https://some-host.com/server-status"
          APACHE_EXPORTER_CLUSTERS - Hash (JSON) Clusters and XPath to <TR> element. Example: '{"cluster1": "/html/body/table[5]/tr"}'
        
        Metrics:
          Counter: apache_balancer_acc_total - Total requests count
          Counter: apache_balancer_wr_total - Total bytes written
          Counter: apache_balancer_rd_total - Total bytes read
          Gauge: apache_balancer_route_ok - Ok status of the route
          Gauge: apache_balancer_route_dis - Dis status of the route
          Gauge: apache_balancer_route_err - Err status of the route
          Gauge: apache_scoreboard_current - Count of workers grouped by status
    """
    def __init__(self,
                 url):
        self.url = url
        
        self.metrics_registry = CollectorRegistry()

        self.worker_status = Gauge('apache_scoreboard_current', 'Count of workers grouped by status', 
                                  ['status'], registry=self.metrics_registry)                                  
        self.balancer_acc = Gauge('apache_balancer_acc_total', 'Total requests count', 
                                   ['cluster', 'host', 'route'], registry=self.metrics_registry)
        self.balancer_wr = Gauge('apache_balancer_wr_total', 'Total bytes written',
                                  ['cluster', 'host', 'route'], registry=self.metrics_registry)
        self.balancer_rd = Gauge('apache_balancer_rd_total', 'Total bytes read', 
                                  ['cluster', 'host', 'route'], registry=self.metrics_registry)
        self.balancer_route_ok = Gauge('apache_balancer_route_ok', 'Ok status of the route', 
                                      ['cluster', 'host', 'route'], registry=self.metrics_registry)
        self.balancer_route_dis = Gauge('apache_balancer_route_dis', 'Dis status of the route', 
                                       ['cluster', 'host', 'route'], registry=self.metrics_registry)
        self.balancer_route_err = Gauge('apache_balancer_route_err', 'Err status of the route', 
                                       ['cluster', 'host', 'route'], registry=self.metrics_registry)

    def generate_latest_scrape(self):
        """ Return a content of Prometheus registry """
        return generate_latest(self.metrics_registry)

    def ping(self):
        """ Check Apache availability """
        try:
            ping = requests.get(self.url, verify=False)
            if ping.status_code==requests.codes.Ok:
                return 1
            else:
                return 0
        except:
            return 0

    def scrape(self): 
        """ Scrape /server-status url and collect metrics """      
        page = requests.get(self.url, verify=False )       
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
            self.worker_status.labels(status=worker_status).set(workers_map[worker_status])

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

                # Update requests, wr, rd counters
                self.balancer_acc.labels(cluster=cluster,host=host,route=route).set(int(acc))
                self.balancer_wr.labels(cluster=cluster,host=host,route=route).set(int(wr))
                self.balancer_rd.labels(cluster=cluster,host=host,route=route).set(int(rd))

                # Update nodes statuses
                if status == "Ok":
                    self.balancer_route_ok.labels(cluster=cluster,host=host,route=route).set(1)
                    self.balancer_route_dis.labels(cluster=cluster,host=host,route=route).set(0)
                    self.balancer_route_err.labels(cluster=cluster,host=host,route=route).set(0)
                elif status == "Dis":
                    self.balancer_route_ok.labels(cluster=cluster,host=host,route=route).set(0)
                    self.balancer_route_dis.labels(cluster=cluster,host=host,route=route).set(1)
                    self.balancer_route_err.labels(cluster=cluster,host=host,route=route).set(0)
                elif status == "Err":
                    self.balancer_route_ok.labels(cluster=cluster,host=host,route=route).set(0)
                    self.balancer_route_dis.labels(cluster=cluster,host=host,route=route).set(0)
                    self.balancer_route_err.labels(cluster=cluster,host=host,route=route).set(1)
                else:
                    self.balancer_route_ok.labels(cluster=cluster,host=host,route=route).set(0)
                    self.balancer_route_dis.labels(cluster=cluster,host=host,route=route).set(0)
                    self.balancer_route_err.labels(cluster=cluster,host=host,route=route).set(0)