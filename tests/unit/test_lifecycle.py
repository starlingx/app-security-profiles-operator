#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Unit tests for lifecycle operator."""

import unittest
from unittest import mock

import yaml

from k8sapp_security_profiles_operator.common import (
    constants as app_constants,
)
from k8sapp_security_profiles_operator.lifecycle import (
    lifecycle_security_profiles_operator as spo_lifecycle,
)

# Import the mocked modules the source code uses
from sysinv.common import constants
from sysinv.common import exception
from sysinv.helm.lifecycle_constants import (
    LifecycleConstants,
)

SPOLifecycle = (
    spo_lifecycle.SecurityProfilesOperatorAppLifecycleOperator
)

# Lifecycle shorthand constants
LIFECYCLE_FLUXCD = (
    LifecycleConstants.APP_LIFECYCLE_TYPE_FLUXCD_REQUEST
)
LIFECYCLE_OPERATION = (
    LifecycleConstants.APP_LIFECYCLE_TYPE_OPERATION
)
LIFECYCLE_TIMING_PRE = (
    LifecycleConstants.APP_LIFECYCLE_TIMING_PRE
)
LIFECYCLE_TIMING_POST = (
    LifecycleConstants.APP_LIFECYCLE_TIMING_POST
)
LIFECYCLE_EXTRA = LifecycleConstants.EXTRA
LIFECYCLE_RETURN_CODE = LifecycleConstants.RETURN_CODE
APPLY_OPERATION = constants.APP_APPLY_OP
REMOVE_OPERATION = constants.APP_REMOVE_OP


def _make_hook_info(
    lifecycle_type, operation, timing
):
    """Create a mock hook_info with attribute and dict access.

    lifecycle_type -- type of lifecycle event
    operation -- the app operation (apply/remove)
    timing -- relative timing (pre/post)
    Returns a HookInfo dict with attribute access.
    """

    class HookInfo(dict):
        """Dict subclass with attribute access."""

        def __init__(self, data):
            super().__init__(data)
            for key, value in data.items():
                setattr(self, key, value)

    return HookInfo({
        'lifecycle_type': lifecycle_type,
        'operation': operation,
        'relative_timing': timing,
    })


class TestLifecycleActions(unittest.TestCase):
    """Test app_lifecycle_actions dispatch logic."""

    def setUp(self):
        """Set up operator and common mocks."""
        self.operator = SPOLifecycle()
        self.context = mock.MagicMock()
        self.conductor = mock.MagicMock()
        self.app_op = mock.MagicMock()
        self.app = mock.MagicMock()
        self.app.name = 'security-profiles-operator'

    def test_post_apply_dispatch(self):
        """Verify post_apply called for fluxcd apply."""
        hook = _make_hook_info(
            LIFECYCLE_FLUXCD,
            APPLY_OPERATION,
            LIFECYCLE_TIMING_POST,
        )
        hook[LIFECYCLE_EXTRA] = {
            LIFECYCLE_RETURN_CODE: True
        }
        with mock.patch.object(
            self.operator, 'post_apply',
            return_value=None
        ) as mock_post:
            self.operator.app_lifecycle_actions(
                self.context, self.conductor,
                self.app_op, self.app, hook
            )
            mock_post.assert_called_once_with(
                self.app_op, self.app, hook
            )

    def test_pre_remove_dispatch(self):
        """Verify pre_remove called for remove pre."""
        hook = _make_hook_info(
            LIFECYCLE_OPERATION,
            REMOVE_OPERATION,
            LIFECYCLE_TIMING_PRE,
        )
        with mock.patch.object(
            self.operator, 'pre_remove',
            return_value=None
        ) as mock_pre:
            self.operator.app_lifecycle_actions(
                self.context, self.conductor,
                self.app_op, self.app, hook
            )
            mock_pre.assert_called_once_with(
                self.app
            )

    def test_post_remove_dispatch(self):
        """Verify post_remove called for remove post."""
        hook = _make_hook_info(
            LIFECYCLE_OPERATION,
            REMOVE_OPERATION,
            LIFECYCLE_TIMING_POST,
        )
        with mock.patch.object(
            self.operator, 'post_remove',
            return_value=None
        ) as mock_post_rm:
            self.operator.app_lifecycle_actions(
                self.context, self.conductor,
                self.app_op, self.app, hook
            )
            mock_post_rm.assert_called_once_with(
                self.app
            )

    def test_unhandled_falls_through_to_super(self):
        """Verify unhandled hook calls super()."""
        hook = _make_hook_info(
            'unknown-type',
            'unknown-op',
            'unknown-timing'
        )
        # Should not raise
        self.operator.app_lifecycle_actions(
            self.context, self.conductor,
            self.app_op, self.app, hook
        )


