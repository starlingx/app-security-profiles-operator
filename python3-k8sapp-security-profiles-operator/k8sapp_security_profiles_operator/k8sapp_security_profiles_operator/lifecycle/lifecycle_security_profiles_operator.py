#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
# All Rights Reserved.
#

""" System inventory App lifecycle operator."""

import os

from k8sapp_security_profiles_operator.common import constants as app_constants
from oslo_log import log as logging
from sysinv.common import constants
from sysinv.common import exception
from sysinv.common import kubernetes
from sysinv.common import utils as cutils
from sysinv.helm import lifecycle_base as base
from sysinv.helm.lifecycle_constants import LifecycleConstants
import yaml

LOG = logging.getLogger(__name__)


class SecurityProfilesOperatorAppLifecycleOperator(base.AppLifecycleOperator):
    def app_lifecycle_actions(self, context, conductor_obj, app_op, app, hook_info):
        """Perform lifecycle actions for an operation

        :param context: request context, can be None
        :param conductor_obj: conductor object, can be None
        :param app_op: AppOperator object
        :param app: AppOperator.Application object
        :param hook_info: LifecycleHookInfo object

        """
        if hook_info.lifecycle_type == constants.APP_LIFECYCLE_TYPE_FLUXCD_REQUEST:
            if hook_info.operation == constants.APP_APPLY_OP:
                if hook_info.relative_timing == constants.APP_LIFECYCLE_TIMING_POST:
                    return self.post_apply(app_op, app, hook_info)

        if hook_info.lifecycle_type == constants.APP_LIFECYCLE_TYPE_OPERATION:
            if hook_info.operation == constants.APP_REMOVE_OP:
                if hook_info.relative_timing == constants.APP_LIFECYCLE_TIMING_PRE:
                    return self.pre_remove(app)

        if hook_info.lifecycle_type == constants.APP_LIFECYCLE_TYPE_OPERATION:
            if hook_info.operation == constants.APP_REMOVE_OP:
                if hook_info.relative_timing == constants.APP_LIFECYCLE_TIMING_POST:
                    return self.post_remove(app)

        super(SecurityProfilesOperatorAppLifecycleOperator, self).app_lifecycle_actions(
            context, conductor_obj, app_op, app, hook_info
        )

    def post_apply(self, app_op, app, hook_info):

        if LifecycleConstants.EXTRA not in hook_info:
            raise exception.LifecycleMissingInfo("Missing {}".format(LifecycleConstants.EXTRA))
        if LifecycleConstants.RETURN_CODE not in hook_info[LifecycleConstants.EXTRA]:
            raise exception.LifecycleMissingInfo(
                "Missing {} {}".format(LifecycleConstants.EXTRA, LifecycleConstants.RETURN_CODE))

        # Raise a specific exception to be caught by the
        # retry decorator and attempt a re-apply
        if not hook_info[LifecycleConstants.EXTRA][LifecycleConstants.RETURN_CODE] and \
                not app_op.is_app_aborted(app.name):
            LOG.info("%s app failed applying. Retrying." % str(app.name))
            raise exception.ApplicationApplyFailure(name=app.name)

        dbapi_instance = app_op._dbapi
        db_app_id = dbapi_instance.kube_app_get(app.name).id

        client_core = app_op._kube._get_kubernetesclient_core()
        component_constant = app_constants.HELM_COMPONENT_LABEL_SPO

        # chart overrides
        chart_overrides = self._get_helm_user_overrides(
            dbapi_instance,
            db_app_id)

        override_label = {}

        # Namespaces variables
        namespace = client_core.read_namespace(app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR)

        # Old namespace variable
        old_namespace_label = (namespace.metadata.labels.get(component_constant)
                               if component_constant in namespace.metadata.labels
                               else None)

        if component_constant in chart_overrides:
            # User Override variables
            dict_chart_overrides = yaml.safe_load(chart_overrides)
            override_label = dict_chart_overrides.get(component_constant)

        if override_label == 'application':
            namespace.metadata.labels.update({component_constant: 'application'})
            app_op._kube.kube_patch_namespace(app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR, namespace)
        elif override_label == 'platform':
            namespace.metadata.labels.update({component_constant: 'platform'})
            app_op._kube.kube_patch_namespace(app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR, namespace)
        elif not override_label:
            namespace.metadata.labels.update({component_constant: 'platform'})
            app_op._kube.kube_patch_namespace(app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR, namespace)
        else:
            LOG.info(f'WARNING: Namespace label {override_label} not supported')

        namespace_label = namespace.metadata.labels.get(component_constant)
        if old_namespace_label != namespace_label:
            self._delete_security_profiles_operator_pods(app_op, client_core)

    def pre_remove(self, app):
        LOG.debug(
            "Executing pre_remove for {} app".format(app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR)
        )
        yfile = os.path.join(app.sync_fluxcd_manifest, 'security-profiles-operator/security-profiles-operator.yaml')
        if os.path.exists(yfile):
            cmd = ['kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
                   'delete', '-f', yfile]
            stdout, stderr = cutils.trycmd(*cmd)
            LOG.debug("{} app: cmd={} stdout={} stderr={}".format(app.name, cmd, stdout, stderr))

        # Comment out security-profiles-operator.yaml in the kustomization.yaml
        kust_file = os.path.join(app.sync_fluxcd_manifest, 'security-profiles-operator/kustomization.yaml')
        cmd = ['sed', '-i', '/security-profiles-operator.yaml/s/^/#/g', kust_file]
        stdout, stderr = cutils.trycmd(*cmd)
        LOG.debug("{} app: cmd={} stdout={} stderr={}".format(app.name, cmd, stdout, stderr))

        # remove seccomp profiles before app deletion. This is a workaround for SPO known issue
        LOG.debug("deleting seccomp profiles")
        cmd = ['kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
               'delete', 'seccompprofiles', '--all', '--all-namespaces']

        stdout, stderr = cutils.trycmd(*cmd)
        LOG.info("{} app: cmd={} stdout={} stderr={}".format(app.name, cmd, stdout, stderr))

    def post_remove(self, app):
        LOG.debug(
            "Executing post_remove for {} app".format(app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR)
        )
        # Uncomment security-profiles-operator.yaml in the kustomization.yaml
        kust_file = os.path.join(app.sync_fluxcd_manifest, 'security-profiles-operator/kustomization.yaml')
        cmd = ['sed', '-i', '/security-profiles-operator.yaml/s/^#//g', kust_file]
        stdout, stderr = cutils.trycmd(*cmd)
        LOG.debug("{} app: post_remove cmd={} stdout={} stderr={}".format(app.name, cmd, stdout, stderr))

    def _get_helm_user_overrides(self, dbapi_instance, db_app_id):
        try:
            overrides = dbapi_instance.helm_override_get(
                app_id=db_app_id,
                name=app_constants.HELM_CHART_SECURITY_PROFILES_OPERATOR,
                namespace=app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
            )
        except exception.HelmOverrideNotFound:
            values = {
                "name": app_constants.HELM_CHART_SECURITY_PROFILES_OPERATOR,
                "namespace": app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
                "db_app_id": db_app_id,
            }
            overrides = dbapi_instance.helm_override_create(values=values)
        return overrides.user_overrides or ""

    def _delete_security_profiles_operator_pods(self, app_op, client_core):
        # pod list
        system_pods = client_core.list_namespaced_pod(app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR)

        # On namespace label change delete pods to force restart
        for pod in system_pods.items:
            app_op._kube.kube_delete_pod(
                name=pod.metadata.name,
                namespace=app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
                grace_periods_seconds=0
            )
