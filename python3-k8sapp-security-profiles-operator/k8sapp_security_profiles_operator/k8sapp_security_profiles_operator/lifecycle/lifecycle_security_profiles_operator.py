#
# Copyright (c) 2022-2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
# All Rights Reserved.
#

""" System inventory App lifecycle operator."""

import glob
import os
import tarfile
import tempfile

from k8sapp_security_profiles_operator.common import constants as app_constants
from oslo_log import log as logging
from sysinv.common import constants
from sysinv.common import exception
from sysinv.common import kubernetes
from sysinv.common import utils as cutils
from sysinv.helm import lifecycle_base as base
from sysinv.helm import lifecycle_utils as lifecycle_utils
from sysinv.helm.lifecycle_constants import LifecycleConstants
import yaml

LOG = logging.getLogger(__name__)

# CRD group suffix for security-profiles-operator
SPO_CRD_GROUP = 'security-profiles-operator.x-k8s.io'


class SecurityProfilesOperatorAppLifecycleOperator(base.AppLifecycleOperator):
    def app_lifecycle_actions(self, context, conductor_obj, app_op, app, hook_info):
        """Perform lifecycle actions for an operation

        :param context: request context, can be None
        :param conductor_obj: conductor object, can be None
        :param app_op: AppOperator object
        :param app: AppOperator.Application object
        :param hook_info: LifecycleHookInfo object

        """
        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_RESOURCE:
            if hook_info.operation == constants.APP_APPLY_OP:
                if hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_PRE:
                    return self.pre_apply(app_op, app, hook_info)

        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_RESOURCE:
            if hook_info.operation == constants.APP_DOWNGRADE_OP:
                if hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_PRE:
                    return self.pre_downgrade(app_op, app, hook_info)

        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_FLUXCD_REQUEST:
            if hook_info.operation == constants.APP_APPLY_OP:
                if hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_POST:
                    return self.post_apply(app_op, app, hook_info)

        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_OPERATION:
            if hook_info.operation == constants.APP_REMOVE_OP:
                if hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_PRE:
                    return self.pre_remove(app)

        if hook_info.lifecycle_type == LifecycleConstants.APP_LIFECYCLE_TYPE_OPERATION:
            if hook_info.operation == constants.APP_REMOVE_OP:
                if hook_info.relative_timing == LifecycleConstants.APP_LIFECYCLE_TIMING_POST:
                    return self.post_remove(app)

        super(SecurityProfilesOperatorAppLifecycleOperator, self).app_lifecycle_actions(
            context, conductor_obj, app_op, app, hook_info
        )

    def pre_apply(self, app_op, app, hook_info):
        """Perform pre-apply actions including CRD upgrade handling.

        During an upgrade from SPO versions using v1alpha1 CRDs (Namespaced scope)
        to v1.0.0+ using v1 CRDs (Cluster scope), the CRD scope field is immutable
        and cannot be changed with kubectl apply. This hook detects incompatible
        CRDs and replaces them before the helm upgrade runs.
        """
        LOG.info("%s app: executing pre_apply" % app.name)

        # Call the base class to create registry secrets and PSA labels
        lifecycle_utils.create_local_registry_secrets(app_op, app, hook_info)
        lifecycle_utils.add_pod_security_admission_controller_labels(app_op, app, hook_info)

        # Handle CRD upgrade if old incompatible CRDs exist
        self._upgrade_crds_if_needed(app)

        # Delete webhook deployment so the operator recreates it with the correct image
        self._delete_webhook_deployment()

    def pre_downgrade(self, app_op, app, hook_info):
        """Prepare for downgrade by cleaning up CRDs, webhooks, and helm state.

        Called from the 26.10 (source) plugin BEFORE the 26.03 (target) plugin
        takes over. The securityprofilesoperatordaemons CRD is preserved to keep
        the SPOD CR with its enableAppArmor configuration intact.
        """
        LOG.info("%s app: executing pre_downgrade" % app.name)
        self._cleanup_for_rollback()
        self._patch_crds_for_rollback()
        self._delete_webhook_deployment()
        self._delete_spod_resources()

    def _upgrade_crds_if_needed(self, app):
        """Handle CRD replacement for both upgrade and rollback directions.

        CRD scope is immutable, so we must delete and recreate them when
        transitioning between v1alpha1/Namespaced and v1/Cluster.
        """
        incompatibility = self._check_crd_incompatibility(app)
        if not incompatibility:
            return

        LOG.info("%s: Incompatible CRDs detected (%s), replacing" %
                 (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, incompatibility))

        crds_file = self._extract_crds_from_chart(app)
        if not crds_file:
            LOG.error("%s: Failed to extract CRDs from chart" %
                      app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR)
            return

        try:
            if incompatibility == 'rollback':
                self._cleanup_for_rollback()
            self._delete_old_crds()
            self._apply_new_crds(crds_file)
        finally:
            if os.path.exists(crds_file):
                os.remove(crds_file)

    def _check_crd_incompatibility(self, app):
        """Return 'upgrade', 'rollback', or None based on CRD vs target chart mismatch."""
        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'get', 'crd',
            'securityprofilesoperatordaemons.security-profiles-operator.x-k8s.io',
            '-o', 'jsonpath={.spec.versions[*].name},{.spec.scope}'
        ]
        try:
            stdout, _ = cutils.execute(*cmd)
        except Exception:
            return None

        if not stdout or not stdout.strip():
            return None

        parts = stdout.strip().split(',')
        versions = parts[0] if parts else ''
        scope = parts[1] if len(parts) > 1 else ''
        target_has_v1 = self._target_chart_has_v1_crds(app)

        if target_has_v1 and ('v1' not in versions.split() or scope == 'Namespaced'):
            LOG.info("%s: CRD versions=[%s] scope=[%s], upgrade needed" %
                     (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, versions, scope))
            return 'upgrade'

        if not target_has_v1 and 'v1' in versions.split():
            LOG.info("%s: CRD versions=[%s] scope=[%s], rollback needed" %
                     (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, versions, scope))
            return 'rollback'

        return None

    def _target_chart_has_v1_crds(self, app):
        """Check if the target chart tarball contains v1/Cluster scope CRDs."""
        chart_pattern = os.path.join(app.inst_charts_dir,
                                     'security-profiles-operator-*.tgz')
        chart_files = glob.glob(chart_pattern)
        if not chart_files:
            return False

        try:
            with tarfile.open(chart_files[0], 'r:gz') as tar:
                crd_members = [m for m in tar.getmembers()
                               if '/crds/' in m.name and m.name.endswith('.yaml')]
                if not crd_members:
                    return False
                f = tar.extractfile(crd_members[0])
                if f:
                    content = f.read().decode('utf-8')
                    for doc in yaml.safe_load_all(content):
                        if not doc or doc.get('kind') != 'CustomResourceDefinition':
                            continue
                        spec = doc.get('spec', {})
                        if spec.get('scope') != 'Cluster':
                            continue
                        versions = spec.get('versions', [])
                        if any(v.get('name') == 'v1' for v in versions):
                            return True
        except Exception as e:
            LOG.warning("%s: Failed to inspect chart CRDs: %s" %
                        (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, e))
        return False

    def _cleanup_for_rollback(self):
        """Remove webhook configs, helm secrets and HelmRelease for clean rollback."""
        LOG.info("%s: Cleaning up for rollback" %
                 app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR)

        # Delete webhook configurations
        for wh_name in ['spo-validating-webhook-configuration',
                        'spo-mutating-webhook-configuration']:
            wh_type = 'validatingwebhookconfiguration' if 'validating' in wh_name \
                else 'mutatingwebhookconfiguration'
            cmd = [
                'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
                'delete', wh_type, wh_name, '--ignore-not-found=true'
            ]
            stdout, stderr = cutils.execute(*cmd)
            LOG.info("%s: delete %s: %s %s" %
                     (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                      wh_name, stdout, stderr))

        # Delete helm release secrets to force fresh install
        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'delete', 'secrets', '-n',
            app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
            '-l', 'owner=helm', '--ignore-not-found=true'
        ]
        stdout, stderr = cutils.execute(*cmd)
        LOG.info("%s: delete helm secrets: %s %s" %
                 (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, stdout, stderr))

        # Patch out finalizers and delete existing HelmRelease to avoid cached failure
        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'patch', 'helmrelease',
            app_constants.HELM_CHART_SECURITY_PROFILES_OPERATOR,
            '-n', app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
            '--type=merge', '-p', '{"metadata":{"finalizers":null}}'
        ]
        try:
            cutils.execute(*cmd)
        except Exception:
            pass

        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'delete', 'helmrelease',
            app_constants.HELM_CHART_SECURITY_PROFILES_OPERATOR,
            '-n', app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
            '--ignore-not-found=true'
        ]
        stdout, stderr = cutils.execute(*cmd)
        LOG.info("%s: delete helmrelease: %s %s" %
                 (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, stdout, stderr))

    def _extract_crds_from_chart(self, app):
        """Extract the crds/crds.yaml from the helm chart tarball.

        :param app: Application object with inst_charts_dir path
        :returns: path to the extracted crds.yaml file, or None on failure
        """
        chart_pattern = os.path.join(app.inst_charts_dir,
                                     'security-profiles-operator-*.tgz')
        chart_files = glob.glob(chart_pattern)

        if not chart_files:
            LOG.error("%s: No chart tarball found matching %s" %
                      (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                       chart_pattern))
            return None

        chart_tarball = chart_files[0]
        LOG.info("%s: Extracting CRDs from %s" %
                 (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                  chart_tarball))

        try:
            crds_tmpfile = tempfile.NamedTemporaryFile(
                prefix='spo-crds-', suffix='.yaml', delete=False)
            crds_tmpfile.close()

            with tarfile.open(chart_tarball, 'r:gz') as tar:
                # Look for crds/crds.yaml or similar inside the chart
                crd_members = [m for m in tar.getmembers()
                               if '/crds/' in m.name and m.name.endswith('.yaml')]

                if not crd_members:
                    LOG.error("%s: No CRD files found in chart tarball" %
                              app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR)
                    os.remove(crds_tmpfile.name)
                    return None

                # Concatenate all CRD yaml files
                with open(crds_tmpfile.name, 'w') as outfile:
                    for member in crd_members:
                        f = tar.extractfile(member)
                        if f:
                            content = f.read().decode('utf-8')
                            outfile.write(content)
                            outfile.write('\n---\n')

            LOG.info("%s: Extracted %d CRD file(s) to %s" %
                     (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                      len(crd_members), crds_tmpfile.name))
            return crds_tmpfile.name

        except Exception as e:
            LOG.error("%s: Failed to extract CRDs from chart: %s" %
                      (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, e))
            if os.path.exists(crds_tmpfile.name):
                os.remove(crds_tmpfile.name)
            return None

    def _delete_webhook_deployment(self):
        """Delete the webhook deployment so the operator recreates it with correct image.

        The webhook deployment is managed by the SPO operator binary, not helm.
        On upgrade, the old webhook persists with the old image. Deleting it
        forces the new operator to recreate it with its own image.
        """
        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'delete', 'deployment', 'security-profiles-operator-webhook',
            '-n', app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
            '--ignore-not-found=true'
        ]
        stdout, stderr = cutils.execute(*cmd)
        LOG.info("%s: delete webhook deployment: %s %s" %
                 (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, stdout, stderr))

    def _delete_spod_resources(self):
        """Delete the spod daemonset so the operator recreates it correctly.

        The spod daemonset is managed by the SPO operator binary via the
        SecurityProfilesOperatorDaemon CR, not directly by helm.
        """
        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'delete', 'daemonset', 'spod',
            '-n', app_constants.HELM_NS_SECURITY_PROFILES_OPERATOR,
            '--ignore-not-found=true'
        ]
        stdout, stderr = cutils.execute(*cmd)
        LOG.info("%s: delete spod daemonset: %s %s" %
                 (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR, stdout, stderr))

    def _patch_crds_for_rollback(self):
        """Delete most SPO CRDs but preserve securityprofilesoperatordaemons.

        The securityprofilesoperatordaemons CRD holds the SPOD CR which contains
        enableAppArmor config. Deleting it causes the operator to recreate the
        spod without privileged access, leading to crashes. We patch it to remove
        the conversion webhook and keep the CR intact.
        """
        LOG.info("%s: Handling CRDs for rollback" %
                 app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR)

        spod_crd = 'securityprofilesoperatordaemons.security-profiles-operator.x-k8s.io'

        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'get', 'crds', '-o', 'name'
        ]
        try:
            stdout, _ = cutils.execute(*cmd)
        except Exception:
            return

        if not stdout:
            return

        spo_crds = [crd.replace('customresourcedefinition.apiextensions.k8s.io/', '')
                    for crd in stdout.strip().split('\n')
                    if SPO_CRD_GROUP in crd]

        for crd_name in spo_crds:
            if crd_name == spod_crd:
                patch = '{"spec":{"conversion":{"strategy":"None","webhook":null}}}'
                cmd = [
                    'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
                    'patch', 'crd', crd_name,
                    '--type=merge', '-p', patch
                ]
                try:
                    stdout, stderr = cutils.execute(*cmd)
                    LOG.info("%s: patch CRD %s (preserve SPOD CR): %s %s" %
                             (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                              crd_name, stdout, stderr))
                except Exception as e:
                    LOG.warning("%s: failed to patch CRD %s: %s" %
                                (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                                 crd_name, e))
            else:
                cmd = [
                    'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
                    'delete', 'crd', crd_name, '--ignore-not-found=true'
                ]
                stdout, stderr = cutils.execute(*cmd)
                LOG.info("%s: delete CRD %s: %s %s" %
                         (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                          crd_name, stdout, stderr))

    def _delete_old_crds(self):
        """Delete all SPO CRDs discovered dynamically."""
        LOG.info("%s: Deleting SPO CRDs" %
                 app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR)

        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'get', 'crds', '-o', 'name'
        ]
        try:
            stdout, _ = cutils.execute(*cmd)
        except Exception:
            return

        if not stdout:
            return

        spo_crds = [crd.replace('customresourcedefinition.apiextensions.k8s.io/', '')
                    for crd in stdout.strip().split('\n')
                    if SPO_CRD_GROUP in crd]

        for crd_name in spo_crds:
            cmd = [
                'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
                'delete', 'crd', crd_name, '--ignore-not-found=true'
            ]
            stdout, stderr = cutils.execute(*cmd)
            LOG.info("%s: delete CRD %s: %s %s" %
                     (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                      crd_name, stdout, stderr))

    def _apply_new_crds(self, crds_file):
        """Apply new CRDs from the extracted file.

        :param crds_file: path to the yaml file containing new CRD definitions
        """
        LOG.info("%s: Applying new CRDs from %s" %
                 (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                  crds_file))

        cmd = [
            'kubectl', '--kubeconfig', kubernetes.KUBERNETES_ADMIN_CONF,
            'apply', '-f', crds_file
        ]
        stdout, stderr = cutils.execute(*cmd)
        LOG.info("%s: apply CRDs: stdout=%s stderr=%s" %
                 (app_constants.HELM_APP_SECURITY_PROFILES_OPERATOR,
                  stdout, stderr))

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