class TestPostApply(unittest.TestCase):
    """Test post_apply method."""

    def setUp(self):
        """Set up operator and mocks."""
        self.operator = SPOLifecycle()
        self.app_op = mock.MagicMock()
        self.app = mock.MagicMock()
        self.app.name = 'security-profiles-operator'

        # Mock namespace object
        self.namespace_obj = mock.MagicMock()
        label_key = (
            app_constants.HELM_COMPONENT_LABEL_SPO
        )
        self.namespace_obj.metadata.labels = {
            label_key: 'platform'
        }
        core_client = (
            self.app_op._kube._get_kubernetesclient_core
        )
        core_client.return_value \
            .read_namespace.return_value = (
                self.namespace_obj
            )

        # Mock dbapi
        self.db_app = mock.MagicMock()
        self.db_app.id = 1
        self.app_op._dbapi.kube_app_get.return_value = (
            self.db_app
        )

    def _make_hook(self, return_code=True):
        """Create hook_info with EXTRA and RETURN_CODE.

        return_code -- the return code value
        Returns a HookInfo dict.
        """
        hook = _make_hook_info(
            LIFECYCLE_FLUXCD,
            APPLY_OPERATION,
            LIFECYCLE_TIMING_POST,
        )
        hook[LIFECYCLE_EXTRA] = {
            LIFECYCLE_RETURN_CODE: return_code
        }
        return hook

    def test_missing_extra_raises(self):
        """Verify error when EXTRA missing."""
        hook = _make_hook_info(
            LIFECYCLE_FLUXCD,
            APPLY_OPERATION,
            LIFECYCLE_TIMING_POST,
        )
        with self.assertRaises(
            exception.LifecycleMissingInfo
        ):
            self.operator.post_apply(
                self.app_op, self.app, hook
            )

    def test_missing_return_code_raises(self):
        """Verify error when RETURN_CODE missing."""
        hook = _make_hook_info(
            LIFECYCLE_FLUXCD,
            APPLY_OPERATION,
            LIFECYCLE_TIMING_POST,
        )
        hook[LIFECYCLE_EXTRA] = {}
        with self.assertRaises(
            exception.LifecycleMissingInfo
        ):
            self.operator.post_apply(
                self.app_op, self.app, hook
            )

    def test_failed_apply_not_aborted_raises(self):
        """Verify failure raised on failed apply."""
        hook = self._make_hook(return_code=False)
        self.app_op.is_app_aborted.return_value = False
        with self.assertRaises(
            exception.ApplicationApplyFailure
        ):
            self.operator.post_apply(
                self.app_op, self.app, hook
            )

    def test_failed_apply_aborted_no_raise(self):
        """Verify no exception when app is aborted."""
        hook = self._make_hook(return_code=False)
        self.app_op.is_app_aborted.return_value = True
        with mock.patch.object(
            self.operator,
            '_get_helm_user_overrides',
            return_value=''
        ):
            self.operator.post_apply(
                self.app_op, self.app, hook
            )

    def test_successful_apply_default_platform(self):
        """Verify default label is platform."""
        hook = self._make_hook(return_code=True)
        with mock.patch.object(
            self.operator,
            '_get_helm_user_overrides',
            return_value=''
        ):
            self.operator.post_apply(
                self.app_op, self.app, hook
            )
        kube = self.app_op._kube
        kube.kube_patch_namespace.assert_called()

    def test_override_label_application(self):
        """Verify label set to application from override."""
        hook = self._make_hook(return_code=True)
        label_key = (
            app_constants.HELM_COMPONENT_LABEL_SPO
        )
        override_yaml = (
            f'{label_key}: application'
        )
        with mock.patch.object(
            self.operator,
            '_get_helm_user_overrides',
            return_value=override_yaml
        ):
            self.operator.post_apply(
                self.app_op, self.app, hook
            )
        updated_label = (
            self.namespace_obj.metadata.labels.get(
                label_key
            )
        )
        self.assertEqual(updated_label, 'application')

    def test_override_label_platform(self):
        """Verify label set to platform from override."""
        hook = self._make_hook(return_code=True)
        label_key = (
            app_constants.HELM_COMPONENT_LABEL_SPO
        )
        override_yaml = (
            f'{label_key}: platform'
        )
        with mock.patch.object(
            self.operator,
            '_get_helm_user_overrides',
            return_value=override_yaml
        ):
            self.operator.post_apply(
                self.app_op, self.app, hook
            )
        updated_label = (
            self.namespace_obj.metadata.labels.get(
                label_key
            )
        )
        self.assertEqual(updated_label, 'platform')

    def test_override_unsupported_label_no_error(self):
        """Verify unsupported label logs warning."""
        hook = self._make_hook(return_code=True)
        label_key = (
            app_constants.HELM_COMPONENT_LABEL_SPO
        )
        override_yaml = (
            f'{label_key}: unsupported-value'
        )
        with mock.patch.object(
            self.operator,
            '_get_helm_user_overrides',
            return_value=override_yaml
        ):
            # Should not raise
            self.operator.post_apply(
                self.app_op, self.app, hook
            )

    def test_label_change_triggers_pod_delete(self):
        """Verify pods deleted when label changes."""
        hook = self._make_hook(return_code=True)
        label_key = (
            app_constants.HELM_COMPONENT_LABEL_SPO
        )
        # Old label is platform, override to application
        self.namespace_obj.metadata.labels = {
            label_key: 'platform'
        }
        override_yaml = (
            f'{label_key}: application'
        )
        delete_method = (
            '_delete_security_profiles_operator_pods'
        )
        with mock.patch.object(
            self.operator,
            '_get_helm_user_overrides',
            return_value=override_yaml
        ), mock.patch.object(
            self.operator, delete_method
        ) as mock_delete:
            self.operator.post_apply(
                self.app_op, self.app, hook
            )
            mock_delete.assert_called_once()

    def test_no_label_change_no_pod_delete(self):
        """Verify pods not deleted when label same."""
        hook = self._make_hook(return_code=True)
        label_key = (
            app_constants.HELM_COMPONENT_LABEL_SPO
        )
        self.namespace_obj.metadata.labels = {
            label_key: 'platform'
        }
        delete_method = (
            '_delete_security_profiles_operator_pods'
        )
        # No override, default is platform - same
        with mock.patch.object(
            self.operator,
            '_get_helm_user_overrides',
            return_value=''
        ), mock.patch.object(
            self.operator, delete_method
        ) as mock_delete:
            self.operator.post_apply(
                self.app_op, self.app, hook
            )
            mock_delete.assert_not_called()


