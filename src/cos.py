#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""COS integration for WordPress charm."""
from typing import Dict, List, TypedDict

from charms.loki_k8s.v0.loki_push_api import LogProxyConsumer
from ops.pebble import Check, Layer, Service


class PrometheusStaticConfig(TypedDict, total=False):
    """Configuration parameters for prometheus metrics endpoint scraping.

    For more information, see:
    https://prometheus.io/docs/prometheus/latest/configuration/configuration/#static_config

    Attrs:
        targets: list of hosts to scrape, e.g. "*:8080", every unit's port 8080
        labels: labels assigned to all metrics scraped from the targets.
    """

    targets: List[str]
    labels: Dict[str, str]


class PrometheusMetricsJob(TypedDict, total=False):
    """Configuration parameters for prometheus metrics scraping job.

    For more information, see:
    https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config

    Attrs:
        metrics_path: The HTTP resource path on which to fetch metrics from targets.
        static_configs: List of labeled statically configured targets for this job.
    """

    metrics_path: str
    static_configs: List[PrometheusStaticConfig]


APACHE_PROMETHEUS_SCRAPE_PORT = "9117"
_APACHE_EXPORTER_PEBBLE_SERVICE = Service(
    name="apache-exporter",
    raw={
        "override": "replace",
        "summary": "Apache Exporter",
        "command": "apache_exporter",
        "startup": "enabled",
    },
)
_APACHE_EXPORTER_PEBBLE_CHECK = Check(
    name="apache-exporter-up",
    raw={
        "override": "replace",
        "level": "alive",
        "http": {"url": f"http://localhost:{APACHE_PROMETHEUS_SCRAPE_PORT}/metrics"},
    },
)
PROM_EXPORTER_PEBBLE_CONFIG = Layer(
    {
        "summary": "Apache prometheus exporter",
        "description": "Prometheus exporter for apache",
        "services": {
            _APACHE_EXPORTER_PEBBLE_SERVICE.name: _APACHE_EXPORTER_PEBBLE_SERVICE.to_dict()
        },
        "checks": {_APACHE_EXPORTER_PEBBLE_CHECK.name: _APACHE_EXPORTER_PEBBLE_CHECK.to_dict()},
    }
)

APACHE_LOG_PATHS = [
    "/var/log/apache2/access.*.log",
    "/var/log/apache2/error.*.log",
]

REQUEST_DURATION_MICROSECONDS_BUCKETS = [
    10000,
    25000,
    50000,
    100000,
    200000,
    300000,
    400000,
    500000,
    750000,
    1000000,
    1500000,
    2000000,
    2500000,
    5000000,
    10000000,
]


class ApacheLogProxyConsumer(LogProxyConsumer):
    """Extends LogProxyConsumer to add a metrics pipeline to promtail."""

    def _scrape_configs(self) -> dict:
        """Generate the scrape_configs section of the Promtail config file.

        Returns:
            A dict representing the `scrape_configs` section.
        """
        scrape_configs = super()._scrape_configs()
        scrape_configs["scrape_configs"].append(
            {
                "job_name": "access_log_exporter",
                "static_configs": [{"labels": {"__path__": "/var/log/apache2/access.*.log"}}],
                "pipeline_stages": [
                    {
                        "logfmt": {
                            "mapping": {
                                "request_duration_microseconds": "request_duration_microseconds",
                                "content_type": "content_type",
                            }
                        }
                    },
                    {
                        "match": {
                            "selector": '!= "/server-status"',
                            "action": "drop",
                        }
                    },
                    {"labeldrop": ["filename"]},
                    {
                        "metrics": {
                            "request_duration_microseconds": {
                                "type": "Histogram",
                                "source": "request_duration_microseconds",
                                "prefix": "apache_access_log_",
                                "config": {"buckets": REQUEST_DURATION_MICROSECONDS_BUCKETS},
                            }
                        }
                    },
                ],
            }
        )
        return scrape_configs
