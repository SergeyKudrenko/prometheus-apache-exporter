### Apache exporter 
Exporter scrapes Apache /server-status for worker status and  route balancing statistics
 
### Exporter is configured via environment variables:
* APACHE_EXPORTER_URL - Apache /server-status url. Example: "https://some-host.com/server-status"
* APACHE_EXPORTER_CLUSTERS - Hash (JSON) Clusters and XPath to <TR> element. Example: {"cluster1": "/html/body/table[5]/tr"}

### Metrics:
* Counter: apache_balancer_acc_total - Total requests count
* Counter: apache_balancer_wr_total  - Total bytes written
* Counter: apache_balancer_rd_total  - Total bytes read
* Gauge: apache_balancer_route_ok  - Balancing status of the route is OK
* Gauge: apache_balancer_route_dis - Balancing status of the route is DISABLED
* Gauge: apache_balancer_route_err - Balancing status of the route is ERROR
* Gauge: apache_balancer_route_unk - Balancing status of the route is UNKNOWN
* Gauge: apache_scoreboard_current - Count of workers grouped by status

### Endpoints
* /healthz/up - liveness probe
* /healthz/ready - readiness probe
* /metrics - apache metrics

### Run
```bash
docker run -it \
-p 9345:9345 \
-e APACHE_EXPORTER_URL='https://some-host.com/server-status' \
-e APACHE_EXPORTER_CLUSTERS='{"cluster1":"/html/body/table[5]/tr"}' \
--name apache-exporter sergeykudrenko/prometheus-apache-exporter:latest
```