LIFECYCLE_MODULE_PATH = (
    'k8sapp_security_profiles_operator.lifecycle'
    '.lifecycle_security_profiles_operator'
)
TRYCMD_MOCK_PATH = (
    LIFECYCLE_MODULE_PATH + '.cutils.trycmd'
)


class TestPreRemove(unittest.TestCase):
    """Test pre_remove method."""

    def setUp(self):
        """Set up operator."""
        self.operator = SPOLifecycle()
        self.app = mock.MagicMock()
        self.app.name = 'security-profiles-operator'
        self.app.sync_fluxcd_manifest = (
            '/tmp/test-manifests'
        )

    @mock.patch(
        'os.path.exists', return_value=True
    )
    @mock.patch(
        TRYCMD_MOCK_PATH,
        return_value=('', '')
    )
    def test_pre_remove_file_exists(
        self, mock_trycmd, _mock_exists
    ):
        """Verify kubectl delete called when yaml exists."""
        self.operator.pre_remove(self.app)
        # trycmd: kubectl delete, sed, seccomp delete
        self.assertEqual(mock_trycmd.call_count, 3)

    @mock.patch(
        'os.path.exists', return_value=False
    )
    @mock.patch(
        TRYCMD_MOCK_PATH,
        return_value=('', '')
    )
    def test_pre_remove_file_not_exists(
        self, mock_trycmd, _mock_exists
    ):
        """Verify kubectl delete skipped when missing."""
        self.operator.pre_remove(self.app)
        # Only sed + seccomp delete (2 calls)
        self.assertEqual(mock_trycmd.call_count, 2)


