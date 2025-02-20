# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for WordPress charm ingress integration."""

import kubernetes
import pytest
import requests

from tests.integration.helper import WordpressApp


@pytest.mark.usefixtures("prepare_mysql", "prepare_nginx_ingress", "prepare_swift")
async def test_ingress(wordpress: WordpressApp):
    """
    arrange: after WordPress charm has been deployed and db relation established.
    act: deploy the nginx-ingress-integrator charm and create the relation between ingress charm
        and WordPress charm.
    assert: A Kubernetes ingress should be created and the ingress should accept HTTPS connections.
    """
    response = requests.get("http://127.0.0.1", headers={"Host": wordpress.name}, timeout=5)
    assert (
        response.status_code == 200 and "wordpress" in response.text.lower()
    ), "Ingress should accept requests to WordPress and return correct contents"

    new_hostname = "wordpress.test"
    await wordpress.set_config({"blog_hostname": new_hostname})
    await wordpress.model.wait_for_idle(status="active")
    response = requests.get(
        "https://127.0.0.1", headers={"Host": new_hostname}, timeout=5, verify=False
    )  # nosec
    assert (
        response.status_code == 200 and "wordpress" in response.text.lower()
    ), "Ingress should update the server name indication based routing after blog_hostname updated"


@pytest.mark.usefixtures("prepare_mysql", "prepare_nginx_ingress", "prepare_swift")
async def test_ingress_modsecurity(
    wordpress: WordpressApp,
    kube_config: str,
):
    """
    arrange: WordPress charm is running and Nginx ingress integrator deployed and related to it.
    act: update the use_nginx_ingress_modsec WordPress charm config.
    assert: A Kubernetes ingress modsecurity should be enabled and proper rules should be set up
        for WordPress.
    """
    await wordpress.set_config({"use_nginx_ingress_modsec": "true"})
    await wordpress.model.wait_for_idle(status="active")

    kubernetes.config.load_kube_config(config_file=kube_config)
    kube = kubernetes.client.NetworkingV1Api()

    def get_ingress_annotation():
        """Get ingress annotations from kubernetes.

        Returns:
            Nginx ingress annotations.
        """
        ingress_list = kube.list_namespaced_ingress(namespace=wordpress.model.name).items
        return ingress_list[0].metadata.annotations

    ingress_annotations = get_ingress_annotation()
    assert ingress_annotations["nginx.ingress.kubernetes.io/enable-modsecurity"] == "true"
    assert (
        ingress_annotations["nginx.ingress.kubernetes.io/enable-owasp-modsecurity-crs"] == "true"
    )
    assert (
        'SecAction "id:900130,phase:1,nolog,pass,t:none,setvar:tx.crs_exclusions_wordpress=1"\n'
        in ingress_annotations["nginx.ingress.kubernetes.io/modsecurity-snippet"]
    )
