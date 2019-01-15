### Apache exporter 
Provides information about current workers, status of requests balancing within preconfigured clusters 
 
### Exporter is configured via environment variables:
* APACHE_EXPORTER_URL - Apache /server-status url. Example: "https://some-host.com/server-status"
* APACHE_EXPORTER_CLUSTERS - Hash (JSON) Clusters and XPath to <TR> element. Example: {"cluster1": "/html/body/table[5]/tr"}

### Metrics:
* Counter: apache_balancer_acc_total - Total requests count
* Counter: apache_balancer_wr_total - Total bytes written
* Counter: apache_balancer_rd_total - Total bytes read
* Gauge: apache_balancer_route_ok - Ok status of the route
* Gauge: apache_balancer_route_dis - Dis status of the route
* Gauge: apache_balancer_route_err - Err status of the route
* Gauge: apache_scoreboard_current - Count of workers grouped by status

### Endpoints
* /healthz/up - liveness probe url
* /healthz/ready - readiness probe url
* /metrics - apache metrics

### Run
```bash
docker run -it \
-p 9345:9345 \
-e APACHE_EXPORTER_URL='https://some-host.com/server-status' \
-e APACHE_EXPORTER_CLUSTERS='{"cluster1":"/html/body/table[5]/tr"}' \
--name apache-exporter sergeykudrenko/prometheus-apache-exporter:latest
```