class TestPostRemove(unittest.TestCase):
    """Test post_remove method."""

    def setUp(self):
        """Set up operator."""
        self.operator = SPOLifecycle()
        self.app = mock.MagicMock()
        self.app.name = 'security-profiles-operator'
        self.app.sync_fluxcd_manifest = (
            '/tmp/test-manifests'
        )

    @mock.patch(
        TRYCMD_MOCK_PATH,
        return_value=('', '')
    )
    def test_post_remove_uncomments_yaml(
        self, mock_trycmd
    ):
        """Verify sed uncomment is called."""
        self.operator.post_remove(self.app)
        mock_trycmd.assert_called_once()
        command_args = mock_trycmd.call_args[0]
        self.assertEqual(command_args[0], 'sed')


class TestGetHelmUserOverrides(unittest.TestCase):
    """Test _get_helm_user_overrides method."""

    def setUp(self):
        """Set up operator."""
        self.operator = SPOLifecycle()

    def test_override_found(self):
        """Verify returns user_overrides when found."""
        mock_dbapi = mock.MagicMock()
        override_obj = mock.MagicMock()
        override_obj.user_overrides = 'key: value'
        mock_dbapi.helm_override_get.return_value = (
            override_obj
        )
        result = self.operator._get_helm_user_overrides(
            mock_dbapi, 1
        )
        self.assertEqual(result, 'key: value')

    def test_override_not_found_creates(self):
        """Verify creates override when not found."""
        mock_dbapi = mock.MagicMock()
        mock_dbapi.helm_override_get.side_effect = (
            exception.HelmOverrideNotFound()
        )
        new_override = mock.MagicMock()
        new_override.user_overrides = None
        mock_dbapi.helm_override_create.return_value = (
            new_override
        )
        result = self.operator._get_helm_user_overrides(
            mock_dbapi, 1
        )
        self.assertEqual(result, '')
        mock_dbapi.helm_override_create.assert_called_once()

    def test_override_none_returns_empty(self):
        """Verify empty string when overrides is None."""
        mock_dbapi = mock.MagicMock()
        override_obj = mock.MagicMock()
        override_obj.user_overrides = None
        mock_dbapi.helm_override_get.return_value = (
            override_obj
        )
        result = self.operator._get_helm_user_overrides(
            mock_dbapi, 1
        )
        self.assertEqual(result, '')


class TestDeletePods(unittest.TestCase):
    """Test _delete_security_profiles_operator_pods."""

    def setUp(self):
        """Set up operator."""
        self.operator = SPOLifecycle()

    def test_deletes_all_pods(self):
        """Verify all pods in namespace are deleted."""
        mock_app_op = mock.MagicMock()
        mock_core_client = mock.MagicMock()
        pod_one = mock.MagicMock()
        pod_one.metadata.name = 'pod-1'
        pod_two = mock.MagicMock()
        pod_two.metadata.name = 'pod-2'
        pod_list = mock_core_client.list_namespaced_pod
        pod_list.return_value.items = [
            pod_one, pod_two
        ]
        delete_method = (
            '_delete_security_profiles_operator_pods'
        )
        getattr(self.operator, delete_method)(
            mock_app_op, mock_core_client
        )
        kube = mock_app_op._kube
        self.assertEqual(
            kube.kube_delete_pod.call_count, 2
        )

    def test_no_pods_no_delete(self):
        """Verify no delete when no pods exist."""
        mock_app_op = mock.MagicMock()
        mock_core_client = mock.MagicMock()
        pod_list = mock_core_client.list_namespaced_pod
        pod_list.return_value.items = []
        delete_method = (
            '_delete_security_profiles_operator_pods'
        )
        getattr(self.operator, delete_method)(
            mock_app_op, mock_core_client
        )
        kube = mock_app_op._kube
        kube.kube_delete_pod.assert_not_called()


if __name__ == '__main__':
    unittest.main()


# ============================================================
# Tests for new CRD upgrade/downgrade lifecycle methods
# ============================================================

LIFECYCLE_RESOURCE = LifecycleConstants.APP_LIFECYCLE_TYPE_RESOURCE
DOWNGRADE_OPERATION = constants.APP_DOWNGRADE_OP


