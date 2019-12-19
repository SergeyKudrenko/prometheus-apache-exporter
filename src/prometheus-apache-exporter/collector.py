import os
import re
import time
import json
import logging
import requests
import tornado.web
from lxml import html

from prometheus_client import generate_latest
from prometheus_client.core import (REGISTRY, GaugeMetricFamily,
    CounterMetricFamily, HistogramMetricFamily)

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
    Provides information about current workers, status of 
    requests balancing within preconfigured clusters"""
    def __init__(self):
        logging.basicConfig(level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(type(self).__name__)

        try:
            self.url = os.environ['APACHE_EXPORTER_URL']
        except Exception as e:
            self.logger.error(f'Variable APACHE_EXPORTER_URL is not set. {e}')
            raise SystemExit

        try:           
            self.url_substract_rules = json.loads(
                os.environ['APACHE_URL_SUBSTRACT_RULES']
            )
        except Exception as e:
            self.logger.warn(
                f'Could not get APACHE_URL_SUBSTRACT_RULES. {e}'
            )
            self.logger.warn(
                'APACHE_URL_SUBSTRACT_RULES value: {}'.format(
                    self.url_substract_rules
                )
            )

        #  Collect additional statistics about requests
        try:
            self.endpoint_stats = os.environ['APACHE_ENDPOINT_STATISTICS']
            if self.endpoint_stats.lower() == "true":
                self.endpoint_stats = True
            else:
                self.endpoint_stats = False
        except Exception as e:
            self.endpoint_stats = False

        self.url_count = {}
        self.url_sum = {}      


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
            self.logger.error(f'Failed to ping Apache. Exception: {e}')
            return 0


    @staticmethod
    def str_to_bytes(str):
        """ Converts string to bytes """
        str = str.upper()
        res = 0

        pos = str.find('K')
        if pos > 0:
            res = float(str[0:pos].strip()) * 2**10
            return res       
        pos = str.find('M')
        if pos > 0:
            res = float(str[0:pos].strip()) * 2**20
            return res
        pos = str.find('G')
        if pos > 0:
            res = float(str[0:pos].strip()) * 2**30
            return res
        pos = str.find('B')
        if pos > 0:
            res = float(str[0:pos].strip())
            return res

        return res


    def sanitize_url(self, input_url):       
        if input_url == 'NULL' or input_url == '..reading..' \
            or input_url.find(" ") == -1:
            return None, None
        if self.url_substract_rules is None:
            return None, None

        #  split into method and url       
        method, tmp = input_url.split(sep=" ", maxsplit=1)                
        
        #  take first 5 contexts
        url = ""
        url_parts = tmp.strip().split(sep="/", maxsplit=6)            
        for x in url_parts[1:5]:
            url += "/%s" % x
        
        #  remove dymanic content
        for rule in self.url_substract_rules:
            pos = url.find(rule)            
            if pos >= 0:
                url = url[0:pos+len(rule)]

        return method, url


    def put_histogram_values(self, method, url, duration):
        buckets = [0.01,0.1,0.25,0.5,1.0,2.5,5.0,10.0,30.0,999999]
        buckets.sort(reverse=True)

        for b in buckets:
            bucket_name = str(b).replace('999999','+inf')
            if duration <= b:
                if (method, url, bucket_name) not in self.url_count:
                    self.url_count[method, url, bucket_name] = 1
                else:
                    self.url_count[method, url, bucket_name] += 1
                if (method, url) not in self.url_sum:
                    self.url_sum[method, url] = duration
                else:
                    self.url_sum[method, url] += duration
            elif duration > b:
                if (method, url, bucket_name) not in self.url_count:
                    self.url_count[method, url, bucket_name] = 0
                if (method, url) not in self.url_sum:
                    self.url_sum[method, url] = 0


    def collect(self):
        """ Scrape /server-status url and collect metrics """      
        #  Counters
        accesses_total = CounterMetricFamily('apache_accesses_total', 
            'Total requests served count since startup',
            labels=['exporter_name'])                                     
        traffic_total = CounterMetricFamily('apache_traffic_bytes_total', 
            'Total bytes transfered since startup', 
            labels=['exporter_name'])
        balancer_acc = CounterMetricFamily('apache_balancer_requests_total', 
            'Total requests count', 
            labels=['cluster', 'host', 'route', 'exporter_name'])                                        
        balancer_wr = CounterMetricFamily('apache_balancer_write_bytes_total', 
            'Total bytes written', 
            labels=['cluster', 'host', 'route', 'exporter_name'])
        balancer_rd = CounterMetricFamily('apache_balancer_read_bytes_total', 
            'Total bytes read', 
            labels=['cluster', 'host', 'route', 'exporter_name'])       
        #  Gauges
        requests_sec = GaugeMetricFamily('apache_requests_per_second', 
            'Requests per second', 
            labels=['exporter_name'])
        bytes_sec = GaugeMetricFamily('apache_io_bytes_per_second', 
            'Bytes write/read per second', 
            labels=['exporter_name'])
        bytes_request = GaugeMetricFamily('apache_io_bytes_per_request', 
            'Bytes write/read  per request', 
            labels=['exporter_name'])
        route_ok = GaugeMetricFamily('apache_balancer_route_ok', 
            'Balancing status of the route is OK', 
            labels=['cluster', 'host', 'route', 'exporter_name'])
        route_dis = GaugeMetricFamily('apache_balancer_route_disabled', 
            'Balancing status of the route is DISABLED', 
            labels=['cluster', 'host', 'route', 'exporter_name'])
        route_err = GaugeMetricFamily('apache_balancer_route_error', 
            'Balancing status of the route is ERROR', 
            labels=['cluster', 'host', 'route', 'exporter_name'])
        route_unk = GaugeMetricFamily('apache_balancer_route_unknown', 
            'Balancing status of the route is UNKNOWN', 
            labels=['cluster', 'host', 'route', 'exporter_name'])
        scoreboard = GaugeMetricFamily('apache_scoreboard_current', 
            'Count of workers grouped by status',
            labels=['status', 'exporter_name'])
        latest_scrape=GaugeMetricFamily(
            'apache_latest_scrape_duration_seconds',
            'Latest scrape duration in seconds',
            labels=['metric_name','exporter_name']
        )
        operation_duration=GaugeMetricFamily(
            'apache_operation_duration_seconds',
            'Operation duration in seconds',
            labels=['operation','exporter_name']
        )

        #  Histograms
        endpoint_response_time = HistogramMetricFamily(
            'apache_endpoint_response_time_seconds', 
            'Response time by endpoints', 
            labels=['method', 'endpoint', 'exporter_name']
        )

        try:
            exporter_name = os.environ['APACHE_EXPORTER_NAME']
        except:
            exporter_name = 'none'

        start = time.clock()
        try:
            page = requests.get(self.url, verify=False)
            page.raise_for_status()
        except Exception as e:
            self.logger.error(f'Failed to Apache status page. Exception: {e}')
        duration = float("%.3g" % (time.clock()-start))
        operation_duration.add_metric(['load_page',exporter_name], duration)

        start = time.clock()
        try:
            root = html.fromstring(page.content)
        except Exception as e:
            self.logger.error(f'Failed to parse page as html. Exception: {e}')
        duration = float("%.3g" % (time.clock()-start))
        operation_duration.add_metric(['parse_page',exporter_name], duration)

        #  Total traffic and accesses and requests,bytes per second/request
        start = time.clock()
        for x in range(1, 20):
            tmp_str = root.xpath("/html/body/dl[2]/dt[%d]" % x)[0].text.strip()
            if tmp_str.find('Total accesses:') >=0:
                match = re.match('Total accesses: (.*) - Total Traffic: (.*)', 
                                 tmp_str)
                _accesses_total = match.group(1)
                _traffic_total = self.str_to_bytes(match.group(2))
                #  Update metrics if they were found
                if _accesses_total is not None:
                    accesses_total.add_metric([exporter_name], _accesses_total)
                if _traffic_total is not None:
                    traffic_total.add_metric([exporter_name], _traffic_total)
                break
        duration = float("%.3g" % (time.clock()-start))
        latest_scrape.add_metric(['apache_accesses_total',exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_traffic_bytes_total',exporter_name], 
                                 duration)

        start = time.clock()
        for x in range(1, 20):
            tmp_str = root.xpath("/html/body/dl[2]/dt[%d]" % x)[0].text.strip()
            if tmp_str.find('requests') >=0 and tmp_str.find('second') >=0:
                match=re.match(
                    '(.*) requests/sec - (.*/second) - (.*/request)', tmp_str
                )
                _requests_sec = match.group(1)
                _bytes_sec = self.str_to_bytes(match.group(2))
                _bytes_request = self.str_to_bytes(match.group(3))
                #  Update metrics if they were found
                if _requests_sec is not None:
                    requests_sec.add_metric([exporter_name], _requests_sec)
                if _bytes_sec is not None:
                    bytes_sec.add_metric([exporter_name], _bytes_sec)
                if _bytes_request is not None:
                    bytes_request.add_metric([exporter_name], _bytes_request)
                break
        duration = float("%.3g" % (time.clock()-start))
        latest_scrape.add_metric(['apache_requests_per_second',exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_io_bytes_per_second',exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_io_bytes_per_request',exporter_name], 
                                 duration)

        #  Get workers statuses
        start = time.clock()
        workers_map = {}
        workers = root.xpath('/html/body/pre')[0].text.strip()
        for symbol in range (0,len(workers)):
            if workers[symbol] in workers_map:
                workers_map[workers[symbol]] += 1
            else:
                workers_map[workers[symbol]] = 1            
        #  Update metrics 
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
                #Update workers scoreboard
                scoreboard.add_metric([status, exporter_name], 
                                      int(workers_map[worker_status]))
        duration = float("%.3g" % (time.clock()-start))
        latest_scrape.add_metric(['apache_scoreboard_current',exporter_name], 
                                 duration)

        #  Get balancing and routes status
        start = time.clock()        
        try:
            cluster_xpaths = json.loads(os.environ['APACHE_EXPORTER_CLUSTERS'])
        except Exception as e:
            self.logger.error(f'Cannot load APACHE_EXPORTER_CLUSTERS. {e}')
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
                    wr = self.str_to_bytes(row[8].text)
                    rd =  self.str_to_bytes(row[9].text)

                #  Update nodes statuses
                ok, dis, err, unk = 0, 0, 0, 0
                if status.find('Ok') >= 0:
                    ok = 1                    
                elif status.find('Dis') >= 0:
                    dis = 1
                elif status.find('Err') >= 0:
                    err = 1
                else:
                    unk = 1
                #  Route statuses
                route_ok.add_metric([cluster,host,route,exporter_name], ok)
                route_dis.add_metric([cluster,host,route,exporter_name], dis)
                route_err.add_metric([cluster,host,route,exporter_name], err)
                route_unk.add_metric([cluster,host,route,exporter_name], unk)
                #  Update requests, wr, rd counters
                balancer_acc.add_metric([cluster,host,route,exporter_name], 
                                        int(acc))
                balancer_wr.add_metric([cluster,host,route,exporter_name], 
                                        int(wr))
                balancer_rd.add_metric([cluster,host,route,exporter_name], 
                                        int(rd))
        duration = float("%.3g" % (time.clock()-start))
        latest_scrape.add_metric(['apache_balancer_route_ok',
                                 exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_balancer_route_disabled',
                                 exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_balancer_route_error',
                                 exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_balancer_route_unknown',
                                 exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_balancer_requests_total',
                                 exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_balancer_write_bytes_total',
                                 exporter_name], 
                                 duration)
        latest_scrape.add_metric(['apache_balancer_read_bytes_total',
                                 exporter_name], 
                                 duration)

        #  Get response time by endpoints
        start = time.clock()        
        h = 0
        for row in root.xpath('/html/body/table[1]/tr'):
            last_column = len(row)
            if h == 0:
                h += 1
                for h in range(0,last_column):
                    header = row[h].text.upper()
                    if header == 'REQ':
                        req_pos = h
                    elif header == 'REQUEST':
                        request_pos = h
                continue
            else:
                try:
                    duration = float(row[req_pos].text) / 1000
                    url = ("%s" % row[request_pos].text).strip()
                    method, url = self.sanitize_url(url)
                    if method is not None and url is not None:
                        self.put_histogram_values(method, url, duration)
                except:
                    pass
        
        #  group buckets into one list
        url_buckets = {}
        for i in self.url_count:
            if (i[0],i[1]) not in url_buckets:
                url_buckets[i[0],i[1]] = [[i[2],self.url_count[i]]]
            else:
                url_buckets[i[0],i[1]].append([i[2],self.url_count[i]])
        
        for t in url_buckets:
            if (t[0], t[1]) in self.url_sum:
                endpoint_response_time.add_metric([t[0], t[1], exporter_name],
                                                  buckets=url_buckets[t],
                                                  sum_value=self.url_sum[t[0], 
                                                                         t[1]])
        duration = float("%.3g" % (time.clock()-start))
        latest_scrape.add_metric(['apache_endpoint_response_time_seconds',
                                 exporter_name], 
                                 duration)

        #  counters
        yield accesses_total
        yield traffic_total
        yield balancer_acc
        yield balancer_wr
        yield balancer_rd
        #  gauges
        yield requests_sec
        yield bytes_sec
        yield bytes_request
        yield route_ok
        yield route_dis
        yield route_err
        yield route_unk
        yield scoreboard
        yield latest_scrape
        yield operation_duration
        #  histograms
        if self.endpoint_stats:
            yield endpoint_response_time
