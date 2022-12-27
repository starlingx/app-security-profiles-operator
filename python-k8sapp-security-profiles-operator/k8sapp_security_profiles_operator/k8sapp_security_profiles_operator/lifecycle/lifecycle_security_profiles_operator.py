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
from sysinv.helm.lifecycle_hook import LifecycleHookInfo
from sysinv.helm.lifecycle_constants import LifecycleConstants

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

        stdout,stderr = cutils.trycmd(*cmd)
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