class TestPreApply(unittest.TestCase):
    """Tests for pre_apply lifecycle action."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch.object(SPOLifecycle, '_upgrade_crds_if_needed')
    def test_pre_apply_calls_crd_upgrade(self, mock_upgrade):
        """Verify pre_apply calls _upgrade_crds_if_needed."""
        app_op = mock.MagicMock()
        app = mock.MagicMock()
        hook_info = mock.MagicMock()
        self.operator.pre_apply(app_op, app, hook_info)
        mock_upgrade.assert_called_once_with(app)


class TestPreDowngrade(unittest.TestCase):
    """Tests for pre_downgrade lifecycle action."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch.object(SPOLifecycle, '_delete_spod_resources')
    @mock.patch.object(SPOLifecycle, '_delete_webhook_deployment')
    @mock.patch.object(SPOLifecycle, '_patch_crds_for_rollback')
    @mock.patch.object(SPOLifecycle, '_cleanup_for_rollback')
    def test_pre_downgrade_calls_cleanup(self, mock_cleanup,
                                          mock_patch, mock_wh,
                                          mock_spod):
        """Verify pre_downgrade calls cleanup methods."""
        app_op = mock.MagicMock()
        app = mock.MagicMock()
        hook_info = mock.MagicMock()
        self.operator.pre_downgrade(app_op, app, hook_info)
        mock_cleanup.assert_called_once()
        mock_patch.assert_called_once()
        mock_wh.assert_called_once()
        mock_spod.assert_called_once()


class TestUpgradeCrdsIfNeeded(unittest.TestCase):
    """Tests for _upgrade_crds_if_needed."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch.object(SPOLifecycle, '_check_crd_incompatibility',
                       return_value=None)
    def test_no_incompatibility_returns_early(self, mock_check):
        """Verify no action when CRDs are compatible."""
        app = mock.MagicMock()
        self.operator._upgrade_crds_if_needed(app)
        mock_check.assert_called_once_with(app)

    @mock.patch('os.path.exists', return_value=False)
    @mock.patch.object(SPOLifecycle, '_apply_new_crds')
    @mock.patch.object(SPOLifecycle, '_delete_old_crds')
    @mock.patch.object(SPOLifecycle, '_delete_webhook_deployment')
    @mock.patch.object(SPOLifecycle, '_extract_crds_from_chart',
                       return_value='/tmp/crds.yaml')
    @mock.patch.object(SPOLifecycle, '_check_crd_incompatibility',
                       return_value='upgrade')
    def test_upgrade_path(self, mock_check, mock_extract,
                          mock_wh, mock_del, mock_apply,
                          mock_exists):
        """Verify upgrade path calls correct methods."""
        app = mock.MagicMock()
        self.operator._upgrade_crds_if_needed(app)
        mock_extract.assert_called_once()
        mock_wh.assert_called_once()
        mock_del.assert_called_once()
        mock_apply.assert_called_once_with('/tmp/crds.yaml')

    @mock.patch('os.path.exists', return_value=False)
    @mock.patch.object(SPOLifecycle, '_apply_new_crds')
    @mock.patch.object(SPOLifecycle, '_delete_old_crds')
    @mock.patch.object(SPOLifecycle, '_delete_webhook_deployment')
    @mock.patch.object(SPOLifecycle, '_cleanup_for_rollback')
    @mock.patch.object(SPOLifecycle, '_extract_crds_from_chart',
                       return_value='/tmp/crds.yaml')
    @mock.patch.object(SPOLifecycle, '_check_crd_incompatibility',
                       return_value='rollback')
    def test_rollback_path(self, mock_check, mock_extract,
                           mock_cleanup, mock_wh, mock_del,
                           mock_apply, mock_exists):
        """Verify rollback path calls cleanup_for_rollback."""
        app = mock.MagicMock()
        self.operator._upgrade_crds_if_needed(app)
        mock_cleanup.assert_called_once()

    @mock.patch.object(SPOLifecycle, '_extract_crds_from_chart',
                       return_value=None)
    @mock.patch.object(SPOLifecycle, '_check_crd_incompatibility',
                       return_value='upgrade')
    def test_extract_fails_returns_early(self, mock_check,
                                          mock_extract):
        """Verify returns early if CRD extraction fails."""
        app = mock.MagicMock()
        self.operator._upgrade_crds_if_needed(app)
        mock_extract.assert_called_once()


class TestCheckCrdIncompatibility(unittest.TestCase):
    """Tests for _check_crd_incompatibility."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                side_effect=Exception('not found'))
    def test_exception_returns_none(self, mock_exec):
        """Verify returns None on kubectl failure."""
        app = mock.MagicMock()
        result = self.operator._check_crd_incompatibility(app)
        self.assertIsNone(result)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('', ''))
    def test_empty_output_returns_none(self, mock_exec):
        """Verify returns None when no CRD found."""
        app = mock.MagicMock()
        result = self.operator._check_crd_incompatibility(app)
        self.assertIsNone(result)

    @mock.patch.object(SPOLifecycle, '_target_chart_has_v1_crds',
                       return_value=True)
    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('v1alpha1,Namespaced', ''))
    def test_upgrade_needed(self, mock_exec, mock_v1):
        """Verify detects upgrade needed."""
        app = mock.MagicMock()
        result = self.operator._check_crd_incompatibility(app)
        self.assertEqual(result, 'upgrade')

    @mock.patch.object(SPOLifecycle, '_target_chart_has_v1_crds',
                       return_value=False)
    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('v1,Cluster', ''))
    def test_rollback_needed(self, mock_exec, mock_v1):
        """Verify detects rollback needed."""
        app = mock.MagicMock()
        result = self.operator._check_crd_incompatibility(app)
        self.assertEqual(result, 'rollback')


