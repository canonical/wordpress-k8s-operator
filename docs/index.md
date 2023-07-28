# WordPress Operator

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) deploying and managing WordPress on Kubernetes. [WordPress](https://wordpress.com/) is the world's most popular website builder, and it's free and open-source.

This charm simplifies initial deployment and "day N" operations of WordPress on Kubernetes, including scaling the number of instances, integration with SSO, access to OpenStack Swift object storage for redundant file storage and more. It allows for deployment on many different Kubernetes platforms, from [MicroK8s](https://microk8s.io/) to [Charmed Kubernetes](https://ubuntu.com/kubernetes) to public cloud Kubernetes offerings.

As such, the charm makes it easy for those looking to take control of their own content management system whilst keeping operations simple, and gives them the freedom to deploy on the Kubernetes platform of their choice.

For DevOps or SRE teams this charm will make operating WordPress simple and straightforward through Juju's clean interface. It will allow easy deployment into multiple environments for testing of changes, and supports scaling out for enterprise deployments.
