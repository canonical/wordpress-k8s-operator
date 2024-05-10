<!-- markdownlint-disable -->

<a href="../src/cos.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `cos.py`
COS integration for WordPress charm. 

**Global Variables**
---------------
- **APACHE_PROMETHEUS_SCRAPE_PORT**
- **APACHE_LOG_PATHS**
- **REQUEST_DURATION_MICROSECONDS_BUCKETS**


---

## <kbd>class</kbd> `ApacheLogProxyConsumer`
Extends LogProxyConsumer to add a metrics pipeline to promtail. 


---

#### <kbd>property</kbd> loki_endpoints

Fetch Loki Push API endpoints sent from LokiPushApiProvider through relation data. 



**Returns:**
  A list of dictionaries with Loki Push API endpoints, for instance:  [ 
 - <b>`{"url"`</b>:  "http://loki1:3100/loki/api/v1/push"}, 
 - <b>`{"url"`</b>:  "http://loki2:3100/loki/api/v1/push"}, ] 

---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 

---

#### <kbd>property</kbd> rsyslog_config

Generates a config line for use with rsyslog. 



**Returns:**
  The rsyslog config line as a string 

---

#### <kbd>property</kbd> syslog_port

Gets the port on which promtail is listening for syslog. 



**Returns:**
  A str representing the port 




---

## <kbd>class</kbd> `PrometheusMetricsJob`
Configuration parameters for prometheus metrics scraping job. 

For more information, see: https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config 

Attrs:  metrics_path: The HTTP resource path on which to fetch metrics from targets.  static_configs: List of labeled statically configured targets for this job. 





---

## <kbd>class</kbd> `PrometheusStaticConfig`
Configuration parameters for prometheus metrics endpoint scraping. 

For more information, see: https://prometheus.io/docs/prometheus/latest/configuration/configuration/#static_config 

Attrs:  targets: list of hosts to scrape, e.g. "*:8080", every unit's port 8080  labels: labels assigned to all metrics scraped from the targets. 