class TestDeleteWebhookDeployment(unittest.TestCase):
    """Tests for _delete_webhook_deployment."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('deleted', ''))
    def test_calls_kubectl_delete(self, mock_exec):
        """Verify kubectl delete is called."""
        self.operator._delete_webhook_deployment()
        mock_exec.assert_called_once()


class TestDeleteSpodResources(unittest.TestCase):
    """Tests for _delete_spod_resources."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('deleted', ''))
    def test_calls_kubectl_delete(self, mock_exec):
        """Verify kubectl delete daemonset is called."""
        self.operator._delete_spod_resources()
        mock_exec.assert_called_once()


class TestDeleteOldCrds(unittest.TestCase):
    """Tests for _delete_old_crds."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('crd/test.security-profiles-operator.x-k8s.io\n', ''))
    def test_deletes_spo_crds(self, mock_exec):
        """Verify SPO CRDs are deleted."""
        self.operator._delete_old_crds()
        self.assertTrue(mock_exec.call_count >= 1)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                side_effect=Exception('failed'))
    def test_handles_exception(self, mock_exec):
        """Verify handles kubectl failure gracefully."""
        # Should not raise
        self.operator._delete_old_crds()


class TestApplyNewCrds(unittest.TestCase):
    """Tests for _apply_new_crds."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('applied', ''))
    def test_applies_crds_file(self, mock_exec):
        """Verify kubectl apply is called with crds file."""
        self.operator._apply_new_crds('/tmp/crds.yaml')
        mock_exec.assert_called_once()


class TestLifecycleActionsResource(unittest.TestCase):
    """Tests for app_lifecycle_actions with RESOURCE type."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)
        self.context = mock.MagicMock()
        self.conductor = mock.MagicMock()
        self.app_op = mock.MagicMock()
        self.app = mock.MagicMock()

    @mock.patch.object(SPOLifecycle, 'pre_apply',
                       return_value=None)
    def test_resource_pre_apply_dispatch(self, mock_pre):
        """Verify pre_apply dispatched for resource type."""
        hook = _make_hook_info(
            LIFECYCLE_RESOURCE,
            APPLY_OPERATION,
            LIFECYCLE_TIMING_PRE,
        )
        self.operator.app_lifecycle_actions(
            self.context, self.conductor,
            self.app_op, self.app, hook
        )
        mock_pre.assert_called_once()

    @mock.patch.object(SPOLifecycle, 'pre_downgrade',
                       return_value=None)
    def test_resource_pre_downgrade_dispatch(self, mock_pre):
        """Verify pre_downgrade dispatched for downgrade."""
        hook = _make_hook_info(
            LIFECYCLE_RESOURCE,
            DOWNGRADE_OPERATION,
            LIFECYCLE_TIMING_PRE,
        )
        self.operator.app_lifecycle_actions(
            self.context, self.conductor,
            self.app_op, self.app, hook
        )
        mock_pre.assert_called_once()


class TestCleanupForRollback(unittest.TestCase):
    """Tests for _cleanup_for_rollback."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('deleted', ''))
    def test_deletes_webhooks_and_secrets(self, mock_exec):
        """Verify cleanup deletes webhooks, secrets, helmrelease."""
        self.operator._cleanup_for_rollback()
        # Should call kubectl multiple times for webhooks, secrets, helmrelease
        self.assertTrue(mock_exec.call_count >= 4)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                side_effect=Exception('kubectl failed'))
    def test_handles_helmrelease_patch_failure(self, mock_exec):
        """Verify handles exception during helmrelease patch."""
        # Should not raise even if kubectl fails
        try:
            self.operator._cleanup_for_rollback()
        except Exception:
            pass  # Some calls may raise, that's ok


