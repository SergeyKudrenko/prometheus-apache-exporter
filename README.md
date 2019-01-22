### Apache exporter 
Exporter scrapes Apache /server-status for worker status and route balancing statistics
 
### Exporter is configured via environment variables:
* APACHE_EXPORTER_NAME - Fully qualified name to distinguish apache instance in metrics
* APACHE_EXPORTER_URL - Apache /server-status url. Example: "https://some-host.com/server-status"
* APACHE_EXPORTER_CLUSTERS - Hash (JSON) Clusters and XPath to <TR> element. Example: {"cluster1": "/html/body/table[5]/tr"}

### Metrics:
* Counter: **apache_accesses_total** - Total requests served count since startup
* Counter: **apache_traffic_bytes_total** - Total bytes transfered since startup
* Counter: **apache_balancer_requests_total** - Total requests count
* Counter: **apache_balancer_write_bytes_total**  - Total bytes written
* Counter: **apache_balancer_read_bytes_total**  - Total bytes read

* Gauge: **apache_requests_per_second** - Requests per second
* Gauge: **apache_io_bytes_per_second** - Bytes write/read per second
* Gauge: **apache_io_bytes_per_request** - Bytes write/read  per request
* Gauge: **apache_balancer_route_ok**  - Balancing status of the route is OK
* Gauge: **apache_balancer_route_disabled** - Balancing status of the route is DISABLED
* Gauge: **apache_balancer_route_error** - Balancing status of the route is ERROR
* Gauge: **apache_balancer_route_unknown** - Balancing status of the route is UNKNOWN
* Gauge: **apache_scoreboard_current** - Count of workers grouped by status

* Histogram: **apache_endpoint_response_time_seconds** - Response time by endpoints

### Endpoints
* /healthz/up - liveness probe
* /healthz/ready - readiness probe
* /metrics - apache metrics

### Run
```bash
docker pull sergeykudrenko/prometheus-apache-exporter:latest
docker run -it \
-p 9345:9345 \
-e APACHE_EXPORTER_NAME='some-host.com' \
-e APACHE_EXPORTER_URL='https://some-host.com/server-status' \
-e APACHE_EXPORTER_CLUSTERS='{"cluster1":"/html/body/table[5]/tr"}' \
--name apache-exporter sergeykudrenko/prometheus-apache-exporter:latest
```
