#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""COS integration for WordPress charm."""
from typing import TypedDict

from ops.pebble import Check, Layer, Service


class PrometheusStaticConfig(TypedDict, total=False):
    """Configuration parameters for prometheus metrics endpoint scraping.

    For more information, see:
    https://prometheus.io/docs/prometheus/latest/configuration/configuration/#static_config

    Attrs:
        targets: list of hosts to scrape, e.g. "*:8080", every unit's port 8080
        labels: labels assigned to all metrics scraped from the targets.
    """

    targets: list[str]
    labels: dict[str, str]


class PrometheusMetricsJob(TypedDict, total=False):
    """Configuration parameters for prometheus metrics scraping job.

    For more information, see:
    https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config

    Attrs:
        metrics_path: The HTTP resource path on which to fetch metrics from targets.
        static_configs: List of labeled statically configured targets for this job.
    """

    metrics_path: str
    static_configs: list[PrometheusStaticConfig]


APACHE_PROMETHEUS_SCRAPE_PORT = "9117"
WORDPRESS_SCRAPE_JOBS = [
    PrometheusMetricsJob(
        static_configs=[
            PrometheusStaticConfig(
                targets=[
                    f"*:{APACHE_PROMETHEUS_SCRAPE_PORT}",
                ]
            )
        ]
    )
]
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