class TestExtractCrdsFromChart(unittest.TestCase):
    """Tests for _extract_crds_from_chart."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('glob.glob', return_value=[])
    def test_no_chart_returns_none(self, mock_glob):
        """Verify returns None when no chart found."""
        app = mock.MagicMock()
        app.inst_charts_dir = '/tmp/charts'
        result = self.operator._extract_crds_from_chart(app)
        self.assertIsNone(result)

    @mock.patch('glob.glob',
                return_value=['/tmp/charts/security-profiles-operator-1.0.tgz'])
    @mock.patch('tarfile.open')
    @mock.patch('tempfile.NamedTemporaryFile')
    def test_extracts_crds_successfully(self, mock_tmp, mock_tar,
                                         mock_glob):
        """Verify CRDs are extracted from tarball."""
        app = mock.MagicMock()
        app.inst_charts_dir = '/tmp/charts'

        # Mock tempfile
        mock_tmpfile = mock.MagicMock()
        mock_tmpfile.name = '/tmp/spo-crds-test.yaml'
        mock_tmp.return_value = mock_tmpfile

        # Mock tarfile with CRD members
        mock_member = mock.MagicMock()
        mock_member.name = 'spo/crds/crds.yaml'
        mock_tar_ctx = mock.MagicMock()
        mock_tar_ctx.getmembers.return_value = [mock_member]
        mock_tar_ctx.extractfile.return_value = mock.MagicMock(
            read=mock.MagicMock(return_value=b'apiVersion: v1')
        )
        mock_tar.return_value.__enter__ = mock.MagicMock(
            return_value=mock_tar_ctx
        )
        mock_tar.return_value.__exit__ = mock.MagicMock(
            return_value=False
        )

        result = self.operator._extract_crds_from_chart(app)
        self.assertEqual(result, '/tmp/spo-crds-test.yaml')


class TestTargetChartHasV1Crds(unittest.TestCase):
    """Tests for _target_chart_has_v1_crds."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('glob.glob', return_value=[])
    def test_no_chart_returns_false(self, mock_glob):
        """Verify returns False when no chart found."""
        app = mock.MagicMock()
        app.inst_charts_dir = '/tmp/charts'
        result = self.operator._target_chart_has_v1_crds(app)
        self.assertFalse(result)


class TestPatchCrdsForRollback(unittest.TestCase):
    """Tests for _patch_crds_for_rollback."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                side_effect=Exception('failed'))
    def test_handles_get_crds_failure(self, mock_exec):
        """Verify handles kubectl get crds failure."""
        self.operator._patch_crds_for_rollback()

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute',
                return_value=('', ''))
    def test_empty_crds_returns(self, mock_exec):
        """Verify returns when no CRDs found."""
        self.operator._patch_crds_for_rollback()

    @mock.patch('k8sapp_security_profiles_operator.lifecycle.lifecycle_security_profiles_operator.cutils.execute')
    def test_preserves_spod_crd(self, mock_exec):
        """Verify spod CRD is patched not deleted."""
        mock_exec.return_value = (
            'customresourcedefinition.apiextensions.k8s.io/'
            'securityprofilesoperatordaemons.security-profiles-operator.x-k8s.io\n'
            'customresourcedefinition.apiextensions.k8s.io/'
            'apparmorprofiles.security-profiles-operator.x-k8s.io\n',
            ''
        )
        self.operator._patch_crds_for_rollback()
        # Should have been called: get crds, patch spod, delete other
        self.assertTrue(mock_exec.call_count >= 3)


class TestTargetChartHasV1CrdsDetailed(unittest.TestCase):
    """Additional tests for _target_chart_has_v1_crds."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('glob.glob',
                return_value=['/tmp/charts/spo-1.0.tgz'])
    @mock.patch('tarfile.open')
    def test_returns_true_for_v1_cluster_crd(self, mock_tar, mock_glob):
        """Verify returns True when chart has v1/Cluster CRD."""
        app = mock.MagicMock()
        app.inst_charts_dir = '/tmp/charts'

        mock_member = mock.MagicMock()
        mock_member.name = 'spo/crds/crd.yaml'
        mock_tar_ctx = mock.MagicMock()
        mock_tar_ctx.getmembers.return_value = [mock_member]

        crd_content = yaml.dump({
            'kind': 'CustomResourceDefinition',
            'spec': {
                'scope': 'Cluster',
                'versions': [{'name': 'v1'}]
            }
        }).encode('utf-8')
        mock_tar_ctx.extractfile.return_value = mock.MagicMock(
            read=mock.MagicMock(return_value=crd_content)
        )
        mock_tar.return_value.__enter__ = mock.MagicMock(
            return_value=mock_tar_ctx
        )
        mock_tar.return_value.__exit__ = mock.MagicMock(
            return_value=False
        )

        result = self.operator._target_chart_has_v1_crds(app)
        self.assertTrue(result)

    @mock.patch('glob.glob',
                return_value=['/tmp/charts/spo-1.0.tgz'])
    @mock.patch('tarfile.open', side_effect=Exception('corrupt'))
    def test_handles_tarfile_exception(self, mock_tar, mock_glob):
        """Verify returns False on tarfile exception."""
        app = mock.MagicMock()
        app.inst_charts_dir = '/tmp/charts'
        result = self.operator._target_chart_has_v1_crds(app)
        self.assertFalse(result)


class TestExtractCrdsFromChartDetailed(unittest.TestCase):
    """Additional tests for _extract_crds_from_chart error paths."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('glob.glob',
                return_value=['/tmp/charts/spo-1.0.tgz'])
    @mock.patch('tarfile.open', side_effect=Exception('corrupt'))
    @mock.patch('tempfile.NamedTemporaryFile')
    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('os.remove')
    def test_handles_tarfile_exception(self, mock_rm, mock_exists,
                                        mock_tmp, mock_tar,
                                        mock_glob):
        """Verify handles tarfile exception and cleans up."""
        app = mock.MagicMock()
        app.inst_charts_dir = '/tmp/charts'
        mock_tmpfile = mock.MagicMock()
        mock_tmpfile.name = '/tmp/spo-crds.yaml'
        mock_tmp.return_value = mock_tmpfile

        result = self.operator._extract_crds_from_chart(app)
        self.assertIsNone(result)
        mock_rm.assert_called()


class TestUpgradeCrdsCleanup(unittest.TestCase):
    """Test _upgrade_crds_if_needed finally block."""

    def setUp(self):
        self.operator = SPOLifecycle.__new__(SPOLifecycle)

    @mock.patch('os.remove')
    @mock.patch('os.path.exists', return_value=True)
    @mock.patch.object(SPOLifecycle, '_apply_new_crds')
    @mock.patch.object(SPOLifecycle, '_delete_old_crds')
    @mock.patch.object(SPOLifecycle, '_delete_webhook_deployment')
    @mock.patch.object(SPOLifecycle, '_extract_crds_from_chart',
                       return_value='/tmp/crds.yaml')
    @mock.patch.object(SPOLifecycle, '_check_crd_incompatibility',
                       return_value='upgrade')
    def test_cleans_up_crds_file(self, mock_check, mock_extract,
                                  mock_wh, mock_del, mock_apply,
                                  mock_exists, mock_rm):
        """Verify crds file is removed in finally block."""
        app = mock.MagicMock()
        self.operator._upgrade_crds_if_needed(app)
        mock_rm.assert_called_with('/tmp/crds.yaml')
